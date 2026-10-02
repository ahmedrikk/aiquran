import { createClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || import.meta.env.VITE_SUPABASE_ANON_KEY;
export const supabase = url && key ? createClient(url, key) : null;
export const API_ORIGIN = (import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '')).replace(/\/+$/, '').replace(/\/api$/, '');
export const API_BASE_URL = `${API_ORIGIN}/api`;

const jsonResponse = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
});

function syncSession(session: { access_token: string; user: { id: string; email?: string; user_metadata: Record<string, unknown> } } | null) {
  if (!session) {
    localStorage.removeItem('user_token');
    localStorage.removeItem('user_profile');
    return;
  }
  localStorage.setItem('user_token', session.access_token);
  localStorage.setItem('user_profile', JSON.stringify({
    id: session.user.id, email: session.user.email,
    name: session.user.user_metadata.full_name || session.user.user_metadata.name || session.user.email,
    picture: session.user.user_metadata.avatar_url || session.user.user_metadata.picture,
  }));
}

export async function initializeSession() {
  if (!supabase) return;
  const { data } = await supabase.auth.getSession();
  syncSession(data.session);
  supabase.auth.onAuthStateChange((_event, session) => syncSession(session));
}

export async function signOut() {
  if (supabase) await supabase.auth.signOut();
  syncSession(null);
}

function check(error: { message: string } | null) {
  if (error) throw new Error(error.message);
}

/** Preserve the app's API contract while using Supabase Auth, RLS and Edge Functions. */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  if (!supabase) {
    try {
      return await fetch(input, { ...init, signal: init.signal || AbortSignal.timeout(65_000) });
    } catch {
      return jsonResponse({ detail: 'The service is temporarily unavailable. Please try again shortly.' }, 503);
    }
  }
  const path = new URL(input, window.location.origin).pathname;
  const method = init.method || 'GET';
  const body = typeof init.body === 'string' ? JSON.parse(init.body) : {};
  try {
    if (path === '/auth/google') {
      const { data, error } = await supabase.auth.signInWithIdToken({ provider: 'google', token: body.credential });
      if (error || !data.session) return jsonResponse({ detail: 'Google sign-in failed. Please try again.' }, 401);
      syncSession(data.session);
      return jsonResponse({ access_token: data.session.access_token, user: JSON.parse(localStorage.getItem('user_profile')!) });
    }

    const { data: { session }, error: sessionError } = await supabase.auth.getSession();
    check(sessionError);
    syncSession(session);
    if (path === '/api/chat/guest' || path === '/api/chat') {
      if (path === '/api/chat' && !session) return jsonResponse({ detail: 'Session expired. Please sign in again.' }, 401);
      return await fetch(`${url}/functions/v1/quran-chat`, {
        method: 'POST',
        headers: {
          apikey: key!, 'Content-Type': 'application/json',
          ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}),
        },
        body: JSON.stringify(body), signal: init.signal || AbortSignal.timeout(65_000),
      });
    }
    if (!session) return jsonResponse({ detail: 'Session expired. Please sign in again.' }, 401);

    if (path === '/api/chats') {
      const { data, error } = await supabase.from('quran_chats').select('id,title,created_at,updated_at').order('updated_at', { ascending: false }).limit(50);
      check(error);
      return jsonResponse({ chats: data });
    }
    const chatId = path.match(/^\/api\/chats\/([\w-]+)$/)?.[1];
    if (chatId) {
      if (method === 'DELETE') {
        const { error } = await supabase.from('quran_chats').delete().eq('id', chatId);
        check(error);
        return jsonResponse({ success: true });
      }
      if (method === 'PATCH') {
        const { data, error } = await supabase.from('quran_chats').update({ title: body.title }).eq('id', chatId).select('id,title').single();
        check(error);
        return jsonResponse(data);
      }
      const { data: chat, error } = await supabase.from('quran_chats').select('id,title').eq('id', chatId).maybeSingle();
      check(error);
      if (!chat) return jsonResponse({ detail: 'Chat not found' }, 404);
      const { data: messages, error: messagesError } = await supabase.from('quran_messages').select('id,role,content,sources_used,created_at').eq('chat_id', chatId).order('created_at').order('role', { ascending: false });
      check(messagesError);
      const { data: bookmarks, error: bookmarksError } = await supabase.from('quran_bookmarks').select('message_id');
      check(bookmarksError);
      const bookmarked = new Set(bookmarks?.map(b => b.message_id));
      return jsonResponse({ ...chat, messages: messages?.map(m => ({ ...m, sources: m.sources_used, is_bookmarked: bookmarked.has(m.id) })) });
    }
    const messageId = path.match(/^\/api\/messages\/([\w-]+)\/bookmark$/)?.[1];
    if (messageId) {
      const { data, error } = await supabase.from('quran_bookmarks').select('message_id').eq('message_id', messageId).maybeSingle();
      check(error);
      const result = data
        ? await supabase.from('quran_bookmarks').delete().eq('message_id', messageId)
        : await supabase.from('quran_bookmarks').insert({ user_id: session.user.id, message_id: messageId });
      check(result.error);
      return jsonResponse({ is_bookmarked: !data });
    }
    if (path === '/api/bookmarks') {
      const { data, error } = await supabase.from('quran_bookmarks').select('created_at,quran_messages!inner(id,content,chat_id,quran_chats!inner(title))').order('created_at', { ascending: false });
      check(error);
      return jsonResponse({ bookmarks: data?.map(b => {
        const m = b.quran_messages as unknown as { id: string; content: string; chat_id: string; quran_chats: { title: string } };
        return { id: m.id, content: m.content, chat_id: m.chat_id, chat_title: m.quran_chats.title, created_at: b.created_at };
      }) });
    }
    return jsonResponse({ detail: 'Endpoint not found' }, 404);
  } catch {
    return jsonResponse({ detail: 'The service could not complete your request. Please try again.' }, 503);
  }
}

export async function readApiResponse(response: Response) {
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.detail || (response.status === 401 ? 'Session expired. Please sign in again.' : 'The service is temporarily unavailable. Please try again shortly.'));
  if (!data) throw new Error('The service returned an invalid response. Please try again.');
  return data;
}
