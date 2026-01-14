#!/usr/bin/env python3
"""
Simple script to view the contents of the tasks.db database.
Usage: python view_db.py [table_name]
If no table is specified, shows all tables.
"""

import sqlite3
import sys
from datetime import datetime

DATABASE = 'tasks.db'

def print_table(conn, table_name):
    """Print all rows from a table in a readable format"""
    cursor = conn.execute(f"SELECT * FROM {table_name}")
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()
    
    print(f"\n{'='*80}")
    print(f"Table: {table_name}")
    print(f"Rows: {len(rows)}")
    print(f"{'='*80}")
    
    if not rows:
        print("(No rows)")
        return
    
    # Calculate column widths
    col_widths = {}
    for col in columns:
        col_widths[col] = max(len(col), max((len(str(row[columns.index(col)])) for row in rows), default=0))
    
    # Print header
    header = " | ".join(str(col).ljust(col_widths[col]) for col in columns)
    print(header)
    print("-" * len(header))
    
    # Print rows
    for row in rows:
        row_str = " | ".join(str(row[columns.index(col)]).ljust(col_widths[col]) for col in columns)
        print(row_str)
    
    print()

def list_tables(conn):
    """List all tables in the database"""
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    return tables

def show_schema(conn, table_name):
    """Show the schema of a table"""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    print(f"\nSchema for table '{table_name}':")
    print("-" * 80)
    print(f"{'Column':<20} {'Type':<15} {'NotNull':<10} {'Default':<20} {'PK':<5}")
    print("-" * 80)
    for col in columns:
        print(f"{col[1]:<20} {col[2]:<15} {'YES' if col[3] else 'NO':<10} {str(col[4]):<20} {'YES' if col[5] else 'NO':<5}")
    print()

def main():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    
    tables = list_tables(conn)
    
    if len(sys.argv) > 1:
        table_name = sys.argv[1]
        if table_name not in tables:
            print(f"Error: Table '{table_name}' not found.")
            print(f"Available tables: {', '.join(tables)}")
            conn.close()
            return
        show_schema(conn, table_name)
        print_table(conn, table_name)
    else:
        print("\n" + "="*80)
        print("DATABASE OVERVIEW")
        print("="*80)
        
        # Show all tables
        for table in tables:
            show_schema(conn, table)
            print_table(conn, table)
        
        # Show some statistics
        print("\n" + "="*80)
        print("STATISTICS")
        print("="*80)
        
        # Count users
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        admin_count = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0]
        print(f"Total users: {user_count} (Admins: {admin_count}, Regular: {user_count - admin_count})")
        
        # Count tasks
        total_tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        completed_tasks = conn.execute("SELECT COUNT(*) FROM tasks WHERE completed = 1").fetchone()[0]
        pending_tasks = total_tasks - completed_tasks
        print(f"Total tasks: {total_tasks} (Pending: {pending_tasks}, Completed: {completed_tasks})")
        
        # Count requests
        account_requests = conn.execute("SELECT COUNT(*) FROM account_requests").fetchone()[0]
        completion_requests = conn.execute("SELECT COUNT(*) FROM task_completion_requests WHERE status = 'pending'").fetchone()[0]
        print(f"Pending account requests: {account_requests}")
        print(f"Pending completion requests: {completion_requests}")
        print()
    
    conn.close()

if __name__ == '__main__':
    main()
