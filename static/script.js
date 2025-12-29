let currentDate = new Date();
let currentMonth = currentDate.getMonth();
let currentYear = currentDate.getFullYear();
let editingTaskId = null;
let showingCompleted = false;
let currentUser = null;
let isAdmin = false;
let currentTaskFilter = 'all';
let allTasks = []; // Store all tasks for filtering

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
            checkTaskCompletionRequests();
            loadUsers();
            setupAdminTaskFilter();
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
        const accountResponse = await fetch('/api/account-requests');
        if (!accountResponse.ok) return;
        
        const accountRequests = await accountResponse.json();
        const completionResponse = await fetch('/api/task-completion-requests');
        const completionRequests = completionResponse.ok ? await completionResponse.json() : [];
        
        await updateAdminNotification(accountRequests.length, completionRequests.length);
    } catch (error) {
        console.error('Error checking account requests:', error);
    }
}

async function checkTaskCompletionRequests() {
    try {
        const response = await fetch('/api/task-completion-requests');
        if (!response.ok) return;
        
        const requests = await response.json();
        const accountResponse = await fetch('/api/account-requests');
        const accountRequests = accountResponse.ok ? await accountResponse.json() : [];
        
        await updateAdminNotification(accountRequests.length, requests.length);
    } catch (error) {
        console.error('Error checking task completion requests:', error);
    }
}

async function updateAdminNotification(accountCount = 0, completionCount = 0) {
    const notification = document.getElementById('admin-notification');
    const notificationText = document.getElementById('notification-text');
    
    if (accountCount > 0 || completionCount > 0) {
        notification.style.display = 'block';
        let message = '';
        if (accountCount > 0 && completionCount > 0) {
            message = `You have ${accountCount} pending account request${accountCount > 1 ? 's' : ''} and ${completionCount} pending task completion request${completionCount > 1 ? 's' : ''}`;
        } else if (accountCount > 0) {
            message = `You have ${accountCount} pending account request${accountCount > 1 ? 's' : ''}`;
        } else if (completionCount > 0) {
            message = `You have ${completionCount} pending task completion request${completionCount > 1 ? 's' : ''}`;
        }
        if (message) {
            notificationText.textContent = message;
        }
    } else {
        notification.style.display = 'none';
    }
}

function openChangePasswordPopup() {
    const menu = document.getElementById('user-menu');
    if (menu) {
        menu.style.display = 'none';
    }
    const popup = document.getElementById('change-password-popup');
    const form = document.getElementById('change-password-form');
    const errorDiv = document.getElementById('change-password-error');
    const successDiv = document.getElementById('change-password-success');
    
    // Reset form and messages
    form.reset();
    errorDiv.style.display = 'none';
    successDiv.style.display = 'none';
    
    popup.classList.add('show');
}

function closeChangePasswordPopup() {
    const popup = document.getElementById('change-password-popup');
    popup.classList.remove('show');
    const form = document.getElementById('change-password-form');
    const errorDiv = document.getElementById('change-password-error');
    const successDiv = document.getElementById('change-password-success');
    form.reset();
    errorDiv.style.display = 'none';
    successDiv.style.display = 'none';
}

async function handleChangePassword(event) {
    event.preventDefault();
    
    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-new-password').value;
    const errorDiv = document.getElementById('change-password-error');
    const successDiv = document.getElementById('change-password-success');
    
    errorDiv.style.display = 'none';
    successDiv.style.display = 'none';
    
    if (newPassword !== confirmPassword) {
        errorDiv.textContent = 'New passwords do not match';
        errorDiv.style.display = 'block';
        return;
    }
    
    if (newPassword.length < 6) {
        errorDiv.textContent = 'New password must be at least 6 characters';
        errorDiv.style.display = 'block';
        return;
    }
    
    try {
        const response = await fetch('/api/auth/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            errorDiv.textContent = data.error || 'Failed to change password';
            errorDiv.style.display = 'block';
            return;
        }
        
        successDiv.textContent = 'Password changed successfully!';
        successDiv.style.display = 'block';
        
        // Clear form and close after 2 seconds
        setTimeout(() => {
            closeChangePasswordPopup();
        }, 2000);
    } catch (error) {
        console.error('Error changing password:', error);
        errorDiv.textContent = 'An error occurred. Please try again.';
        errorDiv.style.display = 'block';
    }
}

