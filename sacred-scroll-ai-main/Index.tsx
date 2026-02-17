import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Send, 
  Loader2, 
  Moon, 
  Sun,
  Menu,
  X,
  Sparkles,
  BookOpen,
  Share2,
  Flame,
  MessageCircle,
  Bookmark,
  Compass,
  Heart,
  Scale,
  Shield,
  Clock
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

// API Configuration
const API_URL = "http://localhost:9099/v1/chat/completions";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

// Sample daily verse
const DAILY_VERSE = {
  arabic: "إِنَّ مَعَ الْعُسْرِ يُسْرًا",
  translation: "Indeed, with hardship comes ease.",
  reference: "Ash-Sharh 94:6"
};

// Topic explorations
const TOPICS = [
  { name: "Patience", icon: Clock, color: "text-emerald-600" },
  { name: "Gratitude", icon: Heart, color: "text-gold" },
  { name: "Justice", icon: Scale, color: "text-emerald-600" },
  { name: "Protection", icon: Shield, color: "text-gold" },
];

// Parse and render markdown-style content
const renderFormattedText = (text: string) => {
  // Split by lines first
  const lines = text.split('\n');
  
  return lines.map((line, lineIndex) => {
    if (!line.trim()) return <br key={lineIndex} />;
    
    // Check for source citations (--- followed by Sources)
    if (line.trim() === '---') {
      return <hr key={lineIndex} className="my-4 border-emerald-200 dark:border-emerald-800" />;
    }
    
    // Check for source header
    if (line.includes('📚 Sources') || line.includes('**📚 Sources')) {
      return (
        <p key={lineIndex} className="mt-4 mb-2 text-sm font-semibold text-emerald-700 dark:text-sage">
          📚 Sources
        </p>
      );
    }
    
    // Check for source list items
    if (line.trim().startsWith('- 📖') || line.trim().startsWith('- 📜')) {
      const sourceText = line.replace(/^-\s*/, '');
      return (
        <span 
          key={lineIndex} 
          className="inline-block mr-2 mb-1 px-3 py-1 text-xs font-medium rounded-full bg-gold/20 text-amber-700 dark:text-gold border border-gold/30"
        >
          {sourceText}
        </span>
      );
    }
    
    // Parse inline formatting
    const parts = parseInlineFormatting(line);
    
    return (
      <p key={lineIndex} className="mb-3 leading-relaxed last:mb-0">
        {parts}
      </p>
    );
  });
};

// Parse inline markdown: **bold**, *italic*, and Surah references
const parseInlineFormatting = (text: string) => {
  const elements: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;
  
  while (remaining.length > 0) {
    // Check for bold **text**
    const boldMatch = remaining.match(/^\*\*(.+?)\*\*/);
    if (boldMatch) {
      const content = boldMatch[1];
      // Check if it's a Surah reference
      if (/Surah\s+\d+:\d+|^\d+:\d+$/.test(content) || content.includes('Surah')) {
        elements.push(
          <span 
            key={key++} 
            className="inline-block mx-1 px-2 py-0.5 text-sm font-semibold rounded-lg bg-gold/20 text-amber-700 dark:text-gold border border-gold/30"
          >
            {content}
          </span>
        );
      } else {
        elements.push(
          <strong key={key++} className="font-semibold text-emerald-800 dark:text-sage">
            {content}
          </strong>
        );
      }
      remaining = remaining.slice(boldMatch[0].length);
      continue;
    }
    
    // Check for italic *text*
    const italicMatch = remaining.match(/^\*([^*]+)\*/);
    if (italicMatch) {
      elements.push(
        <em key={key++} className="italic text-emerald-700 dark:text-sage/90">
          "{italicMatch[1]}"
        </em>
      );
      remaining = remaining.slice(italicMatch[0].length);
      continue;
    }
    
    // Check for Surah reference pattern without markdown (e.g., Surah 31:11)
    const surahMatch = remaining.match(/^(Surah\s+[\w-]+\s+\d+:\d+)/i);
    if (surahMatch) {
      elements.push(
        <span 
          key={key++} 
          className="inline-block mx-1 px-2 py-0.5 text-sm font-semibold rounded-lg bg-gold/20 text-amber-700 dark:text-gold border border-gold/30"
        >
          {surahMatch[1]}
        </span>
      );
      remaining = remaining.slice(surahMatch[0].length);
      continue;
    }
    
    // Find next special character or end
    const nextSpecial = remaining.search(/\*|Surah\s+[\w-]+\s+\d+:\d+/i);
    if (nextSpecial === -1) {
      elements.push(<span key={key++}>{remaining}</span>);
      break;
    } else if (nextSpecial === 0) {
      // No match found, move forward by one character
      elements.push(<span key={key++}>{remaining[0]}</span>);
      remaining = remaining.slice(1);
    } else {
      elements.push(<span key={key++}>{remaining.slice(0, nextSpecial)}</span>);
      remaining = remaining.slice(nextSpecial);
    }
  }
  
  return elements;
};

