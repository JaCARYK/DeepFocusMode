/**
 * Popup script for Deep Focus Mode extension.
 * Handles UI interactions and displays current status.
 */

const API_BASE_URL = 'http://localhost:5000';

// DOM elements
let elements = {};

/**
 * Initialize popup when DOM is ready
 */
document.addEventListener('DOMContentLoaded', async () => {
  // Cache DOM elements
  elements = {
    toggleSwitch: document.getElementById('toggle-extension'),
    focusStatus: document.getElementById('focus-status'),
    activeApp: document.getElementById('active-app'),
    sessionTime: document.getElementById('session-time'),
    focusTime: document.getElementById('focus-time'),
    blocksCount: document.getElementById('blocks-count'),
    productivityScore: document.getElementById('productivity-score'),
    startFocusBtn: document.getElementById('start-focus'),
    viewRulesBtn: document.getElementById('view-rules'),
    openOptionsBtn: document.getElementById('open-options'),
    viewDashboard: document.getElementById('view-dashboard'),
    helpLink: document.getElementById('help-link')
  };
  
  // Load current state
  await loadStatus();
  await loadStats();
  
  // Set up event listeners
  setupEventListeners();
  
  // Update status every 5 seconds
  setInterval(loadStatus, 5000);
});

/**
 * Load current extension and session status
 */
async function loadStatus() {
  try {
    // Get extension status from background
    const response = await chrome.runtime.sendMessage({ action: 'getStatus' });
    
    if (response) {
      // Update toggle switch
      elements.toggleSwitch.checked = response.enabled;
      
      // Update session status
      if (response.session) {
        updateSessionDisplay(response.session);
      }
    }
    
    // Get detailed status from API
    const apiResponse = await fetch(`${API_BASE_URL}/api/status`);
    if (apiResponse.ok) {
      const status = await apiResponse.json();
      updateDetailedStatus(status);
    }
  } catch (error) {
    console.error('Failed to load status:', error);
    showConnectionError();
  }
}

/**
 * Load today's statistics
 */
async function loadStats() {
  try {
    const response = await chrome.runtime.sendMessage({ action: 'getStats' });
    
    if (response) {
      updateStatsDisplay(response);
    }
  } catch (error) {
    console.error('Failed to load stats:', error);
  }
}

/**
 * Update session display
 */
function updateSessionDisplay(session) {
  if (session.is_actively_coding) {
    elements.focusStatus.textContent = 'Active';
    elements.focusStatus.className = 'status-value active';
    
    if (session.current_session) {
      const duration = Math.round(session.current_session.duration_minutes);
      elements.sessionTime.textContent = formatDuration(duration);
    }
  } else {
    elements.focusStatus.textContent = 'Inactive';
    elements.focusStatus.className = 'status-value inactive';
    elements.sessionTime.textContent = '--:--';
  }
  
  elements.activeApp.textContent = session.current_app || 'Unknown';
}

/**
 * Update detailed status display
 */
function updateDetailedStatus(status) {
  // Update activity indicator
  const activityClass = status.keystroke_activity === 'high' ? 'high-activity' :
                       status.keystroke_activity === 'medium' ? 'medium-activity' :
                       status.keystroke_activity === 'low' ? 'low-activity' : '';
  
  if (activityClass) {
    elements.focusStatus.classList.add(activityClass);
  }
  
  // Update keystrokes per minute indicator
  if (status.keystrokes_per_minute > 0) {
    const kpmIndicator = document.createElement('span');
    kpmIndicator.className = 'kpm-indicator';
    kpmIndicator.textContent = `${Math.round(status.keystrokes_per_minute)} kpm`;
    elements.focusStatus.parentElement.appendChild(kpmIndicator);
  }
}

/**
 * Update statistics display
 */
function updateStatsDisplay(stats) {
  if (!stats) return;
  
  elements.focusTime.textContent = Math.round(stats.total_focus_minutes || 0);
  elements.blocksCount.textContent = stats.distractions_blocked || 0;
  elements.productivityScore.textContent = `${Math.round(stats.productivity_score || 0)}%`;
  
  // Update productivity score color
  const score = stats.productivity_score || 0;
  if (score >= 80) {
    elements.productivityScore.className = 'stat-value excellent';
  } else if (score >= 60) {
    elements.productivityScore.className = 'stat-value good';
  } else if (score >= 40) {
    elements.productivityScore.className = 'stat-value moderate';
  } else {
    elements.productivityScore.className = 'stat-value low';
  }
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
  // Toggle extension
  elements.toggleSwitch.addEventListener('change', async (e) => {
    const response = await chrome.runtime.sendMessage({ action: 'toggleExtension' });
    if (response) {
      showNotification(response.enabled ? 'Focus Mode Enabled' : 'Focus Mode Disabled');
    }
  });
  
  // Start focus session
  elements.startFocusBtn.addEventListener('click', async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions/start`, {
        method: 'POST'
      });
      
      if (response.ok) {
        showNotification('Focus session started!');
        await loadStatus();
      }
    } catch (error) {
      console.error('Failed to start session:', error);
      showNotification('Failed to start session. Is the desktop app running?', 'error');
    }
  });
  
  // View rules
  elements.viewRulesBtn.addEventListener('click', () => {
    chrome.tabs.create({ url: chrome.runtime.getURL('src/options/options.html#rules') });
    window.close();
  });
  
  // Open options
  elements.openOptionsBtn.addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
    window.close();
  });
  
  // View dashboard
  elements.viewDashboard.addEventListener('click', (e) => {
    e.preventDefault();
    chrome.tabs.create({ url: `${API_BASE_URL}/dashboard` });
    window.close();
  });
  
  // Help link
  elements.helpLink.addEventListener('click', (e) => {
    e.preventDefault();
    chrome.tabs.create({ url: 'https://github.com/yourusername/deep-focus-mode/wiki' });
    window.close();
  });
}

/**
 * Format duration in minutes to HH:MM format
 */
function formatDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  
  if (hours > 0) {
    return `${hours}:${mins.toString().padStart(2, '0')}`;
  } else {
    return `${mins} min`;
  }
}

/**
 * Show notification message
 */
function showNotification(message, type = 'success') {
  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.textContent = message;
  
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.classList.add('show');
  }, 10);
  
  setTimeout(() => {
    notification.classList.remove('show');
    setTimeout(() => notification.remove(), 300);
  }, 3000);
}

/**
 * Show connection error
 */
function showConnectionError() {
  elements.focusStatus.textContent = 'Disconnected';
  elements.focusStatus.className = 'status-value error';
  
  const errorMsg = document.createElement('div');
  errorMsg.className = 'connection-error';
  errorMsg.innerHTML = `
    <p>Cannot connect to desktop app</p>
    <small>Make sure the Deep Focus Mode desktop app is running</small>
  `;
  
  const statusSection = document.querySelector('.status-section');
  if (!statusSection.querySelector('.connection-error')) {
    statusSection.appendChild(errorMsg);
  }
}