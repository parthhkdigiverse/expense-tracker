from fpdf import FPDF
from flask_mail import Message
import datetime
import os

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Pocket Expense Tracker - Monthly Report', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_pdf_report(expenses, username, total=None):
    """
    Generates a PDF report for the given expenses.
    Returns the filename of the generated PDF.
    Calculates totals internally based on transaction type.
    """
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # User Info
    pdf.cell(0, 10, f"User: {username}", 0, 1)
    pdf.cell(0, 10, f"Date: {datetime.date.today().strftime('%d-%m-%Y')}", 0, 1)
    pdf.ln(10)

    # Table Header
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(30, 10, "Date", 1, 0, 'C', True)
    pdf.cell(40, 10, "Category", 1, 0, 'C', True)
    pdf.cell(80, 10, "Description", 1, 0, 'C', True)
    pdf.cell(40, 10, "Amount", 1, 1, 'C', True)

    # Table Body
    pdf.set_font("Arial", size=12)
    
    total_income = 0
    total_expense = 0
    
    for expense in expenses:
        # expense: dict or object. 
        # Adapting to Supabase return format which is a list of dicts:
        # {'date':..., 'category':..., 'amount':..., 'description':..., 'type':...}
        
        if isinstance(expense, dict):
             date_str = str(expense.get('date', ''))
             category = str(expense.get('category', ''))
             amount_val = float(expense.get('amount', 0))
             description = str(expense.get('description', ''))
             tx_type = expense.get('type', 'expense')
        else:
             # Fallback if tuple
             date_str = str(expense[2])
             category = str(expense[3])
             amount_val = float(expense[4])
             description = str(expense[5])
             tx_type = 'expense' # Default for legacy tuples

        if tx_type == 'income':
            total_income += amount_val
            amount_str = f"+{amount_val:.2f}"
            pdf.set_text_color(0, 128, 0) # Green
        else:
            total_expense += amount_val
            amount_str = f"-{amount_val:.2f}"
            pdf.set_text_color(200, 0, 0) # Red

        pdf.cell(30, 10, date_str, 1)
        pdf.cell(40, 10, category, 1)
        pdf.cell(80, 10, description, 1)
        pdf.cell(40, 10, amount_str, 1, 1, 'R')
        
        pdf.set_text_color(0, 0, 0) # Reset to black

    pdf.ln(5)
    
    # Summary
    net_total = total_income - total_expense
    
    pdf.set_font("Arial", '', 12)
    pdf.cell(150, 10, "Total Income:", 0, 0, 'R')
    pdf.set_text_color(0, 128, 0)
    pdf.cell(40, 10, f"+{total_income:.2f}", 1, 1, 'R')
    pdf.set_text_color(0, 0, 0)
    
    pdf.cell(150, 10, "Total Expenses:", 0, 0, 'R')
    pdf.set_text_color(200, 0, 0)
    pdf.cell(40, 10, f"-{total_expense:.2f}", 1, 1, 'R')
    pdf.set_text_color(0, 0, 0)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(150, 10, "Net Total:", 0, 0, 'R')
    
    if net_total >= 0:
        pdf.set_text_color(0, 128, 0)
    else:
        pdf.set_text_color(200, 0, 0)
        
    pdf.cell(40, 10, f"{net_total:.2f}", 1, 1, 'R')
    pdf.set_text_color(0, 0, 0)

    # Use /tmp for serverless/read-only environments
    import tempfile
    
    # Create a temp file path
    temp_dir = tempfile.gettempdir()
    filename = os.path.join(temp_dir, f"Report_{username}_{datetime.date.today()}.pdf")
    
    pdf.output(filename)
    return filename

def send_email_report(mail, app, email_address, subject, body, attachment_path):
    """
    Sends an email with the PDF report attached.
    """
    try:
        msg = Message(subject, recipients=[email_address])
        msg.body = body
        
        with app.open_resource(attachment_path) as fp:
            msg.attach(os.path.basename(attachment_path), "application/pdf", fp.read())
            
        mail.send(msg)
        return True, "Email sent successfully!"
    except Exception as e:
        return False, str(e)
