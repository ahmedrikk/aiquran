import { useState } from "react";
import { GoogleLogin, CredentialResponse } from '@react-oauth/google';
import { useNavigate } from "react-router-dom";

const API_BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000");

const Login = () => {
    const navigate = useNavigate();
    const [error, setError] = useState<string | null>(null);

    const handleLoginSuccess = async (credentialResponse: CredentialResponse) => {
        if (!credentialResponse.credential) return;
        setError(null);
        try {
            const response = await fetch(`${API_BASE}/auth/google`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ credential: credentialResponse.credential }),
            });
            if (!response.ok) throw new Error(`Auth failed: ${response.status}`);
            const data = await response.json();
            // data = { access_token, token_type, user: { id, email, name, picture, ... } }
            localStorage.setItem('user_token', data.access_token);
            localStorage.setItem('user_profile', JSON.stringify(data.user));
            navigate('/');
        } catch (err) {
            console.error("Auth failed", err);
            setError("Sign-in failed. Please try again.");
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

            {/* Login Form */}
            <form className="w-full space-y-5" onSubmit={(e) => e.preventDefault()}>
                {/* Email Input */}
                <div className="flex flex-col w-full">
                    <label className="text-sm font-semibold text-primary/80 dark:text-primary mb-1.5 ml-1">Email Address</label>
                    <div className="relative flex items-center group">
                        <span className="material-symbols-outlined absolute left-4 text-slate-400 group-focus-within:text-primary transition-colors">mail</span>
                        <input
                            className="w-full h-14 pl-12 pr-4 rounded-xl border border-slate-200 dark:border-primary/20 bg-white dark:bg-background-dark/50 focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all outline-none text-base"
                            placeholder="Enter your email"
                            type="email"
                        />
                    </div>
                </div>

                {/* Password Input */}
                <div className="flex flex-col w-full">
                    <div className="flex justify-between items-center mb-1.5 ml-1">
                        <label className="text-sm font-semibold text-primary/80 dark:text-primary">Password</label>
                        <a className="text-xs font-bold text-gold-accent hover:underline" href="#">Forgot Password?</a>
                    </div>
                    <div className="relative flex items-center group">
                        <span className="material-symbols-outlined absolute left-4 text-slate-400 group-focus-within:text-primary transition-colors">lock</span>
                        <input
                            className="w-full h-14 pl-12 pr-12 rounded-xl border border-slate-200 dark:border-primary/20 bg-white dark:bg-background-dark/50 focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all outline-none text-base"
                            placeholder="••••••••"
                            type="password"
                        />
                        <button className="absolute right-4 text-slate-400 hover:text-primary" type="button">
                            <span className="material-symbols-outlined">visibility</span>
                        </button>
                    </div>
                </div>

                {/* Login Button */}
                <button
                    className="w-full h-14 bg-primary text-white font-bold text-lg rounded-xl shadow-lg shadow-primary/20 hover:bg-primary/90 transition-all flex items-center justify-center gap-2 group"
                    type="submit"
                >
                    Sign In
                    <span className="material-symbols-outlined group-hover:translate-x-1 transition-transform">arrow_forward</span>
                </button>
            </form>

            {/* Divider */}
            <div className="w-full flex items-center my-8">
                <div className="flex-1 h-px bg-slate-200 dark:bg-primary/10"></div>
                <span className="px-4 text-xs font-medium text-slate-400 uppercase tracking-widest">or continue with</span>
                <div className="flex-1 h-px bg-slate-200 dark:bg-primary/10"></div>
            </div>

            {/* Google Login */}
            <div className="w-full flex flex-col items-center gap-3 mb-8">
                <GoogleLogin
                    onSuccess={handleLoginSuccess}
                    onError={() => setError("Google sign-in failed. Please try again.")}
                    theme="filled_blue"
                    shape="pill"
                    text="continue_with"
                    size="large"
                    width="100%"
                />
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
