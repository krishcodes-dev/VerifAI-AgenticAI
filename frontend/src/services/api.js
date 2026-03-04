import axios from 'axios';

const api = axios.create({
    baseURL: 'http://localhost:8000/api', // Using 8001 based on previous port conflict resolution
    headers: {
        'Content-Type': 'application/json',
    },
});

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
    failedQueue.forEach(prom => {
        if (error) {
            prom.reject(error);
        } else {
            prom.resolve(token);
        }
    });
    failedQueue = [];
};

// --- Helpers for Tokens ---
export const getAuthToken = () => localStorage.getItem('access_token');
export const getRefreshToken = () => localStorage.getItem('refresh_token');
export const setAuthToken = (token) => localStorage.setItem('access_token', token);
export const setRefreshToken = (token) => localStorage.setItem('refresh_token', token);
export const clearAuthTokens = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
};

// Request Interceptor
api.interceptors.request.use((config) => {
    const token = getAuthToken();
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
}, (error) => Promise.reject(error));

// Response Interceptor
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
            if (isRefreshing) {
                return new Promise(function (resolve, reject) {
                    failedQueue.push({ resolve, reject });
                }).then(token => {
                    originalRequest.headers.Authorization = `Bearer ${token}`;
                    return api(originalRequest);
                }).catch(err => Promise.reject(err));
            }

            originalRequest._retry = true;
            isRefreshing = true;

            const refreshToken = getRefreshToken();

            if (!refreshToken) {
                // No refresh token, logout logic should trigger in store/hook via event or direct redirect
                // For now, we reject so the caller knows auth failed
                return Promise.reject(error);
            }

            try {
                const response = await axios.post('http://localhost:8000/api/auth/refresh', {
                    refresh_token: refreshToken,
                });

                const { access_token } = response.data;
                setAuthToken(access_token);

                api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
                processQueue(null, access_token);

                return api(originalRequest);
            } catch (err) {
                processQueue(err, null);
                clearAuthTokens();
                window.location.href = '/auth?view=login'; // Force redirect
                return Promise.reject(err);
            } finally {
                isRefreshing = false;
            }
        }

        return Promise.reject(error);
    }
);

export default api;
