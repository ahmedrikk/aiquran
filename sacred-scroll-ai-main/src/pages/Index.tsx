import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import Account from "./Account";
import Sidebar from "@/components/Sidebar";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

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

// Markdown renderer with code block highlighting
const MarkdownRenderer = ({ content }: { content: string }) => (
  <ReactMarkdown
    remarkPlugins={[remarkGfm]}
    components={{
      pre({ children }) {
        return <div className="my-3 rounded-xl overflow-hidden text-sm">{children}</div>;
      },
      code({ className, children }) {
        const match = /language-(\w+)/.exec(className || "");
        if (match) {
          return (
            <SyntaxHighlighter
              language={match[1]}
              style={oneDark}
              customStyle={{ margin: 0, borderRadius: "0.75rem", fontSize: "0.8rem" }}
            >
              {String(children).replace(/\n$/, "")}
            </SyntaxHighlighter>
          );
        }
        return (
          <code className="bg-slate-100 dark:bg-black/30 rounded px-1.5 py-0.5 text-[0.82em] font-mono text-primary dark:text-primary-foreground">
            {children}
          </code>
        );
      },
      p({ children }) {
        return <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>;
      },
      ul({ children }) {
        return <ul className="list-disc pl-5 mb-2 space-y-1">{children}</ul>;
      },
      ol({ children }) {
        return <ol className="list-decimal pl-5 mb-2 space-y-1">{children}</ol>;
      },
      li({ children }) {
        return <li className="leading-relaxed">{children}</li>;
      },
      strong({ children }) {
        return <strong className="font-bold text-primary dark:text-primary-foreground">{children}</strong>;
      },
      blockquote({ children }) {
        return (
          <blockquote className="border-l-4 border-gold-accent/60 pl-4 italic text-slate-500 dark:text-slate-400 my-2">
            {children}
          </blockquote>
        );
      },
      h1({ children }) { return <h1 className="text-xl font-bold text-primary mb-2 mt-3">{children}</h1>; },
      h2({ children }) { return <h2 className="text-lg font-bold text-primary mb-1 mt-3">{children}</h2>; },
      h3({ children }) { return <h3 className="text-base font-semibold text-primary mb-1 mt-2">{children}</h3>; },
    }}
  >
    {content}
  </ReactMarkdown>
);

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

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const navigate = useNavigate();
  const token = localStorage.getItem("user_token");

  // Auth guard — redirect to login if not authenticated
  useEffect(() => {
    if (!token) {
      navigate("/login", { replace: true });
    }
  }, [token, navigate]);

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

  const callChat = async (messageContent: string): Promise<void> => {
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
        navigate("/login", { replace: true });
        throw new Error("Session expired");
      }
      throw new Error(`API Error: ${response.status}`);
    }
    const data = await response.json();

    if (data.chat_id && data.chat_id !== currentChatId) {
      setCurrentChatId(data.chat_id);
      setRefreshSidebarTrigger(prev => prev + 1);
    }

    return data;
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const tempId = Date.now().toString();
    const userMessage: Message = { id: tempId, role: "user", content: input.trim() };

    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const data: any = await callChat(userMessage.content);

      const assistantMessage: Message = {
        id: data.message_id || (Date.now() + 1).toString(),
        role: "assistant",
        content: data.response,
        thinking: data.thinking,
        sources: data.sources_used,
        is_bookmarked: data.is_bookmarked
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

    // Find the last user message
    const lastUserMsg = [...messages].reverse().find(m => m.role === "user");
    if (!lastUserMsg) return;

    // Drop the last assistant message from the UI
    setMessages(prev => {
      const idx = prev.map(m => m.role).lastIndexOf("assistant");
      return idx === -1 ? prev : prev.filter((_, i) => i !== idx);
    });

    setIsLoading(true);
    try {
      const data: any = await callChat(lastUserMsg.content);

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
    if (!token) return;

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
      setMessages(prev => prev.map(msg =>
        msg.id === messageId ? { ...msg, is_bookmarked: !msg.is_bookmarked } : msg
      ));
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

  // Index of the last assistant message (for regenerate button)
  const lastAssistantIdx = messages.map(m => m.role).lastIndexOf("assistant");

  const renderContent = () => {
    if (activeTab === "account") {
      return <Account />;
    }

    return (
      <div className="flex flex-col h-full bg-background-light dark:bg-background-dark relative">
        {/* Header */}
        <header className="relative z-10 border-b border-primary/10 bg-white/80 backdrop-blur-sm dark:border-primary/20 dark:bg-background-dark/80">
          <div className="islamic-pattern absolute inset-0 opacity-5" />
          <div className="relative flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={() => setIsSidebarOpen(true)} className="text-primary hover:bg-primary/10">
                <span className="material-symbols-outlined">menu</span>
              </Button>
              <div className="flex items-center gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10">
                  <span className="material-symbols-outlined text-primary text-xl">auto_awesome</span>
                </div>
                <h1 className="text-lg font-extrabold text-primary dark:text-primary">AlQuran</h1>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" onClick={() => { setMessages([]); setCurrentChatId(null); }} className="text-primary hover:bg-primary/10 lg:hidden">
                <span className="material-symbols-outlined">add_comment</span>
              </Button>
              <Button variant="ghost" size="icon" onClick={() => setIsDarkMode(!isDarkMode)} className="text-primary hover:bg-primary/10">
                <span className="material-symbols-outlined">{isDarkMode ? "light_mode" : "dark_mode"}</span>
              </Button>
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
                <div className="py-8 text-center">
                  <h2 className="mb-2 font-display text-3xl font-bold text-primary dark:text-primary">Assalamu Alaikum ✨</h2>
                  <p className="text-slate-600 dark:text-slate-400">Welcome to AlQuran. How may I assist your spiritual journey today?</p>
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
                            ? <MarkdownRenderer content={message.content} />
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
                              {message.sources.map((src: any, i) => (
                                <span key={i} className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-gold-accent/10 text-[10px] text-yellow-800 dark:text-gold-accent border border-gold-accent/20">
                                  {src.type === "quran" ? "📖" : "📜"}
                                  {src.type === "quran"
                                    ? `Ayah ${src.surah_name} ${src.verse_number}`
                                    : `Hadith ${src.collection} #${src.hadith_number}`}
                                </span>
                              ))}
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

                            {/* Bookmark */}
                            <Button
                              variant="ghost" size="icon"
                              className={cn("h-7 w-7", message.is_bookmarked ? "text-gold-accent" : "text-slate-400 hover:text-gold-accent")}
                              onClick={() => handleBookmark(message.id)}
                              title={message.is_bookmarked ? "Remove Bookmark" : "Save to Bookmarks"}
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

        {/* Input Area */}
        <div className="relative border-t border-primary/10 bg-white/60 px-4 py-4 backdrop-blur-xl dark:border-primary/20 dark:bg-background-dark/80">
          <div className="mx-auto max-w-3xl">
            <div className="flex gap-3 rounded-xl border border-primary/20 bg-white p-2 shadow-sm focus-within:ring-2 focus-within:ring-primary/20 transition-all dark:bg-card-dark dark:border-primary/20">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Bismillah... Ask your question"
                className="min-h-[44px] flex-1 resize-none border-0 bg-transparent text-slate-800 placeholder:text-slate-400 focus-visible:ring-0 dark:text-slate-200"
                rows={1}
              />
              <Button onClick={sendMessage} disabled={!input.trim() || isLoading} className="h-11 w-11 shrink-0 rounded-lg bg-primary text-white shadow-md hover:bg-primary/90">
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

      <div className="flex-1 flex flex-col relative w-full h-full overflow-hidden">
        {renderContent()}

        {/* Bottom Nav - Mobile only */}
        <nav className="lg:hidden sticky bottom-0 bg-white dark:bg-background-dark border-t border-primary/10 px-4 py-2 flex items-center justify-around z-50">
          <button onClick={() => { setActiveTab("home"); setIsSidebarOpen(false); }} className={cn("flex flex-col items-center gap-1 p-2", activeTab === "home" ? "text-primary scale-105" : "text-slate-400")}>
            <span className={cn("material-symbols-outlined", activeTab === "home" && "fill-1")}>home</span>
            <span className="text-[10px] font-bold">Home</span>
          </button>
          <button onClick={() => { setActiveTab("account"); setIsSidebarOpen(false); }} className={cn("flex flex-col items-center gap-1 p-2", activeTab === "account" ? "text-primary scale-105" : "text-slate-400")}>
            <span className={cn("material-symbols-outlined", activeTab === "account" && "fill-1")}>account_circle</span>
            <span className="text-[10px] font-bold">Account</span>
          </button>
        </nav>
      </div>
    </div>
  );
};

export default Index;
