# Chore Tracker

A web-based chore tracking application for Raspberry Pi.

## Features

- **Calendar View**: Monthly calendar with navigation arrows to view different months
- **Task Management**: Add, edit, delete, and mark tasks as complete
- **Date-based Organization**: Tasks are organized by today, this week, and remaining
- **Completed Tasks**: View and restore completed tasks (auto-deleted after 1 month)
- **Day View**: Click on any calendar day to see all tasks for that day

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

1. Start the Flask server:
```bash
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5001
```

## Usage

- Click "Add Chore" button to add a new task
- Tasks can have an optional date and time
- Tasks with dates appear on the calendar
- Click on a calendar day to view tasks for that day
- Mark tasks as complete to remove them from the active list
- Use "Show Completed Tasks" to view and restore completed tasks
- Edit or delete tasks using the action buttons

## Database

The application uses SQLite database (`chores.db`) which is automatically created on first run. Completed tasks are automatically deleted from the database after 1 month.

