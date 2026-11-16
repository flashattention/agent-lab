-- schema.sql 의 행 단위 보안·권한·트리거 검증. 실패하면 예외로 중단된다.
--   docker run -d --name pg -e POSTGRES_PASSWORD=pw postgres:17
--   psql -f supabase/tests/stub.sql -f supabase/schema.sql -f supabase/tests/rls_test.sql
\set ON_ERROR_STOP on
\set QUIET on

create or replace function pg_temp.expect(ok boolean, what text) returns void language plpgsql as $$
begin
  if not ok then raise exception 'FAIL: %', what; end if;
  raise notice 'ok - %', what;
end $$;

-- 거부되어야 하는 문장: 실패하면 true
create or replace function pg_temp.denied(stmt text) returns boolean language plpgsql as $$
begin
  execute stmt;
  return false;
exception when others then
  return true;
end $$;

grant execute on all functions in schema pg_temp to anon, authenticated;

do $$
declare
  decl jsonb := '{"nodes":[{"id":"a","kind":"agent","data":{"name":"a","tools":["web_search"]}},{"id":"s","kind":"subgraph","data":{"name":"s","graph":{"nodes":[{"id":"t","kind":"tools","data":{"name":"t","tools":["calculator"]}}],"edges":[]}}}],"edges":[]}';
  fn jsonb := '{"nodes":[{"id":"s","kind":"subgraph","data":{"name":"s","graph":{"nodes":[{"id":"f","kind":"function","data":{"name":"f","code":"return {}"}}],"edges":[]}}}],"edges":[]}';
  ctool jsonb := '{"nodes":[{"id":"t","kind":"tools","data":{"name":"t","tools":["my_tool"]}}],"edges":[],"tools":[{"name":"my_tool","code":"@tool"}]}';
begin
  perform pg_temp.expect(public.agentlab_is_declarative(decl), '기본 도구만 쓰는 중첩 그래프는 선언형');
  perform pg_temp.expect(not public.agentlab_is_declarative(fn), '서브그래프 안의 Function 노드는 비선언형');
  perform pg_temp.expect(not public.agentlab_is_declarative(ctool), '커스텀 도구 정의가 있으면 비선언형');
  perform pg_temp.expect(not public.agentlab_is_declarative('{"nodes":[{"kind":"agent","data":{"tools":["rm_rf"]}}]}'), '모르는 도구 이름은 비선언형');
  perform set_config('t.decl', decl::text, false);
  perform set_config('t.fn', fn::text, false);
end $$;

-- Alice
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000a', false) \g /dev/null
insert into public.agent_presets (name, node_name, graph, visibility, category) values ('웹 리서처', 'researcher', current_setting('t.decl')::jsonb, 'public', '리서치');
insert into public.agent_presets (name, graph, visibility) values ('코드 포함', current_setting('t.fn')::jsonb, 'link');
insert into public.agent_presets (name, graph) values ('비공개', current_setting('t.decl')::jsonb);
do $$ begin
  perform pg_temp.expect((select author_name = 'Alice' and published_at is not null from public.agent_presets where name = '웹 리서처'), '작성자 이름은 계정에서, 공개 시각 기록');
  perform pg_temp.expect(pg_temp.denied($q$insert into public.agent_presets (name, graph, visibility) values ('x', current_setting('t.fn')::jsonb, 'public')$q$), '코드 포함 프리셋은 공개로 만들 수 없다');
  perform pg_temp.expect(pg_temp.denied($q$update public.agent_presets set visibility = 'public' where name = '코드 포함'$q$), '코드 포함 프리셋을 공개로 바꿀 수 없다');
  perform pg_temp.expect(pg_temp.denied($q$update public.agent_presets set installs = 9999$q$), '설치 수는 직접 바꿀 수 없다');
  perform pg_temp.expect(pg_temp.denied($q$update public.agent_presets set author_name = 'Anthropic'$q$), '작성자 이름은 직접 바꿀 수 없다');
  perform pg_temp.expect(pg_temp.denied($q$update public.agent_presets set hidden = false$q$), '숨김 여부는 직접 바꿀 수 없다');
  perform set_config('t.before', (select updated_at::text from public.agent_presets where name = '비공개'), false);
  update public.agent_presets set visibility = 'link' where name = '비공개';
  perform pg_temp.expect((select updated_at::text from public.agent_presets where name = '비공개') = current_setting('t.before'), '공개 범위만 바꾸면 수정 시각이 그대로');
  update public.agent_presets set visibility = 'private' where name = '비공개';
  perform set_config('t.pub', (select id::text from public.agent_presets where name = '웹 리서처'), false);
  perform set_config('t.link', (select id::text from public.agent_presets where name = '코드 포함'), false);
  perform set_config('t.priv', (select id::text from public.agent_presets where name = '비공개'), false);
