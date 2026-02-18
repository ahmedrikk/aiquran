import { useEffect, useState } from "react";

const DISMISS_KEY = "pwa-install-dismissed-at";
const DISMISS_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

function isDismissed(): boolean {
  const raw = localStorage.getItem(DISMISS_KEY);
  if (!raw) return false;
  return Date.now() - Number(raw) < DISMISS_TTL_MS;
}

function isIOS(): boolean {
  return /iphone|ipad|ipod/i.test(navigator.userAgent) && !(window as any).MSStream;
}

function isInStandaloneMode(): boolean {
  return (
    (window.navigator as any).standalone === true ||
    window.matchMedia("(display-mode: standalone)").matches
  );
}

interface InstallPromptProps {
  messageCount: number;
}

export default function InstallPrompt({ messageCount }: InstallPromptProps) {
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [visible, setVisible] = useState(false);
  const [ios, setIos] = useState(false);

  useEffect(() => {
    if (isInStandaloneMode() || isDismissed()) return;

    const apple = isIOS();
    setIos(apple);

    if (apple) {
      // Show iOS hint once user is engaged
      if (messageCount >= 2) setVisible(true);
      return;
    }

    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };

    window.addEventListener("beforeinstallprompt", handler as EventListener);
    return () => window.removeEventListener("beforeinstallprompt", handler as EventListener);
  }, []);

  // Show Android/Chrome banner once engaged and prompt is ready
  useEffect(() => {
    if (!ios && deferredPrompt && messageCount >= 2 && !isDismissed()) {
      setVisible(true);
    }
  }, [deferredPrompt, messageCount, ios]);

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
    setVisible(false);
  };

  const install = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") {
      setVisible(false);
    }
    setDeferredPrompt(null);
  };

  if (!visible) return null;

  return (
    <div className="mx-auto max-w-3xl px-4 pb-2">
      <div className="flex items-center gap-3 rounded-xl border border-[#064E3B]/30 bg-[#064E3B]/5 px-4 py-3 shadow-sm dark:bg-[#064E3B]/20 dark:border-[#064E3B]/40">
        <span className="text-xl shrink-0">📲</span>

        <p className="flex-1 text-sm text-slate-700 dark:text-slate-200 leading-snug">
          {ios ? (
            <>
              <strong className="text-[#064E3B] dark:text-emerald-400">Add to Home Screen:</strong>{" "}
              tap the share button, then <em>"Add to Home Screen"</em>
            </>
          ) : (
            <>
              <strong className="text-[#064E3B] dark:text-emerald-400">Add AlQuran</strong>{" "}
              to your home screen for the best experience
            </>
          )}
        </p>

        {!ios && (
          <button
            onClick={install}
            className="shrink-0 rounded-lg bg-[#064E3B] px-3 py-1.5 text-sm font-semibold text-white hover:bg-[#053F30] transition-colors"
          >
            Install
          </button>
        )}

        <button
          onClick={dismiss}
          aria-label="Dismiss"
          className="shrink-0 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 text-lg leading-none transition-colors"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
