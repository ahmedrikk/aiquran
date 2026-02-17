# AlQuran - AI-Powered Quran Discovery

A beautiful, sacred-feeling AI-powered Quran discovery tool. The name works as both **"AI Quran"** and **"Al-Quran"** (The Quran in Arabic).

## Features

✨ **Visual Design**
- Deep Emerald (#064E3B) & Gold (#D97706) color scheme
- Ivory/Parchment (#FDFBF7) background
- 'Inter' font for UI, 'Amiri' for Arabic script
- Islamic geometric patterns as subtle overlays
- Soft shadows and thin gold borders

🎨 **Components**
- Daily Reflection card with Arabic verse
- Streak badge showing daily engagement
- Collapsible sidebar with bookmarks & topics
- Beautiful verse cards for Quran citations
- Glassmorphism floating input bar
- Smooth Framer Motion animations

🌙 **Dark Mode**
- Deep Forest Green (#022C22) theme
- Automatic color adjustments

## Quick Setup

### 1. Replace files in your `sacred-scroll-ai` project:

```
sacred-scroll-ai/
├── index.html              ← Replace
├── package.json            ← Replace (adds framer-motion)
├── tailwind.config.ts      ← Replace
└── src/
    ├── index.css           ← Replace
    └── pages/
        └── Index.tsx       ← Replace
```

### 2. Install new dependencies:

```bash
cd sacred-scroll-ai
npm install
# or
npm install framer-motion
```

### 3. Start your backend:

```bash
# In QuranAI folder
./start.sh
```

### 4. Start frontend:

```bash
cd sacred-scroll-ai
npm run dev
```

### 5. Open http://localhost:8080

## API Configuration

The frontend connects to `http://localhost:9099/v1/chat/completions`.

To change this, edit `API_URL` in `src/pages/Index.tsx`:

```typescript
const API_URL = "http://localhost:9099/v1/chat/completions";
```

## Design System

### Colors
| Name | Hex | Usage |
|------|-----|-------|
| Emerald | #064E3B | Primary actions, headers |
| Sage | #D1FAE5 | User messages, highlights |
| Gold | #D97706 | Accents, badges, send button |
| Ivory | #FDFBF7 | Light mode background |
| Forest | #022C22 | Dark mode background |

### Typography
- **UI Text**: Inter (400, 500, 600, 700)
- **Arabic**: Amiri (400, 700)

### Border Radius
- Cards: `rounded-2xl` (1rem)
- Buttons: `rounded-xl` (0.75rem)
- Badges: `rounded-full`

## Customization

### Change Daily Verse
Edit `DAILY_VERSE` in `Index.tsx`:

```typescript
const DAILY_VERSE = {
  arabic: "Your Arabic text",
  translation: "Your translation",
  reference: "Surah:Ayat"
};
```

### Add More Topics
Edit the `TOPICS` array in `Index.tsx`:

```typescript
const TOPICS = [
  { name: "Patience", icon: Clock, color: "text-emerald-600" },
  // Add more...
];
```

## Architecture

```
Browser (localhost:8080)
    ↓
Noor AI Frontend (React + Vite)
    ↓
Pipelines Server (localhost:9099)
    ↓
Quran-Talk Backend (localhost:8000)
    ↓
Ollama + HNSW Vector DB
```

## License

MIT - Built with ❤️ for the Muslim community
