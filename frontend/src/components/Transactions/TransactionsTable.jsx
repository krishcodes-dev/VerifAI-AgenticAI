import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowUpDown, ShoppingBag, Coffee, AlertCircle, Search, ChevronLeft, ChevronRight, Film, Car, Zap } from 'lucide-react';
import { cn } from '../../utils/transactionHelpers';
import RowActions from './RowActions';
import TransactionSparkline from './TransactionSparkline';

const TransactionsTable = ({
    transactions,
    selectedIds,
    onSelectRow,
    onSelectAll,
    onSort,
    sortConfig,
    pagination,
    onPageChange,
    onRowClick,
    focusedIndex
}) => {

    // Helper for status badge
    const getStatusBadge = (status) => {
        switch (status?.toLowerCase()) {
            case 'approved': return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">Approved</span>;
            case 'blocked': return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">Blocked</span>;
            case 'hold': return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400">Hold</span>;
            default: return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-400">{status}</span>;
        }
    };

    // Helper for category icon/badge
    const getCategoryBadge = (category) => {
        // Simple mapping, random for demo if undefined
        const cat = category || 'shopping';
        return (
            <span className="flex items-center gap-1.5 text-xs text-text-muted capitalize">
                {cat === 'food' && <Coffee size={14} className="text-orange-500" />}
                {cat === 'shopping' && <ShoppingBag size={14} className="text-blue-500" />}
                {cat === 'entertainment' && <Film size={14} className="text-purple-500" />}
                {cat === 'transport' && <Car size={14} className="text-indigo-500" />}
                {cat === 'utilities' && <Zap size={14} className="text-yellow-500" />}
                {cat}
            </span>
        );
    };

    // Render sorting arrow
    const SortIcon = ({ column }) => {
        if (sortConfig.key !== column) return <ArrowUpDown size={14} className="text-gray-300 opacity-0 group-hover:opacity-50 transition-opacity" />;
        return <ArrowUpDown size={14} className={cn("text-primary transition-transform", sortConfig.direction === 'desc' ? 'rotate-180' : '')} />;
    };

    if (transactions.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-20 bg-white/50 dark:bg-gray-800/50 rounded-xl border border-border-subtle backdrop-blur-sm">
                <div className="bg-gray-100 dark:bg-white/5 p-4 rounded-full mb-4">
                    <Search size={32} className="text-text-muted" />
                </div>
                <h3 className="text-lg font-medium text-text-primary">No transactions found</h3>
                <p className="text-text-muted mt-1 max-w-sm text-center">We couldn't find any results matching your filters. Try adjusting dates or filters.</p>
            </div>
        );
    }

    return (
        <div className="bg-white/50 dark:bg-gray-800/50 backdrop-blur-md rounded-xl border border-border-subtle shadow-sm overflow-hidden flex flex-col h-full">
            <div className="overflow-x-auto scroller flex-1">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-border-subtle bg-gray-50/50 dark:bg-black/20 text-xs font-semibold text-text-muted uppercase tracking-wider">
                            <th className="p-4 w-12">
                                <input
                                    type="checkbox"
                                    className="rounded border-gray-300 text-primary focus:ring-primary bg-transparent"
                                    checked={transactions.length > 0 && selectedIds.length === transactions.length}
                                    onChange={onSelectAll}
                                />
                            </th>
                            <th
                                className="p-4 cursor-pointer group select-none hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
                                onClick={() => onSort('merchant')}
                            >
                                <div className="flex items-center gap-2">Merchant <SortIcon column="merchant" /></div>
                            </th>
                            <th
                                className="p-4 cursor-pointer group select-none hover:bg-gray-50 dark:hover:bg-white/5 transition-colors text-right"
                                onClick={() => onSort('amount')}
                            >
                                <div className="flex items-center justify-end gap-2">Amount <SortIcon column="amount" /></div>
                            </th>
                            <th className="p-4 hidden md:table-cell">Category</th>
                            <th className="p-4 hidden sm:table-cell">Risk Trend</th>
                            <th
                                className="p-4 cursor-pointer group select-none hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
                                onClick={() => onSort('risk_score')}
                            >
                                <div className="flex items-center gap-2">Risk Score <SortIcon column="risk_score" /></div>
                            </th>
                            <th className="p-4">Status</th>
                            <th
                                className="p-4 cursor-pointer group select-none hover:bg-gray-50 dark:hover:bg-white/5 transition-colors text-right hidden lg:table-cell"
                                onClick={() => onSort('timestamp')}
                            >
                                <div className="flex items-center justify-end gap-2">Date <SortIcon column="timestamp" /></div>
                            </th>
                            <th className="p-4 w-12"></th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-border-subtle text-sm">
                        {transactions.map((txn, idx) => (
                            <motion.tr
                                key={txn.id}
                                layoutId={`row-${txn.id}`}
                                className={cn(
                                    "group hover:bg-white/80 dark:hover:bg-white/5 transition-colors cursor-pointer border-l-2 border-transparent",
                                    selectedIds.includes(txn.id) && "bg-primary/5 hover:bg-primary/10",
                                    focusedIndex === idx && "bg-primary/5 dark:bg-white/10 border-primary ring-1 ring-inset ring-primary/20",
                                )}
                                onClick={() => onRowClick(txn)}
                            >
                                <td className="p-4" onClick={(e) => e.stopPropagation()}>
                                    <input
                                        type="checkbox"
                                        className="rounded border-gray-300 text-primary focus:ring-primary bg-transparent"
                                        checked={selectedIds.includes(txn.id)}
                                        onChange={() => onSelectRow(txn.id)}
                                    />
                                </td>
                                <td className="p-4 font-medium text-text-primary">
                                    <div className="flex flex-col">
                                        <span>{txn.merchant}</span>
                                        <span className="text-xs text-text-muted md:hidden">{txn.date_formatted || new Date(txn.timestamp).toLocaleDateString()}</span>
                                    </div>
                                </td>
                                <td className="p-4 text-right font-mono text-text-primary">
                                    {txn.amount_formatted || `₹${txn.amount?.toLocaleString()}`}
                                </td>
                                <td className="p-4 hidden md:table-cell">
                                    {getCategoryBadge(txn.category)}
                                </td>
                                <td className="p-4 hidden sm:table-cell">
                                    <TransactionSparkline data={txn.history} color={txn.risk_score > 70 ? '#EF4444' : '#10B981'} />
                                </td>
                                <td className="p-4">
                                    <div className="flex items-center gap-3">
                                        <span className={cn(
                                            "font-bold text-sm w-8",
                                            txn.risk_score > 70 ? "text-red-600" : txn.risk_score > 30 ? "text-orange-600" : "text-green-600"
                                        )}>
                                            {txn.risk_score}
                                        </span>
                                        <div className="w-16 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                            <div
                                                className={cn("h-full rounded-full transition-all duration-500",
                                                    txn.risk_score > 70 ? "bg-red-500" : txn.risk_score > 30 ? "bg-orange-500" : "bg-green-500"
                                                )}
                                                style={{ width: `${txn.risk_score}%` }}
                                            />
                                        </div>
                                    </div>
                                </td>
                                <td className="p-4">
                                    {getStatusBadge(txn.status)}
                                </td>
                                <td className="p-4 text-right text-text-muted hidden lg:table-cell">
                                    {txn.date_formatted || new Date(txn.timestamp).toLocaleString()}
                                </td>
                                <td className="p-4 text-right" onClick={(e) => e.stopPropagation()}>
                                    <RowActions onAction={(action) => console.log(action, txn.id)} />
                                </td>
                            </motion.tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Pagination */}
            {pagination && (
                <div className="p-4 border-t border-border-subtle bg-gray-50/50 dark:bg-black/20 flex items-center justify-between text-sm">
                    <span className="text-text-muted">
                        Page <span className="font-medium text-text-primary">{pagination.page}</span> of <span className="font-medium text-text-primary">{pagination.totalPages}</span>
                    </span>
                    <div className="flex gap-2">
                        <button
                            disabled={pagination.page <= 1}
                            onClick={() => onPageChange(pagination.page - 1)}
                            className="p-1.5 rounded-lg border border-border-subtle hover:bg-white dark:hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            <ChevronLeft size={16} />
                        </button>
                        <button
                            disabled={pagination.page >= pagination.totalPages}
                            onClick={() => onPageChange(pagination.page + 1)}
                            className="p-1.5 rounded-lg border border-border-subtle hover:bg-white dark:hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            <ChevronRight size={16} />
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default TransactionsTable;
