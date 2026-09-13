-- Migração aditiva: torna a entrada do aluno atômica sem recriar tabelas.
-- Execute uma única vez no SQL Editor do Supabase antes de publicar o backend.

begin;

create or replace function public.join_session_atomic(
    p_session_code text,
    p_name text,
    p_token_hash text
)
returns table (
    participant_id uuid,
    participant_name text,
    group_number integer,
    role_id uuid,
    role_name text,
    role_type text,
    role_description text,
    session_status text
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
    selected_session public.sessions%rowtype;
    selected_role public.roles%rowtype;
    inserted_participant public.participants%rowtype;
    participant_count bigint;
    role_count bigint;
begin
    -- O bloqueio da sessão serializa entradas entre si e com o início da aula.
    select sessions.*
    into selected_session
    from public.sessions
    where sessions.code = p_session_code
    for update;

    if not found then
        raise exception using errcode = 'P0002', message = 'SESSION_NOT_FOUND';
    end if;

    if selected_session.status <> 'waiting' then
        raise exception using
            errcode = 'P0001', message = 'SESSION_ALREADY_STARTED';
    end if;

    select count(*)
    into participant_count
    from public.participants
    where participants.session_id = selected_session.id;

    select count(*)
    into role_count
    from public.roles
    where roles.session_id = selected_session.id;

    if role_count = 0 then
        raise exception using
            errcode = 'P0001', message = 'JOIN_SESSION_CONFIGURATION_ERROR';
    end if;

    -- Mantém a distribuição original: grupos sequenciais e papéis alternados.
    select roles.*
    into selected_role
    from public.roles
    where roles.session_id = selected_session.id
    order by roles.created_at, roles.id
    offset ((participant_count % selected_session.group_size) % role_count)
    limit 1;

    insert into public.participants (
        session_id,
        role_id,
        name,
        group_number,
        participant_token_hash
    )
    values (
        selected_session.id,
        selected_role.id,
        p_name,
        (participant_count / selected_session.group_size)::integer + 1,
        p_token_hash
    )
    returning participants.* into inserted_participant;

    return query
    select
        inserted_participant.id,
        inserted_participant.name,
        inserted_participant.group_number,
        selected_role.id,
        selected_role.name,
        selected_role.type,
        selected_role.description,
        selected_session.status;
end;
$$;

-- A função aparece na Data API, mas somente a chave secreta do Flask executa.
revoke execute on function public.join_session_atomic(text, text, text)
    from public, anon, authenticated;
grant execute on function public.join_session_atomic(text, text, text)
    to service_role;

commit;
