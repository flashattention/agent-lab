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
