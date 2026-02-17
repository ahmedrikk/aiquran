import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import PrivacyPolicy from "./pages/PrivacyPolicy";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Index />} />

          {/* Actually, looking at the layout, the user wants a Bottom Nav. If the bottom nav is IN the Index page, then Account and Login might be part of that or separate. The prompt says "Add bottom navigation bar with Home, Quran, Prayer, Account tabs". Login is likely separate. */}
          {/* But wait, I just created Login.tsx. */}
          {/* I'll add a proper route for it. */}
          {/* The user didn't explicitly ask for a /login route, but they provided the HTML for it. */}
          {/* I will add it as /login. */}

          {/* Wait, the "Login" HTML page has "Welcome Back" and sign in. */}
          {/* The "Account" HTML page is what shows up in the "Account" tab. */}
          {/* So "Account" is likely a tab within the main app, while "Login" is outside. */}
          <Route path="/login" element={<Login />} />
          <Route path="/privacy" element={<PrivacyPolicy />} />
          {/* Account is handled inside Index via tabs as per plan. */}
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
