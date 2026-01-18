/**
 * API Service Layer
 *
 * Wraps all backend API endpoints for the frontend.
 * Uses apiRequest from utils.js for consistent error handling.
 */

const API = {
    // ==================== Papers ====================

    /**
     * List papers with pagination, search, and filters
     */
    getPapers: async (params = {}) => {
        const queryString = new URLSearchParams(params).toString();
        return await apiRequest(`/papers/?${queryString}`);
    },

    /**
     * Get paper details by ID
     */
    getPaper: async (paperId) => {
        return await apiRequest(`/papers/${paperId}`);
    },

    /**
     * Download paper PDF (opens in new tab)
     */
    downloadPaperPDF: async (paperId) => {
        window.open(`/api/papers/${paperId}/pdf`, '_blank');
    },

    /**
     * Get paper summaries
     */
    getPaperSummaries: async (paperId) => {
        return await apiRequest(`/papers/${paperId}/summary`);
    },

    /**
     * Trigger paper summarization (async background task)
     */
    summarizePaper: async (paperId) => {
        return await apiRequest(`/papers/${paperId}/summarize`, {
            method: 'POST'
        });
    },

    /**
     * Get papers by date
     */
    getPapersByDate: async (date) => {
        return await apiRequest(`/papers/by-date/${date}`);
    },

    // ==================== Users ====================

    /**
     * Get user profile
     */
    getUserProfile: async () => {
        return await apiRequest('/users/profile');
    },

    /**
     * Update user profile (interests and keywords)
     */
    updateUserProfile: async (data) => {
        return await apiRequest('/users/profile', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    /**
     * Get user interactions
     */
    getInteractions: async (params = {}) => {
        const queryString = new URLSearchParams(params).toString();
        return await apiRequest(`/users/interactions?${queryString}`);
    },

    /**
     * Mark paper as interested or not_interested
     */
    markPaper: async (paperId, action, notes = null) => {
        return await apiRequest(`/users/interactions/${paperId}`, {
            method: 'POST',
            body: JSON.stringify({ action, notes })
        });
    },

    /**
     * Clear paper action (reset to no_action)
     */
    clearPaperAction: async (paperId) => {
        return await apiRequest(`/users/interactions/${paperId}`, {
            method: 'DELETE'
        });
    },

    /**
     * Get interested papers list
     */
    getInterestedPapers: async () => {
        return await apiRequest('/users/interested-papers');
    },

    // ==================== Reports ====================

    /**
     * Generate daily report (async background task)
     */
    generateReport: async (data = {}) => {
        return await apiRequest('/reports/generate', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    /**
     * Get recent reports
     */
    getReports: async (params = {}) => {
        const queryString = new URLSearchParams(params).toString();
        return await apiRequest(`/reports/?${queryString}`);
    },

    /**
     * Get report by ID
     */
    getReport: async (reportId) => {
        return await apiRequest(`/reports/${reportId}`);
    },

    /**
     * Get report by date
     */
    getReportByDate: async (date) => {
        return await apiRequest(`/reports/by-date/${date}`);
    },

    /**
     * Get task status (for polling)
     */
    getTaskStatus: async (taskId) => {
        return await apiRequest(`/reports/tasks/${taskId}`);
    },

    // ==================== Recommendations ====================

    /**
     * Generate recommendations
     */
    generateRecommendations: async (data = {}) => {
        return await apiRequest('/recommendations/generate', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    /**
     * Get current recommendations
     */
    getRecommendations: async (params = {}) => {
        const queryString = new URLSearchParams(params).toString();
        return await apiRequest(`/recommendations/?${queryString}`);
    },

    // ==================== Settings ====================

    /**
     * Get all settings
     */
    getSettings: async () => {
        return await apiRequest('/settings/all');
    },

    /**
     * Update paper sources config
     */
    updateSources: async (data) => {
        return await apiRequest('/settings/sources', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    /**
     * Update AI service config
     */
    updateAIConfig: async (data) => {
        return await apiRequest('/settings/ai', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    /**
     * Update recommendation config
     */
    updateRecommendationConfig: async (data) => {
        return await apiRequest('/settings/recommendation', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    /**
     * Get sources config
     */
    getSourcesConfig: async () => {
        return await apiRequest('/settings/sources');
    },

    /**
     * Get AI config
     */
    getAIConfig: async () => {
        return await apiRequest('/settings/ai');
    },

    /**
     * Get recommendation config
     */
    getRecommendationConfig: async () => {
        return await apiRequest('/settings/recommendation');
    },

    // ==================== Refresh ====================

    /**
     * Fetch new papers (download, parse, summarize)
     */
    fetchPapers: async (parse = true, summarize = true, maxResults = null) => {
        const params = new URLSearchParams({
            parse: parse.toString(),
            summarize: summarize.toString()
        });
        if (maxResults) {
            params.append('max_results', maxResults.toString());
        }
        return await apiRequest(`/refresh/fetch?${params}`, {
            method: 'POST'
        });
    },

    /**
     * Get refresh task status
     */
    getRefreshTaskStatus: async (taskId) => {
        return await apiRequest(`/refresh/tasks/${taskId}`);
    },

    /**
     * Get scheduler status
     */
    getSchedulerStatus: async () => {
        return await apiRequest('/refresh/scheduler');
    },

    /**
     * Update scheduler config
     */
    updateSchedulerConfig: async (enabled, scheduleType, dailyTime, weeklyDay, weeklyTime) => {
        const params = new URLSearchParams();
        if (enabled !== null) {
            params.append('enabled', enabled.toString());
        }
        if (scheduleType !== null) {
            params.append('schedule_type', scheduleType);
        }
        if (dailyTime !== null) {
            params.append('daily_time', dailyTime);
        }
        if (weeklyDay !== null) {
            params.append('weekly_day', weeklyDay.toString());
        }
        if (weeklyTime !== null) {
            params.append('weekly_time', weeklyTime);
        }
        return await apiRequest(`/refresh/scheduler?${params}`, {
            method: 'PUT'
        });
    },

    /**
     * Get task history list
     */
    getTaskHistory: async (skip = 0, limit = 20) => {
        const params = new URLSearchParams({
            skip: skip.toString(),
            limit: limit.toString()
        });
        return await apiRequest(`/refresh/history?${params}`);
    },

    /**
     * Get task detail with steps
     */
    getTaskDetail: async (taskId) => {
        return await apiRequest(`/refresh/history/${taskId}`);
    },
};

// Make API available globally
window.API = API;
