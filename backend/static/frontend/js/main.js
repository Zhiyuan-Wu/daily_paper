/**
 * Main Application Entry Point
 *
 * Handles page navigation and initialization.
 */

let currentPage = 'daily-report';

/**
 * Initialize the application
 */
function initApp() {
    console.log('Initializing Daily Paper app...');

    // Initialize page navigation
    initNavigation();

    // Initialize current page
    initCurrentPage();

    console.log('App initialized successfully');
}

/**
 * Initialize navigation event listeners
 */
function initNavigation() {
    // Sidebar navigation (PC)
    document.querySelectorAll('.sidebar-nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            if (page && page !== currentPage) {
                navigateToPage(page);
            }
        });
    });

    // Mobile bottom navigation
    document.querySelectorAll('.mobile-bottom-nav .nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            if (page && page !== currentPage) {
                navigateToPage(page);
            }
        });
    });

    // Mobile hamburger menu
    const hamburgerBtn = document.getElementById('hamburgerBtn');
    if (hamburgerBtn) {
        hamburgerBtn.addEventListener('click', toggleMobileSidebar);
    }

    // Close mobile sidebar when clicking outside
    document.addEventListener('click', (e) => {
        const sidebar = document.querySelector('.sidebar');
        const hamburgerBtn = document.getElementById('hamburgerBtn');

        if (window.innerWidth <= 768 &&
            sidebar &&
            !sidebar.contains(e.target) &&
            !hamburgerBtn.contains(e.target) &&
            sidebar.classList.contains('active')) {
            closeMobileSidebar();
        }
    });
}

/**
 * Navigate to a specific page
 */
function navigateToPage(pageName) {
    console.log(`Navigating to: ${pageName}`);

    // Validate page name
    const validPages = ['daily-report', 'paper-explorer', 'settings'];
    if (!validPages.includes(pageName)) {
        console.error(`Invalid page name: ${pageName}`);
        return;
    }

    // Hide all pages
    document.querySelectorAll('.page-content').forEach(page => {
        page.classList.remove('active');
        page.style.display = 'none';
    });

    // Show target page
    const targetPage = document.getElementById(`${pageName}-page`);
    if (targetPage) {
        targetPage.classList.add('active');
        targetPage.style.display = 'block';
    } else {
        console.error(`Page not found: ${pageName}-page`);
        return;
    }

    // Update navigation active state
    document.querySelectorAll('.sidebar-nav-item, .mobile-bottom-nav .nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.page === pageName) {
            item.classList.add('active');
        }
    });

    // Update current page
    currentPage = pageName;

    // Initialize page
    initCurrentPage();

    // Close mobile sidebar
    closeMobileSidebar();

    // Scroll to top
    window.scrollTo(0, 0);
}

/**
 * Initialize the current page
 */
function initCurrentPage() {
    console.log(`Initializing page: ${currentPage}`);

    try {
        switch (currentPage) {
            case 'daily-report':
                if (typeof initDailyReportPage === 'function') {
                    initDailyReportPage();
                }
                break;
            case 'paper-explorer':
                if (typeof initPaperExplorerPage === 'function') {
                    initPaperExplorerPage();
                }
                break;
            case 'settings':
                if (typeof initSettingsPage === 'function') {
                    initSettingsPage();
                }
                break;
            default:
                console.warn(`No initialization function for page: ${currentPage}`);
        }
    } catch (error) {
        console.error(`Error initializing page ${currentPage}:`, error);
        showMessage(`页面初始化失败: ${error.message}`, 'error');
    }
}

/**
 * Toggle mobile sidebar
 */
function toggleMobileSidebar() {
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
        sidebar.classList.toggle('active');
    }
}

/**
 * Close mobile sidebar
 */
function closeMobileSidebar() {
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
        sidebar.classList.remove('active');
    }
}

