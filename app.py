from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, make_response
from supabase import create_client, Client, ClientOptions
import os
import datetime
import io
import csv
from dotenv import load_dotenv
from flask_mail import Mail, Message
from utils import generate_pdf_report, send_email_report

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME", "parthhkdigiverse@gmail.com")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD", "uqzm jykr xehs cmne") 
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_USERNAME", "parthhkdigiverse@gmail.com")
mail = Mail(app)

# Supabase Setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Warning: SUPABASE_URL and SUPABASE_KEY must be set in .env")
    supabase = None
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_db(token=None):
    if token:
        return create_client(SUPABASE_URL, SUPABASE_KEY, options=ClientOptions(headers={"Authorization": f"Bearer {token}"}))
    return supabase

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        try:
            redirect_url = url_for('verify', _external=True)
            print(f"DEBUG: Redirect URL generated: {redirect_url}")
            res = supabase.auth.sign_in_with_otp({
                "email": email,
                "options": {
                    "email_redirect_to": redirect_url
                }
            })
            flash('OTP sent to your email!', 'info')
            return redirect(url_for('verify', email=email))
        except Exception as e:
            print(f"DEBUG: Error sending OTP: {str(e)}")
            flash(f"Error: {str(e)}", 'error')
    return render_template('login.html')

@app.route('/auth/magic_login', methods=['POST'])
def magic_login():
    data = request.get_json()
    access_token = data.get('access_token')
    
    if not access_token:
        return jsonify({'error': 'No access token provided'}), 400
        
    try:
        # Get user details from the token
        res = supabase.auth.get_user(access_token)
        user = res.user
        
        if user:
            session['user'] = user.id
            session['access_token'] = access_token
            return jsonify({'success': True, 'redirect_url': url_for('dashboard')})
        else:
            return jsonify({'error': 'Invalid token'}), 401
    except Exception as e:
        print(f"DEBUG: Magic login error: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    email = request.args.get('email')
    if request.method == 'POST':
        email = request.form.get('email')
        otp = request.form.get('otp')
        try:
            res = supabase.auth.verify_otp({"email": email, "token": otp, "type": "email"})
            session['user'] = res.user.id
            session['access_token'] = res.session.access_token
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f"Login failed: {str(e)}", 'error')
    return render_template('verify.html', email=email)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Fetch user profile
    token = session.get('access_token')
    try:
        # Check recurring expenses
        if not session.get('recurring_checked'):
             added = check_recurring_expenses(session['user'], token)
             if added > 0:
                 flash(f"{added} recurring expenses added.", 'info')
             session['recurring_checked'] = True

        # supabase.postgrest.auth(token)
        profile_res = get_db(token).table('profiles').select('*').eq('id', session['user']).execute() # RLS might allow read if public, but for update we need auth. Wait, profile read usually needs auth.
        # Let's try .auth(token)
        profile_res = get_db(token).table('profiles').select('*').eq('id', session['user']).execute()
        profile = profile_res.data[0] if profile_res.data else {}
        
        # Recent Expenses (Top 5)
        expenses_res = get_db(token).table('expenses').select('*').eq('user_id', session['user']).order('date', desc=True).limit(5).execute()
        expenses = expenses_res.data
        
        # Calculate Logic - Expenses Only for "Total Spent"
        all_tx_res = get_db(token).table('expenses').select('amount, type').eq('user_id', session['user']).execute()
        total_expense = sum(ex['amount'] for ex in all_tx_res.data if ex['type'] == 'expense')
        total_income = sum(ex['amount'] for ex in all_tx_res.data if ex['type'] == 'income')
        
        budget = float(profile.get('budget', 0) or 0)
        
        percentage = 0
        progress_class = "progress-safe"
        if budget > 0:
            percentage = min((total_expense / budget) * 100, 100)
            if percentage > 90:
                progress_class = "progress-danger"
            elif percentage > 75:
                progress_class = "progress-warning"
                
    except Exception as e:
        flash(f"Error fetching data: {str(e)}", 'error')
        profile = {}
        expenses = []
        total_expense = 0
        total_income = 0
        budget = 0
        percentage = 0
        progress_class = ""

    return render_template('dashboard.html', 
                           profile=profile,
                           expenses=expenses, total=total_expense, total_income=total_income,
                           budget=budget, percentage=percentage, 
                           progress_class=progress_class)

