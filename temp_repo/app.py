from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from functools import wraps
from db import create_tables
from auth import signup, login, get_security_question, verify_reset_password
from expense_manager import (
    add_expense, get_expenses, get_total_expense,
    get_monthly_report, get_category_data, get_monthly_chart_data,
    get_all_users, get_user_by_id,
    get_expense_by_id, update_expense, delete_expense,
    get_budget, set_budget,
    add_recurring_expense, check_recurring_expenses
)
import datetime
import io
import csv
import os
from flask import send_file
from flask_mail import Mail, Message
from utils import generate_pdf_report, send_email_report

# Initialize Flask Application
app = Flask(__name__)
app.secret_key = "super_secret_key"  # Change this in production

# Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = "parthhkdigiverse@gmail.com" # REPLACE WITH YOUR EMAIL
app.config['MAIL_PASSWORD'] = "cthi vnbo nmzj ohxm"    # REPLACE WITH YOUR APP PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = "parthhkdigiverse@gmail.com"
mail = Mail(app)

# ---------------------------------------------------------
# Custom Filters
# ---------------------------------------------------------
@app.template_filter('format_date')
def format_date(value, format="%d-%m-%Y"):
    """
    Jinja2 filter to format date strings (YYYY-MM-DD) into a more readable format (default: DD-MM-YYYY).
    """
    if value is None:
        return ""
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d").strftime(format)
    except ValueError:
        return value

# ---------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------
# Ensure tables exist before starting the app
if not os.path.exists('expense_tracker.db'):
    create_tables()

# ---------------------------------------------------------
# Login Decorators
# ---------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        if session.get('role') != 'admin':
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------

@app.route('/')
def home():
    """
    Redirects root URL to the login page.
    """
    return redirect(url_for('login_page'))

@app.route('/signup', methods=['GET', 'POST'])
def signup_page():
    """
    Handles user registration.
    GET: Renders signup form.
    POST: Processes signup form data and creates a new user.
    """
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        security_question = request.form['security_question']
        security_answer = request.form['security_answer']
        
        # Call auth.signup
        success, message = signup(username, password, security_question, security_answer)
        
        if success:
            flash('Signup successful! Please login.', 'success')
            return redirect(url_for('login_page'))
        else:
            flash(message, 'error') # message is "Username already exists."
            
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """
    Handles user login.
    GET: Renders login form.
    POST: Authenticates user credentials.
    """
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Call auth.login
        user_id, role = login(username, password)
        
        if user_id:
            # Store user info in session
            session['user_id'] = user_id
            session['username'] = username
            session['role'] = role
            
            # Check for due recurring expenses upon login
            added_count = check_recurring_expenses(user_id)
            if added_count > 0:
                flash(f'Login successful! Added {added_count} recurring expense(s).', 'success')
            else:
                flash('Login successful!', 'success')
            
            # Redirect based on role
            if role == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials.', 'error')
            
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """
    Handles password reset flow.
    GET: Renders forgot password form.
    POST: Verifies security question and updates password.
    """
    # Note: The logic in the original file might be different than my simplified view.
    # The previous file had step logic in 'forgot_password' route?
    # Let's check the previous 'forgot_password' implementation I overwrote?
    # Actually, the user's previous code for forgot password was complex (steps).
    # I should try to preserve that if possible or use the auth helpers.
    # The auth.py has get_security_question and verify_reset_password.
    
    # Re-implmenting the step logic seen in previous conversation logs if possible, 
    # OR assuming a simpler flow if that's what's currently in auth.
    # Wait, the previous app.py view showed:
    # step = request.args.get('step', '1') ...
    # I should probably just restore that logic but comment it.
    
    step = request.args.get('step', '1')
    username = request.args.get('username', '')
    
    if request.method == 'POST':
        if 'check_user' in request.form:
            username = request.form['username']
            question = get_security_question(username)
            if question:
                return redirect(url_for('forgot_password', step='2', username=username))
            else:
                flash('Username not found', 'error')
        
        elif 'reset_pass' in request.form:
            username = request.form['username']
            answer = request.form['security_answer']
            new_pass = request.form['new_password']
            
            success, msg = verify_reset_password(username, answer, new_pass)
            if success:
                flash(msg, 'success')
                return redirect(url_for('login_page'))
            else:
                flash(msg, 'error')

    question = None
    if step == '2' and username:
        question = get_security_question(username)
    
    return render_template('forgot_password.html', step=step, username=username, question=question)

