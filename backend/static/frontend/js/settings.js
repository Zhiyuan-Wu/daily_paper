/**
 * Settings Page Logic
 *
 * Handles user interests, paper sources, and AI service configuration.
 */

/**
 * Initialize Settings page
 */
async function initSettingsPage() {
    console.log('Initializing Settings page...');

    // Load user profile
    await loadUserProfile();

    // Load settings configuration
    await loadSettingsConfig();

    // Bind form submissions
    bindForms();
}

/**
 * Load user profile and populate interests form
 */
async function loadUserProfile() {
    try {
        const profile = await API.getUserProfile();
        setFormData('interestsForm', {
            interested_keywords: profile.interested_keywords || '',
            disinterested_keywords: profile.disinterested_keywords || '',
            interest_description: profile.interest_description || ''
        });
    } catch (error) {
        console.error('Failed to load user profile:', error);
        showMessage('加载用户信息失败: ' + error.message, 'error');
    }
}

/**
 * Load settings configuration
 */
async function loadSettingsConfig() {
    try {
        const settings = await API.getSettings();

        // Populate sources form
        setFormData('sourcesForm', {
            arxiv_categories: settings.sources.arxiv_categories || '',
            max_results: settings.sources.max_results || 30
        });

        // Populate AI config form (without API key for security)
        setFormData('aiConfigForm', {
            llm_provider: settings.ai.llm_provider || 'openai',
            openai_api_base: settings.ai.openai_api_base || '',
            openai_model: settings.ai.openai_model || ''
        });

        // Populate recommendation config form
        setFormData('recommendationConfigForm', {
            recommend_strategies: settings.recommendation.strategies || '',
            recommend_top_k: settings.recommendation.top_k || 10,
            recommend_min_similarity: settings.recommendation.min_similarity || 0.5
        });

        // Load auto refresh config
        await loadAutoRefreshConfig();

    } catch (error) {
        console.error('Failed to load settings:', error);
        showMessage('加载设置失败: ' + error.message, 'error');
    }
}

/**
 * Load auto refresh configuration
 */
async function loadAutoRefreshConfig() {
    try {
        const config = await API.getSchedulerStatus();

        // Update form
        const enabledCheckbox = document.getElementById('autoRefreshEnabled');
        const intervalInput = document.getElementById('autoRefreshInterval');
        const statusText = document.getElementById('autoRefreshStatusText');
        const lastRunInfo = document.getElementById('lastRunInfo');

        if (enabledCheckbox) {
            enabledCheckbox.checked = config.enabled;
        }

        if (intervalInput) {
            intervalInput.value = config.interval_hours || 24;
        }

        if (statusText) {
            statusText.textContent = config.enabled ? '已启用' : '禁用';
        }

        // Show last run info if available
        if (lastRunInfo && (config.last_run || config.next_run)) {
            lastRunInfo.style.display = 'block';

            const lastRunTime = document.getElementById('lastRunTime');
            const nextRunTime = document.getElementById('nextRunTime');

            if (lastRunTime && config.last_run) {
                lastRunTime.textContent = formatDate(config.last_run);
            }

            if (nextRunTime && config.next_run) {
                nextRunTime.textContent = formatDate(config.next_run);
            }
        }

    } catch (error) {
        console.error('Failed to load auto refresh config:', error);
    }
}

/**
 * Bind form submission handlers
 */
function bindForms() {
    // Interests form
    const interestsForm = document.getElementById('interestsForm');
    if (interestsForm) {
        interestsForm.addEventListener('submit', saveInterests);
    }

    // Sources form
    const sourcesForm = document.getElementById('sourcesForm');
    if (sourcesForm) {
        sourcesForm.addEventListener('submit', saveSources);
    }

    // AI config form
    const aiConfigForm = document.getElementById('aiConfigForm');
    if (aiConfigForm) {
        aiConfigForm.addEventListener('submit', saveAIConfig);
    }

    // Recommendation config form
    const recommendationConfigForm = document.getElementById('recommendationConfigForm');
    if (recommendationConfigForm) {
        recommendationConfigForm.addEventListener('submit', saveRecommendationConfig);
    }

    // Auto refresh form
    const autoRefreshForm = document.getElementById('autoRefreshForm');
    if (autoRefreshForm) {
        autoRefreshForm.addEventListener('submit', saveAutoRefreshConfig);
    }

    // Toggle checkbox change handler
    const enabledCheckbox = document.getElementById('autoRefreshEnabled');
    if (enabledCheckbox) {
        enabledCheckbox.addEventListener('change', (e) => {
            const statusText = document.getElementById('autoRefreshStatusText');
            if (statusText) {
                statusText.textContent = e.target.checked ? '已启用' : '禁用';
            }
        });
    }
}

/**
 * Save user interests
 */
async function saveInterests(e) {
    e.preventDefault();
    const formData = getFormData('interestsForm');

    try {
        await API.updateUserProfile(formData);
        showMessage('保存成功', 'success');
    } catch (error) {
        console.error('Failed to save interests:', error);
        showMessage('保存失败: ' + error.message, 'error');
    }
}

/**
 * Save paper sources configuration
 */
async function saveSources(e) {
    e.preventDefault();
    const formData = getFormData('sourcesForm');

    try {
        await API.updateSources(formData);
        showMessage('保存成功。服务器重启后生效。', 'success');
    } catch (error) {
        console.error('Failed to save sources:', error);
        showMessage('保存失败: ' + error.message, 'error');
    }
}

/**
 * Save AI service configuration
 */
async function saveAIConfig(e) {
    e.preventDefault();
    const formData = getFormData('aiConfigForm');

    try {
        await API.updateAIConfig(formData);
        showMessage('保存成功。服务器重启后生效。', 'success');
    } catch (error) {
        console.error('Failed to save AI config:', error);
        showMessage('保存失败: ' + error.message, 'error');
    }
}

/**
 * Save recommendation configuration
 */
async function saveRecommendationConfig(e) {
    e.preventDefault();
    const formData = getFormData('recommendationConfigForm');

    try {
        await API.updateRecommendationConfig(formData);
        showMessage('保存成功。服务器重启后生效。', 'success');
    } catch (error) {
        console.error('Failed to save recommendation config:', error);
        showMessage('保存失败: ' + error.message, 'error');
    }
}

/**
 * Save auto refresh configuration
 */
async function saveAutoRefreshConfig(e) {
    e.preventDefault();

    const enabledCheckbox = document.getElementById('autoRefreshEnabled');
    const intervalInput = document.getElementById('autoRefreshInterval');

    const enabled = enabledCheckbox ? enabledCheckbox.checked : false;
    const intervalHours = intervalInput ? parseInt(intervalInput.value) : 24;

    try {
        await API.updateSchedulerConfig(enabled, intervalHours);
        showMessage('自动刷新配置已保存', 'success');

        // Reload config to update display
        await loadAutoRefreshConfig();
    } catch (error) {
        console.error('Failed to save auto refresh config:', error);
        showMessage('保存失败: ' + error.message, 'error');
    }
}
