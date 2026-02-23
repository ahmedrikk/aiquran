import { useState } from "react";
import { GoogleLogin, CredentialResponse } from '@react-oauth/google';
import { useNavigate } from "react-router-dom";
import { Capacitor } from '@capacitor/core';

const API_BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000");

const Login = () => {
    const navigate = useNavigate();
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const isNative = Capacitor.isNativePlatform();

    const sendCredentialToBackend = async (credential: string) => {
        setError(null);
        setLoading(true);
        try {
            const response = await fetch(`${API_BASE}/auth/google`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ credential }),
            });
            if (!response.ok) throw new Error(`Auth failed: ${response.status}`);
            const data = await response.json();
            localStorage.setItem('user_token', data.access_token);
            localStorage.setItem('user_profile', JSON.stringify(data.user));
            navigate('/');
        } catch (err) {
            console.error("Auth failed details:", err);
            setError("Sign-in failed. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    const handleWebLoginSuccess = async (credentialResponse: CredentialResponse) => {
        if (!credentialResponse.credential) return;
        await sendCredentialToBackend(credentialResponse.credential);
    };

    const handleNativeGoogleSignIn = async () => {
        setError(null);
        setLoading(true);
        try {
            const { GoogleAuth } = await import('@codetrix-studio/capacitor-google-auth');
            await GoogleAuth.initialize({
                clientId: '846223196875-iim6ake76pqe61tufn3t8rccogqv7ec2.apps.googleusercontent.com',
                scopes: ['profile', 'email'],
                grantOfflineAccess: true,
            });
            const user = await GoogleAuth.signIn();
            const idToken = user.authentication.idToken;
            if (!idToken) throw new Error("No ID token received from Google");
            await sendCredentialToBackend(idToken);
        } catch (err: unknown) {
            console.error("Native Google Sign-In error:", err);
            const message = err instanceof Error ? err.message : String(err);
            if (!message.includes('cancel') && !message.includes('12501')) {
                setError("Google sign-in failed. Please try again.");
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex-1 flex flex-col items-center justify-center px-6 pb-12 w-full max-w-md mx-auto">
            {/* Welcome Image/Hero */}
            <div className="w-full mb-8 relative group">
                <div className="absolute inset-0 bg-primary/10 rounded-2xl transform rotate-2 group-hover:rotate-1 transition-transform"></div>
                <div
                    className="relative w-full h-48 bg-center bg-no-repeat bg-cover rounded-2xl overflow-hidden shadow-lg border-2 border-white dark:border-primary/20"
                    style={{ backgroundImage: 'url("https://lh3.googleusercontent.com/aida-public/AB6AXuAAQVu1WP2qjxFdSMO7HmR-4vpZq7-x8c9Iz7zLgsA-PWLBQML7TMuGaAQtiAx2BvWSqSPtv3ngJJxmwmqzW-8H-ZKQQshHsZcnZwLXXdhaZAOX0HG6juxwCw2-doC4AfgmGPTFCZr86Wx6H4Pyp5sP28hCtH5Hc-T272Ue_t-bwFwrddemwpghIezQq8dqP8bYO11TudZb36DenWXGYSxZh0ivE1kQJUzb8KWrutGyxUoY13qRrLdp9u8b3ajYlAKXXGcLmA4xEnE")' }}
                >
                    <div className="absolute inset-0 bg-gradient-to-t from-primary/60 to-transparent"></div>
                </div>
            </div>

            <div className="text-center mb-8">
                <h1 className="text-3xl font-bold leading-tight mb-2">Welcome Back</h1>
                <p className="text-slate-600 dark:text-slate-400 text-base">Peace be upon you. Continue your spiritual journey with us.</p>
            </div>

            {/* Google Sign-In */}
            <div className="w-full flex flex-col items-center gap-3 mb-8">
                {isNative ? (
                    <button
                        onClick={handleNativeGoogleSignIn}
                        disabled={loading}
                        className="w-full h-14 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 text-slate-700 dark:text-slate-200 font-semibold text-base rounded-full shadow hover:shadow-md transition-all flex items-center justify-center gap-3 disabled:opacity-60"
                    >
                        {loading ? (
                            <span className="material-symbols-outlined animate-spin">progress_activity</span>
                        ) : (
                            <svg width="20" height="20" viewBox="0 0 48 48">
                                <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z"/>
                                <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z"/>
                                <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z"/>
                                <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z"/>
                            </svg>
                        )}
                        {loading ? 'Signing in...' : 'Continue with Google'}
                    </button>
                ) : (
                    <GoogleLogin
                        onSuccess={handleWebLoginSuccess}
                        onError={() => setError("Google sign-in failed. Please try again.")}
                        theme="filled_blue"
                        shape="pill"
                        text="continue_with"
                        size="large"
                        width="100%"
                    />
                )}
                {error && (
                    <p className="text-sm text-red-500 font-medium text-center">{error}</p>
                )}
            </div>

            {/* Footer Link */}
            <p className="text-slate-600 dark:text-slate-400 font-medium text-center">
                New here? <span className="text-primary font-bold cursor-pointer hover:underline">Sign in with Google to start</span>
            </p>
        </div>
    );
};

export default Login;
