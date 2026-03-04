import { useState, useEffect, useCallback } from 'react';
import { dashboardApi } from '../services/dashboardApi';
import useAuthStore from '../stores/useAuthStore';

export const useDashboard = () => {
    const { user } = useAuthStore();

    // Stats State
    const [stats, setStats] = useState(null);
    const [heatmapData, setHeatmapData] = useState([]);
    const [statsLoading, setStatsLoading] = useState(true);
    const [statsError, setStatsError] = useState(null);

    // Transactions State
    const [transactions, setTransactions] = useState([]);
    const [pagination, setPagination] = useState({ current_page: 1, total_pages: 1, has_next: false });
    const [tableLoading, setTableLoading] = useState(true);
    const [tableError, setTableError] = useState(null);

    // Filter / Page State
    const [filters, setFilters] = useState({ status: 'ALL' });
    const [page, setPage] = useState(1);

    // ── Fetch Stats ───────────────────────────────────────────────
    useEffect(() => {
        const loadStats = async () => {
            setStatsLoading(true);
            setStatsError(null);
            try {
                const statsData = await dashboardApi.fetchDashboardStats();
                setStats(statsData);

                // risk_distribution is now included in the stats response
                if (statsData?.risk_distribution) {
                    setHeatmapData(statsData.risk_distribution);
                }
            } catch (error) {
                console.error('Failed to load dashboard stats:', error);
                setStatsError('Unable to load statistics. Please refresh the page.');
                // Fallback to empty stats so the dashboard doesn't crash
                setStats({
                    total_transactions: 0,
                    blocked: 0,
                    held: 0,
                    approved: 0,
                    avg_fraud_score: 0,
                    fraud_rate: 0,
                    risk_distribution: [],
                });
            } finally {
                setStatsLoading(false);
            }
        };
        loadStats();
    }, []);

    // ── Fetch Transactions ────────────────────────────────────────
    const refreshTransactions = useCallback(async () => {
        setTableLoading(true);
        setTableError(null);
        try {
            const result = await dashboardApi.fetchTransactions(page, 20, filters);
            setTransactions(result.data);
            setPagination(result.pagination);
        } catch (error) {
            console.error('Failed to load transactions:', error);
            setTableError('Unable to load transactions. Please try again.');
            setTransactions([]);
        } finally {
            setTableLoading(false);
        }
    }, [page, filters]);

    useEffect(() => {
        refreshTransactions();
    }, [refreshTransactions]);

    // ── Handlers ──────────────────────────────────────────────────
    const handleStatusFilter = (status) => {
        setFilters(prev => ({ ...prev, status }));
        setPage(1); // Reset to first page on any filter change
    };

    const handlePageChange = (newPage) => {
        setPage(newPage);
    };

    const handleTransactionAction = async (id, action) => {
        try {
            await dashboardApi.verifyTransaction(id, action === 'APPROVE');
            refreshTransactions();
        } catch (error) {
            console.error('Action failed:', error);
        }
    };

    return {
        user,
        stats,
        heatmapData,
        transactions,
        pagination,
        statsLoading,
        tableLoading,
        statsError,
        tableError,
        filters,
        handleStatusFilter,
        handlePageChange,
        handleTransactionAction,
    };
};
