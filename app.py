from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import sqlite3
import os

app = Flask(__name__)
DATABASE = 'tasks.db'

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with tables"""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            date TEXT,
            time TEXT,
            completed INTEGER DEFAULT 0,
            completed_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def cleanup_old_completed_tasks():
    """Remove completed tasks older than 1 month"""
    conn = get_db()
    one_month_ago = (datetime.now() - timedelta(days=30)).isoformat()
    conn.execute('''
        DELETE FROM tasks 
        WHERE completed = 1 AND completed_at < ?
    ''', (one_month_ago,))
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """Main page"""
    cleanup_old_completed_tasks()
    return render_template('index.html')

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Get all tasks"""
    conn = get_db()
    show_completed = request.args.get('completed', 'false').lower() == 'true'
    
    if show_completed:
        tasks = conn.execute('''
            SELECT * FROM tasks 
            WHERE completed = 1 
            ORDER BY completed_at DESC
        ''').fetchall()
    else:
        tasks = conn.execute('''
            SELECT * FROM tasks 
            WHERE completed = 0 
            ORDER BY date ASC, time ASC, created_at ASC
        ''').fetchall()
    
    conn.close()
    return jsonify([dict(task) for task in tasks])

@app.route('/api/tasks', methods=['POST'])
def create_task():
    """Create a new task"""
    data = request.json
    conn = get_db()
    
    conn.execute('''
        INSERT INTO tasks (task, date, time)
        VALUES (?, ?, ?)
    ''', (data['task'], data.get('date'), data.get('time')))
    
    conn.commit()
    task_id = conn.lastrowid
    conn.close()
    
    return jsonify({'id': task_id, 'message': 'Task created successfully'}), 201

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """Update a task"""
    data = request.json
    conn = get_db()
    
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
        conn.execute('''
            UPDATE tasks 
            SET task = ?, date = ?, time = ?
            WHERE id = ?
        ''', (data['task'], data.get('date'), data.get('time'), task_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Task updated successfully'})

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """Delete a task"""
    conn = get_db()
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Task deleted successfully'})

@app.route('/api/tasks/date/<date>', methods=['GET'])
def get_tasks_by_date(date):
    """Get tasks for a specific date"""
    conn = get_db()
    tasks = conn.execute('''
        SELECT * FROM tasks 
        WHERE date = ? AND completed = 0
        ORDER BY time ASC, created_at ASC
    ''', (date,)).fetchall()
    conn.close()
    
    return jsonify([dict(task) for task in tasks])

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)

