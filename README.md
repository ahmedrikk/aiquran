# AlQuran

React/Vite Quran companion with a Supabase backend. The Python/Railway backend is retained for local/legacy use.

## Why the backend changed

The deployed browser app points at `aiquran-production.up.railway.app`, which returned 404 during diagnosis. This implementation follows Pixel Pulse/Talus's separation of browser UI, Supabase data/auth, and server-side Gemini calls. It uses a **separate QuranAI project**; do not apply this migration to Talus.

The old metadata also mislabeled Quran verses (for example 1:1 contained 1:2). The new importer joins Arabic and translation by their explicit chapter, verse and global ayah IDs. It validates all 114 chapters and 6,236 verses. Never upload the legacy `metadata.json` into the new source table.

## Backend behavior

- Google ID-token login through Supabase Auth, with persisted sessions and automatic token refresh.
- Chats, messages and bookmarks in Postgres. Row-level security limits reads and bookmarks to each user. Only the server can create assistant replies. Exchanges are saved transactionally.
- Two free guest explanations, enforced atomically in Postgres, plus a daily limit per hashed network address. Signed-in users have 50 questions per UTC day.
- Server-side Gemini requests with timeouts and aggregate usage logging. Provider keys never enter the browser bundle.
- Full-text retrieval in English and normalized Arabic, plus direct `chapter:verse` lookup. This is lexical retrieval, not the previous semantic embedding index. Other languages may need an English topic or verse reference for retrieval.
- Exact source quotations and references come from the corpus. The model selects source IDs and writes an explanation; unknown IDs and model-written quotations/reference numbers are rejected. This reduces citation errors; explanations still need human verification.
- During provider failure, readers receive clearly labeled source-only results. Failed explanations and missing matches do not consume guest questions.
- Guest history is sent only for the current conversation and is not saved. Authenticated history is stored in the user's private chats.

## Deploy to a separate QuranAI Supabase project

1. Create/select the QuranAI project. Enable Google in Authentication → Providers using the existing Google web client ID and client secret. Allow the deployed domains in Google's authorized JavaScript origins. Set Supabase's Site URL to `https://www.aiquran.live` and allow `https://aiquran.live/**` and `https://www.aiquran.live/**` as redirects.
2. Link the project using the Supabase CLI. Apply `supabase/migrations/20261002000001_quran_backend.sql` with `supabase db push`. Do not run it against Talus.
3. Set the server secrets from `supabase/.env.example`: `GEMINI_API_KEY`, `GEMINI_MODEL`, `GUEST_RATE_LIMIT_SECRET` (random 32 bytes or more), and `FRONTEND_URLS`. Supabase supplies its own URL/service-role key to Edge Functions.
4. `supabase functions deploy quran-chat`. JWT verification is disabled at the gateway for guest requests; the function validates every supplied signed-in token using Supabase Auth.
5. From the repository root run `npm ci` and `npm run sources:download`. Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in the shell, then run `npm run sources:upload`. These are server credentials; never prefix a service-role key with `VITE_` or commit it. Downloads use [Al Quran Cloud](https://alquran.cloud/api) (`en.asad` translation, Uthmani Arabic) and the explicitly numbered [Hadith API](https://github.com/fawazahmed0/hadith-api) Bukhari editions.
6. In Vercel's QuranAI project, keep the root directory `sacred-scroll-ai-main`, build `npm run build`, and output `dist`. Set `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` (or `VITE_SUPABASE_ANON_KEY`), and optionally `VITE_GOOGLE_CLIENT_ID`. The old `VITE_API_URL` is ignored when Supabase config is present. Redeploy so these build-time settings enter the bundle.
7. Verify a guest question, follow-up, guest limit, real Google sign-in, chat reload, bookmark, logout and private chat access before considering production repaired. Existing Python JWTs are not reused; users sign in again. Migrating old SQLite conversations requires the original database, which is not in this repository.

The source-only path works without a provider key, but a working AI explanation requires a configured Gemini key. Real Google login requires the provider settings above.

## Local development and checks

```sh
npm ci
npm run test:database
cd sacred-scroll-ai-main
npm ci
npm test
npx tsc --noEmit -p tsconfig.app.json
npm run build
```

Copy `sacred-scroll-ai-main/.env.example` to `.env.local` and fill in **public** QuranAI project settings; then run `npm run dev`. Without those settings, the legacy Python API is used (localhost in development, `VITE_API_URL` when supplied).

Database tests run a disposable local Postgres runtime and exercise ownership, grants, private bookmarks, transactional message saves, quota reservation/refunds and source search. Handler tests use mocked infrastructure/provider responses; they do not prove live credentials or production deployment.

Official integration references: [Supabase Google sign-in](https://supabase.com/docs/guides/auth/social-login/auth-google), [ID-token exchange](https://supabase.com/docs/reference/javascript/auth-signinwithidtoken), and [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).