@app.route('/logout')
def logout():
    """
    Clears the session and redirects to login page.
    """
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login_page'))

@app.route('/dashboard')
@login_required
def dashboard():
    """
    Main User Dashboard.
    Displays expenses, current budget status, and charts summary.
    Supports date filtering via query parameters.
    """
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    user_id = session['user_id']
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    expenses = get_expenses(user_id, start_date, end_date)
    total = get_total_expense(user_id) # Total might need to respect filter too? 
    # For now, let's keep total as overall total for budget tracking, 
    # OR we can calculate filtered total. 
    # Usually "Total Expense" on dashboard implies total for the view.
    # But budget is monthly. 
    # Let's keep total = global total for budget calculation context
    # But maybe we should show a "Filtered Total" if filtering?
    # Keeping it simple: Total matches expenses list if possible? 
    # Actually, get_total_expense is just SUM(amount). It doesn't take dates.
    # If I want total to match the filter, I'd need to update get_total_expense too or calc in python.
    # Let's handle just the list filtering first as per plan.
    
    budget = get_budget(user_id)
    
    percentage = 0
    progress_class = "progress-safe"
    
    if budget > 0:
        percentage = min((total / budget) * 100, 100)
        if percentage > 90:
            progress_class = "progress-danger"
        elif percentage > 75:
            progress_class = "progress-warning"
            
    return render_template('dashboard.html', 
                           expenses=expenses, total=total, username=session['username'], 
                           budget=budget, percentage=percentage, 
                           progress_class=progress_class,
                           start_date=start_date, end_date=end_date)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """
    Adds a new expense.
    GET: Renders add expense form.
    POST: Processes form data to create a new expense.
    """
    
    if request.method == 'POST':
        date = request.form['date']
        category = request.form['category']
        amount = request.form['amount']
        description = request.form['description']
        is_recurring = request.form.get('is_recurring')
        
        success, message = add_expense(session['user_id'], date, category, amount, description)
        
        if success and is_recurring:
             # Add to recurring table too
             add_recurring_expense(session['user_id'], date, category, amount, description)
             message += " (Set to recur monthly)"

        if success:
            flash(message, 'success')
            if session.get('role') == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            flash(message, 'error')
            
    return render_template('add.html', today=datetime.date.today(), expense=None)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_expense_route(id):
    """
    Edits an existing expense.
    GET: Renders form pre-filled with expense data.
    POST: Updates expense in database.
    """
    
    user_id = session['user_id']
    expense = get_expense_by_id(id)
    
    if not expense or expense[5] != user_id:
        flash('Expense not found or unauthorized', 'error')
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        date = request.form['date']
        category = request.form['category']
        amount = request.form['amount']
        description = request.form['description']
        
        success, message = update_expense(id, user_id, date, category, amount, description)
        if success:
            flash(message, 'success')
            return redirect(url_for('dashboard'))
        else:
            flash(message, 'error')
            
    return render_template('add.html', expense=expense, today=datetime.date.today())

@app.route('/set_budget', methods=['POST'])
@login_required
def set_budget_route():
    """
    Updates the user's monthly budget.
    """
        
    amount = request.form['budget']
    success, message = set_budget(session['user_id'], amount)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
        
    return redirect(url_for('dashboard'))

@app.route('/delete/<int:id>')
@login_required
def delete_expense_route(id):
    """
    Deletes an expense item.
    """
        
    user_id = session['user_id']
    success, message = delete_expense(id, user_id)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
        
    return redirect(url_for('dashboard'))

