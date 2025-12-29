let currentDate = new Date();
let currentMonth = currentDate.getMonth();
let currentYear = currentDate.getFullYear();
let editingTaskId = null;
let showingCompleted = false;
let currentUser = null;
let isAdmin = false;

const monthNames = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
];

const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

// Auto-resize textarea function
function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
}

// Authentication functions
async function checkAuth() {
    try {
        const response = await fetch('/api/auth/status');
        const data = await response.json();
        
        if (!data.authenticated) {
            window.location.href = '/login';
            return false;
        }
        
        currentUser = data.user;
        isAdmin = currentUser.is_admin;
        updateUserUI();
        
        if (isAdmin) {
            checkAccountRequests();
            loadUsers();
        }
        
        return true;
    } catch (error) {
        console.error('Error checking auth:', error);
        window.location.href = '/login';
        return false;
    }
}

function updateUserUI() {
    const usernameDisplay = document.getElementById('user-menu-username');
    const adminMenuItem = document.getElementById('user-menu-admin');
    
    if (usernameDisplay && currentUser) {
        usernameDisplay.textContent = currentUser.username;
    }
    
    if (adminMenuItem) {
        adminMenuItem.style.display = isAdmin ? 'block' : 'none';
    }
}

function toggleUserMenu() {
    const menu = document.getElementById('user-menu');
    if (menu) {
        const isVisible = menu.style.display === 'block';
        menu.style.display = isVisible ? 'none' : 'block';
    }
}

// Close user menu when clicking outside
document.addEventListener('click', function(event) {
    const avatarContainer = document.querySelector('.user-avatar-container');
    const menu = document.getElementById('user-menu');
    
    if (avatarContainer && menu && !avatarContainer.contains(event.target)) {
        menu.style.display = 'none';
    }
});

async function checkAccountRequests() {
    try {
        const response = await fetch('/api/account-requests');
        if (!response.ok) return;
        
        const requests = await response.json();
        const notification = document.getElementById('admin-notification');
        const notificationText = document.getElementById('notification-text');
        
        if (requests.length > 0) {
            notification.style.display = 'block';
            notificationText.textContent = `You have ${requests.length} pending account request${requests.length > 1 ? 's' : ''}`;
        } else {
            notification.style.display = 'none';
        }
    } catch (error) {
        console.error('Error checking account requests:', error);
    }
}

async function handleLogout() {
    const menu = document.getElementById('user-menu');
    if (menu) {
        menu.style.display = 'none';
    }
    
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
        window.location.href = '/login';
    } catch (error) {
        console.error('Error logging out:', error);
        window.location.href = '/login';
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async function() {
    // Check authentication first
    const authenticated = await checkAuth();
    if (!authenticated) return;
    
    renderCalendar();
    loadTasks();
    
    // Set up auto-resize for task input textarea
    const taskInput = document.getElementById('task-input');
    if (taskInput) {
        taskInput.addEventListener('input', function() {
            autoResizeTextarea(this);
        });
    }
});

function renderCalendar() {
    const calendar = document.getElementById('calendar');
    const monthYear = document.getElementById('calendar-month-year');
    
    monthYear.textContent = `${monthNames[currentMonth]} ${currentYear}`;
    
    // Clear calendar
    calendar.innerHTML = '';
    
    // Add day headers
    dayNames.forEach(day => {
        const dayHeader = document.createElement('div');
        dayHeader.className = 'calendar-day-header';
        dayHeader.textContent = day;
        calendar.appendChild(dayHeader);
    });
    
    // Get first day of month and number of days
    const firstDay = new Date(currentYear, currentMonth, 1).getDay();
    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
    const today = new Date();
    
    // Add empty cells for days before month starts
    for (let i = 0; i < firstDay; i++) {
        const emptyDay = document.createElement('div');
        emptyDay.className = 'calendar-day other-month';
        calendar.appendChild(emptyDay);
    }
    
    // Add days of the month
    for (let day = 1; day <= daysInMonth; day++) {
        const dayElement = document.createElement('div');
        dayElement.className = 'calendar-day';
        dayElement.textContent = day;
        
        const dateStr = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        
        // Check if it's today
        if (currentYear === today.getFullYear() && 
            currentMonth === today.getMonth() && 
            day === today.getDate()) {
            dayElement.classList.add('today');
        }
        
        // Check if day has tasks (will be updated after loading tasks)
        dayElement.dataset.date = dateStr;
        dayElement.onclick = () => showDayTasks(dateStr);
        
        calendar.appendChild(dayElement);
    }
    
    // Add empty cells for days after month ends
    const totalCells = calendar.children.length;
    const remainingCells = 42 - totalCells; // 6 weeks * 7 days
    for (let i = 0; i < remainingCells; i++) {
        const emptyDay = document.createElement('div');
        emptyDay.className = 'calendar-day other-month';
        calendar.appendChild(emptyDay);
    }
    
    // Update calendar with task indicators
    updateCalendarTaskIndicators();
}