/**
 * Format date for display
 */
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';

    const date = new Date(dateStr);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
        return '今天';
    } else if (diffDays === 1) {
        return '昨天';
    } else if (diffDays < 7) {
        return `${diffDays}天前`;
    } else if (diffDays < 30) {
        return `${Math.floor(diffDays / 7)}周前`;
    } else if (diffDays < 365) {
        return `${Math.floor(diffDays / 30)}月前`;
    } else {
        return date.toLocaleDateString('zh-CN');
    }
}

/**
 * Get form data as object
 */
function getFormData(formId) {
    const form = document.querySelector(`#${formId}`);
    if (!form) return {};

    const formData = new FormData(form);
    const data = {};

    for (let [key, value] of formData.entries()) {
        data[key] = value;
    }

    return data;
}

/**
 * Set form data from object
 */
function setFormData(formId, data) {
    const form = document.querySelector(`#${formId}`);
    if (!form) return;

    Object.keys(data).forEach(key => {
        const input = form.querySelector(`[name="${key}"]`);
        if (input) {
            input.value = data[key] || '';
        }
    });
}

/**
 * Create paper card HTML
 */
function createPaperCard(paper, compact = false) {
    const statusBadge = paper.interaction_status === 'interested'
        ? '<span class="tag-item status-interested">感兴趣</span>'
        : paper.interaction_status === 'not_interested'
        ? '<span class="tag-item status-not-interested">不感兴趣</span>'
        : '';

    // Determine button active states
    const interestedBtnClass = paper.interaction_status === 'interested' ? ' btn-active-success' : '';
    const notInterestedBtnClass = paper.interaction_status === 'not_interested' ? ' btn-active-danger' : '';

    // Determine content display: TLDR if available, otherwise abstract
    const displayContent = paper.tldr
        ? `<div class="paper-tldr${compact ? '-compact' : ''}"><strong>TLDR:</strong> ${compact ? (paper.tldr.length > 150 ? paper.tldr.substring(0, 150) + '...' : paper.tldr) : paper.tldr}</div>`
        : paper.abstract
            ? `<p class="paper-abstract${compact ? '-compact' : ''}">${paper.abstract.substring(compact ? 0 : 0, compact ? 150 : 300)}${(paper.abstract.length > (compact ? 150 : 300)) ? '...' : ''}</p>`
            : `<p class="paper-abstract${compact ? '-compact' : ''}">N/A</p>`;

    if (compact) {
        return `
            <div class="paper-card compact" data-paper-id="${paper.id}" data-status="${paper.interaction_status || 'no_action'}">
                <h4 class="paper-title-compact">${paper.title}</h4>
                <div class="paper-meta-compact">
                    <span class="paper-source">${paper.source}</span>
                    <span class="paper-date">${formatDate(paper.published_date)}</span>
                    ${statusBadge}
                </div>
                ${displayContent}
                <div class="paper-card-actions">
                    <button class="btn btn-sm btn-primary" onclick="viewPaperDetails(${paper.id})">
                        <i class="fas fa-eye"></i> 查看详情
                    </button>
                    <button class="btn btn-sm btn-success${interestedBtnClass}" onclick="togglePaperInterest(${paper.id}, 'interested', this)" title="感兴趣">
                        <i class="fas fa-thumbs-up"></i>
                    </button>
                    <button class="btn btn-sm btn-danger${notInterestedBtnClass}" onclick="togglePaperInterest(${paper.id}, 'not_interested', this)" title="不感兴趣">
                        <i class="fas fa-thumbs-down"></i>
                    </button>
                </div>
            </div>
        `;
    } else {
        return `
            <div class="paper-card" data-paper-id="${paper.id}" data-status="${paper.interaction_status || 'no_action'}">
                <div class="paper-card-header">
                    <h3 class="paper-title">${paper.title}</h3>
                    <div class="paper-actions">
                        ${statusBadge}
                        <button class="action-btn" onclick="viewPaperDetails(${paper.id})" title="查看详情">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="action-btn${interestedBtnClass}" onclick="togglePaperInterest(${paper.id}, 'interested', this)" title="感兴趣">
                            <i class="fas fa-thumbs-up"></i>
                        </button>
                        <button class="action-btn${notInterestedBtnClass}" onclick="togglePaperInterest(${paper.id}, 'not_interested', this)" title="不感兴趣">
                            <i class="fas fa-thumbs-down"></i>
                        </button>
                    </div>
                </div>
                <div class="paper-meta">
                    <span class="paper-source">${paper.source}</span>
                    <span class="paper-authors">${paper.authors || 'Unknown'}</span>
                    <span class="paper-date">${formatDate(paper.published_date)}</span>
                </div>
                ${displayContent}
            </div>
        `;
    }
}

