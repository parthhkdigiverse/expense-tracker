from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from supabase import create_client, Client, ClientOptions
import os
import datetime
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

def check_db_config():
    if not supabase:
        flash("Critical Error: Database configuration missing. Please check server logs.", "error")
        return False
    return True

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
        if not check_db_config():
            return render_template('login.html')

        username = request.form.get('username')
        password = request.form.get('password')
        
        # TESTER BYPASS (Optional: keep or remove, keeping for safety if user relies on it)
        if username == 'tester': # Assuming tester logic might want username 'tester'
             # ... adapting tester logic if needed, but for now focusing on main auth
             pass

        try:
            # 1. Lookup email from username
            print(f"DEBUG: Attempting login for username: {username}")
            
            # Using ilike for case-insensitive match if possible, or usually just check what we have
            user_res = supabase.table('profiles').select('email, id').eq('username', username).execute()
            
            print(f"DEBUG: Profile lookup result: {user_res.data}")
            
            if not user_res.data:
                print("DEBUG: Username not found in profiles.")
                flash('Invalid username or password', 'error')
                return render_template('login.html')
            
            email = user_res.data[0]['email']
            print(f"DEBUG: Found email: {email}")
            
            if not email:
                 print("DEBUG: Email is None in profile!")
                 flash('Account configuration error. Please login with code to fix.', 'error')
                 return render_template('login.html')

            # 2. Sign in with Email + Password
            res = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            print(f"DEBUG: Auth success. User ID: {res.user.id}")
            
            session['user'] = res.user.id
            session['access_token'] = res.session.access_token
            session['refresh_token'] = res.session.refresh_token
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            print(f"DEBUG: Login failed: {str(e)}")
            flash(f"Login failed: Invalid parameters", 'error') # specific error hidden for security
            return render_template('login.html')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not check_db_config():
            return render_template('register.html')

        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        full_name = request.form.get('full_name')

        try:
            # 1. Check if username exists
            existing_user = supabase.table('profiles').select('id').eq('username', username).execute()
            if existing_user.data:
                flash('Username already taken', 'error')
                return render_template('register.html')

            # 2. Sign Up
            res = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "username": username,
                        "full_name": full_name,
                         # Avatar URL will be null initially or default
                    }
                }
            })
            
            if res.user:
                 flash('Registration successful! Please check your email to confirm if required, or login now.', 'success')
                 return redirect(url_for('login'))
            
        except Exception as e:
            flash(f"Registration failed: {str(e)}", 'error')
            
    return render_template('register.html')

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
            # Magic login often doesn't give refresh token easily unless we exchange it properly
            # For now, this route might be legacy/less used, but let's leave it.
            # Ideally we'd need refresh token here too if we want them to change passwords.
            session['refresh_token'] = data.get('refresh_token') # Assume frontend passes it if available
            return jsonify({'success': True, 'redirect_url': url_for('dashboard')})
        else:
            return jsonify({'error': 'Invalid token'}), 401
    except Exception as e:
        print(f"DEBUG: Magic login error: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/login_with_code', methods=['POST'])
def login_with_code():
    if not check_db_config():
        return render_template('login.html')

    email = request.form.get('email')
    try:
        redirect_url = url_for('verify', _external=True)
        res = supabase.auth.sign_in_with_otp({
            "email": email,
            "options": {
                "email_redirect_to": redirect_url
            }
        })
        flash('Magic link sent! Check your email.', 'info')
        return redirect(url_for('verify', email=email))
    except Exception as e:
        flash(f"Error: {str(e)}", 'error')
        return redirect(url_for('login'))

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
            session['refresh_token'] = res.session.refresh_token
            
            # Check if user has a username
            profile = get_user_profile(res.session.access_token)
            
            # Ensure email is in profiles (for legacy users)
            if not profile.get('email'):
                try:
                    get_db(res.session.access_token).table('profiles').update({'email': email}).eq('id', session['user']).execute()
                    profile['email'] = email # Update local dict
                except Exception as e:
                    print(f"Error updating email in profile: {e}")

            if not profile.get('username'):
                session['setup_required'] = True
                flash('Login successful! Please complete your profile setup.', 'info')
                return redirect(url_for('complete_profile'))
                
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f"Login failed: {str(e)}", 'error')
    return render_template('verify.html', email=email)

