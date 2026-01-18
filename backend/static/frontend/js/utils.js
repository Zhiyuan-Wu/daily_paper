/**
 * 工具函数
 */

const API_BASE = '/api';

// 全局缓存
const cache = {
    suppliers: null,
    suppliersTimestamp: null
};

// 模态框计数器（用于背景滚动锁定）
let modalCount = 0;

// 缓存过期时间（毫秒）
const CACHE_EXPIRY = 1 * 60 * 1000; // 1分钟

/**
 * 发送API请求
 * @param {string} url - API路径
 * @param {object} options - 请求选项
 * @returns {Promise} 响应数据
 */
window.apiRequest = async function apiRequest(url, options = {}) {
    const defaultOptions = {
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
        },
    };
    
    const mergedOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers,
        },
    };
    
    try {
        const response = await fetch(`${API_BASE}${url}`, mergedOptions);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || '请求失败');
        }
        
        return data;
    } catch (error) {
        console.error('API请求错误:', error);
        throw error;
    }
}

/**
 * 显示消息提示
 * @param {string} message - 消息内容
 * @param {string} type - 消息类型: 'success', 'error', 'warning'
 * @param {number} duration - 显示时长（毫秒）
 */
window.showMessage = function showMessage(message, type = 'success', duration = 3000) {
    const messageEl = document.getElementById('message');
    if (!messageEl) {
        const msg = document.createElement('div');
        msg.id = 'message';
        msg.className = `message ${type}`;
        document.body.appendChild(msg);
    }
    
    const msg = document.getElementById('message');
    msg.textContent = message;
    msg.className = `message ${type}`;
    msg.classList.remove('hidden');
    
    setTimeout(() => {
        msg.classList.add('hidden');
    }, duration);
}

/**
 * 格式化日期
 * @param {string|Date} date - 日期（UTC时间字符串或Date对象）
 * @returns {string} 格式化后的日期字符串（本地时间）
 */
window.formatDate = function formatDate(date) {
    if (!date) return '';
    const d = new Date(date);
    if (isNaN(d.getTime())) {
        return '';
    }
    return d.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
        timeZone: 'Asia/Shanghai'
    });
}

/**
 * 格式化金额
 * @param {number} amount - 金额
 * @param {number} decimals - 小数位数
 * @returns {string} 格式化后的金额字符串
 */
window.formatCurrency = function formatCurrency(amount, decimals = 2) {
    if (amount === null || amount === undefined) return '-';
    return amount.toFixed(decimals);
}

/**
 * 确认对话框
 * @param {string} message - 确认消息
 * @returns {Promise<boolean>} 用户确认结果
 */
window.confirmDialog = function confirmDialog(message) {
    return new Promise((resolve) => {
        if (confirm(message)) {
            resolve(true);
        } else {
            resolve(false);
        }
    });
}

/**
 * 创建模态框元素
 * @param {string} modalId - 模态框ID
 * @param {string} title - 模态框标题
 * @param {string} content - 模态框内容（HTML）
 * @returns {HTMLElement} 模态框DOM元素
 */
window.createModal = function createModal(modalId, title, content) {
    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal';
    modal.style.display = 'none';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>${title}</h2>
                <span class="close-btn" onclick="closeModal('${modalId}')">&times;</span>
            </div>
            <div class="modal-body">
                ${content}
            </div>
        </div>
    `;
    return modal;
};

/**
 * 打开模态框
 * @param {string} modalId - 模态框ID
 */
window.openModal = function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'block';
        modalCount++;
        // 锁定背景滚动（所有设备）
        document.body.style.overflow = 'hidden';
        document.body.style.position = 'fixed';
        document.body.style.width = '100%';
    }
}

/**
 * 关闭模态框
 * @param {string} modalId - 模态框ID
 */
window.closeModal = function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        // 从DOM中移除模态框，避免重复元素和事件监听器
        modal.remove();
        modalCount--;
        // 只有没有其他模态框时才恢复滚动
        if (modalCount <= 0) {
            modalCount = 0;
            document.body.style.overflow = '';
            document.body.style.position = '';
            document.body.style.width = '';
        }
    }
}

/**
 * 清空表单
 * @param {string|HTMLElement} formId - 表单ID或表单元素
 */
window.clearForm = function clearForm(formId) {
    const form = typeof formId === 'string' ? document.getElementById(formId) : formId;
    if (form) {
        form.reset();
    }
}

/**
 * 获取表单数据
 * @param {string|HTMLElement} formId - 表单ID或表单元素
 * @returns {object} 表单数据对象
 */
window.getFormData = function getFormData(formId) {
    const form = typeof formId === 'string' ? document.getElementById(formId) : formId;
    if (!form) return {};
    
    const formData = new FormData(form);
    const data = {};
    for (const [key, value] of formData.entries()) {
        data[key] = value;
    }
    return data;
}

/**
 * 设置表单数据
 * @param {string|HTMLElement} formId - 表单ID或表单元素
 * @param {object} data - 数据对象
 */
window.setFormData = function setFormData(formId, data) {
    const form = typeof formId === 'string' ? document.getElementById(formId) : formId;
    if (!form) return;
    
    for (const [key, value] of Object.entries(data)) {
        const input = form.querySelector(`[name="${key}"]`);
        if (input) {
            input.value = value;
        }
    }
}

/**
 * 导出Excel文件
 * @param {Array} data - 数据数组
 * @param {Array} columns - 列定义
 * @param {string} filename - 文件名
 */
window.exportToExcel = function exportToExcel(data, columns, filename) {
    // 简单的CSV导出实现
    const headers = columns.map(col => col.label || col.key).join(',');
    const rows = data.map(row => {
        return columns.map(col => {
            const value = row[col.key];
            return value !== null && value !== undefined ? String(value) : '';
        }).join(',');
    });
    
    const csv = [headers, ...rows].join('\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename || 'export.csv';
    link.click();
}

/**
 * 获取供应商列表（带缓存）
 * @returns {Promise<Array>} 供应商列表
 */
window.getSuppliers = async function getSuppliers() {
    // 检查缓存是否存在且未过期
    const now = Date.now();
    if (cache.suppliers && cache.suppliersTimestamp && (now - cache.suppliersTimestamp < CACHE_EXPIRY)) {
        return cache.suppliers;
    }
    
    // 缓存不存在或已过期，从API获取
    try {
        const suppliers = await apiRequest('/suppliers/');
        // 更新缓存
        cache.suppliers = suppliers;
        cache.suppliersTimestamp = now;
        return suppliers;
    } catch (error) {
        console.error('获取供应商列表失败:', error);
        // 如果API请求失败，但缓存存在，返回缓存数据
        if (cache.suppliers) {
            console.log('使用缓存的供应商列表');
            return cache.suppliers;
        }
        // 如果没有缓存，抛出错误
        throw error;
    }
}

/**
 * 刷新供应商列表缓存
 */
window.refreshSuppliersCache = function refreshSuppliersCache() {
    cache.suppliers = null;
    cache.suppliersTimestamp = null;
}