function changeMonth(direction) {
    currentMonth += direction;
    if (currentMonth < 0) {
        currentMonth = 11;
        currentYear--;
    } else if (currentMonth > 11) {
        currentMonth = 0;
        currentYear++;
    }
    renderCalendar();
}

async function updateCalendarTaskIndicators() {
    const tasks = await fetchTasks();
    const dateSet = new Set(tasks.filter(t => t.date).map(t => t.date));
    
    document.querySelectorAll('.calendar-day').forEach(day => {
        if (day.dataset.date && dateSet.has(day.dataset.date)) {
            day.classList.add('has-tasks');
        } else {
            day.classList.remove('has-tasks');
        }
    });
}

async function fetchTasks(showCompleted = false) {
    try {
        const response = await fetch(`/api/tasks?completed=${showCompleted}`);
        const tasks = await response.json();
        return tasks;
    } catch (error) {
        console.error('Error fetching tasks:', error);
        return [];
    }
}

async function loadTasks() {
    const tasks = await fetchTasks(showingCompleted);
    
    if (showingCompleted) {
        displayCompletedTasks(tasks);
    } else {
        displayTasks(tasks);
        updateCalendarTaskIndicators();
    }
}

function displayTasks(tasks) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const todayStr = today.toISOString().split('T')[0];
    const weekEnd = new Date(today);
    weekEnd.setDate(today.getDate() + 7);
    weekEnd.setHours(0, 0, 0, 0);
    
    const todayTasks = [];
    const weekTasks = [];
    const remainingTasks = [];
    
    tasks.forEach(task => {
        if (!task.date) {
            remainingTasks.push(task);
            return;
        }
        
        // Parse date string in local timezone to avoid UTC issues
        const [year, month, day] = task.date.split('-').map(Number);
        const taskDate = new Date(year, month - 1, day);
        taskDate.setHours(0, 0, 0, 0);
        
        if (taskDate <= today) {
            // Today's tasks and overdue tasks (dates before today)
            todayTasks.push(task);
        } else if (taskDate < weekEnd) {
            // Tasks for this week (after today)
            weekTasks.push(task);
        } else {
            // Future dates beyond this week go to remaining
            remainingTasks.push(task);
        }
    });
    
    renderTaskGroup('today-content', todayTasks);
    renderTaskGroup('week-content', weekTasks);
    // All Other Tasks section shows only tasks not in Today or This Week
    renderTaskGroup('remaining-content', remainingTasks);
}

function displayCompletedTasks(tasks) {
    const container = document.getElementById('completed-content');
    container.innerHTML = '';
    
    if (tasks.length === 0) {
        container.innerHTML = '<div class="empty-message">No completed tasks</div>';
        return;
    }
    
    tasks.forEach(task => {
        container.appendChild(createTaskElement(task, true));
    });
}

function renderTaskGroup(containerId, tasks) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';
    
    if (tasks.length === 0) {
        container.innerHTML = '<div class="empty-message">No tasks</div>';
        return;
    }
    
    tasks.forEach(task => {
        container.appendChild(createTaskElement(task, false));
    });
}

