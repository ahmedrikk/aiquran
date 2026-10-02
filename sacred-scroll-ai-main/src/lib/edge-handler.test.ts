// @vitest-environment node
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';

const fixtures = vi.hoisted(() => ({
  rpc: vi.fn(), from: vi.fn(), getUser: vi.fn(),
}));
vi.mock('@supabase/supabase-js', () => ({ createClient: () => ({ ...fixtures, auth: { getUser: fixtures.getUser } }) }));
let handler: (request: Request) => Promise<Response>;
const source = { id: 'quran-2-153', source_type: 'quran', surah_name: 'Al-Baqarah', surah_number: 2, verse_number: 153, text_en: 'Seek help through patience and prayer.', text_ar: 'الصبر', source_url: 'https://alquran.cloud/ayah/2:153' };
let quota: number | null;
let corpusCount: number;
let chat: { id: string } | null;

beforeAll(async () => {
  vi.stubGlobal('crypto', webcrypto);
  vi.stubGlobal('Deno', {
    env: { get: (name: string) => ({ SUPABASE_URL: 'https://test.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'server-test', GEMINI_API_KEY: 'provider-test', GUEST_RATE_LIMIT_SECRET: 'unit-test-only-secret' })[name] },
    serve: (fn: typeof handler) => { handler = fn; },
  });
  await import('../../../supabase/functions/quran-chat/index');
});

beforeEach(() => {
  quota = 1; corpusCount = 1; chat = null;
  fixtures.getUser.mockReset().mockResolvedValue({ data: { user: null }, error: new Error('Invalid token') });
  fixtures.rpc.mockReset().mockImplementation(async (name: string) => {
    if (name === 'quran_reserve_quota') return { data: quota, error: null };
    if (name === 'quran_search_sources') return { data: [source], error: null };
    if (name === 'quran_save_exchange') return { data: { chat_id: 'saved-chat', message_id: 'saved-answer' }, error: null };
    return { data: null, error: null };
  });
  fixtures.from.mockReset().mockImplementation((table: string) => ({
    select: (_fields: string, options?: { head?: boolean }) => table === 'quran_sources' ? (options?.head ? Promise.resolve({ count: corpusCount, error: null }) : {
      eq: function () { return this; },
      textSearch: function () { return this; },
      order: function () { return this; },
      limit: async () => ({ data: [source], error: null }),
    }) : {
      eq: function () { return this; },
      maybeSingle: async () => ({ data: chat, error: null }),
    },
    insert: async () => ({ error: null }),
  }));
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ candidates: [{ content: { parts: [{ text: JSON.stringify({ answer: 'This passage encourages perseverance.', source_ids: [source.id] }) }] } }] }), { status: 200 })));
});

function request(body = { message: 'What does the Quran say about patience?', guest_id: 'guest_test123' }, headers = {}) {
  return new Request('https://test.supabase.co/functions/v1/quran-chat', {
    method: 'POST', headers: { origin: 'https://aiquran.live', 'Content-Type': 'application/json', 'x-forwarded-for': '127.0.0.1', ...headers }, body: JSON.stringify(body),
  });
}

describe('chat request flow', () => {
  it('returns a grounded guest answer and charges one question', async () => {
    const response = await handler(request());
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ queries_used: 1, queries_remaining: 1, sources_used: [{ id: source.id }] });
    expect(fixtures.rpc.mock.calls.filter(c => c[0] === 'quran_release_quota')).toHaveLength(0);
  });
  it('rejects invalid authentication before calling the model', async () => {
    const response = await handler(request(undefined, { authorization: 'Bearer forged' }));
    expect(response.status).toBe(401);
    expect(fetch).not.toHaveBeenCalled();
    expect(fixtures.rpc).not.toHaveBeenCalled();
  });
  it('blocks exhausted guests without provider usage', async () => {
    quota = null;
    const response = await handler(request());
    expect(await response.json()).toMatchObject({ limit_reached: true, queries_used: 2 });
    expect(fetch).not.toHaveBeenCalled();
  });
  it('returns verified sources and refunds both reservations on provider failure', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Provider offline'));
    const response = await handler(request());
    expect(await response.json()).toMatchObject({ degraded: true, queries_used: 0, queries_remaining: 2 });
    expect(fixtures.rpc.mock.calls.filter(c => c[0] === 'quran_release_quota')).toHaveLength(2);
  });
  it('reports an empty corpus as service unavailable and refunds the question', async () => {
    corpusCount = 0;
    const response = await handler(request());
    expect(response.status).toBe(503);
    expect(fetch).not.toHaveBeenCalled();
    expect(fixtures.rpc.mock.calls.filter(c => c[0] === 'quran_release_quota')).toHaveLength(2);
  });
  it('does not read another users chat', async () => {
    fixtures.getUser.mockResolvedValue({ data: { user: { id: 'alice' } }, error: null });
    const response = await handler(request({ message: 'Explain patience', chat_id: '00000000-0000-4000-8000-000000000002' } as never, { authorization: 'Bearer alice-token' }));
    expect(response.status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
  });
  it('saves signed-in messages only after a successful response', async () => {
    fixtures.getUser.mockResolvedValue({ data: { user: { id: 'alice' } }, error: null });
    const response = await handler(request(undefined, { authorization: 'Bearer alice-token' }));
    expect(await response.json()).toMatchObject({ chat_id: 'saved-chat', message_id: 'saved-answer' });
    expect(fixtures.rpc.mock.calls.find(c => c[0] === 'quran_save_exchange')?.[1].p_user).toBe('alice');
  });
  it('blocks unexpected browser origins', async () => {
    const response = await handler(request(undefined, { origin: 'https://untrusted.example' }));
    expect(response.status).toBe(403);
    expect(fixtures.rpc).not.toHaveBeenCalled();
  });
});