@app.route('/expenses')
def expenses():
    if 'user' not in session: return redirect(url_for('login'))
    
    try:
        token = session.get('access_token')

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        category = request.args.get('category')
        bank_id = request.args.get('bank_id') # New Filter
        
        # Query with Join to get Bank Name
        # Syntax for join: select('*, bank_accounts(bank_name)')
        exp_query = get_db(token).table('expenses').select('*, bank_accounts(bank_name)').eq('user_id', session['user']).order('date', desc=True)
        
        if start_date: exp_query = exp_query.gte('date', start_date)
        if end_date: exp_query = exp_query.lte('date', end_date)
        if category and category != 'All': exp_query = exp_query.eq('category', category)
        if bank_id:
             if bank_id == 'Cash':
                 exp_query = exp_query.is_('bank_account_id', 'null')
             elif bank_id != 'All':
                 exp_query = exp_query.eq('bank_account_id', bank_id)
        
        expenses_res = exp_query.execute()
        expenses = expenses_res.data
        
        # Fetch Banks for Filter Dropdown
        banks_res = get_db(token).table('bank_accounts').select('id, bank_name').eq('user_id', session['user']).execute()
        banks = banks_res.data
        
    except Exception as e:
        flash(f"Error fetching expenses: {str(e)}", 'error')
        expenses = []
        banks = []
        
    return render_template('expenses.html', expenses=expenses, banks=banks)