const Index = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [streak, setStreak] = useState(7);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [input]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const apiMessages = [...messages, userMessage].map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "quran-talk",
          messages: apiMessages,
          stream: false,
        }),
      });

      if (!response.ok) throw new Error(`API Error: ${response.status}`);

      const data = await response.json();
      const assistantContent = data.choices?.[0]?.message?.content || "I could not generate a response.";

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: assistantContent,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Error:", error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "⚠️ Unable to connect to the knowledge base. Please ensure the backend is running.",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleTopicClick = (topic: string) => {
    setInput(`What does the Quran say about ${topic.toLowerCase()}?`);
    textareaRef.current?.focus();
  };

  const handleSpecialButton = (type: string) => {
    if (type === "quote") {
      setInput("Give me an inspiring quote from the Quran");
    } else if (type === "progress") {
      setInput("What should I read today to continue my Quran journey?");
    }
    textareaRef.current?.focus();
  };

  return (
    <div className={cn(
      "flex h-screen overflow-hidden transition-colors duration-300",
      "bg-ivory dark:bg-forest"
    )}>
      {/* Sidebar */}
      <AnimatePresence>
        {isSidebarOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/20 lg:hidden"
              onClick={() => setIsSidebarOpen(false)}
            />
            
            {/* Sidebar Panel */}
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="fixed left-0 top-0 z-50 h-full w-[280px] border-r border-emerald-200 bg-white/95 backdrop-blur-sm dark:border-emerald-900 dark:bg-forest-light/95 lg:relative lg:z-0"
            >
              <div className="flex h-full flex-col">
                {/* Sidebar Header */}
                <div className="flex items-center justify-between border-b border-emerald-100 p-4 dark:border-emerald-900">
                  <h2 className="font-semibold text-emerald-900 dark:text-sage">Navigation</h2>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setIsSidebarOpen(false)}
                    className="lg:hidden"
                  >
                    <X className="h-5 w-5" />
                  </Button>
                </div>

                <ScrollArea className="flex-1 p-4">
                  {/* Recent Inquiries */}
                  <div className="mb-6">
                    <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-emerald-700 dark:text-sage/80">
                      <MessageCircle className="h-4 w-4" />
                      Recent Inquiries
                    </h3>
                    <div className="space-y-2">
                      {["Meaning of patience", "Surah Al-Fatiha", "Prophet's guidance"].map((item, i) => (
                        <button
                          key={i}
                          className="w-full rounded-xl p-3 text-left text-sm text-emerald-800 transition-all hover:bg-sage/50 dark:text-sage dark:hover:bg-emerald-900/50"
                        >
                          {item}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Bookmarked Ayats */}
                  <div className="mb-6">
                    <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-emerald-700 dark:text-sage/80">
                      <Bookmark className="h-4 w-4" />
                      Bookmarked Ayats
                    </h3>
                    <div className="space-y-2">
                      {["Al-Baqarah 2:286", "Al-Imran 3:139", "Ar-Rahman 55:13"].map((item, i) => (
                        <button
                          key={i}
                          className="w-full rounded-xl border border-gold/20 p-3 text-left text-sm text-emerald-800 transition-all hover:border-gold/50 hover:bg-gold/10 dark:text-sage"
                        >
                          {item}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Topic Explorations */}
                  <div>
                    <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-emerald-700 dark:text-sage/80">
                      <Compass className="h-4 w-4" />
                      Topic Explorations
                    </h3>
                    <div className="grid grid-cols-2 gap-2">
                      {TOPICS.map((topic, i) => (
                        <button
                          key={i}
                          onClick={() => handleTopicClick(topic.name)}
                          className="flex items-center gap-2 rounded-xl border border-emerald-200 p-3 text-sm text-emerald-800 transition-all hover:border-gold hover:bg-sage/30 dark:border-emerald-800 dark:text-sage dark:hover:bg-emerald-900/50"
                        >
                          <topic.icon className={cn("h-4 w-4", topic.color)} />
                          {topic.name}
                        </button>
                      ))}
                    </div>
                  </div>
                </ScrollArea>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Main Content */}
      <div className="flex flex-1 flex-col">
        {/* Header */}
        <header className="relative z-10 border-b border-emerald-200 bg-white/80 backdrop-blur-sm dark:border-emerald-900 dark:bg-forest-light/80">
          {/* Geometric Pattern Overlay */}
          <div className="islamic-pattern absolute inset-0 opacity-5" />
          
          <div className="relative flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsSidebarOpen(true)}
                className="text-emerald-700 hover:bg-sage/50 dark:text-sage"
              >
                <Menu className="h-5 w-5" />
              </Button>
              
              <div className="flex items-center gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-600 to-emerald-800 shadow-md">
                  <Moon className="h-5 w-5 text-gold" />
                </div>
                <div>
                  <h1 className="text-lg font-semibold text-emerald-900 dark:text-sage">
                    AlQuran
                  </h1>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Streak Badge */}
              <motion.div
                whileHover={{ scale: 1.05 }}
                className="hidden items-center gap-2 rounded-full border border-gold/30 bg-gradient-to-r from-gold/10 to-amber-500/10 px-3 py-1.5 sm:flex"
              >
                <Flame className="h-4 w-4 text-gold" />
                <span className="text-sm font-medium text-amber-700 dark:text-gold">
                  {streak} Day Streak
                </span>
              </motion.div>

              {/* Dark Mode Toggle */}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsDarkMode(!isDarkMode)}
                className="text-emerald-700 hover:bg-sage/50 dark:text-sage"
              >
                {isDarkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
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
                  whileHover={{ y: -2, boxShadow: "0 8px 30px rgba(0,0,0,0.08)" }}
                  className="relative overflow-hidden rounded-2xl border border-gold/30 bg-ivory p-6 shadow-sm dark:bg-forest-light/50"
                >
                  <div className="absolute right-3 top-3">
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-emerald-600 hover:bg-sage/50 dark:text-sage">
                      <Share2 className="h-4 w-4" />
                    </Button>
                  </div>
                  
                  <p className="mb-1 text-xs font-medium uppercase tracking-wider text-gold">
                    Daily Reflection
                  </p>
                  
                  <p className="mb-3 font-amiri text-3xl leading-relaxed text-emerald-900 dark:text-sage text-right" dir="rtl">
                    {DAILY_VERSE.arabic}
                  </p>
                  
                  <p className="mb-3 text-lg italic text-emerald-700 dark:text-sage/80">
                    "{DAILY_VERSE.translation}"
                  </p>
                  
                  <span className="inline-block rounded-full bg-gold/20 px-3 py-1 text-xs font-medium text-amber-700 dark:text-gold border border-gold/30">
                    {DAILY_VERSE.reference}
                  </span>
                </motion.div>

                {/* Welcome Message */}
                <div className="py-8 text-center">
                  <motion.h2
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="mb-2 font-amiri text-3xl text-emerald-900 dark:text-sage"
                  >
                    Assalamu Alaikum ✨
                  </motion.h2>
                  <motion.p
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="text-emerald-600 dark:text-sage/70"
                  >
                    Welcome to AlQuran. How may I assist your spiritual journey today?
                  </motion.p>
                </div>

                {/* Special Buttons */}
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                  className="flex justify-center gap-3"
                >
                  <motion.button
                    whileHover={{ scale: 1.03, y: -2 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleSpecialButton("quote")}
                    className="flex items-center gap-2 rounded-2xl border border-gold/30 bg-gradient-to-r from-gold/10 to-amber-500/10 px-5 py-3 text-sm font-medium text-amber-700 transition-all hover:border-gold hover:shadow-md dark:text-gold"
                  >
                    <Sparkles className="h-4 w-4" />
                    Quote of the Day
                  </motion.button>
                  
                  <motion.button
                    whileHover={{ scale: 1.03, y: -2 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleSpecialButton("progress")}
                    className="flex items-center gap-2 rounded-2xl border border-emerald-300 bg-gradient-to-r from-emerald-50 to-sage/50 px-5 py-3 text-sm font-medium text-emerald-700 transition-all hover:border-emerald-400 hover:shadow-md dark:border-emerald-700 dark:from-emerald-900/30 dark:to-emerald-800/30 dark:text-sage"
                  >
                    <BookOpen className="h-4 w-4" />
                    Daily Reading Progress
                  </motion.button>
                </motion.div>

                {/* Explore Topics */}
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.4 }}
                  className="pt-4"
                >
                  <p className="mb-4 text-center text-sm font-medium text-emerald-600 dark:text-sage/70">
                    Explore Topics
                  </p>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    {TOPICS.map((topic, i) => (
                      <motion.button
                        key={topic.name}
                        whileHover={{ scale: 1.03, y: -2 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => handleTopicClick(topic.name)}
                        className="flex flex-col items-center gap-2 rounded-2xl border border-emerald-200 bg-white/60 p-4 text-sm transition-all hover:border-gold hover:bg-sage/30 hover:shadow-md dark:border-emerald-800 dark:bg-forest-light/30 dark:hover:bg-emerald-900/50"
                      >
                        <topic.icon className={cn("h-6 w-6", topic.color)} />
                        <span className="font-medium text-emerald-800 dark:text-sage">{topic.name}</span>
                      </motion.button>
                    ))}
                  </div>
                </motion.div>
              </div>
            ) : (
              <div className="space-y-4">
                <AnimatePresence>
                  {messages.map((message) => (
                    <motion.div
                      key={message.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -20 }}
                      className={cn(
                        "flex",
                        message.role === "user" ? "justify-end" : "justify-start"
                      )}
                    >
                      <div
                        className={cn(
                          "max-w-[85%] rounded-2xl px-4 py-3",
                          message.role === "user"
                            ? "bg-emerald-700 text-white dark:bg-emerald-800"
                            : "border border-emerald-100 bg-white shadow-sm dark:border-emerald-800 dark:bg-forest-light"
                        )}
                      >
                        {message.role === "assistant" && (
                          <div className="mb-3 flex items-center gap-2">
                            <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-700">
                              <Moon className="h-3 w-3 text-gold" />
                            </div>
                            <span className="text-xs font-semibold text-emerald-600 dark:text-sage/70">
                              AlQuran
                            </span>
                          </div>
                        )}
                        <div className={cn(
                          "text-[15px]",
                          message.role === "user" 
                            ? "text-white" 
                            : "text-emerald-900 dark:text-sage"
                        )}>
                          {message.role === "assistant" 
                            ? renderFormattedText(message.content)
                            : <p>{message.content}</p>
                          }
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
                
                {isLoading && (
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex justify-start"
                  >
                    <div className="rounded-2xl border border-emerald-100 bg-white px-5 py-4 shadow-sm dark:border-emerald-800 dark:bg-forest-light">
                      <div className="flex items-center gap-3 text-emerald-600 dark:text-sage">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span className="text-sm">Reflecting on your question...</span>
                      </div>
                    </div>
                  </motion.div>
                )}
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Input Area */}
        <div className="relative border-t border-emerald-200 bg-white/60 px-4 py-4 backdrop-blur-xl dark:border-emerald-900 dark:bg-forest-light/60">
          <div className="mx-auto max-w-3xl">
            <div className="flex gap-3 rounded-2xl border border-emerald-200 bg-white/80 p-2 shadow-lg backdrop-blur-sm dark:border-emerald-800 dark:bg-forest-light/80">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Bismillah... Ask your question"
                className="min-h-[44px] flex-1 resize-none border-0 bg-transparent text-emerald-900 placeholder:text-emerald-400 focus-visible:ring-0 dark:text-sage dark:placeholder:text-sage/50"
                rows={1}
              />
              <Button
                onClick={sendMessage}
                disabled={!input.trim() || isLoading}
                className="h-11 w-11 shrink-0 rounded-xl bg-gradient-to-br from-emerald-600 to-emerald-800 p-0 text-white shadow-md transition-all hover:from-emerald-700 hover:to-emerald-900 hover:shadow-lg disabled:opacity-50"
              >
                {isLoading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Send className="h-5 w-5 text-gold" />
                )}
              </Button>
            </div>
            <p className="mt-2 text-center text-xs text-emerald-500 dark:text-sage/50">
              AlQuran provides guidance based on Quran and Hadith. Consult qualified scholars for specific rulings.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Index;
