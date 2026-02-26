import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import Account from "./Account";
import Sidebar from "@/components/Sidebar";
import InstallPrompt from "@/components/InstallPrompt";
import FormattedMessage from "@/components/FormattedMessage";

// API Configuration — falls back to localhost for local dev
const API_BASE_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000") + "/api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  sources?: any[];
  is_bookmarked?: boolean;
}

// Sample daily verse
const DAILY_VERSE = {
  arabic: "إِنَّ مَعَ الْعُسْرِ يُسْرًا",
  translation: "Indeed, with hardship comes ease.",
  reference: "Ash-Sharh 94:6"
};

// Topic explorations
const TOPICS = [
  { name: "Patience", icon: "hourglass_empty", color: "text-primary" },
  { name: "Gratitude", icon: "favorite", color: "text-gold-accent" },
  { name: "Justice", icon: "balance", color: "text-primary" },
  { name: "Protection", icon: "shield", color: "text-gold-accent" },
];

// Guest ID generation
const getGuestId = () => {
  let guestId = localStorage.getItem("guest_id");
  if (!guestId) {
    guestId = "guest_" + Math.random().toString(36).substring(2, 15);
    localStorage.setItem("guest_id", guestId);
  }
  return guestId;
};

const Index = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [activeTab, setActiveTab] = useState<"home" | "account">("home");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [refreshSidebarTrigger, setRefreshSidebarTrigger] = useState(0);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [guestQueriesUsed, setGuestQueriesUsed] = useState(0);
  const [isGuest, setIsGuest] = useState(true);

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const navigate = useNavigate();
  const token = localStorage.getItem("user_token");

  // Check if user is logged in
  useEffect(() => {
    setIsGuest(!token);
  }, [token]);

  // Load guest query count from localStorage
  useEffect(() => {
    const savedCount = localStorage.getItem("guest_queries_used");
    if (savedCount) {
      setGuestQueriesUsed(parseInt(savedCount, 10));
    }
  }, []);

  // Toggle dark mode
  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDarkMode);
  }, [isDarkMode]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const loadChat = async (chatId: string) => {
    if (!token) {
      setShowLoginModal(true);
      return;
    }
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/chats/${chatId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setMessages(data.messages);
        setCurrentChatId(chatId);
        setActiveTab("home");
      }
    } catch (error) {
      console.error("Failed to load chat", error);
    } finally {
      setIsLoading(false);
    }
  };

  const callGuestChat = async (messageContent: string): Promise<any> => {
    const response = await fetch(`${API_BASE_URL}/chat/guest`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ 
        message: messageContent, 
        guest_id: getGuestId() 
      }),
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    return response.json();
  };

  const callAuthChat = async (messageContent: string): Promise<any> => {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ message: messageContent, chat_id: currentChatId }),
    });

    if (!response.ok) {
      if (response.status === 401) {
        localStorage.removeItem("user_token");
        localStorage.removeItem("user_profile");
        setIsGuest(true);
        throw new Error("Session expired");
      }
      throw new Error(`API Error: ${response.status}`);
    }
    return response.json();
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    // If guest has used 2 queries, show login modal
    if (isGuest && guestQueriesUsed >= 2) {
      setShowLoginModal(true);
      return;
    }

    const tempId = Date.now().toString();
    const userMessage: Message = { id: tempId, role: "user", content: input.trim() };

    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      let data: any;
      
      if (isGuest) {
        data = await callGuestChat(userMessage.content);
        
        // Update guest query count
        if (data.queries_used) {
          setGuestQueriesUsed(data.queries_used);
          localStorage.setItem("guest_queries_used", data.queries_used.toString());
        }
        
        // Check if limit reached
        if (data.limit_reached) {
          setShowLoginModal(true);
          setIsLoading(false);
          return;
        }
      } else {
        data = await callAuthChat(userMessage.content);
        
        if (data.chat_id && data.chat_id !== currentChatId) {
          setCurrentChatId(data.chat_id);
          setRefreshSidebarTrigger(prev => prev + 1);
        }
      }

      const assistantMessage: Message = {
        id: data.message_id || (Date.now() + 1).toString(),
        role: "assistant",
        content: data.response,
        thinking: data.thinking,
        sources: data.sources_used,
        is_bookmarked: data.is_bookmarked || false
      };

      setMessages(prev => {
        const updated = prev.map(msg =>
          msg.id === tempId ? { ...msg, id: data.user_message_id || msg.id } : msg
        );
        return [...updated, assistantMessage];
      });
    } catch (error) {
      console.error("Error:", error);
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "⚠️ Unable to connect to the knowledge base. Please check your connection.",
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegenerate = async () => {
    if (isLoading) return;
    
    if (isGuest && guestQueriesUsed >= 2) {
      setShowLoginModal(true);
      return;
    }

    const lastUserMsg = [...messages].reverse().find(m => m.role === "user");
    if (!lastUserMsg) return;

    setMessages(prev => {
      const idx = prev.map(m => m.role).lastIndexOf("assistant");
      return idx === -1 ? prev : prev.filter((_, i) => i !== idx);
    });

    setIsLoading(true);
    try {
      let data: any;
      
      if (isGuest) {
        data = await callGuestChat(lastUserMsg.content);
        if (data.queries_used) {
          setGuestQueriesUsed(data.queries_used);
          localStorage.setItem("guest_queries_used", data.queries_used.toString());
        }
      } else {
        data = await callAuthChat(lastUserMsg.content);
      }

      const assistantMessage: Message = {
        id: data.message_id || Date.now().toString(),
        role: "assistant",
        content: data.response,
        thinking: data.thinking,
        sources: data.sources_used,
        is_bookmarked: false,
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Regenerate error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleBookmark = async (messageId: string) => {
    if (!token) {
      setShowLoginModal(true);
      return;
    }

    setMessages(prev => prev.map(msg =>
      msg.id === messageId ? { ...msg, is_bookmarked: !msg.is_bookmarked } : msg
    ));

    try {
      await fetch(`${API_BASE_URL}/messages/${messageId}/bookmark`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
    } catch (error) {
      console.error("Failed to toggle bookmark", error);
    }
  };

  const handleCopy = (id: string, content: string) => {
    navigator.clipboard.writeText(content);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const lastAssistantIdx = messages.map(m => m.role).lastIndexOf("assistant");

  // Gemini-style Login Modal
  const LoginModal = () => (
    <AnimatePresence>
      {showLoginModal && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
          onClick={() => setShowLoginModal(false)}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            className="bg-white dark:bg-card-dark rounded-2xl p-8 max-w-md w-full shadow-2xl border border-primary/10"
            onClick={e => e.stopPropagation()}
          >
            <div className="text-center">
              <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="material-symbols-outlined text-3xl text-primary">auto_awesome</span>
              </div>
              <h2 className="text-2xl font-bold text-primary mb-2">Continue Your Journey</h2>
              <p className="text-slate-600 dark:text-slate-400 mb-6">
                You've used your 2 free questions. Sign in to continue exploring Islamic knowledge and save your chat history.
              </p>
              <div className="flex flex-col gap-3">
                <Button 
                  onClick={() => navigate("/login")}
                  className="w-full bg-primary text-white hover:bg-primary/90 py-6 text-lg font-semibold rounded-xl"
                >
                  Sign in with Google
                </Button>
                <Button 
                  variant="ghost"
                  onClick={() => setShowLoginModal(false)}
                  className="text-slate-500 hover:text-slate-700"
                >
                  Maybe later
                </Button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );

  const renderContent = () => {
    if (activeTab === "account") {
      return <Account />;
    }

    return (
      <div className="flex flex-col h-full bg-background-light dark:bg-background-dark relative">
        {/* Header - Gemini Style */}
        <header className="relative z-10 border-b border-primary/10 bg-white/80 backdrop-blur-sm dark:border-primary/20 dark:bg-background-dark/80">
          <div className="islamic-pattern absolute inset-0 opacity-5" />
          <div className="relative flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-3">
              {token && (
                <Button variant="ghost" size="icon" onClick={() => setIsSidebarOpen(true)} className="text-primary hover:bg-primary/10">
                  <span className="material-symbols-outlined">menu</span>
                </Button>
              )}
              <div className="flex items-center gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10">
                  <span className="material-symbols-outlined text-primary text-xl">auto_awesome</span>
                </div>
                <h1 className="text-lg font-extrabold text-primary dark:text-primary">AlQuran</h1>
              </div>
            </div>
            
            {/* Right side - Gemini style minimal login */}
            <div className="flex items-center gap-2">
              {/* Guest query counter */}
              {isGuest && (
                <span className="text-xs text-slate-500 dark:text-slate-400 hidden sm:inline">
                  {2 - guestQueriesUsed} free {2 - guestQueriesUsed === 1 ? 'question' : 'questions'} left
                </span>
              )}
              
              {/* New Chat button - only show for logged in users */}
              {token && (
                <Button 
                  variant="ghost" 
                  size="icon" 
                  onClick={() => { setMessages([]); setCurrentChatId(null); }} 
                  className="text-primary hover:bg-primary/10"
                  title="New chat"
                >
                  <span className="material-symbols-outlined">edit</span>
                </Button>
              )}
              
              {/* Theme toggle */}
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={() => setIsDarkMode(!isDarkMode)} 
                className="text-primary hover:bg-primary/10"
              >
                <span className="material-symbols-outlined">{isDarkMode ? "light_mode" : "dark_mode"}</span>
              </Button>
              
              {/* Gemini-style Login button */}
              {isGuest ? (
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => navigate("/login")}
                  className="ml-2 rounded-full px-4 border-primary/20 text-primary hover:bg-primary/10 font-medium"
                >
                  Sign in
                </Button>
              ) : (
                <Button 
                  variant="ghost" 
                  size="icon"
                  onClick={() => setActiveTab("account")}
                  className="ml-2 text-primary hover:bg-primary/10"
                >
                  <span className="material-symbols-outlined">account_circle</span>
                </Button>
              )}
            </div>
          </div>
        </header>

        {/* Chat Area */}
        <ScrollArea className="flex-1" ref={scrollRef}>
          <div className="mx-auto max-w-3xl px-4 py-6">
            {messages.length === 0 ? (
              <div className="space-y-6">
                {/* Daily Reflection Card */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="relative overflow-hidden rounded-2xl border border-gold-accent/30 bg-white p-6 shadow-sm dark:bg-card-dark"
                >
                  <p className="mb-1 text-xs font-medium uppercase tracking-wider text-gold-accent">Daily Reflection</p>
                  <p className="mb-3 font-amiri text-3xl leading-relaxed text-primary dark:text-primary-foreground text-right" dir="rtl">{DAILY_VERSE.arabic}</p>
                  <p className="mb-3 text-lg italic text-primary/80 dark:text-primary-foreground/80">"{DAILY_VERSE.translation}"</p>
                  <span className="inline-block rounded-full bg-gold-accent/20 px-3 py-1 text-xs font-medium text-yellow-700 dark:text-gold-accent border border-gold-accent/30">{DAILY_VERSE.reference}</span>
                </motion.div>

                {/* Welcome Message */}
                <div className="py-8 text-center max-w-xl mx-auto">
                  <h2 className="mb-3 font-display text-3xl font-bold text-primary dark:text-primary">Assalamu Alaikum ✨</h2>
                  
                  {isGuest ? (
                    <>
                      <p className="text-slate-600 dark:text-slate-400">
                        Welcome to AlQuran. How may I assist your spiritual journey today?
                      </p>
                      <p className="mt-2 text-sm text-slate-500 dark:text-slate-500">
                        Try 2 questions for free, then sign in to continue.
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="text-slate-600 dark:text-slate-400 mb-2">
                        Welcome back! I'm your AI Islamic scholar, grounded in the Quran, Hadith, and classical scholarship.
                      </p>
                      <p className="text-sm text-slate-500 dark:text-slate-500">
                        Ask me about Islamic rulings, Quranic verses, Hadith, or any questions about your faith journey.
                      </p>
                    </>
                  )}
                </div>

                {/* Topics Grid */}
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {TOPICS.map((topic) => (
                    <button
                      key={topic.name}
                      onClick={() => setInput(`What does the Quran say about ${topic.name}?`)}
                      className="flex flex-col items-center gap-2 rounded-xl border border-primary/10 bg-white p-4 text-sm transition-all hover:border-gold-accent hover:shadow-md dark:bg-card-dark dark:border-primary/20"
                    >
                      <span className={cn("material-symbols-outlined text-3xl", topic.color)}>{topic.icon}</span>
                      <span className="font-bold text-primary dark:text-white">{topic.name}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                <AnimatePresence>
                  {messages.map((message, idx) => (
                    <motion.div
                      key={message.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={cn("flex group relative", message.role === "user" ? "justify-end" : "justify-start")}
                    >
                      <div className={cn("max-w-[85%] rounded-2xl px-5 py-4 shadow-sm",
                        message.role === "user"
                          ? "bg-primary text-white"
                          : "bg-white border border-primary/10 dark:bg-card-dark dark:border-primary/20"
                      )}>
                        {message.role === "assistant" && (
                          <div className="mb-2 flex items-center gap-2">
                            <span className="material-symbols-outlined text-primary text-lg">auto_awesome</span>
                            <span className="text-xs font-bold text-primary">AlQuran Scholar</span>
                          </div>
                        )}

                        {/* Message Content */}
                        <div className={cn("text-[15px] leading-relaxed", message.role === "user" ? "text-white" : "text-slate-800 dark:text-slate-200")}>
                          {message.role === "assistant"
                            ? <FormattedMessage content={message.content} />
                            : message.content}
                        </div>

                        {/* Thinking Block */}
                        {message.thinking && (
                          <div className="mt-3 p-3 bg-slate-50 dark:bg-black/20 rounded-lg text-xs text-slate-500 italic border border-slate-100 dark:border-white/5">
                            <div className="flex items-center gap-1 mb-1 not-italic font-semibold text-slate-400">
                              <span className="material-symbols-outlined text-[14px]">psychology</span>
                              Reasoning
                            </div>
                            {message.thinking}
                          </div>
                        )}

                        {/* Sources Block */}
                        {message.sources && message.sources.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-slate-100 dark:border-white/10">
                            <p className="text-xs font-bold text-primary mb-2 flex items-center gap-1">
                              <span className="material-symbols-outlined text-[14px]">menu_book</span> Sources
                            </p>
                            <div className="flex flex-wrap gap-2">
                              {message.sources.map((src: any, i) => {
                                let label = '';
                                let icon = '📜';
                                if (src.type === 'quran') {
                                  icon = '📖';
                                  label = `Ayah ${src.surah_name} ${src.verse_number}`;
                                } else if (src.type === 'hadith') {
                                  const num = src.hadith_number;
                                  const numStr = num && String(num).toLowerCase() !== 'null' && String(num).toLowerCase() !== 'n/a' && String(num) !== '' ? ` #${num}` : '';
                                  label = `Hadith ${src.collection}${numStr}`;
                                } else if (src.type === 'ijma') {
                                  icon = '⚖️';
                                  label = `Ijma: ${src.topic || 'Scholarly Consensus'}`;
                                } else if (src.type === 'qiyas') {
                                  icon = '⚖️';
                                  label = `Qiyas: ${src.case || 'Analogical Reasoning'}`;
                                } else {
                                  label = src.text || 'Source';
                                }
                                return (
                                  <span key={i} className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-gold-accent/10 text-[10px] text-yellow-800 dark:text-gold-accent border border-gold-accent/20">
                                    {icon} {label}
                                  </span>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* Message Actions — assistant only */}
                        {message.role === "assistant" && (
                          <div className="mt-3 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            {/* Copy */}
                            <Button
                              variant="ghost" size="icon"
                              className="h-7 w-7 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                              onClick={() => handleCopy(message.id, message.content)}
                              title="Copy"
                            >
                              <span className="material-symbols-outlined text-[16px]">
                                {copiedId === message.id ? "check" : "content_copy"}
                              </span>
                            </Button>

                            {/* Regenerate — only on last assistant message */}
                            {idx === lastAssistantIdx && (
                              <Button
                                variant="ghost" size="icon"
                                className="h-7 w-7 text-slate-400 hover:text-primary"
                                onClick={handleRegenerate}
                                title="Regenerate response"
                              >
                                <span className="material-symbols-outlined text-[16px]">refresh</span>
                              </Button>
                            )}

                            {/* Bookmark — requires login */}
                            <Button
                              variant="ghost" size="icon"
                              className={cn("h-7 w-7", message.is_bookmarked ? "text-gold-accent" : "text-slate-400 hover:text-gold-accent")}
                              onClick={() => handleBookmark(message.id)}
                              title={token ? (message.is_bookmarked ? "Remove Bookmark" : "Save to Bookmarks") : "Sign in to bookmark"}
                            >
                              <span
                                className="material-symbols-outlined text-[16px]"
                                style={{ fontVariationSettings: message.is_bookmarked ? "'FILL' 1" : "'FILL' 0" }}
                              >
                                bookmark
                              </span>
                            </Button>
                          </div>
                        )}
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>

                {isLoading && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-2 text-primary items-center p-4 bg-white/50 dark:bg-card-dark/50 rounded-xl w-fit">
                    <span className="material-symbols-outlined animate-spin">progress_activity</span>
                    <span className="text-sm font-medium">Consulting knowledge base...</span>
                  </motion.div>
                )}
              </div>
            )}
          </div>
        </ScrollArea>

        {/* PWA Install Prompt */}
        <InstallPrompt messageCount={messages.length} />

        {/* Input Area */}
        <div className="relative border-t border-primary/10 bg-white/60 px-4 py-4 backdrop-blur-xl dark:border-primary/20 dark:bg-background-dark/80">
          <div className="mx-auto max-w-3xl">
            <div className="flex gap-3 rounded-xl border border-primary/20 bg-white p-2 shadow-sm focus-within:ring-2 focus-within:ring-primary/20 transition-all dark:bg-card-dark dark:border-primary/20">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={isGuest && guestQueriesUsed >= 2 ? "Sign in to continue..." : "Bismillah... Ask your question"}
                disabled={isGuest && guestQueriesUsed >= 2}
                className="min-h-[44px] flex-1 resize-none border-0 bg-transparent text-slate-800 placeholder:text-slate-400 focus-visible:ring-0 dark:text-slate-200 disabled:opacity-50"
                rows={1}
              />
              <Button 
                onClick={sendMessage} 
                disabled={!input.trim() || isLoading || (isGuest && guestQueriesUsed >= 2)} 
                className="h-11 w-11 shrink-0 rounded-lg bg-primary text-white shadow-md hover:bg-primary/90"
              >
                <span className="material-symbols-outlined">{isLoading ? "stop" : "send"}</span>
              </Button>
            </div>
            <p className="mt-2 text-center text-[10px] text-slate-400 dark:text-slate-500 uppercase tracking-widest font-medium">
              AlQuran AI can make mistakes. Verify important information.
            </p>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background-light dark:bg-background-dark font-display text-slate-900 dark:text-white">
      <LoginModal />
      
      {token && (
        <Sidebar
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          currentChatId={currentChatId}
          onSelectChat={loadChat}
          onNewChat={() => {
            setMessages([]);
            setCurrentChatId(null);
            setIsSidebarOpen(false);
          }}
          onProfileClick={() => {
            setActiveTab("account");
            setIsSidebarOpen(false);
          }}
          refreshTrigger={refreshSidebarTrigger}
        />
      )}

      <div className="flex-1 flex flex-col relative w-full h-full overflow-hidden">
        {renderContent()}

        {/* Bottom Nav - Mobile only */}
        <nav className="lg:hidden sticky bottom-0 bg-white dark:bg-background-dark border-t border-primary/10 px-4 py-2 flex items-center justify-around z-50">
          <button onClick={() => { setActiveTab("home"); setIsSidebarOpen(false); }} className={cn("flex flex-col items-center gap-1 p-2", activeTab === "home" ? "text-primary scale-105" : "text-slate-400")}>
            <span className={cn("material-symbols-outlined", activeTab === "home" && "fill-1")}>home</span>
            <span className="text-[10px] font-bold">Home</span>
          </button>
          {token ? (
            <button onClick={() => { setActiveTab("account"); setIsSidebarOpen(false); }} className={cn("flex flex-col items-center gap-1 p-2", activeTab === "account" ? "text-primary scale-105" : "text-slate-400")}>
              <span className={cn("material-symbols-outlined", activeTab === "account" && "fill-1")}>account_circle</span>
              <span className="text-[10px] font-bold">Account</span>
            </button>
          ) : (
            <button onClick={() => navigate("/login")} className="flex flex-col items-center gap-1 p-2 text-slate-400">
              <span className="material-symbols-outlined">login</span>
              <span className="text-[10px] font-bold">Sign in</span>
            </button>
          )}
        </nav>
      </div>
    </div>
  );
};

export default Index;
