/**
 * Daily Report Page Logic
 *
 * Handles daily report generation, display, and paper interactions.
 */

let currentDate = new Date().toISOString().split('T')[0];
let currentReport = null;

/**
 * Initialize Daily Report page
 */
function initDailyReportPage() {
    console.log('Initializing Daily Report page...');

    // Set date selector to today
    const dateSelector = document.getElementById('reportDateSelector');
    if (dateSelector) {
        dateSelector.value = currentDate;
        dateSelector.addEventListener('change', (e) => {
            currentDate = e.target.value;
            loadReportForDate(currentDate);
        });
    }

    // Bind generate report button
    const generateBtn = document.getElementById('generateReportBtn');
    if (generateBtn) {
        generateBtn.addEventListener('click', generateNewReport);
    }

    // Load report for today
    loadReportForDate(currentDate);
}

/**
 * Load report for a specific date
 */
async function loadReportForDate(date) {
    try {
        const report = await API.getReportByDate(date);
        displayReport(report);
    } catch (error) {
        console.log('No report found for date:', date);
        showEmptyReportState();
    }
}

/**
 * Generate new daily report
 */
async function generateNewReport() {
    const btn = document.getElementById('generateReportBtn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';
    }

    try {
        const response = await API.generateReport({
            date: currentDate,
            top_k: 10
        });

        const taskId = response.task_id;

        // Poll for completion
        pollTaskCompletion(taskId, async () => {
            const report = await API.getReportByDate(currentDate);
            displayReport(report);
            showMessage('日报生成成功', 'success');
        });

    } catch (error) {
        console.error('Failed to generate report:', error);
        showMessage('生成日报失败: ' + error.message, 'error');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-magic"></i> 生成日报';
        }
    }
}

/**
 * Display report
 */
