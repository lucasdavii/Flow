-- Migração aditiva: execute no Supabase antes de publicar o backend.
begin;
create or replace function public.submit_conclusion_atomic(
    p_session_code text, p_participant_token_hash text, p_content text
)
returns setof public.submissions
language plpgsql
security invoker
set search_path = ''
as $$
declare
    selected_session public.sessions%rowtype;
    selected_participant public.participants%rowtype;
    selected_stage public.stages%rowtype;
begin
    -- Serializa esta gravação com o avanço ou encerramento da sessão.
    select s.* into selected_session
    from public.sessions s where s.code = p_session_code for update;
    if not found then
        raise exception using errcode = 'P0002', message = 'SESSION_NOT_FOUND';
    end if;
    select p.* into selected_participant from public.participants p
    where p.session_id = selected_session.id
      and p.participant_token_hash = p_participant_token_hash;
    if not found then
        raise exception using errcode = 'P0001', message = 'INVALID_PARTICIPANT_TOKEN';
    end if;
    if selected_session.status <> 'active' then
        raise exception using errcode = 'P0001', message = 'SESSION_NOT_ACTIVE';
    end if;
    select s.* into selected_stage from public.stages s
    where s.id = selected_session.current_stage_id
      and s.session_id = selected_session.id;
    if not found or selected_stage.type <> 'conclusion' then
        raise exception using errcode = 'P0001',
            message = 'SUBMISSION_NOT_ALLOWED_IN_CURRENT_STAGE';
    end if;
    -- Preserva ID e data original; somente texto, autor e atualização mudam.
    return query
    insert into public.submissions (
        session_id, group_number, submitted_by, content, updated_at
    ) values (
        selected_session.id, selected_participant.group_number,
        selected_participant.id, p_content, clock_timestamp()
    )
    on conflict on constraint submissions_session_group_unique
    do update set content = excluded.content,
                  submitted_by = excluded.submitted_by,
                  updated_at = excluded.updated_at
    returning submissions.*;
end;
$$;
revoke execute on function public.submit_conclusion_atomic(text, text, text)
    from public, anon, authenticated;
grant execute on function public.submit_conclusion_atomic(text, text, text)
    to service_role;
commit;
