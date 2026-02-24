from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from functools import wraps
from blueprints.database_service import SupabaseService, get_supabase_client, get_supabase_service_client

admin_bp = Blueprint('admin', __name__)

def _svc():
    """Helper to get a standard client for normal checks."""
    return SupabaseService(get_supabase_client(session.get('access_token')))

def _admin_svc():
    """Helper to get a Service Role client that actively bypasses RLS for admin tasks."""
    return SupabaseService(get_supabase_service_client())

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        
        # Verify the actively logged-in user is an admin
        is_admin = _svc().check_is_admin(session['user'])
        if not is_admin:
            flash('Unauthorized Access. Admin privileges required.', 'error')
            return redirect(url_for('dashboard'))
            
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    admin_svc = _admin_svc()
    
    # We can fetch counts from the db
    # Alternatively, just get all users and count them
    users = admin_svc.get_all_users()
    total_users = len(users)
    total_enterprises = admin_svc.get_total_enterprises()
    
    return render_template('admin/dashboard.html', 
                           total_users=total_users, 
                           total_enterprises=total_enterprises)

@admin_bp.route('/users')
@admin_required
def users():
    admin_svc = _admin_svc()
    users_list = admin_svc.get_all_users()
    return render_template('admin/users.html', users=users_list)

@admin_bp.route('/users/toggle_role/<user_id>', methods=['POST'])
@admin_required
def toggle_role(user_id):
    if user_id == session.get('user'):
        flash("You cannot demote or promote yourself.", "error")
        return redirect(url_for('admin.users'))
        
    action = request.form.get('action') # 'promote' or 'demote'
    
    new_status = False
    if action == 'promote':
        new_status = True
    elif action == 'demote':
        new_status = False
    else:
        flash("Invalid action.", "error")
        return redirect(url_for('admin.users'))
        
    admin_svc = _admin_svc()
    success = admin_svc.toggle_admin_status(user_id, new_status)
    
    if success:
        # Log the action
        admin_id = session.get('user')
        action_name = 'PROMOTE' if new_status else 'DEMOTE'
        old_data = {'is_admin': not new_status}
        new_data = {'is_admin': new_status}
        
        # Fire and forget / catch failure in the service
        admin_svc.log_admin_action(
            admin_id=admin_id,
            action=action_name,
            target_table='profiles',
            target_record_id=user_id,
            old_data=old_data,
            new_data=new_data
        )
        
        flash(f"User has been successfully {'promoted to Admin' if new_status else 'demoted from Admin'}.", "success")
    else:
        flash("Failed to update user status.", "error")
        
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/edit/<user_id>', methods=['POST'])
@admin_required
def edit_user(user_id):
    full_name = request.form.get('full_name')
    currency = request.form.get('currency')
    
    admin_svc = _admin_svc()
    
    # Ideally, fetch the old data first to record it accurately, 
    # but for brevity we'll just log the new changes.
    update_data = {}
    if full_name is not None:
        update_data['full_name'] = full_name
    if currency is not None:
        update_data['currency'] = currency
        
    if not update_data:
        flash("No data provided to update.", "error")
        return redirect(url_for('admin.users'))
        
    success = admin_svc.update_user_profile(user_id, update_data)
    if success:
        admin_svc.log_admin_action(
            admin_id=session.get('user'),
            action='EDIT_PROFILE',
            target_table='profiles',
            target_record_id=user_id,
            old_data=None, # In a real prod environment, query old state here
            new_data=update_data
        )
        flash("User profile updated.", "success")
    else:
        flash("Failed to update user profile.", "error")
        
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/suspend/<user_id>', methods=['POST'])
@admin_required
def suspend_user(user_id):
    if user_id == session.get('user'):
        flash("You cannot suspend your own account.", "error")
        return redirect(url_for('admin.users'))
        
    action = request.form.get('action') # 'suspend' or 'unsuspend'
    suspend_status = True if action == 'suspend' else False
    
    admin_svc = _admin_svc()
    success = admin_svc.toggle_user_suspension(user_id, suspend_status)
    
    if success:
        admin_svc.log_admin_action(
            admin_id=session.get('user'),
            action='SUSPEND' if suspend_status else 'UNSUSPEND',
            target_table='profiles',
            target_record_id=user_id,
            old_data={'is_suspended': not suspend_status},
            new_data={'is_suspended': suspend_status}
        )
        flash(f"User account has been {'suspended' if suspend_status else 'restored'}.", "success")
    else:
        flash("Failed to change user suspension status.", "error")
        
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/delete/<user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    if user_id == session.get('user'):
        flash("You cannot delete your own account.", "error")
        return redirect(url_for('admin.users'))
        
    admin_svc = _admin_svc()
    success = admin_svc.delete_user_completely(user_id)
    
    if success:
        admin_svc.log_admin_action(
            admin_id=session.get('user'),
            action='HARD_DELETE',
            target_table='profiles',
            target_record_id=user_id,
            old_data=None,
            new_data=None
        )
        flash("User and all associated data have been permanently deleted.", "success")
        flash("Failed to delete the user. They may have already been removed.", "error")
        
    return redirect(url_for('admin.users'))

@admin_bp.route('/businesses')
@admin_required
def businesses():
    admin_svc = _admin_svc()
    orgs = admin_svc.get_all_organizations()
    return render_template('admin/businesses.html', businesses=orgs)

