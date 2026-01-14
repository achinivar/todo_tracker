#!/usr/bin/env python3
"""
Database Migration Script
Migrates an old database to the new schema with recurring tasks and checklist support.

New additions:
1. tasks.recurrence (TEXT) - stores recurrence pattern (weekly, bi-weekly, monthly, yearly)
2. tasks.parent_task_id (INTEGER) - links recurring task instances to their parent
3. checklist_items table - new table for task checklists/subtasks
"""

import sqlite3
import sys
import os

DATABASE = 'tasks.db'

def migrate_database():
    """Migrate database to new schema"""
    if not os.path.exists(DATABASE):
        print(f"Error: Database file '{DATABASE}' not found.")
        print("Please make sure the database file exists in the current directory.")
        sys.exit(1)
    
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    
    try:
        print("Starting database migration...")
        print("=" * 60)
        
        # Check current schema
        cursor = conn.execute("PRAGMA table_info(tasks)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"Current tasks table columns: {', '.join(columns)}")
        print()
        
        # 1. Add recurrence column if it doesn't exist
        if 'recurrence' not in columns:
            print("Adding 'recurrence' column to tasks table...")
            conn.execute('ALTER TABLE tasks ADD COLUMN recurrence TEXT')
            print("  ✓ Added 'recurrence' column (default: NULL)")
        else:
            print("  ✓ 'recurrence' column already exists")
        
        # 2. Add parent_task_id column if it doesn't exist
        if 'parent_task_id' not in columns:
            print("Adding 'parent_task_id' column to tasks table...")
            conn.execute('ALTER TABLE tasks ADD COLUMN parent_task_id INTEGER')
            print("  ✓ Added 'parent_task_id' column (default: NULL)")
        else:
            print("  ✓ 'parent_task_id' column already exists")
        
        # 3. Create indexes for the new columns
        print("Creating indexes...")
        try:
            conn.execute('CREATE INDEX IF NOT EXISTS idx_parent_task_id ON tasks(parent_task_id)')
            print("  ✓ Created index on parent_task_id")
        except sqlite3.OperationalError as e:
            print(f"  ⚠ Index on parent_task_id may already exist: {e}")
        
        # 4. Create checklist_items table if it doesn't exist
        print("Creating checklist_items table...")
        try:
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
            print("  ✓ Created checklist_items table")
        except sqlite3.OperationalError as e:
            print(f"  ⚠ checklist_items table may already exist: {e}")
        
        # 5. Create index for checklist_items
        print("Creating checklist_items index...")
        try:
            conn.execute('CREATE INDEX IF NOT EXISTS idx_checklist_task_id ON checklist_items(task_id)')
            print("  ✓ Created index on checklist_items.task_id")
        except sqlite3.OperationalError as e:
            print(f"  ⚠ Index may already exist: {e}")
        
        # Commit all changes
        conn.commit()
        
        print()
        print("=" * 60)
        print("Migration completed successfully!")
        print()
        
        # Show final schema
        cursor = conn.execute("PRAGMA table_info(tasks)")
        final_columns = [row[1] for row in cursor.fetchall()]
        print(f"Final tasks table columns: {', '.join(final_columns)}")
        print()
        
        # Show statistics
        task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        print(f"Total tasks in database: {task_count}")
        
        # Check if checklist_items table exists and show count
        try:
            checklist_count = conn.execute("SELECT COUNT(*) FROM checklist_items").fetchone()[0]
            print(f"Total checklist items: {checklist_count}")
        except:
            pass
        
    except sqlite3.Error as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    print("Database Migration Script")
    print("=" * 60)
    print()
    print("This script will add the following to your database:")
    print("  1. 'recurrence' column to tasks table (default: NULL)")
    print("  2. 'parent_task_id' column to tasks table (default: NULL)")
    print("  3. 'checklist_items' table (for task checklists)")
    print()
    
    response = input("Do you want to proceed? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("Migration cancelled.")
        sys.exit(0)
    
    print()
    migrate_database()
