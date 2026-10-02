import { createClient } from 'npm:@supabase/supabase-js@2';
import { boundedSources, composeAnswer, searchQuestion, sourceOnlyAnswer, SYSTEM_PROMPT, validateQuestion, type Source } from './core.ts';

const allowedOrigins = (Deno.env.get('FRONTEND_URLS') || 'https://aiquran.live,https://www.aiquran.live,http://localhost:8080').split(',').map(s => s.trim());
const url = Deno.env.get('SUPABASE_URL')!;
const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const db = createClient(url, serviceKey, { auth: { persistSession: false, autoRefreshToken: false } });

function response(body: unknown, status: number, origin: string) {
  return new Response(JSON.stringify(body), { status, headers: {
    'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Vary': 'Origin',
    'Access-Control-Allow-Origin': origin, 'Access-Control-Allow-Headers': 'authorization,apikey,content-type,x-client-info',
    'Access-Control-Allow-Methods': 'POST,OPTIONS', 'X-Content-Type-Options': 'nosniff',
  } });
}

async function fingerprint(value: string) {
  const secret = Deno.env.get('GUEST_RATE_LIMIT_SECRET');
  if (!secret) throw new Error('Guest rate limiting is not configured');
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const digest = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('');
}

async function generate(prompt: string) {
  const apiKey = Deno.env.get('GEMINI_API_KEY');
  const model = Deno.env.get('GEMINI_MODEL') || 'gemini-3.5-flash-lite';
  if (!apiKey) throw new Error('AI provider not configured');
  const started = Date.now();
  let status: number | undefined;
  let usage: Record<string, number> = {};
  let success = false;
  try {
    const result = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`, {
      method: 'POST', signal: AbortSignal.timeout(45_000),
      headers: { 'x-goog-api-key': apiKey, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] },
        contents: [{ role: 'user', parts: [{ text: prompt }] }],
        generationConfig: { responseMimeType: 'application/json', temperature: 0.2, maxOutputTokens: 4096 },
      }),
    });
    status = result.status;
    if (!result.ok) throw new Error(`Provider unavailable (${status})`);
    const data = await result.json();
    usage = data.usageMetadata || {};
    const text = data.candidates?.[0]?.content?.parts?.map((p: { text?: string; thought?: boolean }) => p.thought ? '' : p.text || '').join('');
    if (!text) throw new Error('Provider returned no explanation');
    success = true;
    return text;
  } finally {
    // Record aggregate usage, never questions, credentials or provider response bodies.
    await db.from('quran_api_usage').insert({ provider: 'Google Gemini', model, success, status_code: status,
      latency_ms: Date.now() - started, prompt_tokens: usage.promptTokenCount, completion_tokens: usage.candidatesTokenCount });
  }
}

Deno.serve(async request => {
  const origin = request.headers.get('origin') || '';
  if (origin && !allowedOrigins.includes(origin)) return response({ detail: 'Origin not allowed' }, 403, '');
  if (request.method === 'OPTIONS') return response({}, 200, origin);
  if (request.method !== 'POST') return response({ detail: 'Method not allowed' }, 405, origin);
  if (Number(request.headers.get('content-length') || 0) > 32000) return response({ detail: 'Request too large' }, 413, origin);
  const reservations: string[] = [];
  let completed = false;
  try {
    const raw = await request.text();
    if (raw.length > 32000) return response({ detail: 'Request too large' }, 413, origin);
    let body: Record<string, unknown>;
    let question: string;
    try { body = JSON.parse(raw); question = validateQuestion(body); }
    catch (error) { return response({ detail: error instanceof Error ? error.message : 'Invalid request' }, 400, origin); }

    const bearer = request.headers.get('authorization')?.replace(/^Bearer\s+/i, '');
    let userId: string | null = null;
    if (bearer) {
      const { data, error } = await db.auth.getUser(bearer);
      if (error || !data.user) return response({ detail: 'Session expired. Please sign in again.' }, 401, origin);
      userId = data.user.id;
    }
    if (!userId && body.chat_id) return response({ detail: 'Please sign in to open a saved chat.' }, 401, origin);
    let history: Array<{ role: string; content: string }> = [];
    if (userId && body.chat_id) {
      const { data: chat, error } = await db.from('quran_chats').select('id').eq('id', body.chat_id).eq('user_id', userId).maybeSingle();
      if (error) throw error;
      if (!chat) return response({ detail: 'Chat not found' }, 404, origin);
      const { data, error: historyError } = await db.from('quran_messages').select('role,content').eq('chat_id', chat.id).order('created_at', { ascending: false }).order('role').limit(6);
      if (historyError) throw historyError;
      history = (data || []).reverse();
    } else if (!userId && Array.isArray(body.history)) {
      history = body.history.slice(-6).filter(m => m && ['user','assistant'].includes(m.role) && typeof m.content === 'string').map(m => ({ role: m.role, content: m.content.slice(0, 2000) }));
    }

    let queriesUsed = 0;
    const day = new Date().toISOString().slice(0, 10);
    const buckets: Array<{ bucket: string; limit: number }> = [];
    if (userId) buckets.push({ bucket: `user:${userId}:${day}`, limit: 50 });
    else {
      if (typeof body.guest_id !== 'string' || !/^[\w-]{8,100}$/.test(body.guest_id)) return response({ detail: 'Invalid guest session. Please refresh the page.' }, 400, origin);
      // Supabase gateway-provided IP limits rotating guest IDs, without storing raw IPs.
      const ip = request.headers.get('x-forwarded-for')?.split(',')[0].trim() || 'unknown';
      buckets.push({ bucket: `guest:${await fingerprint(body.guest_id)}`, limit: 2 });
      buckets.push({ bucket: `ip:${await fingerprint(ip)}:${day}`, limit: 10 });
    }
    for (const bucket of buckets) {
      const { data, error } = await db.rpc('quran_reserve_quota', { p_bucket: bucket.bucket, p_limit: bucket.limit });
      if (error) throw error;
      if (data == null) {
        if (!userId && bucket.bucket.startsWith('guest:')) return response({ response: '', limit_reached: true, queries_used: 2, queries_remaining: 0, message: 'Please sign in to continue.' }, 200, origin);
        return response({ detail: 'You have reached today’s question limit. Please try again tomorrow.' }, 429, origin);
      }
      reservations.push(bucket.bucket);
      if (bucket.bucket.startsWith('guest:')) queriesUsed = data;
    }

    const { count, error: corpusError } = await db.from('quran_sources').select('id', { count: 'exact', head: true });
    if (corpusError || !count) throw new Error('Source corpus is not ready');
    const search = searchQuestion(question);
    const { data, error } = /\bquran\b/i.test(question) && search.p_surah === null
      ? await db.from('quran_sources').select('*').eq('source_type', 'quran').textSearch('search_en', search.p_query, { type: 'websearch', config: 'english' }).order('id').limit(5)
      : await db.rpc('quran_search_sources', search);
    if (error) throw error;
    const sources = boundedSources((data || []) as Source[]);
    let answer;
    if (!sources.length) answer = { response: 'I could not find supporting sources for this question. Try a specific topic or a chapter and verse reference such as 2:153.', sources_used: [] };
    else {
      try {
        const output = await generate(JSON.stringify({ question, history, sources: sources.map(({ search_en: _a, search_ar: _b, ...s }: Source & { search_en?: unknown; search_ar?: unknown }) => s) }));
        answer = composeAnswer(output, sources);
      } catch (error) {
        console.warn('Explanation unavailable:', error instanceof Error ? error.message : 'Unknown provider failure');
        answer = sourceOnlyAnswer(sources);
      }
    }
    let saved = {};
    if (userId) {
      const { data, error } = await db.rpc('quran_save_exchange', { p_user: userId, p_chat: body.chat_id || null, p_question: question, p_answer: answer.response, p_sources: answer.sources_used });
      if (error) throw error;
      saved = data;
    }
    // A missing source or provider failure never consumes a free question.
    completed = sources.length > 0 && !('degraded' in answer);
    return response({ ...answer, ...saved, thinking: '', limit_reached: false,
      ...(userId ? {} : { queries_used: completed ? queriesUsed : queriesUsed - 1, queries_remaining: 2 - (completed ? queriesUsed : queriesUsed - 1) }) }, 200, origin);
  } catch {
    return response({ detail: 'The service is temporarily unavailable. Please try again shortly.' }, 503, origin);
  } finally {
    if (!completed) for (const bucket of reservations) await db.rpc('quran_release_quota', { p_bucket: bucket });
  }
});
