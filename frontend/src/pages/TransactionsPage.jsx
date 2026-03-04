import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Toaster, toast } from 'react-hot-toast';
import { RefreshCw, HelpCircle } from 'lucide-react';

// Components
import TransactionFilters from '../components/Transactions/TransactionFilters';
import TransactionsTable from '../components/Transactions/TransactionsTable';
import TransactionDetailSheet from '../components/Transactions/TransactionDetailSheet';
import SavedViews from '../components/Transactions/SavedViews';
import BulkActions from '../components/Transactions/BulkActions';
import { Button } from '../components/ui/Button';

// Service — real API
import { dashboardApi } from '../services/dashboardApi';

const TransactionsPage = () => {
    // State
    const [transactions, setTransactions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedIds, setSelectedIds] = useState([]);
    const [filters, setFilters] = useState({ page: 1, limit: 10, sortOrder: 'desc', sortBy: 'timestamp' });
    const [pagination, setPagination] = useState({ page: 1, totalPages: 1, total: 0 });
    const [selectedTransaction, setSelectedTransaction] = useState(null);
    const [isDetailOpen, setIsDetailOpen] = useState(false);
    const [currentView, setCurrentView] = useState('all');

    // Fetch Data from real backend
    const loadTransactions = useCallback(async () => {
        setLoading(true);
        try {
            const result = await dashboardApi.fetchTransactions(
                filters.page,
                filters.limit,
                {
                    status: filters.status,
                    search: filters.search,
                }
            );
            // Normalise response shape for the table components
            setTransactions(result.data);
            setPagination({
                page: result.pagination.current_page,
                totalPages: result.pagination.total_pages,
                total: result.pagination.total_items,
            });
        } catch (error) {
            console.error('Failed to load transactions', error);
            toast.error('Failed to load transactions — are you logged in?');
            setTransactions([]);
        } finally {
            setLoading(false);
        }
    }, [filters]);

    // Initial Load & Filter Change
    useEffect(() => {
        loadTransactions();
    }, [loadTransactions]);

    // Handlers
    const handleFilterChange = (newFilters) => {
        setFilters(prev => ({ ...prev, ...newFilters, page: 1 }));
    };

    const handlePageChange = (newPage) => {
        setFilters(prev => ({ ...prev, page: newPage }));
    };

    const handleSort = (column) => {
        setFilters(prev => ({
            ...prev,
            sortBy: column,
            sortOrder: prev.sortBy === column && prev.sortOrder === 'desc' ? 'asc' : 'desc'
        }));
    };

    const handleSelectRow = (id) => {
        setSelectedIds(prev =>
            prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
        );
    };

    const handleSelectAll = (e) => {
        if (e.target.checked) {
            setSelectedIds(transactions.map(t => t.id));
        } else {
            setSelectedIds([]);
        }
    };

    const handleRowClick = (transaction) => {
        setSelectedTransaction(transaction);
        setIsDetailOpen(true);
    };

    const handleBulkAction = (action) => {
        toast.success(`Bulk ${action} applied to ${selectedIds.length} transactions`);
        setSelectedIds([]);
        // Here you would call API to update statuses
        loadTransactions();
    };

    const handleViewChange = (viewId) => {
        setCurrentView(viewId);
        const newFilters = { page: 1, limit: 10 };

        // Map view IDs to filters
        if (viewId === 'high_risk') {
            newFilters.riskMin = 70;
        } else if (viewId === 'pending') {
            newFilters.status = 'hold';
        } else if (viewId === 'recent') {
            // Logic for recent would go here
            newFilters.sortBy = 'timestamp';
        }

        setFilters(prev => ({ ...newFilters })); // Reset other filters or merge cautiously
    };

    const [focusedIndex, setFocusedIndex] = useState(-1);

    // Keyboard Shortcuts
    useEffect(() => {
        const handleKeyDown = (e) => {
            // Ignore if input is focused
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            if (e.key === 'r' && !e.metaKey && !e.ctrlKey) {
                loadTransactions();
                toast('Refreshed', { icon: '🔄' });
            }
            if (e.key === 'j') {
                setFocusedIndex(prev => Math.min(prev + 1, transactions.length - 1));
            }
            if (e.key === 'k') {
                setFocusedIndex(prev => Math.max(prev - 1, 0));
            }
            if (e.key === 'Enter' && focusedIndex >= 0) {
                handleRowClick(transactions[focusedIndex]);
            }
            if (e.key === 'Escape') {
                setIsDetailOpen(false);
                setFocusedIndex(-1);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [loadTransactions, transactions, focusedIndex]);

    return (
        <React.Fragment>
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="max-w-7xl mx-auto flex flex-col h-[calc(100vh-100px)]"
            >
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h1 className="text-2xl font-bold text-text-primary">Transactions</h1>
                        <p className="text-text-muted text-sm">Review and manage fraud alerts</p>
                    </div>
                    <div className="flex gap-2">
                        <Button variant="ghost" size="icon" onClick={() => loadTransactions()} disabled={loading}>
                            <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
                        </Button>
                        <Button variant="ghost" size="icon">
                            <HelpCircle size={18} />
                        </Button>
                    </div>
                </div>

                {/* Saved Views */}
                <div className="mb-6">
                    <SavedViews
                        currentView={currentView}
                        onViewChange={handleViewChange}
                        counts={{ high_risk: 12, pending: 5, chargebacks: 2 }}
                    />
                </div>

                {/* Filters */}
                <TransactionFilters
                    filters={filters}
                    onFilterChange={handleFilterChange}
                    onClear={() => setFilters({ page: 1, limit: 10 })}
                />

                {/* Bulk Actions */}
                <AnimatePresence>
                    {selectedIds.length > 0 && (
                        <BulkActions
                            selectedCount={selectedIds.length}
                            onClearSelection={() => setSelectedIds([])}
                            onAction={handleBulkAction}
                        />
                    )}
                </AnimatePresence>

                {/* Table */}
                <div className="flex-1 min-h-0 relative">
                    {loading && (
                        <div className="absolute inset-0 z-10 bg-white/50 dark:bg-black/50 backdrop-blur-sm flex items-center justify-center">
                            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
                        </div>
                    )}

                    <TransactionsTable
                        transactions={transactions}
                        selectedIds={selectedIds}
                        onSelectRow={handleSelectRow}
                        onSelectAll={handleSelectAll}
                        onSort={handleSort}
                        sortConfig={{ key: filters.sortBy, direction: filters.sortOrder }}
                        pagination={pagination}
                        onPageChange={handlePageChange}
                        onRowClick={handleRowClick}
                        focusedIndex={focusedIndex}
                    />
                </div>
            </motion.div>

            {/* Detail Sheet */}
            <TransactionDetailSheet
                transaction={selectedTransaction}
                isOpen={isDetailOpen}
                onClose={() => setIsDetailOpen(false)}
            />
        </React.Fragment>
    );
};

export default TransactionsPage;
