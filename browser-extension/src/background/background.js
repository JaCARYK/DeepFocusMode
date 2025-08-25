/**
 * Background service worker for Deep Focus Mode extension.
 * Handles communication with desktop client and enforces blocking rules.
 */

const API_BASE_URL = 'http://localhost:5000';
const CHECK_INTERVAL = 5000; // 5 seconds
const CACHE_DURATION = 30000; // 30 seconds

// Cache for blocking decisions
const blockCache = new Map();

// Active delays (domains that are in delay period)
const activeDelays = new Map();

// Extension state
let extensionEnabled = true;
let currentSession = null;

/**
 * Initialize extension on install/update
 */
chrome.runtime.onInstalled.addListener(async (details) => {
  console.log('Deep Focus Mode extension installed/updated', details);
  
  // Set default settings
  const settings = await chrome.storage.sync.get(['enabled', 'apiUrl']);
  if (!settings.enabled) {
    await chrome.storage.sync.set({ enabled: true });
  }
  if (!settings.apiUrl) {
    await chrome.storage.sync.set({ apiUrl: API_BASE_URL });
  }
  
  // Create context menu items
  chrome.contextMenus.create({
    id: 'toggle-focus-mode',
    title: 'Toggle Focus Mode',
    contexts: ['action']
  });
  
  // Start monitoring
  startMonitoring();
});

/**
 * Listen for navigation events
 */
chrome.webNavigation.onBeforeNavigate.addListener(
  async (details) => {
    // Only check main frame navigations
    if (details.frameId !== 0 || !extensionEnabled) {
      return;
    }
    
    const url = new URL(details.url);
    const domain = url.hostname;
    
    // Skip localhost and extension pages
    if (domain === 'localhost' || domain === '127.0.0.1' || 
        url.protocol === 'chrome-extension:') {
      return;
    }
    
    // Check if URL should be blocked
    const decision = await checkBlock(url.href);
    
    if (decision && decision.should_block) {
      handleBlockedNavigation(details.tabId, url.href, decision);
    }
  },
  { url: [{ schemes: ['http', 'https'] }] }
);

/**
 * Check if a URL should be blocked
 */
async function checkBlock(url) {
  try {
    // Check cache first
    const cached = blockCache.get(url);
    if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
      return cached.decision;
    }
    
    // Query desktop API
    const response = await fetch(`${API_BASE_URL}/api/check-block`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ url })
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const decision = await response.json();
    
    // Cache the decision
    blockCache.set(url, {
      decision,
      timestamp: Date.now()
    });
    
    return decision;
  } catch (error) {
    console.error('Failed to check block status:', error);
    return null;
  }
}

/**
 * Handle blocked navigation
 */
function handleBlockedNavigation(tabId, url, decision) {
  const { action, delay_seconds, reminder_message, remaining_focus_time } = decision;
  
  switch (action) {
    case 'block':
      // Immediate block - show block page
      showBlockPage(tabId, url, reminder_message);
      break;
      
    case 'delay':
      // Check if delay is active
      const delayKey = new URL(url).hostname;
      const existingDelay = activeDelays.get(delayKey);
      
      if (existingDelay && Date.now() < existingDelay.expiresAt) {
        // Still in delay period
        const remainingSeconds = Math.ceil(
          (existingDelay.expiresAt - Date.now()) / 1000
        );
        showDelayPage(tabId, url, remainingSeconds, reminder_message);
      } else {
        // Start new delay
        activeDelays.set(delayKey, {
          expiresAt: Date.now() + (delay_seconds * 1000)
        });
        showDelayPage(tabId, url, delay_seconds, reminder_message);
      }
      break;
      
    case 'conditional':
      // Show focus requirement
      showFocusRequirement(tabId, url, remaining_focus_time, reminder_message);
      break;
  }
  
  // Log block event
  logBlockEvent(url, action);
}

/**
 * Show block page in tab
 */
function showBlockPage(tabId, blockedUrl, message) {
  chrome.tabs.update(tabId, {
    url: chrome.runtime.getURL('src/blocked/blocked.html') +
         `?url=${encodeURIComponent(blockedUrl)}` +
         `&message=${encodeURIComponent(message || 'This site is blocked during focus time.')}`
  });
}

/**
 * Show delay page with countdown
 */