function createTaskElement(task, isCompleted) {
    const taskDiv = document.createElement('div');
    taskDiv.className = 'task-item';
    
    const taskInfo = document.createElement('div');
    taskInfo.className = 'task-info';
    
    const title = document.createElement('div');
    title.className = 'task-title';
    title.textContent = task.task;
    
    const meta = document.createElement('div');
    meta.className = 'task-meta';
    let metaText = '';
    if (task.date) {
        // Parse date string in local timezone to avoid UTC shift
        const [year, month, day] = task.date.split('-').map(Number);
        const date = new Date(year, month - 1, day);
        metaText = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }
    if (task.time) {
        // Convert 24-hour time to 12-hour AM/PM format
        const [hours, minutes] = task.time.split(':').map(Number);
        const period = hours >= 12 ? 'PM' : 'AM';
        const displayHours = hours % 12 || 12;
        const displayMinutes = String(minutes).padStart(2, '0');
        const timeStr = `${displayHours}:${displayMinutes} ${period}`;
        metaText += metaText ? ` at ${timeStr}` : `Time: ${timeStr}`;
    }
    
    // Add creator and visibility info
    const infoParts = [];
    if (task.creator_username) {
        infoParts.push(`by ${task.creator_username}`);
    }
    if (task.visibility && task.visibility !== 'all') {
        const visibilityLabels = {
            'admins': 'Admins only',
            'private': 'Private'
        };
        infoParts.push(visibilityLabels[task.visibility] || task.visibility);
    }
    
    if (infoParts.length > 0) {
        metaText += metaText ? ' • ' : '';
        metaText += infoParts.join(' • ');
    }
    
    if (metaText) {
        meta.textContent = metaText;
    }
    
    taskInfo.appendChild(title);
    taskInfo.appendChild(meta);
    
    const actions = document.createElement('div');
    actions.className = 'task-actions';
    
    if (isCompleted) {
        if (isAdmin) {
            const incompleteBtn = document.createElement('button');
            incompleteBtn.type = 'button';
            incompleteBtn.className = 'btn-action btn-incomplete';
            incompleteBtn.textContent = 'Mark Incomplete';
            incompleteBtn.onclick = () => markTaskComplete(task.id, false);
            actions.appendChild(incompleteBtn);
        }
    } else {
        if (isAdmin) {
            const completeBtn = document.createElement('button');
            completeBtn.type = 'button';
            completeBtn.className = 'btn-action btn-complete';
            completeBtn.textContent = 'Complete';
            completeBtn.onclick = () => markTaskComplete(task.id, true);
            actions.appendChild(completeBtn);
            
            const editBtn = document.createElement('button');
            editBtn.type = 'button';
            editBtn.className = 'btn-action btn-edit';
            editBtn.textContent = 'Edit';
            editBtn.onclick = () => editTask(task);
            actions.appendChild(editBtn);
            
            const deleteBtn = document.createElement('button');
            deleteBtn.type = 'button';
            deleteBtn.className = 'btn-action btn-delete';
            deleteBtn.textContent = 'Delete';
            deleteBtn.onclick = () => deleteTask(task.id);
            actions.appendChild(deleteBtn);
        }
    }
    
    taskDiv.appendChild(taskInfo);
    taskDiv.appendChild(actions);
    
    return taskDiv;
}

function toggleSection(section) {
    const header = document.getElementById(`${section}-tasks`).querySelector('.task-group-header');
    const content = document.getElementById(`${section}-content`).parentElement;
    
    header.classList.toggle('collapsed');
    content.querySelector('.task-group-content').classList.toggle('collapsed');
}

function openAddPopup() {
    editingTaskId = null;
    document.getElementById('popup-title').textContent = 'Add Task';
    const taskInput = document.getElementById('task-input');
    taskInput.value = '';
    taskInput.style.height = 'auto';
    document.getElementById('date-input').value = '';
    document.getElementById('time-input').value = '';
    
    // Show/hide visibility dropdown for admins
    const visibilityGroup = document.getElementById('visibility-group');
    const visibilityInput = document.getElementById('visibility-input');
    if (isAdmin) {
        visibilityGroup.style.display = 'block';
        visibilityInput.value = 'all';
    } else {
        visibilityGroup.style.display = 'none';
    }
    
    document.getElementById('task-popup').classList.add('show');
}

function closePopup() {
    document.getElementById('task-popup').classList.remove('show');
    editingTaskId = null;
    const taskInput = document.getElementById('task-input');
    taskInput.style.height = 'auto';
}

function editTask(task) {
    editingTaskId = task.id;
    document.getElementById('popup-title').textContent = 'Edit Task';
    const taskInput = document.getElementById('task-input');
    taskInput.value = task.task;
    autoResizeTextarea(taskInput);
    document.getElementById('date-input').value = task.date || '';
    document.getElementById('time-input').value = task.time || '';
    
    // Show/hide visibility dropdown for admins
    const visibilityGroup = document.getElementById('visibility-group');
    const visibilityInput = document.getElementById('visibility-input');
    if (isAdmin) {
        visibilityGroup.style.display = 'block';
        visibilityInput.value = task.visibility || 'all';
    } else {
        visibilityGroup.style.display = 'none';
    }
    
    document.getElementById('task-popup').classList.add('show');
}

