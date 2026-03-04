import React, { useState, useEffect } from 'react';
import { useDashboard } from '../../hooks/useDashboard';
import WelcomeCard from './WelcomeCard';
import StatsCard from './StatsCard';
import HeatmapChart from './HeatmapChart';
import QuickActions from './QuickActions';
import TransactionsTable from './TransactionsTable';
import { Activity, ShieldAlert, BarChart2, Smartphone } from 'lucide-react';
import { motion } from 'framer-motion';

const Dashboard = () => {
    const {
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
        handleTransactionAction
    } = useDashboard();

    // Skeleton Loader for Stats
    const StatSkeleton = () => (
        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-border-subtle animate-pulse h-32">
            <div className="h-10 w-10 bg-gray-200 dark:bg-white/10 rounded-lg mb-4"></div>
            <div className="h-8 w-24 bg-gray-200 dark:bg-white/10 rounded mb-2"></div>
            <div className="h-4 w-32 bg-gray-200 dark:bg-white/10 rounded"></div>
        </div>
    );

    return (
        <React.Fragment>
            {/* Welcome Section */}
            <div className="max-w-7xl mx-auto w-full">
                <WelcomeCard user={user} />
            </div>

            {/* Stats Grid */}
            <div className="max-w-7xl mx-auto w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
                {statsLoading ? (
                    <>
                        <StatSkeleton /><StatSkeleton /><StatSkeleton /><StatSkeleton />
                    </>
                ) : (
                    <>
                        <StatsCard
                            title="Total Transactions"
                            value={stats?.total_transactions?.toLocaleString() ?? '—'}
                            icon={Activity}
                            trend="up"
                            trendValue={null}
                            index={0}
                        />
                        <StatsCard
                            title="Blocked"
                            value={stats?.blocked ?? '—'}
                            icon={ShieldAlert}
                            trend="up"
                            trendValue={null}
                            index={1}
                        />
                        <StatsCard
                            title="Avg Risk Score"
                            value={stats?.avg_fraud_score != null ? `${(stats.avg_fraud_score * 100).toFixed(1)}%` : '—'}
                            icon={BarChart2}
                            trend="down"
                            trendValue={null}
                            index={2}
                        />
                        <StatsCard
                            title="Fraud Rate"
                            value={stats?.fraud_rate != null ? `${(stats.fraud_rate * 100).toFixed(1)}%` : '—'}
                            icon={Smartphone}
                            trend="up"
                            trendValue={null}
                            index={3}
                        />
                        {statsError && (
                            <div className="col-span-full text-sm text-red-500 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg px-4 py-3">
                                ⚠️ {statsError}
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* Middle Section: Heatmap + Quick Actions */}
            <div className="max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, delay: 0.2 }}
                    >
                        <HeatmapChart data={heatmapData} />
                    </motion.div>
                </div>
                <div className="lg:col-span-1">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, delay: 0.3 }}
                        className="h-full"
                    >
                        <QuickActions />
                    </motion.div>
                </div>
            </div>

            {/* Transactions Section */}
            <div className="max-w-7xl mx-auto w-full">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.4 }}
                >
                    <TransactionsTable
                        transactions={transactions}
                        pagination={pagination}
                        filters={filters}
                        isLoading={tableLoading}
                        onFilterChange={handleStatusFilter}
                        onPageChange={handlePageChange}
                        onAction={handleTransactionAction}
                    />
                </motion.div>
            </div>
        </React.Fragment>
    );
};

export default Dashboard;