function showDelayPage(tabId, blockedUrl, delaySeconds, message) {
  chrome.tabs.update(tabId, {
    url: chrome.runtime.getURL('src/blocked/delay.html') +
         `?url=${encodeURIComponent(blockedUrl)}` +
         `&seconds=${delaySeconds}` +
         `&message=${encodeURIComponent(message || 'Access will be granted soon.')}`
  });
}

/**
 * Show focus requirement page
 */
function showFocusRequirement(tabId, blockedUrl, remainingSeconds, message) {
  const remainingMinutes = Math.ceil(remainingSeconds / 60);
  chrome.tabs.update(tabId, {
    url: chrome.runtime.getURL('src/blocked/focus.html') +
         `?url=${encodeURIComponent(blockedUrl)}` +
         `&minutes=${remainingMinutes}` +
         `&message=${encodeURIComponent(message || `Focus for ${remainingMinutes} more minutes to unlock this site.`)}`
  });
}

/**
 * Start monitoring focus session
 */
async function startMonitoring() {
  // Check session status periodically
  setInterval(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/status`);
      if (response.ok) {
        currentSession = await response.json();
        
        // Update extension badge
        updateBadge(currentSession.is_actively_coding);
      }
    } catch (error) {
      console.error('Failed to get session status:', error);
    }
  }, CHECK_INTERVAL);
}

/**
 * Update extension badge based on focus status
 */
function updateBadge(isActive) {
  if (isActive) {
    chrome.action.setBadgeText({ text: 'ON' });
    chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
  } else {
    chrome.action.setBadgeText({ text: '' });
  }
}

/**
 * Handle messages from content scripts and popup
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'getStatus':
      sendResponse({ 
        enabled: extensionEnabled, 
        session: currentSession 
      });
      break;
      
    case 'toggleExtension':
      extensionEnabled = !extensionEnabled;
      chrome.storage.sync.set({ enabled: extensionEnabled });
      sendResponse({ enabled: extensionEnabled });
      break;
      
    case 'overrideBlock':
      // Allow user to override a block (with logging)
      const domain = new URL(request.url).hostname;
      activeDelays.delete(domain);
      blockCache.delete(request.url);
      logOverride(request.url);
      sendResponse({ success: true });
      break;
      
    case 'getRules':
      // Fetch rules from API
      fetchRules().then(sendResponse);
      return true; // Will respond asynchronously
      
    case 'getStats':
      // Fetch statistics from API
      fetchStats().then(sendResponse);
      return true; // Will respond asynchronously
  }
});

/**
 * Fetch blocking rules from API
 */
async function fetchRules() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/rules`);
    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.error('Failed to fetch rules:', error);
  }
  return [];
}

/**
 * Fetch statistics from API
 */
async function fetchStats() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/stats/today`);
    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.error('Failed to fetch stats:', error);
  }
  return null;
}

/**
 * Log block event
 */
function logBlockEvent(url, action) {
  const event = {
    url,
    action,
    timestamp: new Date().toISOString()
  };
  
  // Store in local storage
  chrome.storage.local.get(['blockEvents'], (result) => {
    const events = result.blockEvents || [];
    events.push(event);
    
    // Keep only last 100 events
    if (events.length > 100) {
      events.shift();
    }
    
    chrome.storage.local.set({ blockEvents: events });
  });
}

/**
 * Log override event
 */
function logOverride(url) {
  // Send to API
  fetch(`${API_BASE_URL}/api/override`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ url, timestamp: new Date().toISOString() })
  }).catch(error => {
    console.error('Failed to log override:', error);
  });
}

/**
 * Handle alarms for delayed access
 */
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name.startsWith('delay-')) {
    const domain = alarm.name.replace('delay-', '');
    activeDelays.delete(domain);
    
    // Notify user that site is now accessible
    chrome.notifications.create({
      type: 'basic',
      iconUrl: '/assets/icon-128.png',
      title: 'Site Unblocked',
      message: `${domain} is now accessible.`
    });
  }
});

/**
 * Context menu handler
 */
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'toggle-focus-mode') {
    extensionEnabled = !extensionEnabled;
    chrome.storage.sync.set({ enabled: extensionEnabled });
    updateBadge(extensionEnabled && currentSession?.is_actively_coding);
  }
});