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

def generate_pdf_report(expenses, username, total):
    """
    Generates a PDF report for the given expenses.
    Returns the filename of the generated PDF.
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
    for expense in expenses:
        # expense: (id, date, category, amount, description)
        # We need date, category, description, amount.
        # Check indices from get_expenses: id(0), date(1), category(2), amount(3), description(4)
        
        date_str = str(expense[1])
        category = str(expense[2])
        amount = f"{expense[3]:.2f}"
        description = str(expense[4])

        pdf.cell(30, 10, date_str, 1)
        pdf.cell(40, 10, category, 1)
        pdf.cell(80, 10, description, 1)
        pdf.cell(40, 10, amount, 1, 1, 'R')

    pdf.ln(5)
    
    # Total
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(150, 10, "Total Expenses:", 0, 0, 'R')
    pdf.cell(40, 10, f"{total:.2f}", 1, 1, 'R')

    # Ensure reports directory exists
    if not os.path.exists('reports'):
        os.makedirs('reports')

    filename = f"reports/Expense_Report_{username}_{datetime.date.today()}.pdf"
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
