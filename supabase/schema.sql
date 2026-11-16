-- AgentLab: 프로젝트 저장소
-- Supabase 대시보드 → SQL Editor 에 붙여 넣고 한 번 실행한다. 여러 번 실행해도 안전하다.

create table if not exists public.projects (
  id          uuid primary key default gen_random_uuid(),
  owner       uuid not null default auth.uid() references auth.users (id) on delete cascade,
  name        text not null default '제목 없는 프로젝트' check (char_length(name) between 1 and 80),
  graph       jsonb not null,
  overrides   jsonb not null default '{}'::jsonb,
  pattern_id  text,
  is_public   boolean not null default false,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  -- 한 프로젝트가 지나치게 커지는 것을 막는다 (약 1MB)
  constraint projects_size check (pg_column_size(graph) + pg_column_size(overrides) < 1048576)
);

create index if not exists projects_owner_updated on public.projects (owner, updated_at desc);

-- 저장할 때마다 수정 시각을 갱신한다
create or replace function public.touch_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists projects_touch on public.projects;
create trigger projects_touch before update on public.projects
for each row execute function public.touch_updated_at();

-- Data API 권한: "Automatically expose new tables"를 꺼 둔 경우에도 동작하도록 직접 부여한다.
-- 실제로 어떤 행에 접근할 수 있는지는 아래 RLS 정책이 결정한다.
grant select on public.projects to anon;                                   -- 공유 링크 보기 (비로그인)
grant select, insert, update, delete on public.projects to authenticated;  -- 로그인 사용자

-- 행 단위 보안: 주인은 전부 가능, 그 외에는 공개된 프로젝트를 읽기만 가능
alter table public.projects enable row level security;

drop policy if exists "projects_select" on public.projects;
create policy "projects_select" on public.projects
  for select using (owner = auth.uid() or is_public);

drop policy if exists "projects_insert" on public.projects;
create policy "projects_insert" on public.projects
  for insert to authenticated with check (owner = auth.uid());

drop policy if exists "projects_update" on public.projects;
create policy "projects_update" on public.projects
  for update to authenticated using (owner = auth.uid()) with check (owner = auth.uid());

drop policy if exists "projects_delete" on public.projects;
create policy "projects_delete" on public.projects
  for delete to authenticated using (owner = auth.uid());

-- ---------------------------------------------------------------------------
-- 에이전트 프리셋: 만들어 둔 에이전트를 저장해 두고 다른 그래프에서 Sub-agent 로 불러온다.
create table if not exists public.agent_presets (
  id          uuid primary key default gen_random_uuid(),
  owner       uuid not null default auth.uid() references auth.users (id) on delete cascade,
  name        text not null check (char_length(name) between 1 and 80),
  node_name   text not null default 'sub_agent' check (node_name ~ '^[a-z_][a-z0-9_]*$'),
  description text not null default '' check (char_length(description) <= 500),
  graph       jsonb not null,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint agent_presets_size check (pg_column_size(graph) < 524288)
);

create index if not exists agent_presets_owner_updated on public.agent_presets (owner, updated_at desc);

drop trigger if exists agent_presets_touch on public.agent_presets;
create trigger agent_presets_touch before update on public.agent_presets
for each row execute function public.touch_updated_at();

alter table public.agent_presets enable row level security;

drop policy if exists "agent_presets_select" on public.agent_presets;
create policy "agent_presets_select" on public.agent_presets
  for select to authenticated using (owner = auth.uid());

drop policy if exists "agent_presets_insert" on public.agent_presets;
create policy "agent_presets_insert" on public.agent_presets
  for insert to authenticated with check (owner = auth.uid());

drop policy if exists "agent_presets_update" on public.agent_presets;
create policy "agent_presets_update" on public.agent_presets
  for update to authenticated using (owner = auth.uid()) with check (owner = auth.uid());

drop policy if exists "agent_presets_delete" on public.agent_presets;
create policy "agent_presets_delete" on public.agent_presets
  for delete to authenticated using (owner = auth.uid());

-- ---------------------------------------------------------------------------
-- 에이전트 마켓: 프리셋을 링크로 공유하거나 공개 갤러리에 올린다.
--   private : 나만 (기본)
--   link    : 링크(id)를 아는 사람만 get_shared_preset() 으로 읽는다. 목록 조회로는 보이지 않는다.
--   public  : 공개 갤러리. 선언형(Function 노드·커스텀 도구 없이 기본 도구만 쓰는) 프리셋만 허용한다.

-- 실행되는 사용자 코드가 없는 '선언형' 그래프인지. 기본 도구 목록은 frontend/src/lib/playground/catalog.ts 와 맞춘다.
create or replace function public.agentlab_is_declarative(g jsonb) returns boolean
language sql immutable parallel safe as $$
  select not jsonb_path_exists(g, 'lax $.**.kind ? (@ == "function")')
     and not jsonb_path_exists(g, 'lax $.**.tools[*] ? (@.type() != "string")')
     and not jsonb_path_exists(g, 'lax $.**.tools[*] ? (@.type() == "string" && !(@ == "get_weather" || @ == "web_search" || @ == "calculator" || @ == "search_docs" || @ == "get_order_status" || @ == "issue_refund" || @ == "get_current_time"))')
$$;