function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    const button = input.nextElementSibling;
    const svg = button.querySelector('svg');
    
    if (input.type === 'password') {
        input.type = 'text';
        // Eye with slash icon
        svg.innerHTML = `
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
            <line x1="1" y1="1" x2="23" y2="23"/>
        `;
    } else {
        input.type = 'password';
        // Regular eye icon
        svg.innerHTML = `
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
        `;
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
    allTasks = tasks; // Store all tasks
    
    if (showingCompleted) {
        displayCompletedTasks(tasks);
    } else {
        const filteredTasks = isAdmin ? applyTaskFilterToTasks(tasks) : tasks;
        displayTasks(filteredTasks);
        updateCalendarTaskIndicators();
    }
}

async function setupAdminTaskFilter() {
    const filterContainer = document.getElementById('admin-task-filter');
    const filterSelect = document.getElementById('task-filter-select');
    
    if (!filterContainer || !filterSelect) return;
    
    filterContainer.style.display = 'block';
    
    // Load non-admin users and add them to the filter
    try {
        const response = await fetch('/api/users/non-admin');
        if (response.ok) {
            const users = await response.json();
            // Clear existing user options (keep the first 3 default options)
            const defaultOptions = Array.from(filterSelect.querySelectorAll('option')).slice(0, 3);
            filterSelect.innerHTML = '';
            defaultOptions.forEach(opt => filterSelect.appendChild(opt));
            
            // Add non-admin users
            users.forEach(user => {
                const option = document.createElement('option');
                option.value = `user_${user.id}`;
                option.textContent = user.username;
                filterSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading non-admin users for filter:', error);
    }
}

function applyTaskFilter() {
    const filterSelect = document.getElementById('task-filter-select');
    if (!filterSelect) return;
    
    currentTaskFilter = filterSelect.value;
    
    if (showingCompleted) {
        displayCompletedTasks(allTasks);
    } else {
        const filteredTasks = applyTaskFilterToTasks(allTasks);
        displayTasks(filteredTasks);
        updateCalendarTaskIndicators();
    }
}

function applyTaskFilterToTasks(tasks) {
    if (!isAdmin || currentTaskFilter === 'all') {
        return tasks;
    }
    
    switch (currentTaskFilter) {
        case 'admins':
            // Tasks with visibility='admins'
            return tasks.filter(task => task.visibility === 'admins');
        
        case 'private':
            // Tasks with visibility='private'
            return tasks.filter(task => task.visibility === 'private');
        
        default:
            // Filter by user assignment (format: user_<id>)
            if (currentTaskFilter.startsWith('user_')) {
                const userId = parseInt(currentTaskFilter.split('_')[1]);
                return tasks.filter(task => task.assigned_to === userId);
            }
            return tasks;
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
    // Apply filter if admin
    const filteredTasks = isAdmin ? applyTaskFilterToTasks(tasks) : tasks;
    
    const container = document.getElementById('completed-content');
    container.innerHTML = '';
    
    if (filteredTasks.length === 0) {
        container.innerHTML = '<div class="empty-message">No completed tasks</div>';
        return;
    }
    
    filteredTasks.forEach(task => {
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
    
    // Add creator, assignment, and visibility info
    const infoParts = [];
    if (task.creator_username) {
        infoParts.push(`by ${task.creator_username}`);
    }
    if (task.assigned_to_username) {
        infoParts.push(`assigned to ${task.assigned_to_username}`);
    }
    if (task.visibility && task.visibility !== 'all' && !task.assigned_to) {
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
        } else {
            // Regular users can request to mark task as complete
            const requestCompleteBtn = document.createElement('button');
            requestCompleteBtn.type = 'button';
            requestCompleteBtn.className = 'btn-action btn-request-complete';
            
            // Check if there's a pending request for this task
            if (task.has_pending_request) {
                requestCompleteBtn.textContent = 'Request Pending';
                requestCompleteBtn.disabled = true;
                requestCompleteBtn.style.opacity = '0.6';
                requestCompleteBtn.style.cursor = 'not-allowed';
            } else {
                requestCompleteBtn.textContent = 'Mark Complete';
                requestCompleteBtn.onclick = () => requestTaskComplete(task.id);
            }
            
            actions.appendChild(requestCompleteBtn);
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

async function openAddPopup() {
    editingTaskId = null;
    document.getElementById('popup-title').textContent = 'Add Task';
    const taskInput = document.getElementById('task-input');
    taskInput.value = '';
    taskInput.style.height = 'auto';
    document.getElementById('date-input').value = '';
    document.getElementById('time-input').value = '';
    
    // Show/hide assign dropdown for admins only
    const assignGroup = document.getElementById('assign-group');
    const assignInput = document.getElementById('assign-input');
    if (isAdmin) {
        assignGroup.style.display = 'block';
        assignInput.value = '';
        
        // Load non-admin users and populate dropdown
        try {
            const response = await fetch('/api/users/non-admin');
            if (response.ok) {
                const users = await response.json();
                // Clear existing options except the first three
                assignInput.innerHTML = `
                    <option value="">All Users</option>
                    <option value="admins">Admins only</option>
                    <option value="private">Private</option>
                `;
                // Add non-admin users
                users.forEach(user => {
                    const option = document.createElement('option');
                    option.value = user.id;
                    option.textContent = user.username;
                    assignInput.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Error loading non-admin users:', error);
        }
    } else {
        assignGroup.style.display = 'none';
    }
    
    document.getElementById('task-popup').classList.add('show');
}

function closePopup() {
    document.getElementById('task-popup').classList.remove('show');
    editingTaskId = null;
    const taskInput = document.getElementById('task-input');
    taskInput.style.height = 'auto';
}

async function editTask(task) {
    editingTaskId = task.id;
    document.getElementById('popup-title').textContent = 'Edit Task';
    const taskInput = document.getElementById('task-input');
    taskInput.value = task.task;
    autoResizeTextarea(taskInput);
    document.getElementById('date-input').value = task.date || '';
    document.getElementById('time-input').value = task.time || '';
    
    // Show/hide assign dropdown for admins only
    const assignGroup = document.getElementById('assign-group');
    const assignInput = document.getElementById('assign-input');
    if (isAdmin) {
        assignGroup.style.display = 'block';
        
        // Load non-admin users and populate dropdown
        try {
            const response = await fetch('/api/users/non-admin');
            if (response.ok) {
                const users = await response.json();
                // Clear existing options except the first three
                assignInput.innerHTML = `
                    <option value="">All Users</option>
                    <option value="admins">Admins only</option>
                    <option value="private">Private</option>
                `;
                // Add non-admin users
                users.forEach(user => {
                    const option = document.createElement('option');
                    option.value = user.id;
                    option.textContent = user.username;
                    assignInput.appendChild(option);
                });
                
                // Set the current value
                if (task.assigned_to) {
                    assignInput.value = task.assigned_to;
                } else {
                    assignInput.value = task.visibility || 'all';
                }
            }
        } catch (error) {
            console.error('Error loading non-admin users:', error);
        }
    } else {
        assignGroup.style.display = 'none';
    }
    
    document.getElementById('task-popup').classList.add('show');
}

async function saveTask(event) {
    event.preventDefault();
    
    const task = document.getElementById('task-input').value;
    const date = document.getElementById('date-input').value || null;
    const time = document.getElementById('time-input').value || null;
    
    let assigned_to = null;
    let visibility = 'all';
    
    if (isAdmin) {
        const assignInput = document.getElementById('assign-input');
        const assignValue = assignInput.value;
        
        // Check if a user ID was selected (numeric value)
        if (assignValue && !isNaN(assignValue) && assignValue !== '') {
            assigned_to = parseInt(assignValue);
            visibility = 'all'; // When assigned, use 'all' visibility
        } else {
            // Use visibility options (all, admins, private)
            visibility = assignValue || 'all';
            assigned_to = null;
        }
    } else {
        // Non-admin users: no assignment, visibility is 'all'
        visibility = 'all';
        assigned_to = null;
    }
    
    const taskData = { task, date, time, visibility };
    if (assigned_to !== null) {
        taskData.assigned_to = assigned_to;
    }
    
    try {
        if (editingTaskId) {
            await fetch(`/api/tasks/${editingTaskId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(taskData)
            });
        } else {
            await fetch('/api/tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(taskData)
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
    const changePasswordPopup = document.getElementById('change-password-popup');
    const adminChangePasswordPopup = document.getElementById('admin-change-password-popup');
    
    if (event.target === addPopup) {
        closePopup();
    }
    if (event.target === dayPopup) {
        closeDayPopup();
    }
    if (event.target === requestsPopup) {
        closeRequestsPopup();
    }
    if (event.target === changePasswordPopup) {
        closeChangePasswordPopup();
    }
    if (event.target === adminChangePasswordPopup) {
        closeAdminChangePasswordPopup();
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
        loadTaskCompletionRequests();
        loadAccountRequests();
        loadUsers();
    } else {
        dashboard.style.display = 'none';
    }
}

async function loadTaskCompletionRequests() {
    if (!isAdmin) return;
    
    try {
        const response = await fetch('/api/task-completion-requests');
        if (!response.ok) {
            console.error('Failed to fetch task completion requests:', response.status);
            return;
        }
        
        const requests = await response.json();
        const container = document.getElementById('task-completion-requests-list');
        
        if (!container) {
            console.error('task-completion-requests-list container not found');
            return;
        }
        
        if (requests.length === 0) {
            container.innerHTML = '<div class="empty-dashboard">No pending task completion requests</div>';
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
            
            let taskInfo = req.task || 'Unknown task';
            if (req.date) {
                const [year, month, day] = req.date.split('-').map(Number);
                const taskDate = new Date(year, month - 1, day);
                taskInfo += ` (${taskDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })})`;
            }
            
            html += `
                <div class="request-item">
                    <div class="request-info">
                        <div class="request-username">Task: ${taskInfo}</div>
                        <div class="request-date">Requested by: ${req.requester_username || 'Unknown'} on ${dateStr}</div>
                    </div>
                    <div class="request-actions">
                        <button class="btn-approve-admin" onclick="handleTaskCompletionRequest(${req.id}, 'approve')">Approve</button>
                        <button class="btn-reject" onclick="handleTaskCompletionRequest(${req.id}, 'reject')">Reject</button>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    } catch (error) {
        console.error('Error loading task completion requests:', error);
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

async function requestTaskComplete(taskId) {
    try {
        const response = await fetch('/api/task-completion-requests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: taskId })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            alert(data.error || 'Error submitting completion request');
            return;
        }
        
        alert('Completion request submitted. Waiting for admin approval.');
        // Reload tasks to update button to "Request Pending"
        await loadTasks();
    } catch (error) {
        console.error('Error requesting task completion:', error);
        alert('Error submitting request. Please try again.');
    }
}

async function handleTaskCompletionRequest(requestId, action) {
    if (!isAdmin) return;
    
    try {
        const response = await fetch(`/api/task-completion-requests/${requestId}`, {
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
        await loadTaskCompletionRequests();
        await checkAccountRequests(); // This will update notification with both counts
        loadTasks(); // Reload tasks in case one was marked complete
    } catch (error) {
        console.error('Error handling task completion request:', error);
        alert('Error processing request. Please try again.');
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
        await checkAccountRequests(); // This will update notification with both counts
        
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
                            <button class="btn-change-password-admin" onclick="openAdminChangePasswordPopup(${user.id}, '${user.username}')">Change Password</button>
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

let adminChangePasswordUserId = null;

function openAdminChangePasswordPopup(userId, username) {
    adminChangePasswordUserId = userId;
    const popup = document.getElementById('admin-change-password-popup');
    const form = document.getElementById('admin-change-password-form');
    const errorDiv = document.getElementById('admin-change-password-error');
    const successDiv = document.getElementById('admin-change-password-success');
    const usernameSpan = document.getElementById('admin-change-password-username');
    
    usernameSpan.textContent = username;
    
    // Reset form and messages
    form.reset();
    errorDiv.style.display = 'none';
    successDiv.style.display = 'none';
    
    popup.classList.add('show');
}

function closeAdminChangePasswordPopup() {
    const popup = document.getElementById('admin-change-password-popup');
    popup.classList.remove('show');
    const form = document.getElementById('admin-change-password-form');
    const errorDiv = document.getElementById('admin-change-password-error');
    const successDiv = document.getElementById('admin-change-password-success');
    form.reset();
    errorDiv.style.display = 'none';
    successDiv.style.display = 'none';
    adminChangePasswordUserId = null;
}

async function handleAdminChangePassword(event) {
    event.preventDefault();
    
    if (!isAdmin || !adminChangePasswordUserId) return;
    
    const adminPassword = document.getElementById('admin-password').value;
    const newPassword = document.getElementById('admin-new-password').value;
    const confirmPassword = document.getElementById('admin-confirm-new-password').value;
    const errorDiv = document.getElementById('admin-change-password-error');
    const successDiv = document.getElementById('admin-change-password-success');
    
    errorDiv.style.display = 'none';
    successDiv.style.display = 'none';
    
    if (newPassword !== confirmPassword) {
        errorDiv.textContent = 'New passwords do not match';
        errorDiv.style.display = 'block';
        return;
    }
    
    if (newPassword.length < 6) {
        errorDiv.textContent = 'New password must be at least 6 characters';
        errorDiv.style.display = 'block';
        return;
    }
    
    try {
        const response = await fetch('/api/auth/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                current_password: adminPassword,
                new_password: newPassword,
                target_user_id: adminChangePasswordUserId
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            errorDiv.textContent = data.error || 'Failed to change password';
            errorDiv.style.display = 'block';
            return;
        }
        
        successDiv.textContent = data.message || 'Password changed successfully!';
        successDiv.style.display = 'block';
        
        // Clear form and close after 2 seconds
        setTimeout(() => {
            closeAdminChangePasswordPopup();
        }, 2000);
    } catch (error) {
        console.error('Error changing password:', error);
        errorDiv.textContent = 'An error occurred. Please try again.';
        errorDiv.style.display = 'block';
    }
}