@app.route('/banks')
def banks():
    if 'user' not in session: return redirect(url_for('login'))
    
    try:
        token = session.get('access_token')

        res = get_db(token).table('bank_accounts').select('*').eq('user_id', session['user']).execute()
        banks = res.data
    except Exception as e:
        flash(f"Error fetching banks: {str(e)}", 'error')
        banks = []
        
    return render_template('banks.html', banks=banks)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Use authenticated client for RLS
    token = session.get('access_token')
    
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        website = request.form.get('website')
        avatar_url = request.form.get('avatar_url')
        
        try:
            # Pass the user's JWT to authorize the request against RLS policies
    
            get_db(token).table('profiles').update({
                'full_name': full_name,
                'website': website,
                'avatar_url': avatar_url
            }).eq('id', session['user']).execute()
            
            flash('Profile updated!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f"Error updating profile: {str(e)}", 'error')

    # Fetch existing profile
    try:

        res = get_db(token).table('profiles').select('*').eq('id', session['user']).execute()
        profile = res.data[0] if res.data else {}
    except:
        profile = {}
    return render_template('profile.html', profile=profile)

@app.route('/add_bank', methods=['POST'])
def add_bank():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    bank_name = request.form.get('bank_name')
    account_number = request.form.get('account_number')
    ifsc_code = request.form.get('ifsc_code')

    try:
        token = session.get('access_token')

        
        data = {
            'user_id': session['user'],
            'bank_name': bank_name,
            'account_number': account_number,
            'ifsc_code': ifsc_code
        }
        get_db(token).table('bank_accounts').insert(data).execute()
        flash('Bank account added!', 'success')
    except Exception as e:
        flash(f"Error adding bank: {str(e)}", 'error')
    
    return redirect(url_for('banks'))

@app.route('/delete_bank/<bank_id>')
def delete_bank(bank_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    try:
        token = session.get('access_token')

        get_db(token).table('bank_accounts').delete().eq('id', bank_id).eq('user_id', session['user']).execute()
        flash('Bank account removed.', 'info')
    except Exception as e:
        flash(f"Error deleting bank: {str(e)}", 'error')
    
    return redirect(url_for('banks'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------------------------------------------------------
# Feature: Expenses & Budget
# ---------------------------------------------------------

@app.template_filter('format_date')
def format_date(value, format="%d-%m-%Y"):
    if value is None:
        return ""
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d").strftime(format)
    except ValueError:
        return value

def check_recurring_expenses(user_id, token):
    """
    Checks for due recurring expenses and adds them.
    Adapted for Supabase.
    """
    try:

        today = datetime.date.today().isoformat()
        
        # Fetch due items
        res = get_db(token).table('recurring_expenses').select('*').eq('user_id', user_id).lte('next_due_date', today).execute()
        due_items = res.data
        
        count = 0
        for item in due_items:
            # Add to main expenses
            desc = item['description'] + " (Auto-Recurring)" if item['description'] else "(Auto-Recurring)"
            expense_data = {
                'user_id': user_id,
                'date': item['next_due_date'],
                'category': item['category'],
                'amount': item['amount'],
                'description': desc
            }
            get_db(token).table('expenses').insert(expense_data).execute()
            count += 1
            
            # Update next due date (+30 days)
            d_obj = datetime.datetime.strptime(item['next_due_date'], "%Y-%m-%d")
            new_due = (d_obj + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
            
            get_db(token).table('recurring_expenses').update({'next_due_date': new_due}).eq('id', item['id']).execute()
            
        return count
    except Exception as e:
        print(f"Error checking recurring expenses: {e}")
        return 0

@app.route('/set_budget', methods=['POST'])
def set_budget():
    if 'user' not in session: return redirect(url_for('login'))
    
    amount = request.form.get('budget')
    try:
        token = session.get('access_token')

        get_db(token).table('profiles').update({'budget': float(amount)}).eq('id', session['user']).execute()
        flash('Budget updated successfully!', 'success')
    except Exception as e:
        flash(f"Error updating budget: {str(e)}", 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/add_expense', methods=['GET', 'POST'])
def add_expense():
    if 'user' not in session: return redirect(url_for('login'))
    
    token = session.get('access_token')

    if request.method == 'POST':
        date = request.form['date']
        category = request.form['category']
        amount = request.form['amount']
        description = request.form['description']
        is_recurring = request.form.get('is_recurring')
        
        # New Fields
        tx_type = request.form.get('type', 'expense')
        bank_account_id = request.form.get('bank_account_id') or None
        
        try:
            # Add Expense/Income
            data = {
                'user_id': session['user'],
                'date': date,
                'category': category,
                'amount': float(amount),
                'description': description,
                'type': tx_type,
                'bank_account_id': bank_account_id
            }
            get_db(token).table('expenses').insert(data).execute()
            
            msg = f"{tx_type.title()} added successfully!"
            
            if is_recurring:
                # Add Recurring
                d_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
                next_due = (d_obj + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
                
                rec_data = {
                    'user_id': session['user'],
                    'category': category,
                    'amount': float(amount),
                    'description': description,
                    'next_due_date': next_due
                }
                get_db(token).table('recurring_expenses').insert(rec_data).execute()
                msg += " (Set to recur monthly)"
            
            flash(msg, 'success')
            return redirect(url_for('expenses'))
        except Exception as e:
            flash(f"Error adding {tx_type}: {str(e)}", 'error')
            
    # GET - Fetch Banks
    try:
        banks_res = get_db(token).table('bank_accounts').select('id, bank_name').eq('user_id', session['user']).execute()
        banks = banks_res.data
    except:
        banks = []

    return render_template('add.html', today=datetime.date.today(), expense=None, banks=banks)

@app.route('/edit_expense/<expense_id>', methods=['GET', 'POST'])
def edit_expense(expense_id):
    if 'user' not in session: return redirect(url_for('login'))
    
    token = session.get('access_token')
    
    if request.method == 'POST':
        date = request.form['date']
        category = request.form['category']
        amount = request.form['amount']
        description = request.form['description']
        tx_type = request.form.get('type', 'expense')
        bank_account_id = request.form.get('bank_account_id') or None
        
        try:
    
            get_db(token).table('expenses').update({
                'date': date,
                'category': category,
                'amount': float(amount),
                'description': description,
                'type': tx_type,
                'bank_account_id': bank_account_id
            }).eq('id', expense_id).execute()
            flash('Transaction updated!', 'success')
            return redirect(url_for('expenses'))
        except Exception as e:
            flash(f"Error updating transaction: {str(e)}", 'error')
            
    # GET - Fetch expense
    try:
        res = get_db(token).table('expenses').select('*').eq('id', expense_id).execute()
        expense = res.data[0] if res.data else None
        
        # Fetch Banks
        banks_res = get_db(token).table('bank_accounts').select('id, bank_name').eq('user_id', session['user']).execute()
        banks = banks_res.data
    except:
        expense = None
        banks = []
        
    if not expense:
        flash('Transaction not found', 'error')
        return redirect(url_for('dashboard'))
        
    return render_template('add.html', expense=expense, banks=banks, today=datetime.date.today())

@app.route('/delete_expense/<expense_id>')
def delete_expense(expense_id):
    if 'user' not in session: return redirect(url_for('login'))
    
    try:
        token = session.get('access_token')

        get_db(token).table('expenses').delete().eq('id', expense_id).execute()
        flash('Expense deleted.', 'info')
    except Exception as e:
        flash(f"Error deleting expense: {str(e)}", 'error')
        
    return redirect(url_for('expenses'))

@app.route('/reports')
def reports():
    if 'user' not in session: return redirect(url_for('login'))
    
    try:
        token = session.get('access_token')

        
        # Get all transactions
        res = get_db(token).table('expenses').select('*').eq('user_id', session['user']).execute()
        transactions = res.data
        
        # Aggregate for Pie Chart (Expense Categories)
        exp_cat_data = {}
        inc_cat_data = {}
        
        # Monthly Data: { 'YYYY-MM': {'income': 0, 'expense': 0} }
        monthly_data = {}
        
        for tx in transactions:
            cat = tx['category']
            amt = tx['amount']
            month = tx['date'][:7] # YYYY-MM
            
            if month not in monthly_data:
                monthly_data[month] = {'income': 0, 'expense': 0}
            
            if tx['type'] == 'income':
                inc_cat_data[cat] = inc_cat_data.get(cat, 0) + amt
                monthly_data[month]['income'] += amt
            else:
                exp_cat_data[cat] = exp_cat_data.get(cat, 0) + amt
                monthly_data[month]['expense'] += amt
            
        # Expense Pie Data
        exp_pie_labels = list(exp_cat_data.keys())
        exp_pie_values = list(exp_cat_data.values())
        
        # Income Pie Data
        inc_pie_labels = list(inc_cat_data.keys())
        inc_pie_values = list(inc_cat_data.values())
        
        # Bar Chart Data
        bar_labels = sorted(monthly_data.keys())
        bar_exp = [monthly_data[m]['expense'] for m in bar_labels]
        bar_inc = [monthly_data[m]['income'] for m in bar_labels]
        
    except Exception as e:
        flash(f"Error generating reports: {str(e)}", 'error')
        exp_pie_labels = []
        exp_pie_values = []
        inc_pie_labels = []
        inc_pie_values = []
        bar_labels = []
        bar_exp = []
        bar_inc = []
        
    return render_template('reports.html', 
                            exp_pie_labels=exp_pie_labels, exp_pie_values=exp_pie_values,
                            inc_pie_labels=inc_pie_labels, inc_pie_values=inc_pie_values,
                            bar_labels=bar_labels, bar_exp=bar_exp, bar_inc=bar_inc)

@app.route('/export')
def export_csv():
    if 'user' not in session: return redirect(url_for('login'))
    
    try:
        token = session.get('access_token')

        res = get_db(token).table('expenses').select('*').eq('user_id', session['user']).execute()
        expenses = res.data
        
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['Date', 'Category', 'Amount', 'Description'])
        
        for ex in expenses:
            cw.writerow([ex['date'], ex['category'], ex['amount'], ex['description']])
            
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=expenses.csv"
        output.headers["Content-type"] = "text/csv"
        return output
    except Exception as e:
        flash(f"Error exporting CSV: {str(e)}", 'error')
        return redirect(url_for('dashboard'))

@app.route('/export_pdf')
def export_pdf_route():
    if 'user' not in session: return redirect(url_for('login'))
    
    try:
        token = session.get('access_token')

        
        # Get data
        expenses_res = get_db(token).table('expenses').select('*').eq('user_id', session['user']).execute()
        expenses = expenses_res.data
        
        # Get user profile name
        prof_res = get_db(token).table('profiles').select('full_name').eq('id', session['user']).execute()
        username = prof_res.data[0]['full_name'] if prof_res.data else "User"
        
        pdf_path = generate_pdf_report(expenses, username)
        return send_file(pdf_path, as_attachment=True)
    except Exception as e:
        flash(f"Error generating PDF: {str(e)}", 'error')
        return redirect(url_for('dashboard'))

@app.route('/email_report', methods=['POST'])
def email_report_route():
    if 'user' not in session: return redirect(url_for('login'))
    
    email = request.form.get('email') # or use logged in email? user session id is uuid, not email.
    # Supabase auth email is not stored in session currently, typically access_token has email claim.
    # We can ask user to input email, or fetch from auth if possible (supabase.auth.get_user(token)).
    
    # If email input not provided, try to get from user profile or auth
    if not email:
        # Try fetch from auth
        try:
             token = session.get('access_token')
             u = supabase.auth.get_user(token)
             email = u.user.email
        except:
             flash('Could not determine email address.', 'error')
             return redirect(url_for('dashboard'))

    try:
        token = session.get('access_token')

        
        expenses_res = get_db(token).table('expenses').select('*').eq('user_id', session['user']).execute()
        expenses = expenses_res.data
        
        prof_res = get_db(token).table('profiles').select('full_name').eq('id', session['user']).execute()
        username = prof_res.data[0]['full_name'] if prof_res.data else "User"
        
        pdf_path = generate_pdf_report(expenses, username)
        
        subject = f"Monthly Transaction Report for {username}"
        body = f"Hello {username},\n\nPlease find attached your monthly transaction report, including both income and expenses.\n\nRegards,\nPocket Expense Tracker"
        
        success, msg = send_email_report(mail, app, email, subject, body, pdf_path)
        if success:
             flash(msg, 'success')
        else:
             flash(f"Failed to send email: {msg}", 'error')
             
    except Exception as e:
         flash(f"Error emailing report: {str(e)}", 'error')
         
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
