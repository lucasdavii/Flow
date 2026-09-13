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

commit;
