-- Teste de integração: todas as linhas criadas aqui são revertidas ao final.
begin;
set local role service_role;
do $test$
declare
    sid uuid;
    stid uuid;
    code_test text;
    first_join record;
    joined record;
    completion record;
    repeated record;
    submission record;
    revised record;
    token_test text := gen_random_uuid()::text;
begin
    loop
        code_test := translate(upper(substr(md5(gen_random_uuid()::text),1,5)), '01', 'XY');
        exit when not exists (select 1 from public.sessions where code=code_test);
    end loop;
    insert into public.sessions(code,activity_title,group_size,teacher_token_hash)
    values(code_test,'Teste transacional revertido',2,gen_random_uuid()::text)
    returning id into sid;
    insert into public.roles(session_id,name,type,description)
    values(sid,'teste','digital','Teste revertido');
    insert into public.stages(session_id,position,title,type,instructions)
    values(sid,1,'Conclusão','conclusion','Teste revertido') returning id into stid;
    select * into first_join from public.join_session_atomic(code_test,'Aluno teste',token_test);
    select * into joined from public.join_session_atomic(code_test,'Aluno teste 2',gen_random_uuid()::text);
    if first_join.group_number <> 1 or joined.group_number <> 1 then
        raise exception 'Distribuição incorreta do primeiro grupo';
    end if;
    select * into joined from public.join_session_atomic(code_test,'Aluno teste 3',gen_random_uuid()::text);
    if joined.group_number <> 2 then raise exception 'Grupo excedeu capacidade'; end if;
    update public.sessions set status='active',current_stage_id=stid where id=sid;
    begin
        perform public.join_session_atomic(code_test,'Atrasado',gen_random_uuid()::text);
        raise exception 'Entrada tardia aceita';
    exception when sqlstate 'P0001' then
        if sqlerrm <> 'SESSION_ALREADY_STARTED' then raise; end if;
    end;
    select * into completion from public.complete_role_atomic(code_test,token_test,stid);
    select * into repeated from public.complete_role_atomic(code_test,token_test,stid);
    if completion.completed_at <> repeated.completed_at then
        raise exception 'Conclusão deixou de ser idempotente';
    end if;
    begin
        perform public.complete_role_atomic(code_test,token_test,gen_random_uuid());
        raise exception 'Etapa incorreta aceita';
    exception when sqlstate 'P0001' then
        if sqlerrm <> 'STAGE_NOT_CURRENT' then raise; end if;
    end;
    select * into submission from public.submit_conclusion_atomic(code_test,token_test,'Primeiro texto');
    select * into revised from public.submit_conclusion_atomic(code_test,token_test,'Segundo texto');
    if submission.id <> revised.id or submission.created_at <> revised.created_at
       or revised.content <> 'Segundo texto' then
        raise exception 'Atualização da conclusão alterou identidade ou falhou';
    end if;
    begin
        perform public.submit_conclusion_atomic(code_test,'invalido','Texto');
        raise exception 'Token inválido aceito';
    exception when sqlstate 'P0001' then
        if sqlerrm <> 'INVALID_PARTICIPANT_TOKEN' then raise; end if;
    end;
    update public.sessions set status='finished',current_stage_id=null where id=sid;
    begin
        perform public.submit_conclusion_atomic(code_test,token_test,'Texto tardio');
        raise exception 'Envio depois do fim aceito';
    exception when sqlstate 'P0001' then
        if sqlerrm <> 'SESSION_NOT_ACTIVE' then raise; end if;
    end;
end;
$test$;
rollback;
select 'passed: joins, capacity, completion idempotency, stale stage, submission update, invalid token, finished session; test rows rolled back' as verification;
