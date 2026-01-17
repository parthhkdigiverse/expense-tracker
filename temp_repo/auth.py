from db import get_connection

def signup(username, password, security_question, security_answer):
    """
    Registers a new user in the database.
    Args:
        username (str): The desired username.
        password (str): The user's password (plaintext for now, hashing recommended).
        security_question (str): Question for password recovery.
        security_answer (str): Answer for password recovery.
    Returns:
        tuple: (success (bool), message (str))
    """
    username = username.strip()
    password = password.strip()
    security_answer = security_answer.strip().lower()

    if not username or not password or not security_question or not security_answer:
        return False, "All fields are required."

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO users (username, password, security_question, security_answer, role) VALUES (?, ?, ?, ?, ?)",
            (username, password, security_question, security_answer, 'user')
        )
        conn.commit()
        return True, "Account created successfully!"
    except:
        return False, "Username already exists."
    finally:
        conn.close()

def login(username, password):
    """
    Authenticates a user.
    Returns:
        tuple: (user_id (int|None), role (str|None))
    """
    username = username.strip()
    password = password.strip()

    if not username or not password:
        return None, None

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, role FROM users WHERE username = ? AND password = ?",
        (username, password)
    )

    user = cursor.fetchone()
    conn.close()

    if user:
        return user[0], user[1] # Return ID and Role
    else:
        return None, None

def get_security_question(username):
    """
    Retrieves the security question for a given username.
    Used in step 1 of password reset.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT security_question FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def verify_reset_password(username, answer, new_password):
    """
    Verifies the security answer and updates the password if correct.
    Returns:
        tuple: (success (bool), message (str))
    """
    answer = answer.strip().lower()
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT security_answer FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return False, "User not found."
        
    stored_answer = result[0]
    
    if stored_answer == answer:
        cursor.execute("UPDATE users SET password = ? WHERE username = ?", (new_password, username))
        conn.commit()
        conn.close()
        return True, "Password updated successfully!"
    else:
        conn.close()
        return False, "Incorrect security answer."
