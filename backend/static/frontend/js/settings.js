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

    } catch (error) {
        console.error('Failed to load settings:', error);
        showMessage('加载设置失败: ' + error.message, 'error');
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

