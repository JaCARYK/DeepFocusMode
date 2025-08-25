/**
 * Content script for Deep Focus Mode extension.
 * Injected into web pages to handle blocking overlays and user interactions.
 */

// Check if we should show an overlay on this page
(function() {
  'use strict';
  
  // Don't run on extension pages or local files
  if (window.location.protocol === 'chrome-extension:' || 
      window.location.protocol === 'file:') {
    return;
  }
  
  let overlayElement = null;
  let countdownInterval = null;
  
  /**
   * Create blocking overlay
   */
  function createOverlay(message, options = {}) {
    // Remove existing overlay if any
    removeOverlay();
    
    // Create overlay container
    overlayElement = document.createElement('div');
    overlayElement.id = 'deep-focus-overlay';
    overlayElement.className = 'dfm-overlay';
    
    // Create content
    const content = document.createElement('div');
    content.className = 'dfm-overlay-content';
    
    // Logo/Icon
    const logo = document.createElement('div');
    logo.className = 'dfm-logo';
    logo.innerHTML = '🎯';
    content.appendChild(logo);
    
    // Title
    const title = document.createElement('h2');
    title.className = 'dfm-title';
    title.textContent = 'Stay Focused!';
    content.appendChild(title);
    
    // Message
    const messageEl = document.createElement('p');
    messageEl.className = 'dfm-message';
    messageEl.textContent = message;
    content.appendChild(messageEl);
    
    // Countdown if delay
    if (options.countdown) {
      const countdownEl = document.createElement('div');
      countdownEl.className = 'dfm-countdown';
      countdownEl.id = 'dfm-countdown';
      content.appendChild(countdownEl);
      startCountdown(options.countdown, countdownEl);
    }
    
    // Focus time remaining if conditional
    if (options.focusMinutes) {
      const focusEl = document.createElement('div');
      focusEl.className = 'dfm-focus-time';
      focusEl.innerHTML = `
        <div class="dfm-progress-ring">
          <svg width="120" height="120">
            <circle cx="60" cy="60" r="54" fill="none" stroke="#e0e0e0" stroke-width="4"/>
            <circle cx="60" cy="60" r="54" fill="none" stroke="#4CAF50" stroke-width="4"
                    stroke-dasharray="339.292" stroke-dashoffset="169.646"
                    transform="rotate(-90 60 60)"/>
          </svg>
          <div class="dfm-progress-text">${options.focusMinutes} min</div>
        </div>
        <p>Keep coding to unlock this site!</p>
      `;
      content.appendChild(focusEl);
    }
    
    // Actions
    const actions = document.createElement('div');
    actions.className = 'dfm-actions';
    
    // Back button
    const backBtn = document.createElement('button');
    backBtn.className = 'dfm-btn dfm-btn-primary';
    backBtn.textContent = 'Go Back';
    backBtn.onclick = () => window.history.back();
    actions.appendChild(backBtn);
    
    // Override button (with confirmation)
    if (options.allowOverride) {
      const overrideBtn = document.createElement('button');
      overrideBtn.className = 'dfm-btn dfm-btn-secondary';
      overrideBtn.textContent = 'Override (Not Recommended)';
      overrideBtn.onclick = () => handleOverride();
      actions.appendChild(overrideBtn);
    }
    
    content.appendChild(actions);
    
    // Tips section
    const tips = document.createElement('div');
    tips.className = 'dfm-tips';
    tips.innerHTML = `
      <h3>Quick Tips to Stay Focused:</h3>
      <ul>
        <li>Take a deep breath and remember your goals</li>
        <li>Set a timer for focused work sessions</li>
        <li>Reward yourself after completing tasks</li>
        <li>Keep a notepad for distracting thoughts</li>
      </ul>
    `;
    content.appendChild(tips);
    
    overlayElement.appendChild(content);
    
    // Add to page
    document.body.appendChild(overlayElement);
    
    // Prevent scrolling
    document.body.style.overflow = 'hidden';
  }
  
  /**
   * Remove overlay
   */
  function removeOverlay() {
    if (overlayElement) {
      overlayElement.remove();
      overlayElement = null;
      document.body.style.overflow = '';
    }
    
    if (countdownInterval) {
      clearInterval(countdownInterval);
      countdownInterval = null;
    }
  }
  
  /**
   * Start countdown timer
   */
  function startCountdown(seconds, element) {
    let remaining = seconds;
    
    function updateCountdown() {
      if (remaining <= 0) {
        clearInterval(countdownInterval);
        element.innerHTML = '<p>Access granted! Refreshing...</p>';
        setTimeout(() => {
          removeOverlay();
          window.location.reload();
        }, 1000);
        return;
      }
      
      const minutes = Math.floor(remaining / 60);
      const secs = remaining % 60;
      
      element.innerHTML = `
        <div class="dfm-countdown-circle">
          <svg width="200" height="200">
            <circle cx="100" cy="100" r="90" fill="none" stroke="#e0e0e0" stroke-width="8"/>
            <circle cx="100" cy="100" r="90" fill="none" stroke="#FF9800" stroke-width="8"
                    stroke-dasharray="${565.486 * (remaining / seconds)} 565.486"
                    transform="rotate(-90 100 100)"/>
          </svg>
          <div class="dfm-countdown-text">
            ${minutes}:${secs.toString().padStart(2, '0')}
          </div>
        </div>
        <p>Access will be granted in ${minutes} minute${minutes !== 1 ? 's' : ''} 
           ${secs} second${secs !== 1 ? 's' : ''}</p>
      `;
      
      remaining--;
    }
    
    updateCountdown();
    countdownInterval = setInterval(updateCountdown, 1000);
  }
  
  /**
   * Handle override request
   */
  function handleOverride() {
    const confirmed = confirm(
      'Are you sure you want to override this block?\n\n' +
      'This will be logged and may affect your productivity score.'
    );
    
    if (confirmed) {
      chrome.runtime.sendMessage({
        action: 'overrideBlock',
        url: window.location.href
      }, (response) => {
        if (response && response.success) {
          removeOverlay();
          window.location.reload();
        }
      });
    }
  }
  
  /**
   * Listen for messages from background script
   */
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    switch (request.action) {
      case 'showOverlay':
        createOverlay(request.message, request.options);
        sendResponse({ success: true });
        break;
        
      case 'removeOverlay':
        removeOverlay();
        sendResponse({ success: true });
        break;
        
      case 'checkOverlay':
        sendResponse({ hasOverlay: overlayElement !== null });
        break;
    }
  });
  
  /**
   * Check if this page should be blocked on load
   */
  function checkInitialBlock() {
    // Send current URL to background script for checking
    chrome.runtime.sendMessage({
      action: 'checkUrl',
      url: window.location.href
    }, (response) => {
      if (response && response.shouldBlock) {
        createOverlay(response.message, response.options);
      }
    });
  }
  
  // Don't check on back/forward navigation - let webNavigation API handle it
  if (window.performance && window.performance.navigation.type === 0) {
    // Type 0 is a normal navigation (not back/forward)
    // Delay check to ensure page is ready
    setTimeout(checkInitialBlock, 100);
  }
})();