end $$;

-- Bob
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000b', false) \g /dev/null
do $$ begin
  perform pg_temp.expect((select array_agg(name) = array['웹 리서처'] from public.agent_presets), '다른 사람에게는 공개 프리셋만 목록에 보인다');
  perform pg_temp.expect((select count(*) = 1 from public.get_shared_preset(current_setting('t.link')::uuid)), '링크 공유 프리셋은 id 로 읽힌다');
  perform pg_temp.expect((select count(*) = 0 from public.get_shared_preset(current_setting('t.priv')::uuid)), '비공개 프리셋은 id 를 알아도 읽히지 않는다');
  update public.agent_presets set name = 'hacked' where id = current_setting('t.pub')::uuid;
  delete from public.agent_presets where id = current_setting('t.pub')::uuid;
  perform pg_temp.expect((select name = '웹 리서처' from public.get_shared_preset(current_setting('t.pub')::uuid)), '남의 프리셋은 고치거나 지울 수 없다');
  perform public.record_preset_install(current_setting('t.pub')::uuid);
  perform public.record_preset_install(current_setting('t.pub')::uuid);
end $$;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000a', false) \g /dev/null
do $$ begin
  perform public.record_preset_install(current_setting('t.pub')::uuid);
  perform pg_temp.expect((select installs = 1 from public.agent_presets where id = current_setting('t.pub')::uuid), '설치 수는 사용자당 한 번, 작성자 본인은 세지 않는다');
end $$;

-- 비로그인
reset role;
set role anon;
select set_config('request.jwt.claim.sub', '', false) \g /dev/null
do $$ begin
  perform pg_temp.expect((select count(*) = 1 from public.agent_presets), '비로그인도 공개 갤러리를 본다');
  perform pg_temp.expect((select count(*) = 1 from public.get_shared_preset(current_setting('t.link')::uuid)), '비로그인도 링크 공유 프리셋을 연다');
  perform pg_temp.expect(pg_temp.denied($q$insert into public.agent_presets (name, graph) values ('anon', '{}'::jsonb)$q$), '비로그인은 프리셋을 만들 수 없다');
end $$;

-- 신고 5건이면 숨김
reset role;
insert into auth.users select ('00000000-0000-0000-0000-0000000000' || i)::uuid, 'u' || i || '@x.com' from generate_series(10, 14) i;
set role authenticated;
do $$ declare i int; begin
  for i in 10..14 loop
    perform set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000' || i, false);
    insert into public.agent_preset_reports (preset_id, reason) values (current_setting('t.pub')::uuid, '스팸');
  end loop;
  perform pg_temp.expect((select count(*) = 0 from public.agent_presets where id = current_setting('t.pub')::uuid), '신고 5건이 쌓이면 갤러리에서 숨겨진다');
  perform pg_temp.expect(pg_temp.denied($q$select count(*) from public.agent_preset_reports$q$), '신고 내용은 읽을 수 없다');
  perform set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000a', false);
  perform pg_temp.expect((select hidden from public.agent_presets where id = current_setting('t.pub')::uuid), '작성자에게는 숨김 상태로 계속 보인다');
end $$;

\echo all rls tests passed
