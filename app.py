from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from calendar import monthrange
import sqlite3
import os
import atexit
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

app = Flask(__name__)
# Use a fixed secret key for sessions (in production, use environment variable)
SECRET_KEY_FILE = '.secret_key'
if os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, 'rb') as f:
        app.secret_key = f.read()
else:
    app.secret_key = os.urandom(24)
    with open(SECRET_KEY_FILE, 'wb') as f:
        f.write(app.secret_key)
# Configure permanent session lifetime to 7 days
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
DATABASE = 'tasks.db'

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with tables"""
    conn = get_db()
    
    # Tasks table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            date TEXT,
            time TEXT,
            completed INTEGER DEFAULT 0,
            completed_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            created_by INTEGER,
            visibility TEXT DEFAULT 'all',
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # Migrate existing tasks: add created_by and visibility if they don't exist
    try:
        # Check if created_by column exists
        cursor = conn.execute("PRAGMA table_info(tasks)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'created_by' not in columns:
            conn.execute('ALTER TABLE tasks ADD COLUMN created_by INTEGER')
            # Set created_by to user_id for existing tasks
            conn.execute('UPDATE tasks SET created_by = user_id WHERE created_by IS NULL')
        
        if 'visibility' not in columns:
            conn.execute('ALTER TABLE tasks ADD COLUMN visibility TEXT DEFAULT "all"')
            # Set visibility to 'all' for existing tasks
            conn.execute('UPDATE tasks SET visibility = "all" WHERE visibility IS NULL')
        
        if 'assigned_to' not in columns:
            conn.execute('ALTER TABLE tasks ADD COLUMN assigned_to INTEGER')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_assigned_to ON tasks(assigned_to)')
        
        if 'recurrence' not in columns:
            conn.execute('ALTER TABLE tasks ADD COLUMN recurrence TEXT')
        
        if 'parent_task_id' not in columns:
            conn.execute('ALTER TABLE tasks ADD COLUMN parent_task_id INTEGER')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_parent_task_id ON tasks(parent_task_id)')
        
        conn.commit()
    except sqlite3.OperationalError:
        # Columns already exist, ignore
        pass
    
    # Users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Account requests table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS account_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            requested_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Task completion requests table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS task_completion_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            requested_by INTEGER NOT NULL,
            requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (requested_by) REFERENCES users(id)
        )
    ''')
    
    # Checklist items table (subtasks/attached lists)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS checklist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            item_text TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    ''')
    
    # Create index for faster lookups
    conn.execute('CREATE INDEX IF NOT EXISTS idx_checklist_task_id ON checklist_items(task_id)')
    
    conn.commit()
    conn.close()

def calculate_recurring_dates(start_date_str, recurrence, end_date):
    """Calculate all recurring dates from start_date up to end_date"""
    if not start_date_str or not recurrence:
        return []
    
    try:
        start_date = datetime.fromisoformat(start_date_str.split('T')[0])
    except:
        # Handle date string format YYYY-MM-DD
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    
    dates = []
    current_date = start_date
    original_day = start_date.day  # Store the original day to always try it first
    
    while current_date <= end_date:
        dates.append(current_date.strftime('%Y-%m-%d'))
        
        if recurrence == 'daily':
            current_date += timedelta(days=1)
        elif recurrence == 'weekly':
            current_date += timedelta(weeks=1)
        elif recurrence == 'bi-weekly':
            current_date += timedelta(weeks=2)
        elif recurrence == 'monthly':
            # Add one month, always try original day first, fall back to last day if needed
            if current_date.month == 12:
                next_month = 1
                next_year = current_date.year + 1
            else:
                next_month = current_date.month + 1
                next_year = current_date.year
            
            # Always try the original day first (e.g., 31st)
            try:
                current_date = current_date.replace(year=next_year, month=next_month, day=original_day)
            except ValueError:
                # Day doesn't exist in target month, use last day of that month
                last_day = monthrange(next_year, next_month)[1]
                current_date = current_date.replace(year=next_year, month=next_month, day=last_day)
        elif recurrence == 'yearly':
            # For yearly, also handle Feb 29 -> Feb 28 in non-leap years
            try:
                current_date = current_date.replace(year=current_date.year + 1, day=original_day)
            except ValueError:
                # Leap year edge case: Feb 29 -> Feb 28 in non-leap year
                current_date = current_date.replace(year=current_date.year + 1, day=28)
        else:
            break
    
    return dates

def generate_recurring_instances(conn, parent_task_id, start_date_str, recurrence, time_str, 
                                user_id, created_by, visibility, assigned_to, end_date):
    """Generate recurring task instances from start_date up to end_date"""
    if not recurrence or not start_date_str:
        return
    
    # Get the parent task details
    parent_task = conn.execute('SELECT * FROM tasks WHERE id = ?', (parent_task_id,)).fetchone()
    if not parent_task:
        return
    
    dates = calculate_recurring_dates(start_date_str, recurrence, end_date)
    
    # Skip the first date (it's the original task)
    if len(dates) > 1:
        for date_str in dates[1:]:
            # Check if instance already exists for this date
            existing = conn.execute('''
                SELECT id FROM tasks 
                WHERE parent_task_id = ? AND date = ?
            ''', (parent_task_id, date_str)).fetchone()
            
            if not existing:
                conn.execute('''
                    INSERT INTO tasks (task, date, time, user_id, created_by, visibility, 
                                     assigned_to, recurrence, parent_task_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (parent_task['task'], date_str, time_str, user_id, created_by, 
                      visibility, assigned_to, recurrence, parent_task_id))

def ensure_recurring_instances_exist(conn, task_id, target_date_str=None):
    """Ensure recurring instances exist up to target_date (default: 1 year from now)"""
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task or not task['recurrence'] or not task['date']:
        return
    
    # If this is already an instance, get the parent
    parent_id = task['parent_task_id'] if task['parent_task_id'] else task_id
    parent_task = conn.execute('SELECT * FROM tasks WHERE id = ?', (parent_id,)).fetchone()
    if not parent_task:
        return
    
    # Determine end date
    if target_date_str:
        try:
            end_date = datetime.strptime(target_date_str, '%Y-%m-%d')
        except:
            end_date = datetime.now() + timedelta(days=365)
    else:
        end_date = datetime.now() + timedelta(days=365)
    
    # Check what's the latest instance date (including parent if it's later)
    latest_instance = conn.execute('''
        SELECT MAX(date) as max_date FROM tasks 
        WHERE (parent_task_id = ? OR id = ?) AND date IS NOT NULL
    ''', (parent_id, parent_id)).fetchone()
    
    latest_date = None
    if latest_instance and latest_instance['max_date']:
        latest_date = datetime.strptime(latest_instance['max_date'], '%Y-%m-%d')
    
    # If we need more instances, generate them
    if not latest_date or latest_date < end_date:
        parent_date = datetime.strptime(parent_task['date'], '%Y-%m-%d')
        recurrence = parent_task['recurrence']
        
        # Calculate the next occurrence date based on the recurrence pattern
        original_day = parent_date.day  # Always use the original day from parent task
        
        if latest_date:
            # Find the next occurrence after latest_date based on the pattern
            next_date = latest_date
            while next_date <= latest_date:
                if recurrence == 'daily':
                    next_date += timedelta(days=1)
                elif recurrence == 'weekly':
                    next_date += timedelta(weeks=1)
                elif recurrence == 'bi-weekly':
                    next_date += timedelta(weeks=2)
                elif recurrence == 'monthly':
                    # Add one month, always try original day first, fall back to last day if needed
                    if next_date.month == 12:
                        next_month = 1
                        next_year = next_date.year + 1
                    else:
                        next_month = next_date.month + 1
                        next_year = next_date.year
                    
                    # Always try the original day first (e.g., 31st)
                    try:
                        next_date = next_date.replace(year=next_year, month=next_month, day=original_day)
                    except ValueError:
                        # Day doesn't exist in target month, use last day of that month
                        last_day = monthrange(next_year, next_month)[1]
                        next_date = next_date.replace(year=next_year, month=next_month, day=last_day)
                elif recurrence == 'yearly':
                    # For yearly, also handle Feb 29 -> Feb 28 in non-leap years
                    try:
                        next_date = next_date.replace(year=next_date.year + 1, day=original_day)
                    except ValueError:
                        # Leap year edge case: Feb 29 -> Feb 28 in non-leap year
                        next_date = next_date.replace(year=next_date.year + 1, day=28)
                else:
                    break
            start_gen_date = next_date
        else:
            # First time generating - start from parent date
            start_gen_date = parent_date
        
        # Only generate if start date is before or equal to end date
        if start_gen_date <= end_date:
            # Use calculate_recurring_dates to get all dates from start_gen_date to end_date
            # This ensures we generate all months correctly
            dates = calculate_recurring_dates(start_gen_date.strftime('%Y-%m-%d'), recurrence, end_date)
            
            # Get existing instance dates to avoid duplicates
            existing_dates = set()
            existing = conn.execute('''
                SELECT date FROM tasks 
                WHERE parent_task_id = ? AND date IS NOT NULL
            ''', (parent_id,)).fetchall()
            for row in existing:
                existing_dates.add(row['date'])
            
            # Insert missing dates
            # Include all dates from calculate_recurring_dates, but skip if they already exist
            # Note: start_gen_date is the next date after latest_date, so we want to include it
            for date_str in dates:
                if date_str not in existing_dates:
                    conn.execute('''
                        INSERT INTO tasks (task, date, time, user_id, created_by, visibility, 
                                         assigned_to, recurrence, parent_task_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (parent_task['task'], date_str, 
                          parent_task['time'] if parent_task['time'] else None,
                          parent_task['user_id'], parent_task['created_by'],
                          parent_task['visibility'], parent_task['assigned_to'],
                          recurrence, parent_id))

def extend_recurring_instances_job():
    """Weekly job to extend recurring task instances that are expiring soon and clean up old instances"""
    conn = get_db()
    try:
        now = datetime.now()
        # Check for instances expiring in the next month
        one_month_ahead = now + timedelta(days=30)
        target_date = one_month_ahead.strftime('%Y-%m-%d')
        
        # Delete instances that are more than 3 months old
        three_months_ago = now - timedelta(days=90)
        three_months_ago_str = three_months_ago.strftime('%Y-%m-%d')
        
        deleted_count = conn.execute('''
            DELETE FROM tasks 
            WHERE parent_task_id IS NOT NULL 
            AND date IS NOT NULL 
            AND date < ?
        ''', (three_months_ago_str,)).rowcount
        
        # Find all parent recurring tasks
        parent_tasks = conn.execute('''
            SELECT DISTINCT id FROM tasks 
            WHERE recurrence IS NOT NULL AND parent_task_id IS NULL
        ''').fetchall()
        
        extended_count = 0
        for parent in parent_tasks:
            parent_id = parent['id']
            
            # Check the latest instance date
            latest_instance = conn.execute('''
                SELECT MAX(date) as max_date FROM tasks 
                WHERE (parent_task_id = ? OR id = ?) AND date IS NOT NULL
            ''', (parent_id, parent_id)).fetchone()
            
            if latest_instance and latest_instance['max_date']:
                latest_date = datetime.strptime(latest_instance['max_date'], '%Y-%m-%d')
                
                # If latest instance is within the next month, extend by another year
                if latest_date <= one_month_ahead:
                    # Extend to 1 year from now
                    extend_to_date = now + timedelta(days=365)
                    ensure_recurring_instances_exist(conn, parent_id, extend_to_date.strftime('%Y-%m-%d'))
                    extended_count += 1
        
        conn.commit()
        print(f"[Weekly Job] Deleted {deleted_count} old instance(s) (>3 months), extended {extended_count} recurring task(s) that were expiring soon")
    except Exception as e:
        print(f"[Weekly Job] Error in weekly job: {e}")
        conn.rollback()
    finally:
        conn.close()

def cleanup_old_completed_tasks():
    """Remove completed tasks older than 1 month"""
    conn = get_db()
    one_month_ago = (datetime.now() - timedelta(days=30)).isoformat()
    conn.execute('''
        DELETE FROM tasks 
        WHERE completed = 1 AND completed_at < ?
    ''', (one_month_ago,))
    # Also clean up old completion requests
    conn.execute('''
        DELETE FROM task_completion_requests 
        WHERE status != 'pending' AND requested_at < ?
    ''', (one_month_ago,))
    conn.commit()
    conn.close()

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        conn = get_db()
        user = conn.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()
        if not user or not user['is_admin']:
            return jsonify({'error': 'Admin privileges required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def can_edit_tasks():
    """Check if current user can edit/delete tasks"""
    if 'user_id' not in session:
        return False
    conn = get_db()
    user = conn.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return user and user['is_admin'] == 1

@app.route('/')
def index():
    """Main page - redirect to login if not authenticated"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    cleanup_old_completed_tasks()
    return render_template('index.html')

