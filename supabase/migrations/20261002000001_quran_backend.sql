create table public.quran_chats (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null check (char_length(title) between 1 and 200),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on public.quran_chats (user_id, updated_at desc);

create table public.quran_messages (
  id uuid primary key default gen_random_uuid(),
  chat_id uuid not null references public.quran_chats(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null check (char_length(content) between 1 and 30000),
  sources_used jsonb not null default '[]',
  created_at timestamptz not null default now()
);
create index on public.quran_messages (chat_id, created_at);

create table public.quran_bookmarks (
  user_id uuid not null references auth.users(id) on delete cascade,
  message_id uuid not null references public.quran_messages(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, message_id)
);

create function public.quran_normalize_ar(p_text text) returns text
language sql immutable strict set search_path = public as $$
  select regexp_replace(translate(p_text, 'آأإٱى', 'ااااي'), '[ـً-ٰٟ]', '', 'g');
$$;

create table public.quran_sources (
  id text primary key,
  source_type text not null check (source_type in ('quran', 'hadith')),
  surah_number integer,
  surah_name text,
  verse_number integer,
  collection text,
  hadith_number text,
  text_en text not null,
  text_ar text not null,
  source_url text not null,
  search_en tsvector generated always as (to_tsvector('english', text_en)) stored,
  search_ar tsvector generated always as (to_tsvector('simple', public.quran_normalize_ar(text_ar))) stored,
  check (source_type <> 'quran' or (surah_number between 1 and 114 and verse_number > 0))
);
create index on public.quran_sources using gin (search_en);
create index on public.quran_sources using gin (search_ar);

-- No raw IP addresses or guest questions are stored in the quota table.
create table public.quran_usage (
  bucket text primary key,
  used integer not null default 0,
  updated_at timestamptz not null default now()
);
create table public.quran_api_usage (
  id bigint generated always as identity primary key,
  provider text not null,
  model text not null,
  success boolean not null,
  status_code integer,
  latency_ms integer,
  prompt_tokens integer,
  completion_tokens integer,
  created_at timestamptz not null default now()
);

alter table public.quran_chats enable row level security;
alter table public.quran_messages enable row level security;
alter table public.quran_bookmarks enable row level security;
alter table public.quran_sources enable row level security;
alter table public.quran_usage enable row level security;
alter table public.quran_api_usage enable row level security;

create policy chats_read on public.quran_chats for select to authenticated using (user_id = auth.uid());
create policy chats_rename on public.quran_chats for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy chats_delete on public.quran_chats for delete to authenticated using (user_id = auth.uid());
create policy messages_read on public.quran_messages for select to authenticated using (
  exists (select 1 from public.quran_chats c where c.id = chat_id and c.user_id = auth.uid())
);
create policy bookmarks_read on public.quran_bookmarks for select to authenticated using (user_id = auth.uid());
create policy bookmarks_insert on public.quran_bookmarks for insert to authenticated with check (
  user_id = auth.uid() and exists (
    select 1 from public.quran_messages m join public.quran_chats c on c.id = m.chat_id
    where m.id = message_id and m.role = 'assistant' and c.user_id = auth.uid()
  )
);
create policy bookmarks_delete on public.quran_bookmarks for delete to authenticated using (user_id = auth.uid());

-- Only the server writes chat messages; clients cannot forge assistant replies.
revoke all on public.quran_sources, public.quran_usage, public.quran_api_usage from anon, authenticated;
revoke all on public.quran_chats, public.quran_messages, public.quran_bookmarks from anon, authenticated;
grant select, delete on public.quran_chats to authenticated;
grant update(title) on public.quran_chats to authenticated;
grant select on public.quran_messages to authenticated;
grant select, insert, delete on public.quran_bookmarks to authenticated;
grant all on public.quran_chats, public.quran_messages, public.quran_bookmarks, public.quran_sources, public.quran_usage, public.quran_api_usage to service_role;
grant usage, select on sequence public.quran_api_usage_id_seq to service_role;

create function public.quran_reserve_quota(p_bucket text, p_limit integer)
returns integer language plpgsql security definer set search_path = public as $$
declare v_used integer;
begin
  insert into quran_usage (bucket, used) values (p_bucket, 1)
  on conflict (bucket) do update set used = quran_usage.used + 1, updated_at = now()
  where quran_usage.used < p_limit
  returning used into v_used;
  return v_used;
end;
$$;
create function public.quran_release_quota(p_bucket text)
returns void language sql security definer set search_path = public as $$
  update quran_usage set used = greatest(used - 1, 0), updated_at = now() where bucket = p_bucket;
$$;

create function public.quran_search_sources(p_query text, p_surah integer default null, p_verse integer default null)
returns setof public.quran_sources language sql stable set search_path = public as $$
  select s.* from quran_sources s
  where (p_surah is not null and s.surah_number = p_surah and s.verse_number = p_verse)
    or (p_surah is null and (
      s.search_en @@ websearch_to_tsquery('english', p_query)
      or s.search_ar @@ websearch_to_tsquery('simple', public.quran_normalize_ar(p_query))
    ))
  order by ts_rank_cd(s.search_en, websearch_to_tsquery('english', p_query)) desc, s.id
  limit 5;
$$;

-- Atomically save the exchange only after a successful provider response.
create function public.quran_save_exchange(
  p_user uuid, p_chat uuid, p_question text, p_answer text, p_sources jsonb
) returns jsonb language plpgsql security definer set search_path = public as $$
declare v_chat uuid; v_user_message uuid; v_message uuid;
begin
  if p_chat is null then
    insert into quran_chats (user_id, title) values (p_user, left(p_question, 80)) returning id into v_chat;
  else
    select id into v_chat from quran_chats where id = p_chat and user_id = p_user for update;
    if v_chat is null then raise exception 'Chat not found'; end if;
    update quran_chats set updated_at = now() where id = v_chat;
  end if;
  insert into quran_messages (chat_id, role, content) values (v_chat, 'user', p_question) returning id into v_user_message;
  insert into quran_messages (chat_id, role, content, sources_used) values (v_chat, 'assistant', p_answer, p_sources) returning id into v_message;
  return jsonb_build_object('chat_id', v_chat, 'user_message_id', v_user_message, 'message_id', v_message);
end;
$$;

revoke all on function public.quran_reserve_quota(text, integer), public.quran_release_quota(text), public.quran_search_sources(text, integer, integer), public.quran_save_exchange(uuid, uuid, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.quran_reserve_quota(text, integer), public.quran_release_quota(text), public.quran_search_sources(text, integer, integer), public.quran_save_exchange(uuid, uuid, text, text, jsonb) to service_role;
