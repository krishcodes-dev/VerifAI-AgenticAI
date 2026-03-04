/**
 * dashboardApi.js
 *
 * Connects the dashboard and transactions UI to the real backend API.
 * All mock data sources have been replaced with authenticated API calls.
 *
 * Endpoints used:
 *   GET /api/v1/transactions/stats  → dashboard stat cards
 *   GET /api/v1/transactions        → transaction list
 *   POST /api/v1/transactions/process → process a new transaction
 */

import api from './api';

export const dashboardApi = {
    /**
     * Fetch aggregated statistics for the authenticated user's dashboard.
     * Returns: { total_transactions, blocked, held, approved, avg_fraud_score, risk_distribution }
     */
    fetchDashboardStats: async () => {
        const response = await api.get('/v1/transactions/stats');
        return response.data;
    },

    /**
     * Fetch a paginated, optionally filtered list of transactions.
     * @param {number} page - 1-based page number
     * @param {number} limit - items per page
     * @param {Object} filters - { search, status, sortBy, sortOrder }
     */
    fetchTransactions: async (page = 1, limit = 20, filters = {}) => {
        const params = new URLSearchParams();
        params.set('page', page);
        params.set('limit', limit);

        if (filters.status && filters.status !== 'ALL') {
            params.set('status', filters.status.toUpperCase());
        }

        const response = await api.get(`/v1/transactions?${params.toString()}`);

        // Normalise the response shape to match what the UI components expect
        const { transactions, pagination } = response.data;
        return {
            data: transactions,
            pagination: {
                current_page: pagination.page,
                total_pages: pagination.total_pages,
                total_items: pagination.total,
                has_next: pagination.page < pagination.total_pages,
            },
        };
    },

    /**
     * Process a transaction through the fraud detection pipeline.
     * @param {Object} transactionData - { user_id, amount, merchant, merchant_category, device_type, device_ip, user_location, email }
     */
    processTransaction: async (transactionData) => {
        const response = await api.post('/v1/transactions/process', transactionData);
        return response.data;
    },

    /**
     * Get the status of a specific transaction by ID.
     */
    fetchTransactionStatus: async (transactionId) => {
        const response = await api.get(`/v1/transactions/status/${transactionId}`);
        return response.data;
    },

    /**
     * Record user feedback on a held/flagged transaction.
     * @param {string} transactionId
     * @param {boolean} userConfirmed - true if user says transaction is legitimate
     */
    verifyTransaction: async (transactionId, userConfirmed) => {
        const response = await api.post(
            `/v1/transactions/verify/${transactionId}?user_confirmed=${userConfirmed}`
        );
        return response.data;
    },
};