@app.route('/complete_profile', methods=['GET', 'POST'])
def complete_profile():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        token = session.get('access_token')
        
        try:
            # 1. Check if username exists
            existing_user = supabase.table('profiles').select('id').eq('username', username).execute()
            if existing_user.data:
                flash('Username already taken', 'error')
                return render_template('complete_profile.html')
            
            # 2. Update Profile
            get_db(token).table('profiles').update({'username': username}).eq('id', session['user']).execute()
            
            # 3. Update Password (via Auth Admin or User Update)
            # User update requires authenticated client
            # 3. Update Password
            # We need to ensure we have a valid session for the auth client
            refresh_token = session.get('refresh_token')
            if refresh_token:
                # Create a fresh client and set session
                # We can't rely on get_db(token) for Auth methods usually
                auth_client = create_client(SUPABASE_URL, SUPABASE_KEY)
                auth_client.auth.set_session(token, refresh_token)
                auth_client.auth.update_user({"password": password})
            else:
                 # Fallback (risky if get_db doesn't work) or error
                 # Try get_db just in case it worked before or for some versions
                 get_db(token).auth.update_user({"password": password})
            
            session.pop('setup_required', None)
            flash('Profile setup complete! You can now login with your username.', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
             flash(f"Error updating profile: {str(e)}", 'error')
             
    return render_template('complete_profile.html')

@app.before_request
def check_setup_required():
    if session.get('setup_required'):
        if request.endpoint not in ['complete_profile', 'logout', 'static']:
             return redirect(url_for('complete_profile'))

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
        # Recent Expenses (Top 5)
        # Sort by Transaction Date first, then Entry Time
        expenses_res = get_db(token).table('expenses').select('*').eq('user_id', session['user']).order('date', desc=True).order('created_at', desc=True).limit(5).execute()
        expenses = expenses_res.data
        
        # Calculate Logic - Expenses Only for "Total Spent"
        all_tx_res = get_db(token).table('expenses').select('amount, type').eq('user_id', session['user']).execute()
        total_expense = sum(ex['amount'] for ex in all_tx_res.data if ex['type'] == 'expense')
        total_income = sum(ex['amount'] for ex in all_tx_res.data if ex['type'] == 'income')
        
        # Calculate Total Balance (Opening + Income - Expense)
        banks_res_bal = get_db(token).table('bank_accounts').select('opening_balance').eq('user_id', session['user']).execute()
        total_opening = sum(float(b.get('opening_balance', 0)) for b in banks_res_bal.data)
        current_balance = total_opening + total_income - total_expense

        # Fetch Debt Summary
        debts_res = get_db(token).table('debts').select('amount, type').eq('user_id', session['user']).eq('status', 'active').execute()
        total_lent = sum(d['amount'] for d in debts_res.data if d['type'] == 'lend')
        total_borrowed = sum(d['amount'] for d in debts_res.data if d['type'] == 'borrow')

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
        current_balance = 0
        budget = 0
        percentage = 0
        progress_class = ""

    return render_template('dashboard.html', 
                           profile=profile,
                           expenses=expenses, total=total_expense, total_income=total_income,
                           current_balance=current_balance,
                           budget=budget, percentage=percentage, 
                           progress_class=progress_class,

                           currency=profile.get('currency', '₹'),
                           total_lent=total_lent,
                           total_borrowed=total_borrowed)

def get_filtered_expenses(token, user_id, args):
    """
    Helper function to fetch filtered expenses.
    """
    start_date = args.get('start_date')
    end_date = args.get('end_date')
    category = args.get('category')
    bank_id = args.get('bank_id')

    # Query with Join to get Bank Name
    exp_query = get_db(token).table('expenses').select('*, bank_accounts(bank_name)').eq('user_id', user_id).order('date', desc=True).order('created_at', desc=True)

    if start_date: exp_query = exp_query.gte('date', start_date)
    if end_date: exp_query = exp_query.lte('date', end_date)
    if category and category != 'All': exp_query = exp_query.eq('category', category)
    if bank_id:
            if bank_id == 'Cash':
                exp_query = exp_query.is_('bank_account_id', 'null')
            elif bank_id != 'All':
                exp_query = exp_query.eq('bank_account_id', bank_id)
    
    expenses_res = exp_query.execute()
    return expenses_res.data

@app.route('/expenses')
def expenses():
    if 'user' not in session: return redirect(url_for('login'))
    
    categories = DEFAULT_CATEGORIES
    try:
        token = session.get('access_token')
        
        expenses = get_filtered_expenses(token, session['user'], request.args)
        
        # Fetch Banks for Filter Dropdown
        banks_res = get_db(token).table('bank_accounts').select('id, bank_name').eq('user_id', session['user']).execute()
        banks = banks_res.data
        
        profile_res = get_db(token).table('profiles').select('currency').eq('id', session['user']).execute()
        currency = profile_res.data[0]['currency'] if profile_res.data else '₹'
        
        categories = get_all_categories(token, session['user'])
        
    except Exception as e:
        flash(f"Error fetching expenses: {str(e)}", 'error')
        expenses = []
        banks = []
        currency = '₹'
        categories = DEFAULT_CATEGORIES
        
    return render_template('expenses.html', expenses=expenses, banks=banks, currency=currency, categories=categories)

@app.route('/banks')
def banks():
    if 'user' not in session: return redirect(url_for('login'))
    
    try:
        token = session.get('access_token')

        res = get_db(token).table('bank_accounts').select('*').eq('user_id', session['user']).execute()
        banks = res.data
        
        # Fetch transactions linked to banks
        # We fetch all expenses/incomes representing bank transactions
        tx_res = get_db(token).table('expenses').select('amount, type, bank_account_id').eq('user_id', session['user']).not_.is_('bank_account_id', 'null').execute()
        transactions = tx_res.data
        
        # Calculate current balance for each bank
        # Start with opening balance
        for bank in banks:
            # Initialize with opening balance
            current_bal = float(bank.get('opening_balance', 0))
            
            # Filter transactions for this bank (in-memory filtering for simplicity with small data)
            bank_txs = [t for t in transactions if t.get('bank_account_id') == bank['id']]
            
            for tx in bank_txs:
                amount = float(tx['amount'])
                if tx['type'] == 'income':
                    current_bal += amount
                elif tx['type'] == 'expense':
                    current_bal -= amount
            
            bank['current_balance'] = current_bal
            
    except Exception as e:
        flash(f"Error fetching banks: {str(e)}", 'error')
        banks = []
        import traceback
        traceback.print_exc()
        
    return render_template('banks.html', banks=banks)

# Helper to get profile with defaults
def get_user_profile(token):
    try:
        res = get_db(token).table('profiles').select('*').eq('id', session['user']).execute()
        return res.data[0] if res.data else {}
    except:
        return {}

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Use authenticated client for RLS
    token = session.get('access_token')
    
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        new_username = request.form.get('username')
        avatar_url = request.form.get('avatar_url')
        budget_val = request.form.get('budget', 0)
        currency_val = request.form.get('currency', '₹')
        
        # Check Username uniqueness if changed
        current_profile = get_user_profile(token)
        current_username = current_profile.get('username')
        
        if new_username and new_username != current_username:
             existing_user = get_db(token).table('profiles').select('id').eq('username', new_username).execute()
             if existing_user.data:
                 flash('Username already taken', 'error')
                 return redirect(url_for('profile'))

        if 'avatar_file' in request.files:
            file = request.files['avatar_file']
            if file and file.filename != '':
                try:
                    # Read file content
                    file_content = file.read()
                    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                    file_path = f"{session['user']}/avatar_{int(datetime.datetime.now().timestamp())}.{file_ext}"
                    
                    # Upload to Supabase Storage
                    # Using get_db(token) doesn't give storage access easily with python client typically, 
                    # usually supabase.storage.from_() represents the service key or anon key client.
                    # For RLS on storage, we need authenticated client.
                    
                    # Correct way with supabase-py:
                    # res = get_db(token).storage.from_('avatars').upload(file_path, file_content) 
                    
                    # Store relative to bucket
                    res = get_db(token).storage.from_('avatars').upload(
                        file_path,
                        file_content,
                        {"content-type": f"image/{file_ext}"}
                    )
                    
                    # Get Public URL
                    # The public URL follows pattern: SUPABASE_URL/storage/v1/object/public/avatars/path
                    # Or client.storage.from_('avatars').get_public_url(file_path)
                    
                    public_url = get_db(token).storage.from_('avatars').get_public_url(file_path)
                    avatar_url = public_url # Update variable to save to DB logic below
                    
                except Exception as e:
                    print(f"Upload Error: {e}")
                    flash(f"Error uploading image: {str(e)}", 'error')

        try:
            get_db(token).table('profiles').update({
                'full_name': full_name,
                'username': new_username,
                'avatar_url': avatar_url,
                'budget': float(budget_val),
                'currency': currency_val
            }).eq('id', session['user']).execute()
            
            flash('Profile updated!', 'success')
            return redirect(url_for('profile')) # Stay on profile page
        except Exception as e:
            flash(f"Error updating profile: {str(e)}", 'error')

    # Fetch existing profile and email
    try:
        profile = get_user_profile(token)
        
        # Get Email from Supabase Auth
        u = supabase.auth.get_user(token)
        email = u.user.email if u and u.user else "Unknown"
    except Exception as e:
        profile = {}
        email = "Unknown"
        print(f"Error fetching profile/user: {e}")
    return render_template('profile.html', profile=profile, email=email)

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user' not in session: return redirect(url_for('login'))
    
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if new_password != confirm_password:
        flash("Passwords do not match", "error")
        return redirect(url_for('profile'))
        
    try:
        token = session.get('access_token')
        refresh_token = session.get('refresh_token')
        
        if refresh_token:
             auth_client = create_client(SUPABASE_URL, SUPABASE_KEY)
             auth_client.auth.set_session(token, refresh_token)
             auth_client.auth.update_user({"password": new_password})
        else:
             get_db(token).auth.update_user({"password": new_password})
             
        flash("Password updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating password: {str(e)}", "error")
        
    return redirect(url_for('profile'))

@app.route('/add_bank', methods=['POST'])
def add_bank():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    bank_name = request.form.get('bank_name')
    account_number = request.form.get('account_number')
    ifsc_code = request.form.get('ifsc_code')
    opening_balance = request.form.get('opening_balance', 0)

    try:
        token = session.get('access_token')

        
        data = {
            'user_id': session['user'],
            'bank_name': bank_name,
            'account_number': account_number,
            'ifsc_code': ifsc_code,
            'opening_balance': float(opening_balance)
        }
        get_db(token).table('bank_accounts').insert(data).execute()
        flash('Bank account added!', 'success')
    except Exception as e:
        flash(f"Error adding bank: {str(e)}", 'error')
    
    return redirect(url_for('banks'))

@app.route('/edit_bank/<bank_id>', methods=['POST'])
def edit_bank(bank_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    bank_name = request.form.get('bank_name')
    account_number = request.form.get('account_number')
    ifsc_code = request.form.get('ifsc_code')
    opening_balance = request.form.get('opening_balance', 0)

    try:
        token = session.get('access_token')

        data = {
            'bank_name': bank_name,
            'account_number': account_number,
            'ifsc_code': ifsc_code,
            'opening_balance': float(opening_balance)
        }
        get_db(token).table('bank_accounts').update(data).eq('id', bank_id).eq('user_id', session['user']).execute()
        flash('Bank account updated!', 'success')
    except Exception as e:
        flash(f"Error updating bank: {str(e)}", 'error')
    
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
                'description': desc,
                'recurring_rule_id': item['id']
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

DEFAULT_CATEGORIES = [
    'Food', 'Transport', 'Utilities', 'Entertainment', 'Shopping', 
    'Health', 'Travel', 'Education', 'Salary', 'Freelance', 'Investment', 'Other'
]

def get_all_categories(token, user_id):
    """
    Returns a list of categories (Default + Custom).
    """
    try:
        # Get custom categories from DB
        res = get_db(token).table('user_categories').select('name').eq('user_id', user_id).execute()
        custom_cats = [r['name'] for r in res.data]
        return DEFAULT_CATEGORIES + custom_cats
    except:
        return DEFAULT_CATEGORIES

@app.route('/categories')
def categories():
    if 'user' not in session: return redirect(url_for('login'))
    
    token = session.get('access_token')
    
    # We want to show custom categories allowing delete
    try:
        res = get_db(token).table('user_categories').select('*').eq('user_id', session['user']).execute()
        custom_categories = res.data
    except:
        custom_categories = []
        
    return render_template('categories.html', custom_categories=custom_categories, default_categories=DEFAULT_CATEGORIES)

@app.route('/add_category', methods=['POST'])
def add_category():
    if 'user' not in session: return redirect(url_for('login'))
    
    name = request.form.get('name')
    if not name:
        flash('Category name is required', 'error')
        return redirect(url_for('categories'))
        
    try:
        token = session.get('access_token')
        # Check for duplicates? For now just insert
        get_db(token).table('user_categories').insert({'user_id': session['user'], 'name': name}).execute()
        flash('Category added!', 'success')
    except Exception as e:
        flash(f"Error adding category: {str(e)}", 'error')
        
    return redirect(url_for('categories'))

@app.route('/delete_category/<cat_id>')
def delete_category(cat_id):
    if 'user' not in session: return redirect(url_for('login'))
    
    try:
        token = session.get('access_token')
        get_db(token).table('user_categories').delete().eq('id', cat_id).execute()
        flash('Category deleted.', 'info')
    except Exception as e:
        flash(f"Error deleting category: {str(e)}", 'error')
        
    return redirect(url_for('categories'))

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
        
        # Receipt Upload Logic
        receipt_url = None
        if 'receipt_file' in request.files:
            file = request.files['receipt_file']
            if file and file.filename != '':
                try:
                    file_content = file.read()
                    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                    file_path = f"{session['user']}/receipt_{int(datetime.datetime.now().timestamp())}.{file_ext}"
                    
                    get_db(token).storage.from_('receipts').upload(
                        file_path,
                        file_content,
                        {"content-type": f"image/{file_ext}"}
                    )
                    receipt_url = get_db(token).storage.from_('receipts').get_public_url(file_path)
                except Exception as e:
                    print(f"Receipt Upload Error: {e}")
                    # Don't fail the whole transaction, just warn? Or fail? 
                    # Let's log it and proceed without receipt to avoid losing data, or maybe flash generic error?
                    # Proceeding is safer for user experience if image fails but data is good.
        
        try:
            msg = f"{tx_type.title()} added successfully!"
            recurring_id = None
            
            if is_recurring:
                # Add Recurring Rule First to get ID
                d_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
                next_due = (d_obj + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
                
                rec_data = {
                    'user_id': session['user'],
                    'category': category,
                    'amount': float(amount),
                    'description': description,
                    'next_due_date': next_due
                }
                # Execute and get data to retrieve ID
                rec_res = get_db(token).table('recurring_expenses').insert(rec_data).execute()
                if rec_res.data:
                    recurring_id = rec_res.data[0]['id']
                    
                msg += " (Set to recur monthly)"

            # Add Expense/Income
            data = {
                'user_id': session['user'],
                'date': date,
                'category': category,
                'amount': float(amount),
                'description': description,
                'type': tx_type,
                'bank_account_id': bank_account_id,
                'receipt_url': receipt_url,
                'recurring_rule_id': recurring_id
            }
            get_db(token).table('expenses').insert(data).execute()
            
            flash(msg, 'success')
            return redirect(url_for('expenses'))
        except Exception as e:
            flash(f"Error adding {tx_type}: {str(e)}", 'error')
            
    # GET - Fetch Banks and Currency
    categories = DEFAULT_CATEGORIES
    try:
        banks_res = get_db(token).table('bank_accounts').select('id, bank_name').eq('user_id', session['user']).execute()
        banks = banks_res.data
        
        prof_res = get_db(token).table('profiles').select('currency').eq('id', session['user']).execute()
        currency = prof_res.data[0]['currency'] if prof_res.data else '₹'
        
        categories = get_all_categories(token, session['user'])
    except:
        banks = []
        currency = '₹'
        categories = DEFAULT_CATEGORIES

    return render_template('add.html', today=datetime.date.today(), expense=None, banks=banks, currency=currency, categories=categories)

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
    categories = DEFAULT_CATEGORIES
    try:
        res = get_db(token).table('expenses').select('*').eq('id', expense_id).execute()
        expense = res.data[0] if res.data else None
        
        # Fetch Banks
        banks_res = get_db(token).table('bank_accounts').select('id, bank_name').eq('user_id', session['user']).execute()
        banks = banks_res.data
        
        categories = get_all_categories(token, session['user'])
    except:
        expense = None
        banks = []
        categories = DEFAULT_CATEGORIES
        
    if not expense:
        flash('Transaction not found', 'error')
        return redirect(url_for('dashboard'))
        
    # Get Currency
    try:
         prof_res = get_db(token).table('profiles').select('currency').eq('id', session['user']).execute()
         currency = prof_res.data[0]['currency'] if prof_res.data else '₹'
    except:
         currency = '₹'
         
    return render_template('add.html', expense=expense, banks=banks, today=datetime.date.today(), currency=currency, categories=categories)

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
        
        profile_res = get_db(token).table('profiles').select('currency').eq('id', session['user']).execute()
        currency = profile_res.data[0]['currency'] if profile_res.data else '₹'
        
    except Exception as e:
        flash(f"Error generating reports: {str(e)}", 'error')
        exp_pie_labels = []
        exp_pie_values = []
        inc_pie_labels = []
        inc_pie_values = []
        bar_labels = []
        bar_exp = []
        bar_inc = []
        currency = '₹'
        
    return render_template('reports.html', 
                            exp_pie_labels=exp_pie_labels, exp_pie_values=exp_pie_values,
                            inc_pie_labels=inc_pie_labels, inc_pie_values=inc_pie_values,
                            bar_labels=bar_labels, bar_exp=bar_exp, bar_inc=bar_inc,
                            currency=currency)



@app.route('/export_pdf')
def export_pdf_route():
    if 'user' not in session: return redirect(url_for('login'))
    
    try:
        token = session.get('access_token')
        
        # Get data filtered by query params
        expenses = get_filtered_expenses(token, session['user'], request.args)
        
        # Get user profile name
        prof_res = get_db(token).table('profiles').select('full_name').eq('id', session['user']).execute()
        username = prof_res.data[0]['full_name'] if prof_res.data else "User"
        
        # Pass request.args as filters
        pdf_path = generate_pdf_report(expenses, username, filters=request.args)
        return send_file(pdf_path, as_attachment=True)
    except Exception as e:
        flash(f"Error generating PDF: {str(e)}", 'error')
        return redirect(url_for('dashboard'))

@app.route('/email_report', methods=['POST'])
def email_report_route():
    if 'user' not in session: return redirect(url_for('login'))
    
    email = request.form.get('email')
    
    # If email input not provided, try to get from user profile or auth
    if not email:
        try:
             token = session.get('access_token')
             u = supabase.auth.get_user(token)
             email = u.user.email
        except:
             flash('Could not determine email address.', 'error')
             return redirect(url_for('dashboard'))

    try:
        token = session.get('access_token')

        # Get data filtered by form params (hidden inputs)
        expenses = get_filtered_expenses(token, session['user'], request.form)
        
        prof_res = get_db(token).table('profiles').select('full_name').eq('id', session['user']).execute()
        username = prof_res.data[0]['full_name'] if prof_res.data else "User"
        
        # Pass request.form as filters
        pdf_path = generate_pdf_report(expenses, username, filters=request.form)
        
        subject = f"Monthly Transaction Report for {username}"
        body = f"Hello {username},\n\nPlease find attached your transaction report based on your selected filters.\n\nRegards,\nPocket Expense Tracker"
        
        success, msg = send_email_report(mail, app, email, subject, body, pdf_path)
        if success:
             flash(msg, 'success')
        else:
             flash(f"Failed to send email: {msg}", 'error')
             
    except Exception as e:
         flash(f"Error emailing report: {str(e)}", 'error')
         
@app.route('/delete_recurring/<recurring_id>')
def delete_recurring(recurring_id):
    if 'user' not in session: return redirect(url_for('login'))
    
    try:
        token = session.get('access_token')
        get_db(token).table('recurring_expenses').delete().eq('id', recurring_id).execute()
        flash('Recurring rule stopped successfully.', 'info')
    except Exception as e:
        flash(f"Error stopping recurring rule: {str(e)}", 'error')
        
    return redirect(url_for('expenses'))



@app.route('/debts', methods=['GET', 'POST'])
def debts():
    if 'user' not in session: return redirect(url_for('login'))
    
    token = session.get('access_token')
    
    if request.method == 'POST':
        person_name = request.form.get('person_name')
        amount = float(request.form.get('amount'))
        debt_type = request.form.get('type') # 'lend' or 'borrow'
        bank_id = request.form.get('bank_account_id')
        due_date = request.form.get('due_date') or None
        
        try:
            # 1. Create Debt Record
            debt_data = {
                'user_id': session['user'],
                'person_name': person_name,
                'amount': amount,
                'type': debt_type,
                'due_date': due_date
            }
            res = get_db(token).table('debts').insert(debt_data).execute()
            
            # 2. Create Transaction to update Bank Balance
            # Lend -> Expense (Money goes out)
            # Borrow -> Income (Money comes in)
            tx_type = 'expense' if debt_type == 'lend' else 'income'
            desc = f"Lent to {person_name}" if debt_type == 'lend' else f"Borrowed from {person_name}"
            
            tx_data = {
                'user_id': session['user'],
                'date': datetime.date.today().isoformat(),
                'category': 'Debt', 
                'amount': amount,
                'description': desc,
                'type': tx_type,
                'bank_account_id': bank_id if bank_id else None
            }
            get_db(token).table('expenses').insert(tx_data).execute()
            
            flash('Debt record created successfully!', 'success')
            
        except Exception as e:
            flash(f"Error creating debt: {str(e)}", 'error')
            
        return redirect(url_for('debts'))
        
    # GET
    try:
        res = get_db(token).table('debts').select('*').eq('user_id', session['user']).eq('status', 'active').order('created_at', desc=True).execute()
        debts_list = res.data
        
        lent_list = [d for d in debts_list if d['type'] == 'lend']
        borrowed_list = [d for d in debts_list if d['type'] == 'borrow']
        
        banks_res = get_db(token).table('bank_accounts').select('id, bank_name').eq('user_id', session['user']).execute()
        banks = banks_res.data
        
        prof_res = get_db(token).table('profiles').select('currency').eq('id', session['user']).execute()
        currency = prof_res.data[0]['currency'] if prof_res.data else '₹'
        
    except Exception as e:
        flash(f"Error fetching debts: {str(e)}", 'error')
        lent_list = []
        borrowed_list = []
        banks = []
        currency = '₹'
        
    return render_template('debts.html', lent_list=lent_list, borrowed_list=borrowed_list, banks=banks, currency=currency)

@app.route('/settle_debt/<debt_id>', methods=['POST'])
def settle_debt(debt_id):
    if 'user' not in session: return redirect(url_for('login'))
    
    token = session.get('access_token')
    bank_id = request.form.get('bank_account_id') # Bank used to receive/pay back
    
    try:
        # Get debt details first
        res = get_db(token).table('debts').select('*').eq('id', debt_id).execute()
        if not res.data:
            flash('Debt record not found.', 'error')
            return redirect(url_for('debts'))
            
        debt = res.data[0]
        amount = debt['amount']
        
        # Update status to settled
        get_db(token).table('debts').update({'status': 'settled'}).eq('id', debt_id).execute()
        
        # Create Transaction
        # If I lent (lend), settling means I get money back -> Income
        # If I borrowed (borrow), settling means I pay back -> Expense
        if debt['type'] == 'lend':
            tx_type = 'income'
            desc = f"Repayment received from {debt['person_name']}"
        else:
            tx_type = 'expense'
            desc = f"Repayment paid to {debt['person_name']}"
            
        tx_data = {
            'user_id': session['user'],
            'date': datetime.date.today().isoformat(),
            'category': 'Debt Repayment',
            'amount': amount,
            'description': desc,
            'type': tx_type,
            'bank_account_id': bank_id if bank_id else None
        }
        get_db(token).table('expenses').insert(tx_data).execute()
        
        flash('Debt settled successfully!', 'success')
        
    except Exception as e:
        flash(f"Error settling debt: {str(e)}", 'error')
        
    return redirect(url_for('debts'))

if __name__ == '__main__':
    app.run(debug=True)
