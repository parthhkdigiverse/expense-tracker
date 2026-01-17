import sqlite3

DB_NAME = "expenses.db"

def get_connection():
    """
    Establishes and returns a connection to the SQLite database.
    """
    return sqlite3.connect(DB_NAME)

def create_tables():
    """
    Initializes the database schema.
    Creates tables for users, expenses, and recurring expenses if they don't exist.
    Also handles schema migrations (e.g., adding 'role' or 'budget' columns) for existing databases.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Create Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        security_question TEXT,
        security_answer TEXT,
        role TEXT DEFAULT 'user'
    )
    """)

    # Create Expenses Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        description TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # Attempt migration for existing tables (Role column)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    except sqlite3.OperationalError:
        pass # Column likely already exists

    # Attempt migration for Budget column
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN budget REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass # Column likely already exists

    # Create Recurring Expenses Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recurring_expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        description TEXT NOT NULL,
        frequency TEXT DEFAULT 'monthly',
        next_due_date TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # Create default admin if not exists
    try:
        # Check if admin exists
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ('admin', 'admin123', 'admin'))
            print("Admin user created (admin/admin123)")
    except Exception as e:
        print(f"Error creating admin: {e}")

    conn.commit()
    conn.close()