/**
 * Toggle paper interest status (can turn on or off)
 */
async function togglePaperInterest(paperId, action, buttonElement) {
    const card = buttonElement.closest('.paper-card');
    const currentStatus = card.dataset.status || 'no_action';

    // Get both buttons
    const interestedBtn = card.querySelector('button[onclick*="interested"]');
    const notInterestedBtn = card.querySelector('button[onclick*="not_interested"]');

    // If clicking the same action that's already active, remove it (set to no_action)
    if (currentStatus === action) {
        try {
            await API.clearPaperAction(paperId);
            showMessage('已取消标记', 'success');

            // Update button states
            updateButtonStates(card, 'no_action');

            // Refresh current page
            if (typeof loadPapers === 'function') {
                const page = window.currentPaperPage || 1;
                loadPapers(page);
            } else if (typeof loadDailyReport === 'function') {
                loadDailyReport();
            }
        } catch (error) {
            console.error('Failed to clear paper action:', error);
            showMessage('取消标记失败: ' + error.message, 'error');
        }
    } else {
        // Set new action
        try {
            await API.markPaper(paperId, action);
            showMessage(action === 'interested' ? '已标记为感兴趣' : '已标记为不感兴趣', 'success');

            // Update button states
            updateButtonStates(card, action);

            // Refresh current page
            if (typeof loadPapers === 'function') {
                const page = window.currentPaperPage || 1;
                loadPapers(page);
            } else if (typeof loadDailyReport === 'function') {
                loadDailyReport();
            }
        } catch (error) {
            console.error('Failed to mark paper:', error);
            showMessage('标记失败: ' + error.message, 'error');
        }
    }
}

/**
 * Update button visual states based on status
 */
function updateButtonStates(card, status) {
    const interestedBtn = card.querySelector('button[onclick*="interested"]');
    const notInterestedBtn = card.querySelector('button[onclick*="not_interested"]');

    // Remove all active classes
    interestedBtn.classList.remove('btn-active-success');
    notInterestedBtn.classList.remove('btn-active-danger');

    // Add active class based on status
    if (status === 'interested') {
        interestedBtn.classList.add('btn-active-success');
    } else if (status === 'not_interested') {
        notInterestedBtn.classList.add('btn-active-danger');
    }

    // Update card data attribute
    card.dataset.status = status;
}

/**
 * Reset generate button state
 */
function resetGenerateButton() {
    const btn = document.getElementById('generateReportBtn');
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-magic"></i> 生成日报';
    }
}

/**
 * Poll task completion
 */
async function pollTaskCompletion(taskId, onComplete, onError) {
    const maxAttempts = 60; // 5 minutes
    let attempts = 0;

    const poll = setInterval(async () => {
        attempts++;

        try {
            const status = await API.getTaskStatus(taskId);

            if (status.status === 'completed' || attempts >= maxAttempts) {
                clearInterval(poll);
                await onComplete();
                resetGenerateButton();
            } else if (status.status === 'failed') {
                clearInterval(poll);
                if (onError) {
                    onError(status.error || '任务失败');
                } else {
                    showMessage('任务失败: ' + (status.error || 'Unknown error'), 'error');
                }
                resetGenerateButton();
            }
        } catch (error) {
            clearInterval(poll);
            if (onError) {
                onError(error.message);
            } else {
                showMessage('任务查询失败: ' + error.message, 'error');
            }
            resetGenerateButton();
        }
    }, 5000); // Poll every 5 seconds
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', initApp);