alter table public.agent_presets add column if not exists visibility text not null default 'private' check (visibility in ('private', 'link', 'public'));
alter table public.agent_presets add column if not exists author_name text not null default '';
alter table public.agent_presets add column if not exists category text not null default '기타' check (char_length(category) between 1 and 30);
alter table public.agent_presets add column if not exists tags text[] not null default '{}' check (cardinality(tags) <= 8);
alter table public.agent_presets add column if not exists installs integer not null default 0;
alter table public.agent_presets add column if not exists hidden boolean not null default false; -- 신고 누적으로 숨김
alter table public.agent_presets add column if not exists forked_from uuid references public.agent_presets (id) on delete set null;
alter table public.agent_presets add column if not exists published_at timestamptz;
alter table public.agent_presets add column if not exists declarative boolean generated always as (public.agentlab_is_declarative(graph)) stored;

do $$ begin
  alter table public.agent_presets add constraint agent_presets_public_declarative check (visibility <> 'public' or declarative);
exception when duplicate_object then null;
end $$;

create index if not exists agent_presets_public_popular on public.agent_presets (installs desc) where visibility = 'public' and not hidden;
create index if not exists agent_presets_public_recent on public.agent_presets (published_at desc) where visibility = 'public' and not hidden;

-- 작성자 이름은 계정 정보에서 채우고(사칭 방지), 처음 공개한 시각을 남긴다
create or replace function public.agent_presets_stamp() returns trigger
language plpgsql security definer set search_path = public, auth as $$
begin
  select coalesce(nullif(u.raw_user_meta_data ->> 'full_name', ''), nullif(u.raw_user_meta_data ->> 'name', ''), split_part(u.email, '@', 1), '익명')
    into new.author_name from auth.users u where u.id = new.owner;
  if new.visibility = 'public' and new.published_at is null then
    new.published_at = now();
  end if;
  return new;
end $$;

drop trigger if exists agent_presets_stamp on public.agent_presets;
create trigger agent_presets_stamp before insert or update on public.agent_presets
for each row execute function public.agent_presets_stamp();

-- 내용이 바뀔 때만 수정 시각을 올린다 (공개 범위·설치 수 변경은 '업데이트 있음'으로 보이지 않게)
create or replace function public.agent_presets_touch() returns trigger
language plpgsql as $$
begin
  if (new.graph, new.name, new.node_name, new.description) is distinct from (old.graph, old.name, old.node_name, old.description) then
    new.updated_at = now();
  end if;
  return new;
end $$;

drop trigger if exists agent_presets_touch on public.agent_presets;
create trigger agent_presets_touch before update on public.agent_presets
for each row execute function public.agent_presets_touch();

-- 권한: 설치 수·숨김·작성자 이름은 클라이언트가 직접 바꿀 수 없다
revoke all on public.agent_presets from anon, authenticated;
grant select on public.agent_presets to anon, authenticated;
grant insert (name, node_name, description, graph, visibility, category, tags, forked_from) on public.agent_presets to authenticated;
grant update (name, node_name, description, graph, visibility, category, tags) on public.agent_presets to authenticated;
grant delete on public.agent_presets to authenticated;

drop policy if exists "agent_presets_select" on public.agent_presets;
create policy "agent_presets_select" on public.agent_presets
  for select to anon, authenticated using (owner = auth.uid() or (visibility = 'public' and not hidden));

-- 링크 공유: id 를 아는 사람만 읽는다 (로그인 불필요)
create or replace function public.get_shared_preset(p_id uuid) returns setof public.agent_presets
language sql stable security definer set search_path = public as $$
  select * from public.agent_presets where id = p_id and visibility in ('link', 'public') and not hidden;
$$;
revoke all on function public.get_shared_preset(uuid) from public;
grant execute on function public.get_shared_preset(uuid) to anon, authenticated;

-- 설치 수: 사용자마다 한 번만 센다
create table if not exists public.agent_preset_installs (
  preset_id  uuid not null references public.agent_presets (id) on delete cascade,
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (preset_id, user_id)
);
alter table public.agent_preset_installs enable row level security;
revoke all on public.agent_preset_installs from anon, authenticated;

create or replace function public.record_preset_install(p_id uuid) returns void
language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is null then
    return;
  end if;
  insert into public.agent_preset_installs (preset_id, user_id)
  select p_id, auth.uid()
  where exists (select 1 from public.agent_presets where id = p_id and visibility in ('link', 'public') and not hidden and owner <> auth.uid())
  on conflict do nothing;
  if found then
    update public.agent_presets set installs = installs + 1 where id = p_id;
  end if;
end $$;
revoke all on function public.record_preset_install(uuid) from public;
grant execute on function public.record_preset_install(uuid) to authenticated;

-- 신고: 사용자마다 한 번, 5건이 쌓이면 갤러리와 링크에서 숨긴다 (작성자에게는 계속 보인다)
create table if not exists public.agent_preset_reports (
  preset_id  uuid not null references public.agent_presets (id) on delete cascade,
  reporter   uuid not null default auth.uid() references auth.users (id) on delete cascade,
  reason     text not null check (char_length(reason) between 1 and 500),
  created_at timestamptz not null default now(),
  primary key (preset_id, reporter)
);
alter table public.agent_preset_reports enable row level security;
revoke all on public.agent_preset_reports from anon, authenticated;
grant insert (preset_id, reason) on public.agent_preset_reports to authenticated;

drop policy if exists "agent_preset_reports_insert" on public.agent_preset_reports;
create policy "agent_preset_reports_insert" on public.agent_preset_reports
  for insert to authenticated with check (reporter = auth.uid());

create or replace function public.agent_preset_reports_hide() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if (select count(*) from public.agent_preset_reports where preset_id = new.preset_id) >= 5 then
    update public.agent_presets set hidden = true where id = new.preset_id;
  end if;
  return new;
end $$;

drop trigger if exists agent_preset_reports_hide on public.agent_preset_reports;
create trigger agent_preset_reports_hide after insert on public.agent_preset_reports
for each row execute function public.agent_preset_reports_hide();
