-- Migração aditiva: valida a etapa e conclui a função na mesma transação.
-- Execute uma única vez no SQL Editor do Supabase antes de publicar o backend.

begin;

create or replace function public.complete_role_atomic(
    p_session_code text,
    p_participant_token_hash text,
    p_stage_id uuid
)
returns table (
    participant_id uuid,
    stage_id uuid,
    completed_at timestamptz
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
    selected_session public.sessions%rowtype;
    selected_participant public.participants%rowtype;
    selected_completion public.role_completions%rowtype;
begin
    -- O mesmo bloqueio usado pelo avanço impede validar uma etapa já trocada.
    select sessions.*
    into selected_session
    from public.sessions
    where sessions.code = p_session_code
    for update;

    if not found then
        raise exception using errcode = 'P0002', message = 'SESSION_NOT_FOUND';
    end if;

    select participants.*
    into selected_participant
    from public.participants
    where participants.session_id = selected_session.id
      and participants.participant_token_hash = p_participant_token_hash
    limit 1;

    if not found then
        raise exception using
            errcode = 'P0001', message = 'INVALID_PARTICIPANT_TOKEN';
    end if;

    if selected_session.status <> 'active' then
        raise exception using errcode = 'P0001', message = 'SESSION_NOT_ACTIVE';
    end if;

    if selected_session.current_stage_id is distinct from p_stage_id then
        raise exception using errcode = 'P0001', message = 'STAGE_NOT_CURRENT';
    end if;

    -- DO NOTHING preserva a primeira data quando o aluno repete a requisição.
    insert into public.role_completions (participant_id, stage_id)
    values (selected_participant.id, p_stage_id)
    on conflict on constraint role_completions_participant_stage_unique do nothing
    returning role_completions.* into selected_completion;

    if selected_completion.id is null then
        select role_completions.*
        into selected_completion
        from public.role_completions
        where role_completions.participant_id = selected_participant.id
          and role_completions.stage_id = p_stage_id;
    end if;

    return query
    select
        selected_completion.participant_id,
        selected_completion.stage_id,
        selected_completion.completed_at;
end;
$$;

-- Somente o backend com service_role pode chamar a função pela Data API.
revoke execute on function public.complete_role_atomic(text, text, uuid)
    from public, anon, authenticated;
grant execute on function public.complete_role_atomic(text, text, uuid)
    to service_role;

commit;
