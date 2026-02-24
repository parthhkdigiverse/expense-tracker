# Technical Specification Document: Expense Enterprise

This document provides a comprehensive technical overview of the **Expense Enterprise** project. It is designed to onboard a new AI model or developer by detailing the system architecture, core technologies, and functional modules.

## 1. Project Overview
**Expense Enterprise** is a sophisticated personal and business finance management application. It allows users to track daily expenses, manage recurring transactions, monitor debts, and handle complex enterprise cash flows across multiple organizations.

The project is built on a **Flask** backend with a custom **Hybrid Database Layer** that bridges cloud (Supabase) and local (PostgreSQL) environments.

---

## 2. Technology Stack

| Component | Technology | Use Case |
| :--- | :--- | :--- |
| **Backend Framework** | [Flask](https://flask.palletsprojects.com/) | RESTful API, Route handling, Templates |
| **Primary Cloud DB** | [Supabase](https://supabase.com/) | Auth, RLS, Storage (receipts/avatars), Cloud Data |
| **Secondary Local DB** | [PostgreSQL](https://www.postgresql.org/) | Enterprise data, Local development/testing |
| **Template Engine** | [Jinja2](https://jinja.palletsprojects.com/) | Server-side rendering |
| **PDF Generation** | [fpdf2](https://github.com/PyFPDF/fpdf2) | Exporting transaction reports |
| **Email Service** | [Flask-Mail](https://pythonhosted.org/flask-mail/) | Report delivery, Notifications |
| **Environment** | [python-dotenv](https://saurabh-kumar.com/python-dotenv/) | Sensitive configuration management |

---

## 3. Core Architecture

### 3.1 Backend Structure
The application uses **Flask Blueprints** to modularize functionality:
- `app.py`: Main entry point, global middleware, session logic, and personal finance routes.
- `blueprints/enterprise.py`: Handles all enterprise-specific logic, including organization switching and RBAC.
- `blueprints/database_service.py`: A flexible abstraction layer (Factory Pattern) that handles data operations for both Supabase and PostgreSQL.

### 3.2 Hybrid Database Service (`database_service.py`)
The system employs a `BaseService` interface with two implementations:
1. `SupabaseService`: Communicates with Supabase using the Python client. Supports RLS and cloud storage.
2. `PostgresService`: Connects directly to a local PostgreSQL instance. Includes a "Sync" mechanism that mirrors certain local operations back to Supabase to maintain global state.

### 3.3 Authentication & Session Logic
- **Primary Auth**: Handled via Supabase Auth (Sign-in, Register, MFA, Magic Links).
- **Session Strategy**: Stateless, client-side signed cookies (Flask sessions).
- **Middleware (`manage_session_logic`)**:
    - Enforces inactivity timeouts (default: 10 mins).
    - Automatically refreshes Supabase JWTs if they are within 2 minutes of expiry (`REFRESH_THRESHOLD_SECONDS`).

---

## 4. Database Schema
Major tables in `public` (Supabase) and local PostgreSQL:

### Shared/Personal Tables
- `profiles`: User-specific settings (username, avatar, budget, currency).
- `bank_accounts`: Personal bank details and opening balances.
- `expenses`: Primary transaction table.
- `recurring_expenses`: Blueprints for monthly auto-generated expenses.
- `debts`: Tracking of lent and borrowed amounts.

### Enterprise Tables
- `ent_organizations`: Master list of business entities.
- `ent_members`: RBAC mapping (User -> Organization -> Role).
- `ent_revenue` / `ent_expenses`: Specialized ledger for business cash flow.
- `ent_holding_payments`: Tracking for receivables and payables.
- `ent_investments`: Tracking of capital infusion and withdrawal.
- `enterprise_credentials`: Local-only secondary auth for enterprise accounts.

---

## 5. Feature Deep-Dive

### 5.1 Personal Finance Tracking
- **Bulk Add**: Interface for adding multiple transactions simultaneously.
- **Reporting**: Dynamic chart generation (Chart.js) and PDF report generation (filtering by date/category).
- **Auto-Recurring**: Middleware checks on login for due recurring items and populates the `expenses` table.

### 5.2 Enterprise Management
- **RBAC**: Multi-tenant architecture where users can switch between different organizations.
- **Combined Cashflow**: A unified ledger for enterprise revenue and expenses with specialized filtering.
- **Holding Payments**: A system to track unsettled dues with support for partial vs. full settlement.

---

## 6. Technical Nuances & Known Pitfalls
- **JWT Expiry**: The app is sensitive to expired Supabase tokens. Centralized error handling in `app.py` detects `PGRST303` (JWT Expired) and forces a logout if refresh fails.
- **Local vs Cloud Mapping**: When running with `DB_BACKEND=local`, the `PostgresService` attempts to map local UUIDs to Supabase profiles via email addresses to maintain consistency during sync.
- **Recursive Sync**: Some enterprise operations trigger "Sync" events that insert records into the personal `expenses` table to reflect business transactions in the personal bank balance.

---

## 7. Environment Configuration
Required `.env` keys:
```bash
SUPABASE_URL=...
SUPABASE_KEY=...
FLASK_SECRET_KEY=...
DB_BACKEND=supabase # or 'local'
DATABASE_URL=... # Only if backend is 'local'
MAIL_USERNAME=...
MAIL_PASSWORD=...
```

---
*Generated by Technical Project Lead (AI Assistant)*
