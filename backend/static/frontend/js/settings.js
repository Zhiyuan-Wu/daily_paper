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

    // Initialize time dropdowns
    initializeTimeDropdowns();

    // Load user profile
    await loadUserProfile();

    // Load settings configuration
    await loadSettingsConfig();

    // Bind form submissions
    bindForms();
}

/**
 * Initialize time dropdowns for hour and minute selection
 */
function initializeTimeDropdowns() {
    // Populate hour dropdowns (0-23)
    const hourSelects = ['dailyHour', 'weeklyHour'];
    hourSelects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (select) {
            for (let i = 0; i < 24; i++) {
                const option = document.createElement('option');
                option.value = i;
                option.textContent = i.toString().padStart(2, '0');
                select.appendChild(option);
            }
            // Default to 9 AM
            select.value = 9;
        }
    });

    // Populate minute dropdowns (0, 15, 30, 45)
    const minuteSelects = ['dailyMinute', 'weeklyMinute'];
    minuteSelects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (select) {
            [0, 15, 30, 45].forEach(minute => {
                const option = document.createElement('option');
                option.value = minute;
                option.textContent = minute.toString().padStart(2, '0');
                select.appendChild(option);
            });
            // Default to 0
            select.value = 0;
        }
    });
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
        const scheduleTypeSelect = document.getElementById('scheduleType');
        const dailyHourSelect = document.getElementById('dailyHour');
        const dailyMinuteSelect = document.getElementById('dailyMinute');
        const weeklyDaySelect = document.getElementById('weeklyDay');
        const weeklyHourSelect = document.getElementById('weeklyHour');
        const weeklyMinuteSelect = document.getElementById('weeklyMinute');
        const statusText = document.getElementById('autoRefreshStatusText');
        const lastRunInfo = document.getElementById('lastRunInfo');

        if (enabledCheckbox) {
            enabledCheckbox.checked = config.enabled;
        }

        if (scheduleTypeSelect) {
            scheduleTypeSelect.value = config.schedule_type || 'daily';
            toggleScheduleType();
        }

        // Parse daily time (HH:MM format)
        if (config.daily_time) {
            const [dailyHour, dailyMinute] = config.daily_time.split(':').map(Number);
            if (dailyHourSelect) dailyHourSelect.value = dailyHour;
            if (dailyMinuteSelect) dailyMinuteSelect.value = dailyMinute;
        }

        if (weeklyDaySelect) {
            weeklyDaySelect.value = config.weekly_day ?? 1;
        }

        // Parse weekly time (HH:MM format)
        if (config.weekly_time) {
            const [weeklyHour, weeklyMinute] = config.weekly_time.split(':').map(Number);
            if (weeklyHourSelect) weeklyHourSelect.value = weeklyHour;
            if (weeklyMinuteSelect) weeklyMinuteSelect.value = weeklyMinute;
        }

        if (statusText) {
            statusText.textContent = config.enabled ? '已启用' : '禁用';
        }

        // Show last run info if available
        if (lastRunInfo && (config.last_run_at || config.next_run_at)) {
            lastRunInfo.style.display = 'block';

            const lastRunTime = document.getElementById('lastRunTime');
            const nextRunTime = document.getElementById('nextRunTime');

            if (lastRunTime && config.last_run_at) {
                lastRunTime.textContent = formatDate(config.last_run_at);
            }

            if (nextRunTime && config.next_run_at) {
                nextRunTime.textContent = formatDate(config.next_run_at);
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

    // Schedule type change handler
    const scheduleTypeSelect = document.getElementById('scheduleType');
    if (scheduleTypeSelect) {
        scheduleTypeSelect.addEventListener('change', toggleScheduleType);
    }

    // View history button handler
    const viewHistoryBtn = document.getElementById('viewHistoryBtn');
    if (viewHistoryBtn) {
        viewHistoryBtn.addEventListener('click', showTaskHistoryModal);
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
    const scheduleTypeSelect = document.getElementById('scheduleType');
    const dailyHourSelect = document.getElementById('dailyHour');
    const dailyMinuteSelect = document.getElementById('dailyMinute');
    const weeklyDaySelect = document.getElementById('weeklyDay');
    const weeklyHourSelect = document.getElementById('weeklyHour');
    const weeklyMinuteSelect = document.getElementById('weeklyMinute');

    const enabled = enabledCheckbox ? enabledCheckbox.checked : false;
    const scheduleType = scheduleTypeSelect ? scheduleTypeSelect.value : 'daily';

    // Format daily time as HH:MM
    const dailyHour = dailyHourSelect ? parseInt(dailyHourSelect.value) : 9;
    const dailyMinute = dailyMinuteSelect ? parseInt(dailyMinuteSelect.value) : 0;
    const dailyTime = `${dailyHour.toString().padStart(2, '0')}:${dailyMinute.toString().padStart(2, '0')}`;

    const weeklyDay = weeklyDaySelect ? parseInt(weeklyDaySelect.value) : 1;

    // Format weekly time as HH:MM
    const weeklyHour = weeklyHourSelect ? parseInt(weeklyHourSelect.value) : 9;
    const weeklyMinute = weeklyMinuteSelect ? parseInt(weeklyMinuteSelect.value) : 0;
    const weeklyTime = `${weeklyHour.toString().padStart(2, '0')}:${weeklyMinute.toString().padStart(2, '0')}`;

    try {
        await API.updateSchedulerConfig(
            enabled,
            scheduleType,
            dailyTime,
            weeklyDay,
            weeklyTime
        );
        showMessage('自动刷新配置已保存', 'success');

        // Reload config to update display
        await loadAutoRefreshConfig();
    } catch (error) {
        console.error('Failed to save auto refresh config:', error);
        showMessage('保存失败: ' + error.message, 'error');
    }
}

/**
 * Toggle schedule type fields visibility
 */
function toggleScheduleType() {
    const scheduleTypeSelect = document.getElementById('scheduleType');
    const dailyTimeGroup = document.getElementById('dailyTimeGroup');
    const weeklyGroup = document.getElementById('weeklyGroup');
    const weeklyTimeGroup = document.getElementById('weeklyTimeGroup');

    if (!scheduleTypeSelect) return;

    const scheduleType = scheduleTypeSelect.value;

    if (scheduleType === 'daily') {
        if (dailyTimeGroup) dailyTimeGroup.style.display = 'block';
        if (weeklyGroup) weeklyGroup.style.display = 'none';
        if (weeklyTimeGroup) weeklyTimeGroup.style.display = 'none';
    } else if (scheduleType === 'weekly') {
        if (dailyTimeGroup) dailyTimeGroup.style.display = 'none';
        if (weeklyGroup) weeklyGroup.style.display = 'block';
        if (weeklyTimeGroup) weeklyTimeGroup.style.display = 'block';
    }
}

/**
 * Show task history modal
 */
async function showTaskHistoryModal() {
    try {
        const history = await API.getTaskHistory(0, 20);

        if (!history.tasks || history.tasks.length === 0) {
            showMessage('暂无历史任务', 'info');
            return;
        }

        let content = `
            <div style="max-height: 500px; overflow-y: auto;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #f5f5f5; position: sticky; top: 0;">
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">类型</th>
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">状态</th>
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">进度</th>
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">开始时间</th>
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">操作</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        for (const task of history.tasks) {
            const statusClass = task.status === 'completed' ? 'color: #1f8459;' :
                               task.status === 'failed' ? 'color: #c23c3c;' :
                               'color: #666;';

            const statusText = task.status === 'completed' ? '已完成' :
                              task.status === 'failed' ? '失败' :
                              task.status === 'processing' ? '进行中' : '待处理';

            content += `
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 10px;">${task.task_type}</td>
                    <td style="padding: 10px; ${statusClass} font-weight: 500;">${statusText}</td>
                    <td style="padding: 10px;">${task.progress}%</td>
                    <td style="padding: 10px;">${formatDate(task.started_at)}</td>
                    <td style="padding: 10px;">
                        <button class="btn btn-secondary" onclick="viewTaskDetail('${task.task_id}')" style="padding: 5px 10px; font-size: 0.9rem;">
                            查看详情
                        </button>
                    </td>
                </tr>
            `;
        }

        content += `
                    </tbody>
                </table>
            </div>
        `;

        const modal = createModal('taskHistoryModal', '任务历史', content);
        document.getElementById('modalContainer').appendChild(modal);
        openModal('taskHistoryModal');

    } catch (error) {
        console.error('Failed to load task history:', error);
        showMessage('加载任务历史失败: ' + error.message, 'error');
    }
}

/**
 * View task detail
 */
async function viewTaskDetail(taskId) {
    try {
        const detail = await API.getTaskDetail(taskId);

        let content = `
            <div style="max-height: 500px; overflow-y: auto;">
                <div style="margin-bottom: 20px;">
                    <p><strong>任务ID:</strong> ${detail.task.task_id}</p>
                    <p><strong>类型:</strong> ${detail.task.task_type}</p>
                    <p><strong>状态:</strong> ${detail.task.status}</p>
                    <p><strong>进度:</strong> ${detail.task.progress}%</p>
                    <p><strong>开始时间:</strong> ${formatDate(detail.task.started_at)}</p>
                    ${detail.task.completed_at ? `<p><strong>完成时间:</strong> ${formatDate(detail.task.completed_at)}</p>` : ''}
                    ${detail.task.total_papers > 0 ? `<p><strong>总论文数:</strong> ${detail.task.total_papers}</p>` : ''}
                    ${detail.task.processed_papers > 0 ? `<p><strong>已处理:</strong> ${detail.task.processed_papers}</p>` : ''}
                    ${detail.task.error_message ? `<p style="color: #c23c3c;"><strong>错误:</strong> ${detail.task.error_message}</p>` : ''}
                </div>
                <h3 style="margin-bottom: 10px;">步骤详情</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #f5f5f5;">
                            <th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">步骤</th>
                            <th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">状态</th>
                            <th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">开始时间</th>
                            <th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">持续时间</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        if (detail.steps && detail.steps.length > 0) {
            for (const step of detail.steps) {
                const statusClass = step.status === 'completed' ? 'color: #1f8459;' :
                                   step.status === 'failed' ? 'color: #c23c3c;' :
                                   'color: #666;';

                const durationText = step.duration_ms ?
                    `${(step.duration_ms / 1000).toFixed(2)}秒` :
                    step.completed_at ? '-' : '进行中...';

                content += `
                    <tr style="border-bottom: 1px solid #eee;">
                        <td style="padding: 8px;">${step.step_name}</td>
                        <td style="padding: 8px; ${statusClass} font-weight: 500;">${step.status}</td>
                        <td style="padding: 8px;">${formatDate(step.started_at)}</td>
                        <td style="padding: 8px;">${durationText}</td>
                    </tr>
                `;
            }
        } else {
            content += `<tr><td colspan="4" style="padding: 10px; text-align: center;">暂无步骤数据</td></tr>`;
        }

        content += `
                    </tbody>
                </table>
            </div>
        `;

        closeModal('taskHistoryModal');

        const modal = createModal('taskDetailModal', '任务详情', content);
        document.getElementById('modalContainer').appendChild(modal);
        openModal('taskDetailModal');

    } catch (error) {
        console.error('Failed to load task detail:', error);
        showMessage('加载任务详情失败: ' + error.message, 'error');
    }
}

