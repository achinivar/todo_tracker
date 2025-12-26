from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import sqlite3
import os

app = Flask(__name__)
DATABASE = 'chores.db'

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with tables"""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS chores (
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
        DELETE FROM chores 
        WHERE completed = 1 AND completed_at < ?
    ''', (one_month_ago,))
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """Main page"""
    cleanup_old_completed_tasks()
    return render_template('index.html')

@app.route('/api/chores', methods=['GET'])
def get_chores():
    """Get all chores"""
    conn = get_db()
    show_completed = request.args.get('completed', 'false').lower() == 'true'
    
    if show_completed:
        chores = conn.execute('''
            SELECT * FROM chores 
            WHERE completed = 1 
            ORDER BY completed_at DESC
        ''').fetchall()
    else:
        chores = conn.execute('''
            SELECT * FROM chores 
            WHERE completed = 0 
            ORDER BY date ASC, time ASC, created_at ASC
        ''').fetchall()
    
    conn.close()
    return jsonify([dict(chore) for chore in chores])

@app.route('/api/chores', methods=['POST'])
def create_chore():
    """Create a new chore"""
    data = request.json
    conn = get_db()
    
    conn.execute('''
        INSERT INTO chores (task, date, time)
        VALUES (?, ?, ?)
    ''', (data['task'], data.get('date'), data.get('time')))
    
    conn.commit()
    chore_id = conn.lastrowid
    conn.close()
    
    return jsonify({'id': chore_id, 'message': 'Chore created successfully'}), 201

@app.route('/api/chores/<int:chore_id>', methods=['PUT'])
def update_chore(chore_id):
    """Update a chore"""
    data = request.json
    conn = get_db()
    
    if 'completed' in data:
        # Mark as complete/incomplete
        completed = data['completed']
        completed_at = datetime.now().isoformat() if completed else None
        conn.execute('''
            UPDATE chores 
            SET completed = ?, completed_at = ?
            WHERE id = ?
        ''', (1 if completed else 0, completed_at, chore_id))
    else:
        # Update task details
        conn.execute('''
            UPDATE chores 
            SET task = ?, date = ?, time = ?
            WHERE id = ?
        ''', (data['task'], data.get('date'), data.get('time'), chore_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Chore updated successfully'})

@app.route('/api/chores/<int:chore_id>', methods=['DELETE'])
def delete_chore(chore_id):
    """Delete a chore"""
    conn = get_db()
    conn.execute('DELETE FROM chores WHERE id = ?', (chore_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Chore deleted successfully'})

@app.route('/api/chores/date/<date>', methods=['GET'])
def get_chores_by_date(date):
    """Get chores for a specific date"""
    conn = get_db()
    chores = conn.execute('''
        SELECT * FROM chores 
        WHERE date = ? AND completed = 0
        ORDER BY time ASC, created_at ASC
    ''', (date,)).fetchall()
    conn.close()
    
    return jsonify([dict(chore) for chore in chores])

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)

