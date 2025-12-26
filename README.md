# Task Tracker

A web-based task tracking application for Raspberry Pi.

## Features

- **Calendar View**: Monthly calendar with navigation arrows to view different months
- **Task Management**: Add, edit, delete, and mark tasks as complete
- **Date-based Organization**: Tasks are organized by today, this week, and remaining
- **Completed Tasks**: View and restore completed tasks (auto-deleted after 1 month)
- **Day View**: Click on any calendar day to see all tasks for that day

## Start the application

On a Raspberry Pi or anywhere you want to host the server, run the startup script 
This will automatically create a virtual environment, install dependencies, and start the server.

```bash
./start_server.sh
```

The script will:
- Create a Python virtual environment (if it doesn't exist)
- Install all required dependencies from `requirements.txt`
- Start the Flask server

## Access the application:
   - **On the same device**: Open your browser and navigate to:
     ```
     http://localhost:5001
     ```
   
   - **From other devices on the same WiFi network**: You can access the application from any phone or PC on the same network using either:
     - **IP Address**: `http://[device-ip-address]:5001` (e.g., `http://192.168.1.100:5001`)
     - **Hostname**: `http://[hostname]:5001` (e.g., `http://raspberrypi.local:5001`)
   
   - **Raspberry Pi**: If running on a Raspberry Pi, it typically has `raspberrypi` as the hostname, so you can access it using:
     ```
     http://raspberrypi.local:5001
     ```

## Usage

- Click "Add Task" button to add a new task
- Tasks can have an optional date and time
- Tasks with dates appear on the calendar
- Click on a calendar day to view tasks for that day
- Mark tasks as complete to remove them from the active list
- Use "Show Completed Tasks" to view and restore completed tasks
- Edit or delete tasks using the action buttons

## Database

The application uses SQLite database (`tasks.db`) which is automatically created on first run. Completed tasks are automatically deleted from the database after 1 month.