async function saveTask(event) {
    event.preventDefault();
    
    const task = document.getElementById('task-input').value;
    const date = document.getElementById('date-input').value || null;
    const time = document.getElementById('time-input').value || null;
    const visibility = isAdmin ? (document.getElementById('visibility-input').value || 'all') : 'all';
    
    try {
        if (editingTaskId) {
            await fetch(`/api/tasks/${editingTaskId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task, date, time, visibility })
            });
        } else {
            await fetch('/api/tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task, date, time, visibility })
            });
        }
        
        closePopup();
        loadTasks();
    } catch (error) {
        console.error('Error saving task:', error);
        alert('Error saving task. Please try again.');
    }
}

async function markTaskComplete(taskId, completed) {
    try {
        await fetch(`/api/tasks/${taskId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ completed })
        });
        
        loadTasks();
    } catch (error) {
        console.error('Error updating task:', error);
        alert('Error updating task. Please try again.');
    }
}

async function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task?')) {
        return;
    }
    
    try {
        await fetch(`/api/tasks/${taskId}`, {
            method: 'DELETE'
        });
        
        loadTasks();
    } catch (error) {
        console.error('Error deleting task:', error);
        alert('Error deleting task. Please try again.');
    }
}

function toggleCompletedTasks() {
    showingCompleted = !showingCompleted;
    const btn = document.getElementById('show-completed-btn');
    const completedContainer = document.getElementById('completed-tasks-container');
    const tasksContainer = document.getElementById('tasks-container');
    
    if (showingCompleted) {
        btn.textContent = 'Show Incomplete Tasks';
        completedContainer.style.display = 'block';
        tasksContainer.style.display = 'none';
    } else {
        btn.textContent = 'Show Completed Tasks';
        completedContainer.style.display = 'none';
        tasksContainer.style.display = 'block';
    }
    
    loadTasks();
}

async function showDayTasks(dateStr) {
    try {
        const response = await fetch(`/api/tasks/date/${dateStr}`);
        const tasks = await response.json();
        
        const popup = document.getElementById('day-popup');
        const weekday = document.getElementById('day-weekday');
        const dateSpan = document.getElementById('day-date');
        const content = document.getElementById('day-tasks-content');
        
        // Parse date string in local timezone to avoid UTC shift
        const [year, month, day] = dateStr.split('-').map(Number);
        const date = new Date(year, month - 1, day);
        
        // Set weekday on first line
        weekday.textContent = date.toLocaleDateString('en-US', { weekday: 'long' }) + ',';
        
        // Set date (month, day, year) on second line
        dateSpan.textContent = date.toLocaleDateString('en-US', { 
            month: 'long', 
            day: 'numeric', 
            year: 'numeric' 
        });
        
        content.innerHTML = '';
        
        if (tasks.length === 0) {
            content.innerHTML = '<div class="empty-message">No tasks for this day</div>';
        } else {
            tasks.forEach(task => {
                content.appendChild(createTaskElement(task, false));
            });
        }
        
        popup.classList.add('show');
    } catch (error) {
        console.error('Error fetching day tasks:', error);
        alert('Error loading tasks for this day.');
    }
}

function closeDayPopup() {
    document.getElementById('day-popup').classList.remove('show');
}

// Close popups when clicking outside
window.onclick = function(event) {
    const addPopup = document.getElementById('task-popup');
    const dayPopup = document.getElementById('day-popup');
    const requestsPopup = document.getElementById('requests-popup');
    
    if (event.target === addPopup) {
        closePopup();
    }
    if (event.target === dayPopup) {
        closeDayPopup();
    }
    if (event.target === requestsPopup) {
        closeRequestsPopup();
    }
}

// Admin functions
function toggleAdminDashboard() {
    const dashboard = document.getElementById('admin-dashboard');
    const menu = document.getElementById('user-menu');
    
    // Close the user menu
    if (menu) {
        menu.style.display = 'none';
    }
    
    if (dashboard.style.display === 'none') {
        dashboard.style.display = 'block';
        loadAccountRequests();
        loadUsers();
    } else {
        dashboard.style.display = 'none';
    }
}

