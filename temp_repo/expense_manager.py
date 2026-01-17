from db import get_connection
from datetime import datetime, timedelta

def add_expense(user_id, date, category, amount, description):
    """
    Adds a new expense record to the database.
    Returns:
        tuple: (success (bool), message (str))
    """
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return False, "Invalid date format. Use YYYY-MM-DD."

    if not category or not description:
        return False, "Category and description cannot be empty."

    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
    except ValueError:
        return False, "Amount must be a positive number."

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO expenses (user_id, date, category, amount, description)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, date, category, amount, description))

    conn.commit()
    conn.close()

    return True, "Expense added successfully!"

def get_expenses(user_id, start_date=None, end_date=None):
    """
    Retrieves expenses for a specific user, optionally filtered by a date range.
    Args:
        user_id (int): ID of the user.
        start_date (str, optional): 'YYYY-MM-DD' start filter.
        end_date (str, optional): 'YYYY-MM-DD' end filter.
    Returns:
        list: List of expense rows.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT id, date, category, amount, description
    FROM expenses
    WHERE user_id = ?
    """
    params = [user_id]
    
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
        
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
        
    query += " ORDER BY date DESC"

    cursor.execute(query, params)

    expenses = cursor.fetchall()
    conn.close()
    return expenses

def get_total_expense(user_id):
    """
    Calculates the total sum of all expenses for a user.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ?", (user_id,)
    )

    total = cursor.fetchone()[0]
    conn.close()
    return total or 0

def get_monthly_report(user_id, month):
    """
    Aggregates expenses by category for a specific month for reporting.
    Args:
        user_id (int): ID of the user.
        month (str): 'YYYY-MM' format for the month.
    Returns:
        list: List of (category, total_amount) tuples.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT category, SUM(amount)
    FROM expenses
    WHERE user_id = ? AND date LIKE ?
    GROUP BY category
    """, (user_id, month + "%"))

    results = cursor.fetchall()
    conn.close()
    return results

def get_category_data(user_id):
    """
    Aggregates expenses by category for a user, typically for pie charts.
    Args:
        user_id (int): ID of the user.
    Returns:
        list: List of (category, total_amount) tuples.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT category, SUM(amount)
    FROM expenses
    WHERE user_id = ?
    GROUP BY category
    """, (user_id,))

    results = cursor.fetchall()
    conn.close()
    return results

def get_monthly_chart_data(user_id):
    """
    Aggregates expenses by month for a user, typically for bar charts.
    Args:
        user_id (int): ID of the user.
    Returns:
        tuple: (list of month labels, list of total values).
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT SUBSTR(date, 1, 7) AS month, SUM(amount)
    FROM expenses
    WHERE user_id = ?
    GROUP BY month
    ORDER BY month
    """, (user_id,))

    data = cursor.fetchall()
    conn.close()
    
    months = [row[0] for row in data]
    totals = [row[1] for row in data]
    
    return months, totals

def set_budget(user_id, amount):
    """
    Sets or updates the user's monthly budget.
    Args:
        user_id (int): ID of the user.
        amount (float): The budget amount.
    Returns:
        tuple: (success (bool), message (str))
    """
    try:
        amount = float(amount)
        if amount < 0: raise ValueError
    except ValueError:
        return False, "Budget must be a positive number."
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET budget = ? WHERE id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    return True, "Budget updated successfully!"

def get_budget(user_id):
    """
    Retrieves the user's monthly budget.
    Args:
        user_id (int): ID of the user.
    Returns:
        float: The budget amount, or 0.0 if not set.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT budget FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0.0

def add_recurring_expense(user_id, date, category, amount, description):
    """
    Saves a definition for a recurring expense.
    Calculates the initial next due date (approximately 1 month from the start date).
    Args:
        user_id (int): ID of the user.
        date (str): The start date of the recurring expense ('YYYY-MM-DD').
        category (str): The category of the expense.
        amount (float): The amount of the expense.
        description (str): A description of the expense.
    Returns:
        tuple: (success (bool), message (str))
    """
    # Calculate next due date (approx 1 month from start date)
    # Using simple logic: same day next month
    try:
        start = datetime.strptime(date, "%Y-%m-%d")
        # Simple increment: 30 days roughly, or better logic
        # For simplicity in this scope, let's just add 30 days for "monthly"
        # Or use a library if available. Let's do simple 30 days for now or clean month logic.
        # Ideally: next_month = start.month + 1 ...
        # Let's use a helper for "add one month"
        next_due = (start.replace(day=1) + timedelta(days=32)).replace(day=start.day)
    except ValueError:
        # Fallback if day is out of range (e.g. Jan 31 -> Feb 31 doesnt exist), 
        # python handles this poorly without dateutil.
        # Let's stick to simple +30 days for MVP safety or specific implementation.
        next_due = start + timedelta(days=30)
    
    next_due_str = next_due.strftime("%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO recurring_expenses (user_id, category, amount, description, next_due_date)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, category, float(amount), description, next_due_str))
    conn.commit()
    conn.close()
    return True, "Recurring expense set!"

def check_recurring_expenses(user_id):
    """
    Checks if any recurring expenses are due as of today.
    If due, adds a new expense entry and updates the 'next_due_date'.
    Args:
        user_id (int): ID of the user.
    Returns:
        int: Number of expenses automatically added.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # correct query: select items due
    cursor.execute("""
        SELECT id, category, amount, description, next_due_date
        FROM recurring_expenses
        WHERE user_id = ? AND next_due_date <= ?
    """, (user_id, today))
    
    due_items = cursor.fetchall()
    count = 0
    
    for item in due_items:
        r_id, cat, amt, desc, due_date = item
        
        # Add to main expenses
        add_expense(user_id, due_date, cat, amt, desc + " (Auto-Recurring)")
        count += 1
        
        # Update next due date (+30 days)
        # Verify date format
        d_obj = datetime.strptime(due_date, "%Y-%m-%d")
        new_due = (d_obj + timedelta(days=30)).strftime("%Y-%m-%d")
        
        cursor.execute("UPDATE recurring_expenses SET next_due_date = ? WHERE id = ?", (new_due, r_id))
        
    conn.commit()
    conn.close()
    return count

# Admin Functions
def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role FROM users WHERE role != 'admin'")
    users = cursor.fetchall()
    conn.close()
    return users

def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "Unknown"

def get_expense_by_id(expense_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, date, category, amount, description, user_id FROM expenses WHERE id = ?", (expense_id,))
    expense = cursor.fetchone()
    conn.close()
    return expense

def update_expense(expense_id, user_id, date, category, amount, description):
    # Reuse validation logic ideally, but for now simple check
    try:
        datetime.strptime(date, "%Y-%m-%d")
        amount = float(amount)
        if amount <= 0: raise ValueError
    except ValueError:
        return False, "Invalid input data."

    conn = get_connection()
    cursor = conn.cursor()
    
    # Verify ownership
    cursor.execute("SELECT id FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
    if not cursor.fetchone():
        conn.close()
        return False, "Expense not found or access denied."

    cursor.execute("""
        UPDATE expenses 
        SET date = ?, category = ?, amount = ?, description = ?
        WHERE id = ? AND user_id = ?
    """, (date, category, amount, description, expense_id, user_id))
    
    conn.commit()
    conn.close()
    return True, "Expense updated successfully!"

def delete_expense(expense_id, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Verify ownership just in case (though WHERE clause handles it)
    cursor.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
    
    if cursor.rowcount == 0:
        conn.close()
        return False, "Expense not found or could not be deleted."
        
    conn.commit()
    conn.close()
    return True, "Expense deleted successfully!"
