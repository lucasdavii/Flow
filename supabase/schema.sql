-- Modelo inicial do MVP. Revise no SQL Editor antes de aplicar.
-- O frontend não acessa estas tabelas; somente o Flask usa service_role.

begin;

create table public.sessions (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    activity_title text not null,
    status text not null default 'waiting',
    group_size smallint not null default 4,
    teacher_token_hash text not null unique,
    current_stage_id uuid,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint sessions_code_format check (
        code ~ '^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{5}$'
    ),
    constraint sessions_title_not_blank check (btrim(activity_title) <> ''),
    constraint sessions_status_valid check (
        status in ('waiting', 'active', 'finished')
    ),
    constraint sessions_group_size_valid check (group_size between 2 and 8)
);

create table public.stages (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.sessions(id) on delete cascade,
    position smallint not null,
    title text not null,
    type text not null,
    instructions text not null,
    created_at timestamptz not null default now(),
    constraint stages_position_positive check (position > 0),
    constraint stages_title_not_blank check (btrim(title) <> ''),
    constraint stages_type_valid check (
        type in ('digital', 'presential', 'conclusion')
    ),
    constraint stages_session_position_unique unique (session_id, position)
);

alter table public.sessions
    add constraint sessions_current_stage_fk
    foreign key (current_stage_id) references public.stages(id) on delete set null;

create table public.roles (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.sessions(id) on delete cascade,
    name text not null,
    type text not null,
    description text not null,
    created_at timestamptz not null default now(),
    constraint roles_name_not_blank check (btrim(name) <> ''),
    constraint roles_type_valid check (type in ('digital', 'presential')),
    constraint roles_session_name_unique unique (session_id, name)
);

create table public.participants (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.sessions(id) on delete cascade,
    role_id uuid not null references public.roles(id) on delete restrict,
    name text not null,
    group_number integer not null,
    participant_token_hash text not null unique,
    created_at timestamptz not null default now(),
    constraint participants_name_not_blank check (btrim(name) <> ''),
    constraint participants_group_positive check (group_number > 0)
);

create table public.role_completions (
    id uuid primary key default gen_random_uuid(),
    participant_id uuid not null references public.participants(id) on delete cascade,
    stage_id uuid not null references public.stages(id) on delete cascade,
    completed_at timestamptz not null default now(),
    constraint role_completions_participant_stage_unique
        unique (participant_id, stage_id)
);

create table public.submissions (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.sessions(id) on delete cascade,
    group_number integer not null,
    submitted_by uuid not null references public.participants(id) on delete restrict,
    content text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint submissions_group_positive check (group_number > 0),
    constraint submissions_content_not_blank check (btrim(content) <> ''),
    constraint submissions_session_group_unique unique (session_id, group_number)
);

-- Índices de chaves estrangeiras e consultas mais frequentes.
create index participants_session_id_idx
    on public.participants (session_id);
create index participants_session_group_idx
    on public.participants (session_id, group_number);
create index participants_role_id_idx
    on public.participants (role_id);
create index roles_session_id_idx
    on public.roles (session_id);
create index role_completions_stage_id_idx
    on public.role_completions (stage_id);
create index submissions_submitted_by_idx
    on public.submissions (submitted_by);

-- Defesa em profundidade: o navegador não recebe acesso direto ao banco.
alter table public.sessions enable row level security;
alter table public.stages enable row level security;
alter table public.roles enable row level security;
alter table public.participants enable row level security;
alter table public.role_completions enable row level security;
alter table public.submissions enable row level security;

revoke all on table public.sessions from anon, authenticated;
revoke all on table public.stages from anon, authenticated;
revoke all on table public.roles from anon, authenticated;
revoke all on table public.participants from anon, authenticated;
revoke all on table public.role_completions from anon, authenticated;
revoke all on table public.submissions from anon, authenticated;

grant select, insert, update, delete on table public.sessions to service_role;
grant select, insert, update, delete on table public.stages to service_role;
grant select, insert, update, delete on table public.roles to service_role;
grant select, insert, update, delete on table public.participants to service_role;
grant select, insert, update, delete on table public.role_completions to service_role;
grant select, insert, update, delete on table public.submissions to service_role;

create or replace function public.join_session_atomic(
    p_code text,
    p_name text,
    p_token_hash text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    locked_session public.sessions%rowtype;
    participant_count bigint;
    role_count bigint;
    selected_role public.roles%rowtype;
    inserted_participant public.participants%rowtype;
    position_in_group integer;
begin
    select *
      into locked_session
      from public.sessions
     where code = upper(btrim(p_code))
     for update;

    if not found then
        raise exception using
            errcode = 'P0001',
            message = 'SESSION_NOT_FOUND';
    end if;

    if locked_session.status <> 'waiting' then
        raise exception using
            errcode = 'P0002',
            message = 'SESSION_ALREADY_STARTED';
    end if;

    select count(*)
      into participant_count
      from public.participants
     where session_id = locked_session.id;

    position_in_group := (participant_count % locked_session.group_size)::integer;
    select count(*)
      into role_count
      from public.roles
     where session_id = locked_session.id;

    if role_count = 0 then
        raise exception using
            errcode = 'P0003',
            message = 'SESSION_HAS_NO_ROLES';
    end if;

    select *
      into selected_role
      from public.roles
     where session_id = locked_session.id
     order by created_at, id
     offset (position_in_group % role_count)
     limit 1;

    insert into public.participants (
        session_id,
        role_id,
        name,
        group_number,
        participant_token_hash
    )
    values (
        locked_session.id,
        selected_role.id,
        p_name,
        (participant_count / locked_session.group_size)::integer + 1,
        p_token_hash
    )
    returning * into inserted_participant;

    return jsonb_build_object(
        'participant', jsonb_build_object(
            'id', inserted_participant.id,
            'name', inserted_participant.name,
            'group_number', inserted_participant.group_number,
            'role', jsonb_build_object(
                'id', selected_role.id,
                'name', selected_role.name,
                'type', selected_role.type,
                'description', selected_role.description
            )
        ),
        'session_status', locked_session.status
    );
end;
$$;

revoke all on function public.join_session_atomic(text, text, text) from public;
grant execute on function public.join_session_atomic(text, text, text) to service_role;

commit;
