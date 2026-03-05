import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api, { setAuthToken, setRefreshToken, clearAuthTokens } from '../services/api';

const useAuthStore = create(
    persist(
        (set, get) => ({
            user: null,
            access_token: null,
            refresh_token: null,
            isAuthenticated: false,
            isLoading: false,
            error: null,

            // Login Action
            login: async (identifier, password) => {
                set({ isLoading: true, error: null });
                try {
                    const response = await api.post('/auth/login', { email: identifier, password });
                    const { access_token, refresh_token, user } = response.data;

                    setAuthToken(access_token);
                    setRefreshToken(refresh_token);

                    set({
                        user,
                        access_token,
                        refresh_token,
                        isAuthenticated: true,
                        isLoading: false,
                    });
                    return true;
                } catch (error) {
                    set({
                        error: error.response?.data?.detail || 'Login failed',
                        isLoading: false,
                    });
                    throw error; // Rethrow for UI toast
                }
            },

            // Signup Action
            signup: async (payload) => {
                set({ isLoading: true, error: null });
                try {
                    const response = await api.post('/auth/signup', payload);
                    // Assuming signup might return tokens immediately, otherwise user logs in.
                    // If backend sends tokens on signup:
                    const { access_token, refresh_token, user } = response.data;

                    if (access_token && user) {
                        setAuthToken(access_token);
                        setRefreshToken(refresh_token);
                        set({
                            user,
                            access_token,
                            refresh_token,
                            isAuthenticated: true,
                            isLoading: false
                        });
                    } else {
                        set({ isLoading: false });
                    }
                    return response.data;
                } catch (error) {
                    set({
                        error: error.response?.data?.detail || 'Signup failed',
                        isLoading: false,
                    });
                    throw error;
                }
            },

            // Google Login Handling
            googleLogin: (tokens) => {
                const { access_token, refresh_token, user } = tokens;
                setAuthToken(access_token);
                setRefreshToken(refresh_token);
                set({
                    user,
                    access_token,
                    refresh_token,
                    isAuthenticated: true
                });
            },

            // Fetch Current User
            fetchMe: async () => {
                try {
                    const response = await api.get('/auth/me');
                    set({ user: response.data });
                } catch (error) {
                    // If fetch fails (e.g. invalid token), logout might be handled by interceptor
                    console.error("Failed to fetch user:", error);
                }
            },

            // Logout Action — revokes tokens server-side before clearing local state
            logout: async () => {
                const { refresh_token } = get();
                // Best-effort server-side revocation
                try {
                    await api.post('/auth/logout', { refresh_token });
                } catch (err) {
                    console.warn('Server-side logout failed (token will expire naturally):', err);
                }
                clearAuthTokens();
                set({
                    user: null,
                    access_token: null,
                    refresh_token: null,
                    isAuthenticated: false,
                });
            },
        }),
        {
            name: 'auth-storage', // name of item in the storage (must be unique)
            partialize: (state) => ({
                user: state.user,
                access_token: state.access_token,
                refresh_token: state.refresh_token,
                isAuthenticated: state.isAuthenticated
            }),
        }
    )
);

export default useAuthStore;
