import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useToast } from "@/components/ui/use-toast";

const API_BASE_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000") + "/api";

interface UserProfile {
    name: string;
    email: string;
    picture: string;
    premium?: boolean;
}

interface Bookmark {
    id: string;
    content: string;
    chat_title: string;
    created_at: string;
    chat_id: string;
}

const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
};

const Account = () => {
    const navigate = useNavigate();
    const { toast } = useToast();
    const [user, setUser] = useState<UserProfile | null>(null);
    const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
    const [showBookmarks, setShowBookmarks] = useState(false);
    const [pushEnabled, setPushEnabled] = useState(false);

    useEffect(() => {
        const storedProfile = localStorage.getItem("user_profile");
        if (storedProfile) {
            setUser(JSON.parse(storedProfile));
        }

        // Check if push is supported and permission granted
        if ('Notification' in window && Notification.permission === 'granted') {
            setPushEnabled(true);
        }
    }, []);

    const handleLogout = () => {
        localStorage.removeItem("user_token");
        localStorage.removeItem("user_profile");
        navigate("/login");
    };

    const togglePushNotifications = async () => {
        if (!('Notification' in window)) {
            toast({
                title: "Not Supported",
                description: "This browser does not support desktop notifications.",
                variant: "destructive"
            });
            return;
        }

        if (pushEnabled) {
            // We can't actually revoke permission via JS, but we can stop sending them or update UI state
            setPushEnabled(false);
            toast({ title: "Notifications Disabled", description: "You will no longer receive push notifications." });
        } else {
            const permission = await Notification.requestPermission();
            if (permission === 'granted') {
                setPushEnabled(true);
                new Notification("AlQuran AI", { body: "Notifications enabled successfully!" });
                toast({ title: "Notifications Enabled", description: "You will now receive updates." });
            } else {
                toast({ title: "Permission Denied", description: "Please enable notifications in your browser settings.", variant: "destructive" });
            }
        }
    };

    const fetchBookmarks = async () => {
        try {
            const token = localStorage.getItem("user_token");
            if (!token) return;
            const res = await fetch(`${API_BASE_URL}/bookmarks`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setBookmarks(data.bookmarks);
                setShowBookmarks(true);
            }
        } catch (error) {
            console.error("Failed to fetch bookmarks", error);
            toast({ title: "Error", description: "Failed to load bookmarks", variant: "destructive" });
        }
    };

    const handleRemoveBookmark = async (messageId: string) => {
        const token = localStorage.getItem("user_token");
        if (!token) return;
        // Optimistic removal
        setBookmarks(prev => prev.filter(b => b.id !== messageId));
        try {
            await fetch(`${API_BASE_URL}/messages/${messageId}/bookmark`, {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` }
            });
        } catch (error) {
            console.error("Failed to remove bookmark", error);
            toast({ title: "Error", description: "Failed to remove bookmark", variant: "destructive" });
            // Re-fetch to restore state
            fetchBookmarks();
        }
    };

    const toggleBookmarksView = () => {
        if (!showBookmarks) {
            fetchBookmarks();
        } else {
            setShowBookmarks(false);
        }
    };

    if (showBookmarks) {
        return (
            <div className="flex flex-col h-full bg-background-light dark:bg-background-dark">
                {/* Header */}
                <div className="px-4 py-4 flex items-center gap-3 border-b border-primary/10 bg-white/80 dark:bg-background-dark/80 backdrop-blur-sm sticky top-0 z-10">
                    <button
                        onClick={() => setShowBookmarks(false)}
                        className="p-2 rounded-full hover:bg-primary/10 transition-colors text-primary"
                    >
                        <span className="material-symbols-outlined">arrow_back</span>
                    </button>
                    <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-gold-accent" style={{ fontVariationSettings: "'FILL' 1" }}>bookmarks</span>
                        <h1 className="text-xl font-bold text-primary">Saved Bookmarks</h1>
                    </div>
                    <span className="ml-auto text-xs font-medium text-slate-400 bg-slate-100 dark:bg-white/10 px-2 py-1 rounded-full">
                        {bookmarks.length}
                    </span>
                </div>

                {/* Bookmark List */}
                <div className="flex-1 overflow-y-auto px-4 py-4 max-w-2xl mx-auto w-full">
                    {bookmarks.length === 0 ? (
                        <div className="flex flex-col items-center justify-center mt-24 gap-4 text-center px-6">
                            <div className="size-16 rounded-full bg-primary/10 flex items-center justify-center">
                                <span className="material-symbols-outlined text-3xl text-primary/40">bookmarks</span>
                            </div>
                            <p className="font-semibold text-slate-500 dark:text-slate-400">No saved bookmarks yet</p>
                            <p className="text-sm text-slate-400 dark:text-slate-500">
                                Hover over any AI response in a chat and click the{" "}
                                <span className="material-symbols-outlined text-[14px] align-middle">bookmark</span>{" "}
                                icon to save it here.
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {bookmarks.map(b => (
                                <div key={b.id} className="group bg-white dark:bg-card-dark rounded-xl border border-primary/10 shadow-sm overflow-hidden">
                                    {/* Card Header */}
                                    <div className="flex items-center justify-between px-4 pt-3 pb-2 border-b border-slate-50 dark:border-white/5">
                                        <div className="flex items-center gap-2 min-w-0">
                                            <span className="material-symbols-outlined text-[14px] text-gold-accent flex-shrink-0" style={{ fontVariationSettings: "'FILL' 1" }}>bookmark</span>
                                            <span className="text-xs font-semibold text-primary/70 dark:text-primary/60 truncate uppercase tracking-wide">{b.chat_title}</span>
                                        </div>
                                        <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                                            {b.created_at && (
                                                <span className="text-xs text-slate-400 dark:text-slate-500">{formatDate(b.created_at)}</span>
                                            )}
                                            <button
                                                onClick={() => handleRemoveBookmark(b.id)}
                                                className="p-1 rounded text-slate-300 hover:text-red-500 dark:text-slate-600 dark:hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                                                title="Remove bookmark"
                                            >
                                                <span className="material-symbols-outlined text-[16px]">bookmark_remove</span>
                                            </button>
                                        </div>
                                    </div>
                                    {/* Content */}
                                    <div className="px-4 py-3">
                                        <p className="text-slate-700 dark:text-slate-300 text-sm leading-relaxed line-clamp-5">{b.content}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full">
            {/* Header / Profile Section */}
            <div className="relative pt-12 pb-8 px-6 overflow-hidden">
                {/* Background Pattern & Gradient */}
                <div className="absolute inset-0 bg-primary/90 dark:bg-background-dark">
                    <div className="islamic-pattern absolute inset-0 opacity-10 mix-blend-overlay"></div>
                    <div className="absolute inset-0 bg-gradient-to-b from-black/20 to-transparent"></div>
                </div>

                <div className="relative z-10 flex flex-col items-center gap-4 text-white">
                    <div className="relative">
                        <div className="size-24 rounded-full border-4 border-gold-accent bg-cover bg-center shadow-lg bg-slate-200"
                            style={{ backgroundImage: user?.picture ? `url('${user.picture}')` : undefined }}
                        >
                            {!user?.picture && <span className="material-symbols-outlined text-4xl text-slate-400 flex items-center justify-center h-full">person</span>}
                        </div>
                    </div>
                    <div className="text-center">
                        <h1 className="text-2xl font-bold tracking-tight text-white drop-shadow-md">{user?.name || "Guest User"}</h1>
                        <p className="text-white/80 text-sm font-medium">{user?.email || "Sign in to see details"}</p>
                    </div>
                </div>
            </div>

            {/* Content Sections */}
            <div className="flex-1 px-4 py-6 space-y-6 max-w-2xl mx-auto w-full overflow-y-auto">
                {/* Personal Information */}
                <section>
                    <h2 className="text-primary dark:text-primary/80 text-sm font-bold uppercase tracking-wider px-2 mb-2">Personal Information</h2>
                    <div className="bg-white dark:bg-[#1a2e2e] rounded-xl shadow-sm border border-primary/5 divide-y divide-primary/5 overflow-hidden">
                        <button onClick={() => toast({ title: "Coming Soon", description: "Profile editing will be available in a future update." })} className="w-full flex items-center gap-4 p-4 hover:bg-primary/5 transition-colors group text-left">
                            <div className="size-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                                <span className="material-symbols-outlined">person</span>
                            </div>
                            <span className="flex-1 font-medium">Edit Profile</span>
                            <span className="material-symbols-outlined text-primary/40 group-hover:text-primary">chevron_right</span>
                        </button>
                        <button onClick={toggleBookmarksView} className="w-full flex items-center gap-4 p-4 hover:bg-primary/5 transition-colors group text-left">
                            <div className="size-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                                <span className="material-symbols-outlined">bookmarks</span>
                            </div>
                            <span className="flex-1 font-medium">My Bookmarks</span>
                            <span className="material-symbols-outlined text-primary/40 group-hover:text-primary">chevron_right</span>
                        </button>
                    </div>
                </section>

                {/* App Settings */}
                <section>
                    <h2 className="text-primary dark:text-primary/80 text-sm font-bold uppercase tracking-wider px-2 mb-2">App Settings</h2>
                    <div className="bg-white dark:bg-[#1a2e2e] rounded-xl shadow-sm border border-primary/5 divide-y divide-primary/5 overflow-hidden">
                        <div className="flex items-center gap-4 p-4">
                            <div className="size-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                                <span className="material-symbols-outlined">notifications</span>
                            </div>
                            <div className="flex-1">
                                <p className="font-medium">Push Notifications</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    className="sr-only peer"
                                    type="checkbox"
                                    checked={pushEnabled}
                                    onChange={togglePushNotifications}
                                />
                                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
                            </label>
                        </div>
                    </div>
                </section>

                {/* Account Security */}
                <section>
                    <h2 className="text-primary dark:text-primary/80 text-sm font-bold uppercase tracking-wider px-2 mb-2">Account Security</h2>
                    <div className="bg-white dark:bg-[#1a2e2e] rounded-xl shadow-sm border border-primary/5 divide-y divide-primary/5 overflow-hidden">
                        <button onClick={() => navigate('/privacy')} className="w-full flex items-center gap-4 p-4 hover:bg-primary/5 transition-colors group text-left">
                            <div className="size-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                                <span className="material-symbols-outlined">verified_user</span>
                            </div>
                            <span className="flex-1 font-medium">Privacy Policy</span>
                            <span className="material-symbols-outlined text-primary/40 group-hover:text-primary">chevron_right</span>
                        </button>
                    </div>
                </section>

                {/* Logout Button & Version */}
                <div className="pt-4 pb-8 flex flex-col items-center gap-4">
                    <button onClick={handleLogout} className="w-full max-w-sm py-4 bg-white dark:bg-[#1a2e2e] text-red-600 dark:text-red-400 font-bold rounded-xl border border-red-100 dark:border-red-900/30 flex items-center justify-center gap-2 hover:bg-red-50 dark:hover:bg-red-900/10 transition-colors">
                        <span className="material-symbols-outlined">logout</span>
                        Log Out
                    </button>
                    <p className="text-primary/40 text-xs font-medium tracking-widest">VERSION 2.4.0 (2024)</p>
                </div>
            </div>
        </div>
    );
};

export default Account;
