import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";

import { GoogleOAuthProvider } from '@react-oauth/google';
import { initNativeBridge } from './native-bridge';
import { initializeSession } from './lib/backend';

// REPLACE WITH YOUR ACTUAL GOOGLE CLIENT ID
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "846223196875-iim6ake76pqe61tufn3t8rccogqv7ec2.apps.googleusercontent.com";

Promise.all([initNativeBridge(), initializeSession().catch(() => undefined)]).then(() => {
  createRoot(document.getElementById("root")!).render(
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <App />
    </GoogleOAuthProvider>
  );
});