function displayReport(report) {
    currentReport = report;

    // Display highlights
    const highlightsCard = document.getElementById('highlightsCard');
    const highlightsContent = document.getElementById('highlightsContent');

    if (report.highlights && highlightsContent) {
        highlightsContent.innerHTML = marked.parse(report.highlights);
        if (highlightsCard) {
            highlightsCard.style.display = 'block';
        }
    } else {
        if (highlightsCard) {
            highlightsCard.style.display = 'none';
        }
    }

    // Display themes
    const themesContent = document.getElementById('themesContent');
    if (report.themes_used && report.themes_used.length > 0 && themesContent) {
        themesContent.innerHTML = report.themes_used.map(theme =>
            `<span class="tag-item">${theme}</span>`
        ).join('');
    }

    // Display papers
    const papersList = document.getElementById('reportPapersList');
    if (papersList) {
        if (report.papers && report.papers.length > 0) {
            papersList.innerHTML = report.papers.map(paper => createPaperCard(paper)).join('');
        } else {
            papersList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p>暂无论文</p>
                </div>
            `;
        }
    }
}

/**
 * Show empty report state
 */
function showEmptyReportState() {
    const highlightsCard = document.getElementById('highlightsCard');
    const themesContent = document.getElementById('themesContent');
    const papersList = document.getElementById('reportPapersList');

    if (highlightsCard) {
        highlightsCard.style.display = 'none';
    }

    if (themesContent) {
        themesContent.innerHTML = '';
    }

    if (papersList) {
        papersList.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-calendar-day"></i>
                <p>该日期暂无日报</p>
                <p style="font-size: 0.9rem; color: #666; margin-top: 10px;">
                    请点击右上角的"生成日报"按钮创建报告
                </p>
            </div>
        `;
    }
}

/**
 * View paper details
 */
async function viewPaperDetails(paperId) {
    try {
        const paper = await API.getPaper(paperId);
        const summaries = paper.has_summary ? await API.getPaperSummaries(paperId) : [];

        // Build modal content
        let content = `
            <div class="paper-detail">
                <h2>${paper.title}</h2>
                <div class="paper-meta-full">
                    <p><strong>作者:</strong> ${paper.authors || 'N/A'}</p>
                    <p><strong>来源:</strong> ${paper.source} (${paper.paper_id})</p>
                    <p><strong>发布日期:</strong> ${formatDate(paper.published_date)}</p>
                    ${paper.notes ? `<p><strong>笔记:</strong> ${paper.notes}</p>` : ''}
                </div>
                <div class="paper-abstract-full">
                    <h3>摘要</h3>
                    <p>${paper.abstract || 'N/A'}</p>
                </div>
        `;

        // Add summaries if available
        if (summaries.length > 0) {
            content += `
                <div class="paper-summaries">
                    <h3>AI 生成摘要</h3>
                    ${summaries.map(s => `
                        <div class="summary-section">
                            <h4>${s.step_name}</h4>
                            <div class="summary-content">${marked.parse(s.content)}</div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        // Add action buttons
        content += '<div class="modal-actions">';

        if (paper.has_pdf) {
            content += `
                <button class="btn btn-primary" onclick="API.downloadPaperPDF(${paper.id})">
                    <i class="fas fa-download"></i> 下载 PDF
                </button>
            `;
        }

        if (paper.has_summary) {
            content += `
                <button class="btn btn-secondary" onclick="regenerateSummary(${paper.id})">
                    <i class="fas fa-sync"></i> 重新生成摘要
                </button>
            `;
        } else if (paper.has_pdf) {
            content += `
                <button class="btn btn-success" onclick="generateSummary(${paper.id})">
                    <i class="fas fa-magic"></i> 生成摘要
                </button>
            `;
        }

        // Add note button
        content += `
            <button class="btn btn-secondary" onclick="openNoteModal(${paper.id})">
                <i class="fas fa-sticky-note"></i> 编辑笔记
            </button>
        `;

        // Add external link button
        content += `
            <a href="${paper.url}" target="_blank" class="btn btn-secondary">
                <i class="fas fa-external-link-alt"></i> 在原网站查看
            </a>
        `;

        content += '</div></div>';

        const modal = createModal('paperDetailModal', '论文详情', content);
        document.getElementById('modalContainer').appendChild(modal);
        openModal('paperDetailModal');

    } catch (error) {
        console.error('Failed to load paper details:', error);
        showMessage('加载论文详情失败: ' + error.message, 'error');
    }
}

/**
 * Mark paper as interested
 */
async function markPaperInterested(paperId) {
    try {
        await API.markPaper(paperId, 'interested');
        showMessage('已标记为感兴趣', 'success');
        loadReportForDate(currentDate); // Refresh to show updated status
    } catch (error) {
        console.error('Failed to mark paper:', error);
        showMessage('标记失败: ' + error.message, 'error');
    }
}

/**
 * Mark paper as not interested
 */
async function markPaperNotInterested(paperId) {
    try {
        await API.markPaper(paperId, 'not_interested');
        showMessage('已标记为不感兴趣', 'success');
        loadReportForDate(currentDate); // Refresh to show updated status
    } catch (error) {
        console.error('Failed to mark paper:', error);
        showMessage('标记失败: ' + error.message, 'error');
    }
}

/**
 * Generate paper summary (async)
 */
async function generateSummary(paperId) {
    try {
        const response = await API.summarizePaper(paperId);
        const taskId = response.task_id;

        showMessage('正在生成摘要...', 'info');

        // Poll for completion
        pollTaskCompletion(taskId, async () => {
            showMessage('摘要生成成功', 'success');
            closeModal('paperDetailModal');
            loadReportForDate(currentDate); // Refresh
        }, (error) => {
            showMessage('生成摘要失败: ' + error, 'error');
        });

    } catch (error) {
        console.error('Failed to generate summary:', error);
        showMessage('生成摘要失败: ' + error.message, 'error');
    }
}

/**
 * Regenerate paper summary
 */
async function regenerateSummary(paperId) {
    if (!confirm('确定要重新生成摘要吗？')) return;
    await generateSummary(paperId);
}

/**
 * Open note editing modal
 */
async function openNoteModal(paperId) {
    try {
        const paper = await API.getPaper(paperId);

        const content = `
            <form id="noteForm">
                <div class="form-group">
                    <label><i class="fas fa-sticky-note"></i> 笔记</label>
                    <textarea name="notes" rows="10" placeholder="输入笔记...">${paper.notes || ''}</textarea>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal('noteModal')">
                        取消
                    </button>
                    <button type="submit" class="btn btn-primary">
                        <i class="fas fa-save"></i> 保存
                    </button>
                </div>
            </form>
        `;

        closeModal('paperDetailModal'); // Close detail modal first

        const modal = createModal('noteModal', '编辑笔记', content);
        document.getElementById('modalContainer').appendChild(modal);
        openModal('noteModal');

        // Handle form submission
        document.getElementById('noteForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = getFormData('noteForm');

            try {
                await API.markPaper(paperId, 'interested', formData.notes);
                showMessage('笔记保存成功', 'success');
                closeModal('noteModal');
                loadReportForDate(currentDate); // Refresh
            } catch (error) {
                console.error('Failed to save note:', error);
                showMessage('保存失败: ' + error.message, 'error');
            }
        });

    } catch (error) {
        console.error('Failed to open note modal:', error);
        showMessage('打开笔记编辑器失败: ' + error.message, 'error');
    }
}
