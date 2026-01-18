/**
 * Paper Explorer Page Logic
 *
 * Handles paper browsing, searching, filtering, and pagination.
 */

let currentPaperPage = 1;
const pageSize = 20;
let totalPapers = 0;

/**
 * Initialize Paper Explorer page
 */
function initPaperExplorerPage() {
    console.log('Initializing Paper Explorer page...');

    // Bind search button
    const searchBtn = document.getElementById('searchPapersBtn');
    if (searchBtn) {
        searchBtn.addEventListener('click', () => loadPapers(1));
    }

    // Bind reset button
    const resetBtn = document.getElementById('resetFiltersBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', resetFilters);
    }

    // Bind enter key on search input
    const searchInput = document.getElementById('searchKeyword');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                loadPapers(1);
            }
        });
    }

    // Load initial papers
    loadPapers(1);
}

/**
 * Fetch new papers from sources
 */
async function fetchNewPapers() {
    const btn = document.getElementById('fetchPapersBtn');
    if (!btn) return;

    try {
        // Confirm before starting
        if (!confirm('确定要获取新论文吗？这将从arXiv和HuggingFace下载、解析并总结论文，可能需要较长时间。')) {
            return;
        }

        // Disable button and show loading
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在获取...';

        // Start fetch task
        const response = await API.fetchPapers(true, true);
        const taskId = response.task_id;

        showMessage('正在获取新论文...', 'info');

        // Poll for completion
        pollFetchTaskCompletion(taskId, () => {
            showMessage('论文获取成功！', 'success');
            // Refresh papers list
            loadPapers(1);
        });

    } catch (error) {
        console.error('Failed to fetch papers:', error);
        showMessage('获取论文失败: ' + error.message, 'error');
    } finally {
        // Re-enable button
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-download"></i> 获取新论文';
        }
    }
}

/**
 * Poll fetch task completion
 */
async function pollFetchTaskCompletion(taskId, onComplete) {
    const maxAttempts = 120; // 10 minutes
    let attempts = 0;

    const poll = setInterval(async () => {
        attempts++;

        try {
            const status = await API.getRefreshTaskStatus(taskId);

            // Update UI with progress
            const btn = document.getElementById('fetchPapersBtn');
            if (btn && status.step) {
                const stepNames = {
                    'downloading': '下载中',
                    'parsing': '解析中',
                    'summarizing': '总结中',
                    'completed': '完成'
                };
                const stepText = stepNames[status.step] || status.step;
                btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${stepText} (${status.progress}%)`;
            }

            if (status.status === 'completed' || attempts >= maxAttempts) {
                clearInterval(poll);
                await onComplete();
            } else if (status.status === 'failed') {
                clearInterval(poll);
                showMessage('获取论文失败: ' + (status.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            clearInterval(poll);
            showMessage('查询任务状态失败: ' + error.message, 'error');
        }
    }, 5000); // Poll every 5 seconds
}

/**
 * Load papers with filters
 */
async function loadPapers(page = 1) {
    currentPaperPage = page;

    const params = {
        keyword: document.getElementById('searchKeyword').value.trim(),
        source: document.getElementById('filterSource').value,
        interaction_status: document.getElementById('filterInteraction').value,
        page: page,
        page_size: pageSize
    };

    try {
        const response = await API.getPapers(params);
        displayPapers(response.papers);
        displayPagination(response.total, response.page, response.page_size);
        totalPapers = response.total;
    } catch (error) {
        console.error('Failed to load papers:', error);
        showMessage('加载论文失败: ' + error.message, 'error');
    }
}

/**
 * Display papers in grid
 */
function displayPapers(papers) {
    const grid = document.getElementById('papersGrid');

    if (!grid) return;

    if (papers.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-search"></i>
                <p>暂无论文</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = papers.map(paper => createPaperCard(paper, true)).join('');
}

/**
 * Display pagination controls
 */
function displayPagination(total, page, page_size) {
    const pagination = document.getElementById('papersPagination');

    if (!pagination) return;

    const totalPages = Math.ceil(total / page_size);

    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }

    let html = '<div class="pagination">';

    // Previous button
    if (page > 1) {
        html += `<button class="btn btn-sm btn-secondary" onclick="loadPapers(${page - 1})">上一页</button>`;
    }

    // Page numbers
    const startPage = Math.max(1, page - 2);
    const endPage = Math.min(totalPages, page + 2);

    if (startPage > 1) {
        html += `<button class="btn btn-sm btn-secondary" onclick="loadPapers(1)">1</button>`;
        if (startPage > 2) {
            html += '<span class="pagination-ellipsis">...</span>';
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        const activeClass = i === page ? 'btn-primary' : 'btn-secondary';
        html += `<button class="btn btn-sm ${activeClass}" onclick="loadPapers(${i})">${i}</button>`;
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            html += '<span class="pagination-ellipsis">...</span>';
        }
        html += `<button class="btn btn-sm btn-secondary" onclick="loadPapers(${totalPages})">${totalPages}</button>`;
    }

    // Next button
    if (page < totalPages) {
        html += `<button class="btn btn-sm btn-secondary" onclick="loadPapers(${page + 1})">下一页</button>`;
    }

    html += '</div>';
    html += `<div class="pagination-info">共 ${total} 篇论文，第 ${page}/${totalPages} 页</div>`;

    pagination.innerHTML = html;
}

/**
 * Reset filters and reload papers
 */
function resetFilters() {
    document.getElementById('searchKeyword').value = '';
    document.getElementById('filterSource').value = '';
    document.getElementById('filterInteraction').value = '';
    loadPapers(1);
}

/**
 * View paper details (opens modal)
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
            loadPapers(currentPaperPage); // Refresh
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
                loadPapers(currentPaperPage); // Refresh
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
