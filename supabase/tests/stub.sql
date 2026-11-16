-- 테스트용 Supabase 흉내: auth 스키마, auth.uid(), anon/authenticated 역할 (실제 Supabase 에서는 실행하지 않는다)
create schema auth;
create table auth.users (id uuid primary key, email text, raw_user_meta_data jsonb not null default '{}');
create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
create role anon nologin;
create role authenticated nologin;
grant usage on schema public, auth to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;
insert into auth.users values
 ('00000000-0000-0000-0000-00000000000a', 'alice@x.com', '{"full_name":"Alice"}'),
 ('00000000-0000-0000-0000-00000000000b', 'bob@x.com', '{}');