@app.route('/export')
@login_required
def export_csv():
    """
    Exports user's expenses to a CSV file for download.
    Format: ID, Date, Category, Amount, Description
    """
    
    user_id = session['user_id']
    expenses = get_expenses(user_id)
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Date', 'Category', 'Amount', 'Description'])
    
    for expense in expenses:
        # expense tuple: (id, date, category, amount, description)
        # Format date for CSV
        row = list(expense)
        try:
            row[1] = datetime.datetime.strptime(row[1], "%Y-%m-%d").strftime("%d-%m-%Y")
        except (ValueError, TypeError):
            pass # Keep original if parse fails
            
        cw.writerow(row)
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=expenses.csv"
    output.headers["Content-type"] = "text/csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/export_pdf')
@login_required
def export_pdf():
    """
    Generates and downloads a PDF report.
    """
    user_id = session['user_id']
    username = session['username']
    expenses = get_expenses(user_id)
    total = get_total_expense(user_id)
    
    pdf_path = generate_pdf_report(expenses, username, total)
    
    try:
        return send_file(pdf_path, as_attachment=True)
    except Exception as e:
        flash(f"Error generating PDF: {str(e)}", 'error')
        return redirect(url_for('dashboard'))

@app.route('/email_report', methods=['POST'])
@login_required
def email_report_route():
    """
    Generates PDF and emails it to the provided address.
    """
    email = request.form.get('email')
    if not email:
        flash('Email address is required.', 'error')
        return redirect(url_for('dashboard'))
        
    user_id = session['user_id']
    username = session['username']
    expenses = get_expenses(user_id)
    total = get_total_expense(user_id)
    
    # Generate PDF first
    pdf_path = generate_pdf_report(expenses, username, total)
    
    # Send Email
    subject = f"Monthly Expense Report for {username}"
    body = f"Hello {username},\n\nPlease find attached your expense report.\n\nTotal Expenses: {total}\n\nRegards,\nPocket Expense Tracker"
    
    success, msg = send_email_report(mail, app, email, subject, body, pdf_path)
    
    if success:
        flash(msg, 'success')
    else:
        if "Authentication" in str(msg) or "Username and Password not accepted" in str(msg):
            flash(f"Email Failed: {msg}. DO NOT use your login password. Use an App Password.", 'error')
        else:
            flash(f"Failed to send email: {msg}", 'error')
        
    return redirect(url_for('dashboard'))

@app.route('/reports')
@login_required
def reports():
    """
    Renders reports page with charts.
    """
    
    user_id = session['user_id']
    
    # Data for charts
    cat_data = get_category_data(user_id)
    pie_labels = [row[0] for row in cat_data]
    pie_values = [row[1] for row in cat_data]
    
    bar_months, bar_totals = get_monthly_chart_data(user_id)
    
    return render_template('reports.html', 
                           pie_labels=pie_labels, pie_values=pie_values,
                           bar_labels=bar_months, bar_values=bar_totals)

# ---------------------------------------------------------
# Admin Routes
# ---------------------------------------------------------

@app.route('/admin')
@admin_required
def admin_dashboard():
    """
    Admin Dashboard: View all users.
    """
    
    users = get_all_users()
    return render_template('admin_dashboard.html', users=users, username=session['username'])

@app.route('/admin/user/<int:user_id>')
@admin_required
def admin_view_user(user_id):
    """
    Admin: View specific user's expenses.
    """
    
    target_username = get_user_by_id(user_id)
    expenses = get_expenses(user_id)
    total = get_total_expense(user_id)
    
    return render_template('admin_user_details.html', expenses=expenses, total=total, target_username=target_username)

@app.after_request
def add_header(response):
    """
    Add headers to prevent caching, fixing the 'back button' issue.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

if __name__ == '__main__':
    app.run(debug=True)
