
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";

const API_BASE_URL = "http://localhost:8000/api";

interface Chat {
    id: string;
    title: string;
    created_at: string;
}

interface SidebarProps {
    isOpen: boolean;
    onClose: () => void;
    currentChatId: string | null;
    onSelectChat: (chatId: string) => void;
    onNewChat: () => void;
    onProfileClick: () => void;
    refreshTrigger: number;
}

const Sidebar = ({ isOpen, onClose, currentChatId, onSelectChat, onNewChat, onProfileClick, refreshTrigger }: SidebarProps) => {
    const [chats, setChats] = useState<Chat[]>([]);
    const [searchQuery, setSearchQuery] = useState("");
    const navigate = useNavigate();
    const token = localStorage.getItem("user_token");
    const userProfileString = localStorage.getItem("user_profile");
    const user = userProfileString ? JSON.parse(userProfileString) : null;

    useEffect(() => {
        if (isOpen && token) {
            fetchChats();
        }
    }, [isOpen, token, refreshTrigger]);

    const fetchChats = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/chats?limit=50`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (response.ok) {
                const data = await response.json();
                setChats(data.chats);
            }
        } catch (error) {
            console.error("Failed to fetch chats", error);
        }
    };

    const handleDeleteChat = async (e: React.MouseEvent, chatId: string) => {
        e.stopPropagation();
        if (!confirm("Are you sure you want to delete this chat?")) return;

        try {
            const response = await fetch(`${API_BASE_URL}/chats/${chatId}`, {
                method: "DELETE",
                headers: { Authorization: `Bearer ${token}` },
            });
            if (response.ok) {
                setChats(chats.filter(c => c.id !== chatId));
                if (currentChatId === chatId) onNewChat();
            }
        } catch (error) {
            console.error("Failed to delete chat", error);
        }
    };

    const filteredChats = searchQuery.trim()
        ? chats.filter(c => c.title.toLowerCase().includes(searchQuery.toLowerCase()))
        : chats;

    return (
        <>
            {/* Overlay */}
            {isOpen && (
                <div
                    className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
                    onClick={onClose}
                />
            )}

            {/* Sidebar */}
            <div
                className={cn(
                    "fixed inset-y-0 left-0 z-50 w-72 transform bg-white shadow-xl transition-transform duration-300 dark:bg-card-dark border-r border-primary/10 dark:border-primary/20",
                    isOpen ? "translate-x-0" : "-translate-x-full"
                )}
            >
                <div className="flex h-full flex-col">
                    {/* Header */}
                    <div className="flex items-center justify-between p-4 border-b border-primary/10 dark:border-primary/20">
                        <h2 className="text-lg font-bold text-primary">History</h2>
                        <Button variant="ghost" size="icon" onClick={onClose} className="lg:hidden text-primary">
                            <span className="material-symbols-outlined">close</span>
                        </Button>
                    </div>

                    {/* New Chat + Search */}
                    <div className="p-3 space-y-2 border-b border-primary/10 dark:border-primary/20">
                        <Button
                            onClick={() => {
                                onNewChat();
                                if (window.innerWidth < 1024) onClose();
                            }}
                            className="w-full justify-start gap-2 bg-primary/10 text-primary hover:bg-primary/20 border-0"
                            variant="outline"
                        >
                            <span className="material-symbols-outlined">add</span>
                            New Chat
                        </Button>

                        {/* Search box */}
                        <div className="relative">
                            <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-[16px] text-slate-400 pointer-events-none">
                                search
                            </span>
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={e => setSearchQuery(e.target.value)}
                                placeholder="Search chats..."
                                className="w-full pl-8 pr-3 py-2 text-sm rounded-lg bg-slate-100 dark:bg-black/20 border border-transparent focus:border-primary/30 focus:outline-none text-slate-700 dark:text-slate-300 placeholder:text-slate-400"
                            />
                            {searchQuery && (
                                <button
                                    onClick={() => setSearchQuery("")}
                                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                                >
                                    <span className="material-symbols-outlined text-[16px]">close</span>
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Chat List */}
                    <div className="flex-1 overflow-y-auto px-2 py-2">
                        {!token ? (
                            <div className="p-4 text-center text-sm text-slate-500">
                                <p>Sign in to save your chat history.</p>
                                <Button
                                    variant="link"
                                    className="text-primary mt-2"
                                    onClick={() => navigate("/login")}
                                >
                                    Sign In
                                </Button>
                            </div>
                        ) : filteredChats.length === 0 ? (
                            <p className="text-center text-xs text-slate-400 mt-6">
                                {searchQuery ? "No chats match your search." : "No chats yet."}
                            </p>
                        ) : (
                            <div className="space-y-1">
                                {filteredChats.map(chat => (
                                    <div
                                        key={chat.id}
                                        onClick={() => {
                                            onSelectChat(chat.id);
                                            if (window.innerWidth < 1024) onClose();
                                        }}
                                        className={cn(
                                            "group flex cursor-pointer items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-colors",
                                            currentChatId === chat.id
                                                ? "bg-primary text-white"
                                                : "text-slate-700 hover:bg-primary/5 dark:text-slate-300 dark:hover:bg-primary/10"
                                        )}
                                    >
                                        <div className="flex items-center gap-2 overflow-hidden">
                                            <span className={cn(
                                                "material-symbols-outlined text-[18px] flex-shrink-0",
                                                currentChatId === chat.id ? "text-white/80" : "text-slate-400 group-hover:text-primary"
                                            )}>
                                                chat_bubble_outline
                                            </span>
                                            <span className="truncate font-medium">{chat.title}</span>
                                        </div>

                                        <button
                                            onClick={e => handleDeleteChat(e, chat.id)}
                                            className={cn(
                                                "opacity-0 transition-opacity group-hover:opacity-100 flex-shrink-0 ml-1",
                                                currentChatId === chat.id ? "text-white/70 hover:text-white" : "text-slate-400 hover:text-red-500"
                                            )}
                                        >
                                            <span className="material-symbols-outlined text-[16px]">delete</span>
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* User Profile (Mini) */}
                    {token && user && (
                        <div className="p-4 border-t border-primary/10 dark:border-primary/20">
                            <div
                                className="flex items-center gap-3 cursor-pointer hover:bg-primary/5 p-2 rounded-lg transition-colors"
                                onClick={onProfileClick}
                            >
                                {user.picture ? (
                                    <img src={user.picture} alt={user.name} className="h-8 w-8 rounded-full object-cover border border-primary/20" />
                                ) : (
                                    <div className="h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center text-primary">
                                        <span className="material-symbols-outlined text-sm">person</span>
                                    </div>
                                )}
                                <div className="flex-1 overflow-hidden">
                                    <p className="text-sm font-bold truncate text-primary dark:text-primary-foreground">{user.name}</p>
                                    <p className="text-xs text-slate-500 truncate dark:text-slate-400">{user.email}</p>
                                </div>
                                <span className="material-symbols-outlined text-[16px] text-slate-400">chevron_right</span>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </>
    );
};

export default Sidebar;