@admin_bp.route('/businesses/<org_id>')
@admin_required
def business_detail(org_id):
    admin_svc = _admin_svc()
    orgs = admin_svc.get_all_organizations()
    # Find the specific org name manually since we already pulled them, or do a direct lookup
    org_name = "Unknown Business"
    for o in orgs:
        if o['id'] == org_id:
            org_name = o['name']
            break
            
    members = admin_svc.get_organization_members(org_id)
    return render_template('admin/business_detail.html', org_name=org_name, org_id=org_id, members=members)

@admin_bp.route('/businesses/delete/<org_id>', methods=['POST'])
@admin_required
def delete_business(org_id):
    admin_svc = _admin_svc()
    success = admin_svc.delete_organization_completely(org_id)
    
    if success:
        admin_svc.log_admin_action(
            admin_id=session.get('user'),
            action='HARD_DELETE',
            target_table='ent_organizations',
            target_record_id=org_id,
            old_data=None,
            new_data=None
        )
        flash("Business has been securely deleted. All active member access has been successfully revoked.", "success")
    else:
        flash("Failed to delete the business.", "error")
        
    return redirect(url_for('admin.businesses'))

@admin_bp.route('/ledger')
@admin_required
def ledger():
    admin_svc = _admin_svc()
    transactions = admin_svc.get_all_global_transactions()
    return render_template('admin/ledger.html', transactions=transactions)

@admin_bp.route('/ledger/edit/<trans_type>/<transaction_id>', methods=['POST'])
@admin_required
def edit_ledger_transaction(trans_type, transaction_id):
    # Form data: amount, category, date
    amount = request.form.get('amount')
    category = request.form.get('category')
    date_val = request.form.get('date')
    
    update_data = {}
    if amount:
        update_data['amount'] = float(amount)
    if date_val:
        update_data['date'] = date_val
    if category:
        # If revenue, the column is 'status'. If expense, it's 'category'
        if trans_type == 'revenue':
            update_data['status'] = category
        else:
            update_data['category'] = category
            
    if not update_data:
        flash("No valid data provided for update.", "error")
        return redirect(url_for('admin.ledger'))
        
    admin_svc = _admin_svc()
    success = admin_svc.update_global_transaction(transaction_id, trans_type, update_data)
    
    target_table = "ent_expenses" if trans_type == 'expense' else "ent_revenue"
    
    if success:
        admin_svc.log_admin_action(
            admin_id=session.get('user'),
            action='EDIT_TRANSACTION',
            target_table=target_table,
            target_record_id=transaction_id,
            new_data=update_data
        )
        flash("Transaction successfully updated.", "success")
    else:
        flash("Failed to update transaction.", "error")
        
    return redirect(url_for('admin.ledger'))

@admin_bp.route('/ledger/delete/<trans_type>/<transaction_id>', methods=['POST'])
@admin_required
def delete_ledger_transaction(trans_type, transaction_id):
    admin_svc = _admin_svc()
    success = admin_svc.delete_global_transaction(transaction_id, trans_type)
    
    target_table = "ent_expenses" if trans_type == 'expense' else "ent_revenue"
    
    if success:
        admin_svc.log_admin_action(
            admin_id=session.get('user'),
            action='DELETE_TRANSACTION',
            target_table=target_table,
            target_record_id=transaction_id
        )
        flash("Transaction securely deleted from the ledger.", "success")
    else:
        flash("Failed to delete the transaction.", "error")
        
    return redirect(url_for('admin.ledger'))

# ── Global Holdings & Staff Override ────────────────────────────────────────

@admin_bp.route('/holdings')
@admin_required
def holdings():
    admin_svc = _admin_svc()
    holdings = admin_svc.get_global_holdings()
    return render_template('admin/holdings.html', holdings=holdings)

@admin_bp.route('/holdings/delete/<holding_id>', methods=['POST'])
@admin_required
def delete_holding(holding_id):
    admin_svc = _admin_svc()
    success = admin_svc.delete_global_holding(holding_id)
    
    if success:
        admin_svc.log_admin_action(
            admin_id=session.get('user'),
            action='DELETE_HOLDING',
            target_table='ent_holding_payments',
            target_record_id=holding_id
        )
        flash("Holding payment permanently securely deleted.", "success")
    else:
        flash("Failed to delete the holding.", "error")
        
    return redirect(url_for('admin.holdings'))


@admin_bp.route('/staff')
@admin_required
def staff():
    admin_svc = _admin_svc()
    staff_list = admin_svc.get_global_staff()
    return render_template('admin/staff.html', staff=staff_list)

@admin_bp.route('/staff/delete/<staff_id>', methods=['POST'])
@admin_required
def delete_staff(staff_id):
    admin_svc = _admin_svc()
    success = admin_svc.delete_global_staff(staff_id)
    
    if success:
        admin_svc.log_admin_action(
            admin_id=session.get('user'),
            action='DELETE_STAFF',
            target_table='ent_staff',
            target_record_id=staff_id
        )
        flash("Staff member permanently securely wiped from the platform.", "success")
    else:
        flash("Failed to delete the staff record.", "error")
        
    return redirect(url_for('admin.staff'))
