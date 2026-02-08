from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ..models import StreamUser, db
from datetime import datetime, timedelta
import subprocess
import os

users_bp = Blueprint('users', __name__)
HTPASSWD_FILE = os.environ.get('HTPASSWD_FILE', '/auth/.htpasswd')

def sync_htpasswd():
    """Rebuilds the .htpasswd file from the database"""
    # Verify file directory exists
    os.makedirs(os.path.dirname(HTPASSWD_FILE), exist_ok=True)
    
    active_users = StreamUser.query.filter_by(status='active').all()
    
    # We will use htpasswd command to ensure correct format for each user
    # Ideally, we should truncate file and re-add all, but htpasswd append mode is tricky.
    # Simpler approach: Create new file, iterate users.
    
    # Using 'bcrypyt' mode (-B) requires the plain password, but we store the hash.
    # If we store the hash in DB, we can just write it directly formatted.
    # The 'StreamUser' model should store the HASHED password ideally if we generated it.
    
    # HOWEVER, to allow 'editing' passwords, we usually take plaintext input.
    # Strategy: 
    # 1. We accept plaintext password from UI.
    # 2. We use `htpasswd -B -n user pass` to generate the hash line.
    # 3. We store that hash line (or just the hash part) in DB.
    # 4. We write the file directly.
    
    try:
        with open(HTPASSWD_FILE, 'w') as f:
            for user in active_users:
                # Assuming password_hash is the full Apache hash string
                f.write(f"{user.username}:{user.password_hash}\n")
                
        # Also ensure our 'admin' (load balancer admin) is preserved? 
        # Strategy: The DB should probably contain the 'admin' regular user too if desired.
        # Or we append a hardcoded admin.
        with open(HTPASSWD_FILE, 'a') as f:
             # This is risky if admin is in DB. Let's assume admin is in DB for now.
             pass
             
    except Exception as e:
        flash(f"Error syncing .htpasswd: {str(e)}", "error")

@users_bp.route('/users')
@login_required
def list_users():
    users = StreamUser.query.all()
    return render_template('users.html', users=users)

@users_bp.route('/users/add', methods=['POST'])
@login_required
def add_user():
    username = request.form.get('username')
    password = request.form.get('password')
    notes = request.form.get('notes')
    
    if StreamUser.query.filter_by(username=username).first():
        flash('Username already exists.', 'error')
        return redirect(url_for('users.list_users'))

    # Generate Hash
    # Using apache2-utils: htpasswd -B -n -b user pass
    try:
        expires_at = None
        expiry_str = request.form.get('expiry_date')
        if expiry_str:
            try:
                expires_at = datetime.strptime(expiry_str, '%Y-%m-%d')
            except ValueError:
                pass # Invalid date format, ignore or handle error

        result = subprocess.run(
            ['htpasswd', '-Bb', '-n', username, password],
            capture_output=True, text=True, check=True
        )
        # Output format: username:hash
        full_line = result.stdout.strip()
        password_hash = full_line.split(':')[1]
        
        new_user = StreamUser(
            username=username, 
            password_hash=password_hash, 
            notes=notes,
            expires_at=expires_at
        )
        db.session.add(new_user)
        db.session.commit()
        sync_htpasswd()
        flash('User added successfully.', 'success')
    except Exception as e:
        flash(f"Error creating user: {str(e)}", "error")
        
    return redirect(url_for('users.list_users'))

@users_bp.route('/users/delete/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    user = StreamUser.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    sync_htpasswd()
    flash('User deleted.', 'success')
    return redirect(url_for('users.list_users'))

@users_bp.route('/users/toggle/<int:id>', methods=['POST'])
@login_required
def toggle_status(id):
    user = StreamUser.query.get_or_404(id)
    user.status = 'disabled' if user.status == 'active' else 'active'
    db.session.commit()
    sync_htpasswd()
    flash(f'User {user.username} is now {user.status}.', 'success')
    return redirect(url_for('users.list_users'))

@users_bp.route('/users/edit/<int:id>', methods=['POST'])
@login_required
def edit_user(id):
    user = StreamUser.query.get_or_404(id)
    username = request.form.get('username')
    password = request.form.get('password')
    notes = request.form.get('notes')
    expiry_str = request.form.get('expiry_date')
    
    # Update username if changed (and checks uniqueness)
    if username and username != user.username:
        if StreamUser.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return redirect(url_for('users.list_users'))
        user.username = username

    # Update password if provided
    if password:
        try:
            # We need to preserve the user for the htpasswd command
            result = subprocess.run(
                ['htpasswd', '-Bb', '-n', user.username, password],
                capture_output=True, text=True, check=True
            )
            full_line = result.stdout.strip()
            user.password_hash = full_line.split(':')[1]
        except Exception as e:
            flash(f"Error updating password: {str(e)}", "error")
            return redirect(url_for('users.list_users'))

    # Update notes
    user.notes = notes

    # Update expiry
    if expiry_str:
        try:
            user.expires_at = datetime.strptime(expiry_str, '%Y-%m-%d')
        except ValueError:
            pass
    elif request.form.get('expiry_cleared') == 'true':
         user.expires_at = None

    db.session.commit()
    sync_htpasswd()
    flash('User updated successfully.', 'success')
    return redirect(url_for('users.list_users'))
