import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { PGlite } from '@electric-sql/pglite';

const db = new PGlite();
await db.exec(`
  create role anon; create role authenticated; create role service_role bypassrls;
  create schema auth;
  create table auth.users (id uuid primary key);
  create function auth.uid() returns uuid language sql stable as $$
    select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
  $$;
  grant usage on schema public, auth to anon, authenticated, service_role;
  grant execute on function auth.uid() to authenticated;
`);
await db.exec(await readFile(new URL('../supabase/migrations/20261002000001_quran_backend.sql', import.meta.url), 'utf8'));
const alice = '00000000-0000-4000-8000-000000000001';
const bob = '00000000-0000-4000-8000-000000000002';
await db.query('insert into auth.users values ($1), ($2)', [alice, bob]);
const saved = (await db.query(`select quran_save_exchange($1,null,'Patience','A grounded answer','[]') as result`, [alice])).rows[0].result;
assert.ok(saved.chat_id && saved.message_id && saved.user_message_id);
assert.equal((await db.query('select count(*)::integer as n from quran_messages')).rows[0].n, 2);

async function asUser(id, action) {
  await db.exec('set role authenticated');
  await db.query(`select set_config('request.jwt.claim.sub',$1,false)`, [id]);
  try { await action(); } finally { await db.exec('reset role'); }
}
await asUser(alice, async () => {
  assert.equal((await db.query('select * from quran_chats')).rows.length, 1);
  assert.equal((await db.query('select * from quran_messages')).rows.length, 2);
  await db.query('insert into quran_bookmarks(user_id,message_id) values ($1,$2)', [alice, saved.message_id]);
  await assert.rejects(db.query("insert into quran_messages(chat_id,role,content) values ($1,'assistant','Forged answer')", [saved.chat_id]));
  await assert.rejects(db.query('select * from quran_sources'));
  await assert.rejects(db.query('select quran_reserve_quota($1,2)', ['unauthorized']));
  await assert.rejects(db.query('update quran_chats set user_id=$1 where id=$2', [bob, saved.chat_id]));
});
await asUser(bob, async () => {
  assert.equal((await db.query('select * from quran_chats')).rows.length, 0);
  assert.equal((await db.query('select * from quran_messages')).rows.length, 0);
  assert.equal((await db.query('select * from quran_bookmarks')).rows.length, 0);
  await assert.rejects(db.query('insert into quran_bookmarks(user_id,message_id) values ($1,$2)', [bob, saved.message_id]));
  assert.equal((await db.query('delete from quran_chats where id=$1 returning id', [saved.chat_id])).rows.length, 0);
});
await assert.rejects(db.query(`select quran_save_exchange($1,$2,'intrusion','answer','[]')`, [bob, saved.chat_id]));
assert.equal((await db.query('select count(*)::integer as n from quran_messages')).rows[0].n, 2);

const reserves = await Promise.all(Array.from({ length: 5 }, () => db.query(`select quran_reserve_quota('guest:test',2) as used`)));
assert.deepEqual(reserves.map(r => r.rows[0].used), [1,2,null,null,null]);
await db.query(`select quran_release_quota('guest:test')`);
assert.equal((await db.query(`select quran_reserve_quota('guest:test',2) as used`)).rows[0].used, 2);

await db.query(`insert into quran_sources(id,source_type,surah_number,surah_name,verse_number,text_en,text_ar,source_url)
  values ('quran-2-153','quran',2,'Al-Baqarah',153,'Seek help through patience and prayer.','الصبر','https://alquran.cloud/ayah/2:153')`);
assert.equal((await db.query(`select * from quran_search_sources('patience')`)).rows[0].id, 'quran-2-153');
assert.equal((await db.query(`select * from quran_search_sources('explain',2,153)`)).rows[0].id, 'quran-2-153');
assert.equal((await db.query(`select * from quran_search_sources('الصبر')`)).rows[0].id, 'quran-2-153');

await asUser(alice, async () => { await db.query('delete from quran_chats where id=$1', [saved.chat_id]); });
assert.equal((await db.query('select * from quran_messages')).rows.length, 0);
assert.equal((await db.query('select * from quran_bookmarks')).rows.length, 0);
await db.close();
console.log('Database checks passed: migration, chat transactions, ownership, RLS, bookmarks, quotas, rollback, source search and cascades.');