async function loadAccountRequests() {
    if (!isAdmin) return;
    
    try {
        const response = await fetch('/api/account-requests');
        if (!response.ok) return;
        
        const requests = await response.json();
        const container = document.getElementById('account-requests-list');
        const popupContainer = document.getElementById('requests-popup-content');
        
        if (requests.length === 0) {
            container.innerHTML = '<div class="empty-dashboard">No pending account requests</div>';
            if (popupContainer) {
                popupContainer.innerHTML = '<div class="empty-message">No pending account requests</div>';
            }
            return;
        }
        
        let html = '';
        requests.forEach(req => {
            const date = new Date(req.requested_at);
            const dateStr = date.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric', 
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
            
            html += `
                <div class="request-item">
                    <div class="request-info">
                        <div class="request-username">${req.username}</div>
                        <div class="request-date">Requested: ${dateStr}</div>
                    </div>
                    <div class="request-actions">
                        <button class="btn-approve-admin" onclick="handleAccountRequest(${req.id}, 'approve_admin')">Approve as Admin</button>
                        <button class="btn-approve-user" onclick="handleAccountRequest(${req.id}, 'approve_user')">Approve as User</button>
                        <button class="btn-reject" onclick="handleAccountRequest(${req.id}, 'reject')">Reject</button>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        if (popupContainer) {
            popupContainer.innerHTML = html;
        }
    } catch (error) {
        console.error('Error loading account requests:', error);
    }
}

async function handleAccountRequest(requestId, action) {
    if (!isAdmin) return;
    
    try {
        const response = await fetch(`/api/account-requests/${requestId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });
        
        if (!response.ok) {
            const data = await response.json();
            alert(data.error || 'Error processing request');
            return;
        }
        
        // Reload requests and update notification
        await loadAccountRequests();
        await checkAccountRequests();
        
        // Close popup if open
        closeRequestsPopup();
    } catch (error) {
        console.error('Error handling account request:', error);
        alert('Error processing request. Please try again.');
    }
}

function showAccountRequests() {
    const popup = document.getElementById('requests-popup');
    if (popup) {
        loadAccountRequests();
        popup.classList.add('show');
    }
}

function closeRequestsPopup() {
    const popup = document.getElementById('requests-popup');
    if (popup) {
        popup.classList.remove('show');
    }
}

async function loadUsers() {
    if (!isAdmin) return;
    
    try {
        const response = await fetch('/api/users');
        if (!response.ok) return;
        
        const users = await response.json();
        const container = document.getElementById('users-list');
        
        if (users.length === 0) {
            container.innerHTML = '<div class="empty-dashboard">No users found</div>';
            return;
        }
        
        let html = '';
        users.forEach(user => {
            const date = new Date(user.created_at);
            const dateStr = date.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric', 
                year: 'numeric'
            });
            
            const roleText = user.is_admin ? 'Admin' : 'Regular User';
            const newRole = user.is_admin ? 0 : 1;
            const roleBtnText = user.is_admin ? 'Make Regular User' : 'Make Admin';
            
            html += `
                <div class="user-item">
                    <div class="user-info-item">
                        <div class="user-username">${user.username} ${user.id === currentUser.id ? '(You)' : ''}</div>
                        <div class="user-date">Role: ${roleText} | Created: ${dateStr}</div>
                    </div>
                    <div class="user-actions">
                        ${user.id !== currentUser.id ? `
                            <button class="btn-change-role" onclick="changeUserRole(${user.id}, ${newRole})">${roleBtnText}</button>
                            <button class="btn-delete-user" onclick="deleteUser(${user.id}, '${user.username}')">Delete</button>
                        ` : '<span style="color: #6c757d; font-size: 12px;">Cannot modify own account</span>'}
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

async function changeUserRole(userId, newRole) {
    if (!isAdmin) return;
    
    if (!confirm(`Are you sure you want to change this user's role?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/users/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'change_role', is_admin: newRole })
        });
        
        if (!response.ok) {
            const data = await response.json();
            alert(data.error || 'Error updating user role');
            return;
        }
        
        await loadUsers();
    } catch (error) {
        console.error('Error changing user role:', error);
        alert('Error updating user role. Please try again.');
    }
}

async function deleteUser(userId, username) {
    if (!isAdmin) return;
    
    if (!confirm(`Are you sure you want to delete user "${username}"? This will also delete all their tasks.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/users/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'delete' })
        });
        
        if (!response.ok) {
            const data = await response.json();
            alert(data.error || 'Error deleting user');
            return;
        }
        
        await loadUsers();
    } catch (error) {
        console.error('Error deleting user:', error);
        alert('Error deleting user. Please try again.');
    }
}


