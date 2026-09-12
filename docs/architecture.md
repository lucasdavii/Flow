# Arquitetura

## Visão geral

Uma única aplicação Flask serve os arquivos de `frontend/` e expõe `/api/**`. O navegador nunca acessa Supabase diretamente.

```text
Navegador (HTML/CSS/JS)
        | fetch + polling
        v
Flask (rotas e serviços)
        | chave de serviço somente no servidor
        v
Supabase / PostgreSQL
```

Essa organização evita CORS e dois deploys. Rotas validam HTTP, serviços concentram regras de negócio e `backend/db.py` cria o cliente do banco quando necessário.

## Estado e sincronização

O professor altera o estado no Flask. A tela do aluno consulta `GET /api/sessions/{code}/state` a cada 1,5–2 segundos. Polling é suficiente para a beta e mais simples de demonstrar e depurar que WebSockets. Realtime pode ser avaliado depois do MVP.

## Segurança da beta

- O professor recebe um token aleatório ao criar a sessão.
- Cada aluno recebe um token aleatório ao entrar.
- O banco guarda somente hashes dos tokens.
- `start`, `next` e `results` exigem `X-Teacher-Token`.
- Ações do aluno exigem `X-Participant-Token`.
- O frontend fala apenas com Flask. A chave de serviço do Supabase permanece no servidor.
- As tabelas públicas têm RLS habilitado e privilégios de `anon` e `authenticated` revogados. Não há políticas para acesso direto pelo navegador.

Isso reduz erros óbvios sem introduzir login completo. Tokens não substituem autenticação robusta e são deliberadamente limitados à beta.

## Modelo de dados

- `sessions`: código único, atividade, estado, etapa atual e hash do token do professor.
- `participants`: aluno, sessão, grupo, função e hash do token individual.
- `stages`: etapas ordenadas de uma sessão.
- `roles`: funções complementares disponíveis na sessão.
- `role_completions`: relação entre participante e etapa concluída. A tabela é necessária para preservar o histórico sem duplicar colunas.
- `submissions`: uma conclusão por sessão e número de grupo.

Relacionamentos principais:

```text
sessions 1 --- N stages
sessions 1 --- N roles
sessions 1 --- N participants --- 1 roles
participants 1 --- N role_completions N --- 1 stages
sessions 1 --- N submissions
participants 1 --- N submissions (autor)
```

Não existe tabela `groups`: `participants.group_number` identifica o grupo e a restrição única de `submissions` garante uma conclusão por grupo. Isso atende o MVP com menos operações e menos estado para sincronizar.

## Código de sessão

O backend deve gerar cinco caracteres com alfabeto `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`, converter entrada para maiúsculas e repetir a geração em caso de conflito de unicidade. O banco aceita somente esse formato e garante `UNIQUE`.

## Modo demonstração

O modo futuro reutilizará as mesmas sessões, etapas, funções e transições. Ele poderá preparar professor e quatro alunos de exemplo, mas não será uma aplicação separada nem terá regras paralelas.
