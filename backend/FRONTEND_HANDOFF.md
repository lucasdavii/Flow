# Mensagem para encaminhar no WhatsApp

O backend do Flow tem os oito endpoints implementados. A revisão ficou com
147 testes passando e quatro pendências conhecidas de concorrência. A integração
das telas pode avançar, mas precisamos corrigir no backend a entrada simultânea
antes de testar com uma turma: ela pode colocar alunos demais no mesmo grupo.

Pode passar estas instruções ao seu agente:

1. Leia `AGENTS.md`, `docs/api.md` e `docs/architecture.md`. Trabalhe somente
   em `frontend/**`, com HTML, CSS e JavaScript vanilla. O Flask serve páginas
   e API; use URLs relativas `/api/...`. Não acesse Supabase pelo navegador,
   não coloque chaves no frontend e não invente campos ou endpoints.
   Para integrar localmente, rode `python3 -m backend.app` com o ambiente
   do projeto ativado e abra a página servida pelo Flask.

2. Centralize as chamadas em `frontend/js/api.js`. Envie JSON com
   `Content-Type: application/json` quando houver corpo. Leia `{ok,data,error}`,
   mas trate também resposta não JSON e falha de rede. Exiba conteúdo recebido
   com `textContent`, incluindo nomes, instruções e conclusões.

3. Professor: `POST /api/sessions` recebe `activity_title`, `group_size`,
   `stages` e `roles`, como no contrato. Guarde imediatamente `session.code`
   e `teacher_token`. Em `/api/sessions/{code}`, use `X-Teacher-Token` em
   `POST /start`, `POST /next` e `GET /results`; todos sem corpo.
   `/results` funciona antes, durante e depois da atividade. `groups=[]`
   e `submission=null` são estados normais.

4. Aluno: `POST /api/sessions/{code}/join` recebe `{"name":"Nome"}`.
   Guarde código, participante e `participant_token`. Depois use
   `X-Participant-Token`. Consulte `GET /state` a cada 1,5–2 segundos,
   sem sobrepor requisições; pause em tela inativa e aumente a espera após erro.
   A tela segue `session.status`, `current_stage`, função, grupo e
   `current_stage_completed`. Não trate `current_stage=null` como erro.

5. Concluir função: `POST /complete-role` com `{"stage_id":"UUID da etapa exibida"}`.
   Repetições devem manter esse ID. Conclusão do grupo: `POST /submissions`
   com `{"content":"Texto"}`, apenas em `active` e etapa `conclusion`.
   Qualquer integrante pode enviar; combinar um responsável evita sobrescritas.

6. Separe tokens por sessão e perfil. Para testar vários alunos no mesmo
   navegador, prefira `sessionStorage` por aba ou perfis separados; uma chave
   única em `localStorage` pode misturar os alunos. Nunca coloque tokens em URLs ou logs.
   Bloqueie botões enquanto aguarda resposta. Não repita automaticamente
   criar, entrar ou avançar após timeout: a ação pode já ter sido salva.
   Em 400, corrigir formulário; 401, avisar acesso inválido; 404, conferir sessão;
   409, atualizar o estado disponível; 500/rede, avisar sem simular sucesso.

7. Atenção: `/results` não informa a etapa atual e `/state` não devolve a
   submissão já salva pelo grupo. Não existe recuperação de token. Não use
   `/next` para descobrir a etapa após recarregar: isso avança a atividade.
   Se faltar informação para a tela, descreva a necessidade para alinharmos
   uma mudança de contrato.

Testem professor/alunos em abas ou perfis separados, clique duplo, reload,
rede lenta, troca de etapa durante envio e encerramento. A pendência de
concorrência do backend não se resolve apenas desabilitando botões no frontend.
O relatório técnico está em `backend/REVIEW.md`.
