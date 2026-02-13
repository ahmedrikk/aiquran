# Quran-Talk: Open WebUI Customization Guide

## Quick Start (Updated Files)

Replace your existing files with the simplified versions:
- `backend.py` - Removed thinking mode, always uses fast responses
- `pipelines_server.py` - Single model, cleaner API

## Open WebUI Customization Options

### Option 1: Use Built-in Theming (Easiest)

Open WebUI has built-in customization via Admin Panel:

1. **Branding**
   - Go to `Admin Panel → Settings → Interface`
   - Set custom name: "Quran-Talk"
   - Upload custom logo/favicon

2. **Environment Variables**
   ```bash
   export WEBUI_NAME="Quran-Talk"
   export DEFAULT_MODELS="quran-talk"
   export ENABLE_SIGNUP=false  # Optional: disable public signups
   ```

3. **Custom CSS** (via Admin Panel → Settings → Interface → Custom CSS)
   ```css
   /* Islamic-themed styling */
   :root {
     --primary-color: #C05621;  /* Terracotta */
     --bg-color: #FAF9F6;       /* Warm cream */
   }
   
   /* Custom font for Arabic */
   .message-content {
     font-family: 'Amiri', 'Lora', serif;
   }
   
   /* RTL support for Arabic text */
   [dir="rtl"] {
     font-family: 'Amiri', 'Traditional Arabic', serif;
     font-size: 1.2em;
     line-height: 2;
   }
   ```

---

### Option 2: Fork Open WebUI (Full Customization)

For complete control, fork the Open WebUI repository:

```bash
# Clone the repository
git clone https://github.com/open-webui/open-webui.git quran-talk-ui
cd quran-talk-ui

# Install dependencies
npm install

# Run in development mode
npm run dev
```

**Key files to modify:**

| File | Purpose |
|------|---------|
| `src/lib/constants.ts` | App name, default settings |
| `src/lib/components/` | UI components |
| `src/routes/` | Page layouts |
| `static/` | Logo, favicon, images |
| `tailwind.config.js` | Color theme |

**Example: Change branding in `src/lib/constants.ts`:**
```typescript
export const WEBUI_NAME = 'Quran-Talk';
export const WEBUI_DESCRIPTION = 'Your Islamic Scholar AI';
```

---

### Option 3: Build Custom Frontend (Most Control)

If you want a completely custom UI, build your own frontend that talks to the pipelines API:

**API Endpoints:**

```
GET  /health              - Health check
GET  /v1/models           - List available models
POST /v1/chat/completions - Chat (OpenAI-compatible)
```

**Example: Simple HTML/JS Chat:**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Quran-Talk</title>
    <style>
        body { font-family: 'Lora', serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        #chat { border: 1px solid #ddd; height: 400px; overflow-y: auto; padding: 10px; margin-bottom: 10px; }
        .user { color: #333; margin: 10px 0; }
        .assistant { color: #C05621; margin: 10px 0; background: #f9f9f9; padding: 10px; border-radius: 8px; }
        #input { width: calc(100% - 70px); padding: 10px; }
        button { padding: 10px 20px; background: #C05621; color: white; border: none; cursor: pointer; }
    </style>
</head>
<body>
    <h1>🕌 Quran-Talk</h1>
    <div id="chat"></div>
    <input type="text" id="input" placeholder="Ask about the Quran or Hadith...">
    <button onclick="sendMessage()">Send</button>

    <script>
        const API_URL = 'http://localhost:9099/v1/chat/completions';
        let history = [];

        async function sendMessage() {
            const input = document.getElementById('input');
            const query = input.value.trim();
            if (!query) return;
            
            // Add user message
            history.push({ role: 'user', content: query });
            document.getElementById('chat').innerHTML += `<div class="user"><b>You:</b> ${query}</div>`;
            input.value = '';
            
            // Call API
            const response = await fetch(API_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: 'quran-talk',
                    messages: history,
                    stream: false
                })
            });
            
            const data = await response.json();
            const answer = data.choices[0].message.content;
            
            // Add assistant message
            history.push({ role: 'assistant', content: answer });
            document.getElementById('chat').innerHTML += `<div class="assistant"><b>Scholar:</b> ${answer}</div>`;
            document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;
        }

        // Send on Enter
        document.getElementById('input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    </script>
</body>
</html>
```

---

### Option 4: React/Next.js Custom App

For a production-ready custom frontend:

```bash
npx create-next-app@latest quran-talk-frontend
cd quran-talk-frontend
npm install
```

**Key features to implement:**
- Chat interface with streaming support
- Message history persistence
- Arabic text rendering (RTL support)
- Source citations display
- Mobile-responsive design

---

## Recommended Approach

| Goal | Recommended Option |
|------|-------------------|
| Quick branding changes | Option 1 (Built-in theming) |
| Moderate customization | Option 2 (Fork Open WebUI) |
| Completely unique UI | Option 3 or 4 (Custom frontend) |
| Learning/prototyping | Option 3 (Simple HTML) |

---

## Running the Stack

```bash
# Terminal 1: Backend
cd /path/to/quranai
source venv/bin/activate
uvicorn backend:app --host 0.0.0.0 --port 8000

# Terminal 2: Pipelines Server
python pipelines_server.py

# Terminal 3: Open WebUI (if using)
open-webui serve
```

Then configure Open WebUI:
1. Go to Admin Panel → Settings → Connections
2. Add OpenAI API connection:
   - URL: `http://localhost:9099`
   - Key: `0p3n-w3bu!`
3. Set `quran-talk` as default model

---

## Need Help?

Let me know if you want me to:
1. Build a complete custom React frontend
2. Add specific features to the backend
3. Create a Docker setup for deployment
4. Add authentication/user management
