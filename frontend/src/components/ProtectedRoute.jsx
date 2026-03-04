import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import useAuth from '../hooks/useAuth';
import useAuthStore from '../stores/useAuthStore';

const ProtectedRoute = ({ children }) => {
    const { isAuthenticated, isLoading } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    useEffect(() => {
        let timer;
        if (isLoading) {
            timer = setTimeout(() => {
                console.warn("Auth loading timed out, redirecting to login");
                useAuthStore.getState().logout();
                navigate('/auth?view=login', { replace: true });
            }, 3000); // 3 second timeout
        }
        return () => clearTimeout(timer);
    }, [isLoading, navigate]);

    useEffect(() => {
        if (!isLoading && !isAuthenticated) {
            navigate('/auth?view=login', { state: { from: location }, replace: true });
        }
    }, [isAuthenticated, isLoading, navigate, location]);

    if (isLoading) {
        // Show a spinner or skeleton
        return (
            <div className="flex items-center justify-center min-h-screen bg-background">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
            </div>
        );
    }

    // Only render children if authenticated
    return isAuthenticated ? children : null;
};

export default ProtectedRoute;