@app.route('/login')
def login():
    """Login page"""
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register')
def register():
    """Register page"""
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """Login API endpoint"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['is_admin'] = bool(user['is_admin'])
    session.permanent = True
    
    return jsonify({
        'message': 'Login successful',
        'user': {
            'id': user['id'],
            'username': user['username'],
            'is_admin': bool(user['is_admin'])
        }
    })

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """Register API endpoint"""
    # Ensure database is initialized
    init_db()
    
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    conn = get_db()
    
    # Check if username already exists in users
    existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    if existing_user:
        conn.close()
        return jsonify({'error': 'Username already exists'}), 400
    
    # Check if username already exists in account_requests
    existing_request = conn.execute('SELECT id FROM account_requests WHERE username = ?', (username,)).fetchone()
    if existing_request:
        conn.close()
        return jsonify({'error': 'Account request already pending'}), 400
    
    # Check if there are any users
    try:
        user_count = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
    except Exception as e:
        conn.close()
        app.logger.error(f'Error checking user count: {e}')
        return jsonify({'error': 'Database error occurred'}), 500
    
    password_hash = generate_password_hash(password)
    
    if user_count == 0:
        # First user is automatically an admin
        try:
            conn.execute('''
                INSERT INTO users (username, password_hash, is_admin)
                VALUES (?, ?, 1)
            ''', (username, password_hash))
            conn.commit()
            user_id = conn.lastrowid
            conn.close()
        except Exception as e:
            # Even if there's an exception, check if user was actually created
            # (sometimes exceptions occur but the insert still succeeds)
            try:
                user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
                conn.close()
                if user:
                    # User was created successfully, use that ID
                    user_id = user['id']
                else:
                    # User was not created, return error
                    app.logger.error(f'Error creating first admin user: {e}')
                    return jsonify({'error': f'Failed to create admin account: {str(e)}'}), 500
            except Exception as e2:
                conn.close()
                app.logger.error(f'Error creating first admin user: {e}, {e2}')
                return jsonify({'error': 'Failed to create admin account'}), 500
        
        # Verify we have a user_id, if not fetch it
        if not user_id:
            conn = get_db()
            user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
            conn.close()
            if user:
                user_id = user['id']
            else:
                return jsonify({'error': 'Account creation failed. Please try again.'}), 500
        
        # Auto-login the first admin user
        try:
            session['user_id'] = user_id
            session['username'] = username
            session['is_admin'] = True
            session.permanent = True
            # Explicitly mark session as modified
            session.modified = True
        except Exception as e:
            app.logger.error(f'Error setting session: {e}')
            # Account was created, so return success but warn about login
            return jsonify({
                'message': 'Admin account created successfully',
                'warning': 'Account created but session setup failed. Please log in manually.',
                'user': {
                    'id': user_id,
                    'username': username,
                    'is_admin': True
                }
            }), 201
        
        return jsonify({
            'message': 'Admin account created successfully',
            'user': {
                'id': user_id,
                'username': username,
                'is_admin': True
            }
        }), 201
    else:
        # Add to account_requests for admin approval
        conn.execute('''
            INSERT INTO account_requests (username, password_hash)
            VALUES (?, ?)
        ''', (username, password_hash))
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Account request submitted. Waiting for admin approval.'
        }), 201

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """Logout API endpoint"""
    session.clear()
    return jsonify({'message': 'Logout successful'})

@app.route('/api/auth/status', methods=['GET'])
def api_auth_status():
    """Get current authentication status"""
    if 'user_id' not in session:
        return jsonify({'authenticated': False}), 200
    
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
    if not user:
        session.clear()
        return jsonify({'authenticated': False}), 200
    
    return jsonify({
        'authenticated': True,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'is_admin': bool(user['is_admin'])
        }
    })

@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    data = request.json
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    target_user_id = data.get('target_user_id')  # For admin changing another user's password
    
    if not new_password:
        return jsonify({'error': 'New password is required'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400
    
    conn = get_db()
    admin_id = session['user_id']
    is_admin = session.get('is_admin', False)
    
    # Determine which user's password to change
    if target_user_id and is_admin:
        # Admin changing another user's password
        if not current_password:
            return jsonify({'error': 'Admin password is required'}), 400
        
        # Verify admin's password
        admin = conn.execute('SELECT * FROM users WHERE id = ?', (admin_id,)).fetchone()
        if not admin:
            conn.close()
            return jsonify({'error': 'Admin not found'}), 404
        
        if not check_password_hash(admin['password_hash'], current_password):
            conn.close()
            return jsonify({'error': 'Admin password is incorrect'}), 401
        
        # Get target user
        target_user = conn.execute('SELECT * FROM users WHERE id = ?', (target_user_id,)).fetchone()
        if not target_user:
            conn.close()
            return jsonify({'error': 'Target user not found'}), 404
        
        # Update target user's password
        new_password_hash = generate_password_hash(new_password)
        conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_password_hash, target_user_id))
        conn.commit()
        conn.close()
        
        return jsonify({'message': f"Password changed successfully for user '{target_user['username']}'"})
    else:
        # User changing their own password
        if not current_password:
            return jsonify({'error': 'Current password is required'}), 400
        
        user = conn.execute('SELECT * FROM users WHERE id = ?', (admin_id,)).fetchone()
        if not user:
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        # Verify current password
        if not check_password_hash(user['password_hash'], current_password):
            conn.close()
            return jsonify({'error': 'Current password is incorrect'}), 401
        
        # Update password
        new_password_hash = generate_password_hash(new_password)
        conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_password_hash, admin_id))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Password changed successfully'})

@app.route('/api/account-requests', methods=['GET'])
@login_required
@admin_required
def get_account_requests():
    """Get pending account requests (admin only)"""
    conn = get_db()
    requests = conn.execute('''
        SELECT * FROM account_requests 
        ORDER BY requested_at DESC
    ''').fetchall()
    conn.close()
    
    return jsonify([dict(req) for req in requests])

@app.route('/api/task-completion-requests', methods=['GET'])
@login_required
@admin_required
def get_task_completion_requests():
    """Get pending task completion requests (admin only)"""
    conn = get_db()
    requests = conn.execute('''
        SELECT tcr.*, t.task, t.date, t.time, u.username as requester_username
        FROM task_completion_requests tcr
        JOIN tasks t ON tcr.task_id = t.id
        JOIN users u ON tcr.requested_by = u.id
        WHERE tcr.status = 'pending'
        ORDER BY tcr.requested_at DESC
    ''').fetchall()
    conn.close()
    
    return jsonify([dict(req) for req in requests])

@app.route('/api/task-completion-requests', methods=['POST'])
@login_required
def create_task_completion_request():
    """Create a task completion request (regular users)"""
    data = request.json
    task_id = data.get('task_id')
    
    if not task_id:
        return jsonify({'error': 'Task ID is required'}), 400
    
    conn = get_db()
    user_id = session['user_id']
    
    # Check if task exists and user can see it
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    
    # Check if task is already completed
    if task['completed'] == 1:
        conn.close()
        return jsonify({'error': 'Task is already completed'}), 400
    
    # Check if there's already a pending request for this task
    existing_request = conn.execute('''
        SELECT * FROM task_completion_requests 
        WHERE task_id = ? AND status = 'pending'
    ''', (task_id,)).fetchone()
    
    if existing_request:
        conn.close()
        return jsonify({'error': 'A completion request for this task is already pending'}), 400
    
    # Create the request
    conn.execute('''
        INSERT INTO task_completion_requests (task_id, requested_by, status)
        VALUES (?, ?, 'pending')
    ''', (task_id, user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Completion request submitted. Waiting for admin approval.'}), 201

@app.route('/api/task-completion-requests/<int:request_id>', methods=['POST'])
@login_required
@admin_required
def handle_task_completion_request(request_id):
    """Approve or reject task completion request (admin only)"""
    data = request.json
    action = data.get('action')  # 'approve' or 'reject'
    
    if action not in ['approve', 'reject']:
        return jsonify({'error': 'Invalid action'}), 400
    
    conn = get_db()
    req = conn.execute('SELECT * FROM task_completion_requests WHERE id = ?', (request_id,)).fetchone()
    
    if not req:
        conn.close()
        return jsonify({'error': 'Request not found'}), 404
    
    if req['status'] != 'pending':
        conn.close()
        return jsonify({'error': 'Request is not pending'}), 400
    
    if action == 'reject':
        conn.execute('UPDATE task_completion_requests SET status = ? WHERE id = ?', ('rejected', request_id))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Request rejected'})
    
    # Approve: mark task as complete
    completed_at = datetime.now().isoformat()
    conn.execute('''
        UPDATE tasks 
        SET completed = 1, completed_at = ?
        WHERE id = ?
    ''', (completed_at, req['task_id']))
    
    conn.execute('UPDATE task_completion_requests SET status = ? WHERE id = ?', ('approved', request_id))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Task marked as complete'})

@app.route('/api/account-requests/<int:request_id>', methods=['POST'])
@login_required
@admin_required
def handle_account_request(request_id):
    """Approve or reject account request (admin only)"""
    data = request.json
    action = data.get('action')  # 'approve_admin', 'approve_user', or 'reject'
    
    if action not in ['approve_admin', 'approve_user', 'reject']:
        return jsonify({'error': 'Invalid action'}), 400
    
    conn = get_db()
    req = conn.execute('SELECT * FROM account_requests WHERE id = ?', (request_id,)).fetchone()
    
    if not req:
        conn.close()
        return jsonify({'error': 'Request not found'}), 404
    
    if action == 'reject':
        conn.execute('DELETE FROM account_requests WHERE id = ?', (request_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Request rejected'})
    
    # Approve the account
    is_admin = 1 if action == 'approve_admin' else 0
    conn.execute('''
        INSERT INTO users (username, password_hash, is_admin)
        VALUES (?, ?, ?)
    ''', (req['username'], req['password_hash'], is_admin))
    
    # Delete the request
    conn.execute('DELETE FROM account_requests WHERE id = ?', (request_id,))
    conn.commit()
    conn.close()
    
    return jsonify({
        'message': f'Account approved as {"admin" if is_admin else "regular user"}'
    })

@app.route('/api/users', methods=['GET'])
@login_required
@admin_required
def get_users():
    """Get all users (admin only)"""
    conn = get_db()
    users = conn.execute('''
        SELECT id, username, is_admin, created_at
        FROM users
        ORDER BY created_at DESC
    ''').fetchall()
    conn.close()
    
    return jsonify([dict(user) for user in users])

@app.route('/api/users/non-admin', methods=['GET'])
@login_required
@admin_required
def get_non_admin_users():
    """Get all users for task assignment (admin only) - includes both admins and non-admins"""
    conn = get_db()
    current_user_id = session['user_id']
    users = conn.execute('''
        SELECT id, username, is_admin
        FROM users
        ORDER BY is_admin DESC, username ASC
    ''').fetchall()
    conn.close()
    
    return jsonify([dict(user) for user in users])

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
@admin_required
def update_user(user_id):
    """Update user (admin only) - change role or delete"""
    data = request.json
    action = data.get('action')  # 'change_role' or 'delete'
    
    if action not in ['change_role', 'delete']:
        return jsonify({'error': 'Invalid action'}), 400
    
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    
    # Prevent admin from deleting themselves
    if action == 'delete' and user_id == session['user_id']:
        conn.close()
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    if action == 'delete':
        # Delete user's tasks first
        conn.execute('DELETE FROM tasks WHERE user_id = ?', (user_id,))
        # Delete user
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'User deleted successfully'})
    
    if action == 'change_role':
        new_role = data.get('is_admin')
        if new_role is None:
            conn.close()
            return jsonify({'error': 'is_admin field required'}), 400
        
        # Prevent admin from removing their own admin status
        if user_id == session['user_id'] and new_role == 0:
            conn.close()
            return jsonify({'error': 'Cannot remove your own admin privileges'}), 400
        
        conn.execute('UPDATE users SET is_admin = ? WHERE id = ?', (1 if new_role else 0, user_id))
        conn.commit()
        conn.close()
        return jsonify({'message': 'User role updated successfully'})

@app.route('/api/tasks', methods=['GET'])
@login_required
def get_tasks():
    """Get all tasks visible to the current user"""
    conn = get_db()
    show_completed = request.args.get('completed', 'false').lower() == 'true'
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)
    
    # Ensure recurring instances exist for all parent tasks (up to 1 year ahead)
    parent_tasks = conn.execute('''
        SELECT DISTINCT id FROM tasks 
        WHERE recurrence IS NOT NULL AND parent_task_id IS NULL
    ''').fetchall()
    for parent in parent_tasks:
        ensure_recurring_instances_exist(conn, parent['id'])
    conn.commit()
    
    # Build visibility filter
    if is_admin:
        # Admins see: 
        # - Tasks with visibility='all' and not assigned (assigned to all users)
        # - Tasks with visibility='admins' and not assigned (assigned to all admins)
        # - Tasks assigned to non-admins
        # - Tasks assigned to admins that are NOT private (visibility != 'private')
        # - Their own private tasks (visibility='private' AND created_by = user_id)
        # - All tasks created by regular users (to ensure admin oversight)
        visibility_filter = '''
            ((visibility = 'all' AND assigned_to IS NULL) OR
             (visibility = 'admins' AND assigned_to IS NULL) OR
             (assigned_to IS NOT NULL AND assigned_to IN (SELECT id FROM users WHERE is_admin = 0)) OR
             (assigned_to IS NOT NULL AND assigned_to IN (SELECT id FROM users WHERE is_admin = 1) AND visibility != 'private') OR
             (visibility = 'private' AND created_by = ?) OR
             (created_by IN (SELECT id FROM users WHERE is_admin = 0)))
        '''
        params = (user_id,)
    else:
        # Regular users see: 
        # - Tasks with visibility='all' that are not assigned to anyone (global tasks, typically created by admins)
        # - Tasks assigned to them
        # - Tasks they created (their own tasks)
        # They should NOT see tasks created by other non-admins unless assigned to them
        # Note: Tasks created by non-admins should have assigned_to = created_by, so they won't match the first condition
        visibility_filter = '''
            ((visibility = 'all' AND assigned_to IS NULL AND created_by IN (SELECT id FROM users WHERE is_admin = 1)) OR 
             assigned_to = ? OR 
             (created_by = ? AND visibility != 'admins'))
        '''
        params = (user_id, user_id)
    
    if show_completed:
        query = f'''
            SELECT t.*, u.username as creator_username, u2.username as assigned_to_username,
                   CASE WHEN EXISTS (
                       SELECT 1 FROM task_completion_requests tcr 
                       WHERE tcr.task_id = t.id AND tcr.status = 'pending'
                   ) THEN 1 ELSE 0 END as has_pending_request
            FROM tasks t
            LEFT JOIN users u ON t.created_by = u.id
            LEFT JOIN users u2 ON t.assigned_to = u2.id
            WHERE completed = 1 AND ({visibility_filter}) AND (t.parent_task_id IS NULL)
            ORDER BY completed_at DESC
        '''
        tasks = conn.execute(query, params).fetchall()
    else:
        query = f'''
            SELECT t.*, u.username as creator_username, u2.username as assigned_to_username,
                   CASE WHEN EXISTS (
                       SELECT 1 FROM task_completion_requests tcr 
                       WHERE tcr.task_id = t.id AND tcr.status = 'pending'
                   ) THEN 1 ELSE 0 END as has_pending_request
            FROM tasks t
            LEFT JOIN users u ON t.created_by = u.id
            LEFT JOIN users u2 ON t.assigned_to = u2.id
            WHERE completed = 0 AND ({visibility_filter}) AND (t.parent_task_id IS NULL)
            ORDER BY date ASC, time ASC, created_at ASC
        '''
        tasks = conn.execute(query, params).fetchall()
    
    conn.close()
    return jsonify([dict(task) for task in tasks])

@app.route('/api/tasks', methods=['POST'])
@login_required
def create_task():
    """Create a new task"""
    data = request.json
    conn = get_db()
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)
    created_by = user_id
    
    # Handle assignment/visibility
    assigned_to = data.get('assigned_to', None)
    visibility = data.get('visibility', 'all')
    
    if not is_admin:
        # Non-admin users: no assignment dropdown, task visible only to them and admins
        # Assign task to the user so only they and admins can see it
        visibility = 'all'
        assigned_to = user_id
    else:
        # Admin users: can assign to specific users or use visibility options
        if assigned_to:
            # If assigned to a user, validate the user exists
            assigned_user = conn.execute('SELECT id, is_admin FROM users WHERE id = ?', (assigned_to,)).fetchone()
            if not assigned_user:
                conn.close()
                return jsonify({'error': 'Assigned user not found'}), 400
            # If assigned to an admin, use 'admins' visibility unless it's private
            if assigned_user['is_admin']:
                if visibility == 'private':
                    visibility = 'private'
                else:
                    visibility = 'admins'
            else:
                visibility = 'all'  # When assigned to non-admin, use 'all' visibility
        else:
            # Validate visibility for admins
            if visibility not in ['all', 'admins', 'private']:
                visibility = 'all'
            assigned_to = None
    
    recurrence = data.get('recurrence', None)
    if recurrence and recurrence not in ['weekly', 'bi-weekly', 'monthly', 'yearly']:
        recurrence = None
    
    # Validate: recurring tasks must have a date
    if recurrence and not data.get('date'):
        conn.close()
        return jsonify({'error': 'Recurring tasks require a start date.'}), 400
    
    cursor = conn.execute('''
        INSERT INTO tasks (task, date, time, user_id, created_by, visibility, assigned_to, recurrence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (data['task'], data.get('date'), data.get('time'), user_id, created_by, visibility, assigned_to, recurrence))
    
    conn.commit()
    task_id = cursor.lastrowid
    
    # Fallback: if lastrowid is not available, query for the task ID
    if not task_id:
        task = conn.execute('''
            SELECT id FROM tasks 
            WHERE task = ? AND user_id = ? AND created_by = ? 
            ORDER BY id DESC LIMIT 1
        ''', (data['task'], user_id, created_by)).fetchone()
        if task:
            task_id = task['id']
    
    # Generate recurring instances if recurrence is set and date exists
    if recurrence and data.get('date'):
        end_date = datetime.now() + timedelta(days=365)  # 1 year ahead
        generate_recurring_instances(conn, task_id, data['date'], recurrence, data.get('time'),
                                   user_id, created_by, visibility, assigned_to, end_date)
        conn.commit()
    
    conn.close()
    
    if not task_id:
        return jsonify({'error': 'Failed to create task'}), 500
    
    return jsonify({'id': task_id, 'message': 'Task created successfully'}), 201

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
@login_required
def update_task(task_id):
    """Update a task - only admins can edit"""
    if not can_edit_tasks():
        return jsonify({'error': 'Permission denied. Only admins can edit tasks.'}), 403
    
    data = request.json
    conn = get_db()
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)
    
    # Get task with visibility check
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    
    # Check if user can edit this task
    can_edit = False
    if is_admin:
        # Admins can edit: all tasks, admin-only tasks, and their own private tasks
        if task['visibility'] in ['all', 'admins'] or (task['visibility'] == 'private' and task['user_id'] == user_id):
            can_edit = True
    else:
        # Regular users can only edit their own tasks with visibility 'all'
        if task['user_id'] == user_id and task['visibility'] == 'all':
            can_edit = True
    
    if not can_edit:
        conn.close()
        return jsonify({'error': 'Permission denied. You cannot edit this task.'}), 403
    
    if 'completed' in data:
        # Mark as complete/incomplete
        completed = data['completed']
        completed_at = datetime.now().isoformat() if completed else None
        conn.execute('''
            UPDATE tasks 
            SET completed = ?, completed_at = ?
            WHERE id = ?
        ''', (1 if completed else 0, completed_at, task_id))
    else:
        # Update task details
        # sqlite3.Row doesn't have .get(), use dictionary access instead
        assigned_to = data.get('assigned_to', task['assigned_to'])
        visibility = data.get('visibility', task['visibility'])
        
        if not is_admin:
            # Regular users can't change assignment or visibility
            visibility = task['visibility']
            assigned_to = task['assigned_to']
        else:
            # Admin users can change assignment or visibility
            if assigned_to:
                # If assigned to a user, validate the user exists
                assigned_user = conn.execute('SELECT id, is_admin FROM users WHERE id = ?', (assigned_to,)).fetchone()
                if not assigned_user:
                    conn.close()
                    return jsonify({'error': 'Assigned user not found'}), 400
                # If assigned to an admin, use 'admins' visibility unless it's private
                if assigned_user['is_admin']:
                    if visibility == 'private':
                        visibility = 'private'
                    else:
                        visibility = 'admins'
                else:
                    visibility = 'all'  # When assigned to non-admin, use 'all' visibility
            else:
                # Validate visibility for admins
                if visibility not in ['all', 'admins', 'private']:
                    visibility = task['visibility']
                assigned_to = None
        
        recurrence = data.get('recurrence', task['recurrence'] if task['recurrence'] else None)
        if recurrence and recurrence not in ['weekly', 'bi-weekly', 'monthly', 'yearly']:
            recurrence = None
        if recurrence == '':
            recurrence = None
        
        # Determine if this is a parent task or an instance
        parent_id = task['parent_task_id'] if task['parent_task_id'] else task_id
        is_parent = (parent_id == task_id)
        
        # Get parent task to check its current values
        parent_task = conn.execute('SELECT * FROM tasks WHERE id = ?', (parent_id,)).fetchone()
        if not parent_task:
            conn.close()
            return jsonify({'error': 'Parent task not found'}), 404
        
        # Get the new values
        new_task_name = data.get('task', task['task'])
        new_date = data.get('date', task['date'])
        new_time = data.get('time', task['time'])
        
        # Validate: recurring tasks must have a date
        if recurrence and not new_date:
            conn.close()
            return jsonify({'error': 'Recurring tasks require a start date.'}), 400
        
        # If updating an instance, update the parent and all instances
        if not is_parent:
            # Update parent task with new values
            old_recurrence = parent_task['recurrence'] if parent_task['recurrence'] else None
            
            # Update parent's task name, time, visibility, assigned_to
            conn.execute('''
                UPDATE tasks 
                SET task = ?, time = ?, visibility = ?, assigned_to = ?
                WHERE id = ?
            ''', (new_task_name, new_time, visibility, assigned_to, parent_id))
            
            # If recurrence changed, update parent's recurrence and regenerate instances
            if recurrence != old_recurrence:
                # Update parent's recurrence (keep parent's original date)
                conn.execute('''
                    UPDATE tasks 
                    SET recurrence = ?
                    WHERE id = ?
                ''', (recurrence, parent_id))
                
                # Delete all future instances
                conn.execute('''
                    DELETE FROM tasks 
                    WHERE parent_task_id = ? AND date > ?
                ''', (parent_id, datetime.now().strftime('%Y-%m-%d')))
                
                # Regenerate instances if recurrence is set
                parent_date = parent_task['date'] if parent_task['date'] else None
                if recurrence and parent_date:
                    end_date = datetime.now() + timedelta(days=365)
                    generate_recurring_instances(conn, parent_id, parent_date, recurrence, 
                                               new_time,
                                               parent_task['user_id'], parent_task['created_by'],
                                               visibility, assigned_to, end_date)
            
            # Update all instances with new task name, time, visibility, assigned_to
            # (date is per-instance, recurrence is handled above)
            conn.execute('''
                UPDATE tasks 
                SET task = ?, time = ?, visibility = ?, assigned_to = ?
                WHERE parent_task_id = ?
            ''', (new_task_name, new_time, visibility, assigned_to, parent_id))
            
            # Update this specific instance's date (if changed)
            conn.execute('''
                UPDATE tasks 
                SET date = ?
                WHERE id = ?
            ''', (new_date, task_id))
        else:
            # Updating the parent task
            old_recurrence = task['recurrence'] if task['recurrence'] else None
            old_date = task['date'] if task['date'] else None
            
            # Check if recurrence or date changed
            if (recurrence != old_recurrence) or (new_date != old_date and recurrence):
                # Delete all future instances
                conn.execute('''
                    DELETE FROM tasks 
                    WHERE parent_task_id = ? AND date > ?
                ''', (parent_id, datetime.now().strftime('%Y-%m-%d')))
                
                # Regenerate instances if recurrence is set
                if recurrence and new_date:
                    end_date = datetime.now() + timedelta(days=365)
                    generate_recurring_instances(conn, parent_id, new_date, recurrence, 
                                               new_time,
                                               task['user_id'], task['created_by'],
                                               visibility, assigned_to, end_date)
            
            # Update parent task
            conn.execute('''
                UPDATE tasks 
                SET task = ?, date = ?, time = ?, visibility = ?, assigned_to = ?, recurrence = ?
                WHERE id = ?
            ''', (new_task_name, new_date, new_time, visibility, assigned_to, recurrence, task_id))
            
            # Update all instances with new task name, time, visibility, assigned_to
            # (date and recurrence are handled per-instance, so don't update those)
            conn.execute('''
                UPDATE tasks 
                SET task = ?, time = ?, visibility = ?, assigned_to = ?
                WHERE parent_task_id = ?
            ''', (new_task_name, new_time, visibility, assigned_to, parent_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Task updated successfully'})

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    """Delete a task - only admins can delete"""
    if not can_edit_tasks():
        return jsonify({'error': 'Permission denied. Only admins can delete tasks.'}), 403
    
    # Get delete_all parameter from query string
    delete_all = request.args.get('delete_all', 'false').lower() == 'true'
    
    conn = get_db()
    
    # Verify task exists
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    
    # Determine if this is a parent task or an instance
    is_parent = (task['parent_task_id'] is None or task['parent_task_id'] == 0)
    parent_id = task['parent_task_id'] if task['parent_task_id'] else task_id
    
    if delete_all:
        # Delete all instances of this recurring task (including parent)
        if is_parent:
            # Delete all instances first, then parent
            conn.execute('DELETE FROM tasks WHERE parent_task_id = ?', (task_id,))
            conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        else:
            # Delete parent and all instances
            conn.execute('DELETE FROM tasks WHERE parent_task_id = ? OR id = ?', (parent_id, parent_id))
    else:
        # Delete only this instance
        if is_parent:
            # If deleting parent without instances, just delete it
            # But if it has instances, we need to delete them too (can't have orphaned instances)
            instance_count = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE parent_task_id = ?', (task_id,)).fetchone()['count']
            if instance_count > 0:
                # Has instances - delete them too
                conn.execute('DELETE FROM tasks WHERE parent_task_id = ?', (task_id,))
        conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Task deleted successfully'})

@app.route('/api/tasks/dates', methods=['GET'])
@login_required
def get_task_dates():
    """Get all dates that have tasks (including recurring instances) for calendar indicators"""
    conn = get_db()
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)
    
    # Get optional month/year parameters to determine date range
    month = request.args.get('month')  # 0-11 (JavaScript month format)
    year = request.args.get('year')
    
    # Calculate end date for instance generation
    if month is not None and year is not None:
        try:
            month_num = int(month)
            year_num = int(year)
            # Get last day of the requested month
            last_day = monthrange(year_num, month_num + 1)[1]
            target_end_date = datetime(year_num, month_num + 1, last_day)
        except:
            target_end_date = datetime.now() + timedelta(days=365)
    else:
        # Default to 1 year ahead, but also check what dates we're actually querying
        target_end_date = datetime.now() + timedelta(days=365)
    
    # Ensure recurring instances exist for all parent tasks up to target date
    parent_tasks = conn.execute('''
        SELECT DISTINCT id FROM tasks 
        WHERE recurrence IS NOT NULL AND parent_task_id IS NULL
    ''').fetchall()
    for parent in parent_tasks:
        ensure_recurring_instances_exist(conn, parent['id'], target_end_date.strftime('%Y-%m-%d'))
    conn.commit()
    
    # Build visibility filter (same as get_tasks)
    if is_admin:
        visibility_filter = '''
            ((visibility = 'all' AND assigned_to IS NULL) OR
             (visibility = 'admins' AND assigned_to IS NULL) OR
             (assigned_to IS NOT NULL AND assigned_to IN (SELECT id FROM users WHERE is_admin = 0)) OR
             (assigned_to IS NOT NULL AND assigned_to IN (SELECT id FROM users WHERE is_admin = 1) AND visibility != 'private') OR
             (visibility = 'private' AND created_by = ?) OR
             (created_by IN (SELECT id FROM users WHERE is_admin = 0)))
        '''
        params = (user_id,)
    else:
        visibility_filter = '''
            ((visibility = 'all' AND assigned_to IS NULL AND created_by IN (SELECT id FROM users WHERE is_admin = 1)) OR 
             assigned_to = ? OR 
             (created_by = ? AND visibility != 'admins'))
        '''
        params = (user_id, user_id)
    
    # Get all dates from tasks (including instances) that match visibility and are not completed
    dates = conn.execute(f'''
        SELECT DISTINCT date
        FROM tasks t
        WHERE date IS NOT NULL 
          AND completed = 0 
          AND ({visibility_filter})
        ORDER BY date ASC
    ''', params).fetchall()
    
    conn.close()
    
    # Return just the date strings
    date_list = [row['date'] for row in dates]
    return jsonify(date_list)

@app.route('/api/tasks/date/<date>', methods=['GET'])
@login_required
def get_tasks_by_date(date):
    """Get tasks for a specific date"""
    conn = get_db()
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)
    
    # Ensure recurring instances exist up to the requested date
    # This ensures that if a user clicks on a date in the future, instances are generated
    parent_tasks = conn.execute('''
        SELECT DISTINCT id FROM tasks 
        WHERE recurrence IS NOT NULL AND parent_task_id IS NULL
    ''').fetchall()
    for parent in parent_tasks:
        ensure_recurring_instances_exist(conn, parent['id'], date)
    conn.commit()
    
    # Build visibility filter
    if is_admin:
        # Admins see: 
        # - Tasks with visibility='all' and not assigned (assigned to all users)
        # - Tasks with visibility='admins' and not assigned (assigned to all admins)
        # - Tasks assigned to non-admins
        # - Tasks assigned to admins that are NOT private (visibility != 'private')
        # - Their own private tasks (visibility='private' AND created_by = user_id)
        # - All tasks created by regular users (to ensure admin oversight)
        visibility_filter = '''
            ((visibility = 'all' AND assigned_to IS NULL) OR
             (visibility = 'admins' AND assigned_to IS NULL) OR
             (assigned_to IS NOT NULL AND assigned_to IN (SELECT id FROM users WHERE is_admin = 0)) OR
             (assigned_to IS NOT NULL AND assigned_to IN (SELECT id FROM users WHERE is_admin = 1) AND visibility != 'private') OR
             (visibility = 'private' AND created_by = ?) OR
             (created_by IN (SELECT id FROM users WHERE is_admin = 0)))
        '''
        params = (date, user_id)
    else:
        # Regular users see: 
        # - Tasks with visibility='all' that are not assigned to anyone (global tasks, typically created by admins)
        # - Tasks assigned to them
        # - Tasks they created (their own tasks)
        # They should NOT see tasks created by other non-admins unless assigned to them
        # Note: Tasks created by non-admins should have assigned_to = created_by, so they won't match the first condition
        visibility_filter = '''
            ((visibility = 'all' AND assigned_to IS NULL AND created_by IN (SELECT id FROM users WHERE is_admin = 1)) OR 
             assigned_to = ? OR 
             (created_by = ? AND visibility != 'admins'))
        '''
        params = (date, user_id, user_id)
    
    tasks = conn.execute(f'''
        SELECT t.*, u.username as creator_username, u2.username as assigned_to_username,
               CASE WHEN EXISTS (
                   SELECT 1 FROM task_completion_requests tcr 
                   WHERE tcr.task_id = t.id AND tcr.status = 'pending'
               ) THEN 1 ELSE 0 END as has_pending_request
        FROM tasks t
        LEFT JOIN users u ON t.created_by = u.id
        LEFT JOIN users u2 ON t.assigned_to = u2.id
        WHERE date = ? AND completed = 0 AND ({visibility_filter})
        ORDER BY time ASC, created_at ASC
    ''', params).fetchall()
    conn.close()
    
    return jsonify([dict(task) for task in tasks])

@app.route('/api/tasks/<int:task_id>/checklist', methods=['GET'])
@login_required
def get_checklist_items(task_id):
    """Get all checklist items for a task"""
    conn = get_db()
    
    # Verify task exists and user can access it
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    
    # Check visibility (simplified - using same logic as get_tasks)
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)
    
    can_access = False
    if is_admin:
        can_access = True
    else:
        # Regular users can see if task is assigned to them or created by them
        if task['assigned_to'] == user_id or task['created_by'] == user_id:
            can_access = True
        elif task['visibility'] == 'all' and task['assigned_to'] is None:
            can_access = True
    
    if not can_access:
        conn.close()
        return jsonify({'error': 'Permission denied'}), 403
    
    items = conn.execute('''
        SELECT * FROM checklist_items 
        WHERE task_id = ? 
        ORDER BY created_at ASC
    ''', (task_id,)).fetchall()
    
    conn.close()
    return jsonify([dict(item) for item in items])

@app.route('/api/tasks/<int:task_id>/checklist', methods=['POST'])
@login_required
def create_checklist_item(task_id):
    """Create a new checklist item"""
    data = request.json
    item_text = data.get('item_text', '').strip()
    
    if not item_text:
        return jsonify({'error': 'Item text is required'}), 400
    
    conn = get_db()
    
    # Verify task exists and user can access it
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    
    # Check permissions (same as get_checklist_items)
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)
    
    can_access = False
    if is_admin:
        can_access = True
    else:
        if task['assigned_to'] == user_id or task['created_by'] == user_id:
            can_access = True
        elif task['visibility'] == 'all' and task['assigned_to'] is None:
            can_access = True
    
    if not can_access:
        conn.close()
        return jsonify({'error': 'Permission denied'}), 403
    
    cursor = conn.execute('''
        INSERT INTO checklist_items (task_id, item_text)
        VALUES (?, ?)
    ''', (task_id, item_text))
    
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()
    
    return jsonify({'id': item_id, 'message': 'Checklist item created successfully'}), 201

@app.route('/api/checklist-items/<int:item_id>', methods=['PUT'])
@login_required
def update_checklist_item(item_id):
    """Update a checklist item (text or completed status)"""
    data = request.json
    conn = get_db()
    
    # Get the item and its task
    item = conn.execute('SELECT * FROM checklist_items WHERE id = ?', (item_id,)).fetchone()
    if not item:
        conn.close()
        return jsonify({'error': 'Checklist item not found'}), 404
    
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (item['task_id'],)).fetchone()
    if not task:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    
    # Check permissions
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)
    
    can_access = False
    if is_admin:
        can_access = True
    else:
        if task['assigned_to'] == user_id or task['created_by'] == user_id:
            can_access = True
        elif task['visibility'] == 'all' and task['assigned_to'] is None:
            can_access = True
    
    if not can_access:
        conn.close()
        return jsonify({'error': 'Permission denied'}), 403
    
    # Update item
    if 'item_text' in data:
        item_text = data['item_text'].strip()
        if not item_text:
            conn.close()
            return jsonify({'error': 'Item text cannot be empty'}), 400
        conn.execute('UPDATE checklist_items SET item_text = ? WHERE id = ?', (item_text, item_id))
    
    if 'completed' in data:
        completed = 1 if data['completed'] else 0
        conn.execute('UPDATE checklist_items SET completed = ? WHERE id = ?', (completed, item_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Checklist item updated successfully'})

@app.route('/api/checklist-items/<int:item_id>', methods=['DELETE'])
@login_required
def delete_checklist_item(item_id):
    """Delete a checklist item"""
    conn = get_db()
    
    # Get the item and its task
    item = conn.execute('SELECT * FROM checklist_items WHERE id = ?', (item_id,)).fetchone()
    if not item:
        conn.close()
        return jsonify({'error': 'Checklist item not found'}), 404
    
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (item['task_id'],)).fetchone()
    if not task:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    
    # Check permissions
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)
    
    can_access = False
    if is_admin:
        can_access = True
    else:
        if task['assigned_to'] == user_id or task['created_by'] == user_id:
            can_access = True
        elif task['visibility'] == 'all' and task['assigned_to'] is None:
            can_access = True
    
    if not can_access:
        conn.close()
        return jsonify({'error': 'Permission denied'}), 403
    
    conn.execute('DELETE FROM checklist_items WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Checklist item deleted successfully'})

# Initialize scheduler for background jobs
scheduler = BackgroundScheduler()
scheduler.start()

# Schedule weekly job to extend recurring instances (runs every Monday at 2 AM)
scheduler.add_job(
    func=extend_recurring_instances_job,
    trigger=CronTrigger(day_of_week='mon', hour=2, minute=0),
    id='extend_recurring_instances',
    name='Extend recurring task instances weekly',
    replace_existing=True
)

# Shutdown scheduler when app exits
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    init_db()
    # Run the job once immediately on startup to extend any expiring instances
    extend_recurring_instances_job()
    app.run(host='0.0.0.0', port=5001, debug=True)
