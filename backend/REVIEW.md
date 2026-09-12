# Revisão funcional do backend — 12/09/2026

Base revisada: `61d110d`, branch `backend-dev`. Este documento registra
correções e limitações verificadas; não altera `docs/api.md`.

## Atualização: correções transacionais

As quatro regressões foram tratadas com RPCs que bloqueiam a linha da sessão
durante validação e escrita. Os contratos HTTP permanecem os mesmos.
A revisão abaixo é o registro histórico anterior às correções.

- `supabase/atomic_join.sql`: entrada, capacidade e distribuição dos grupos.
- `supabase/atomic_complete_role.sql`: conclusão da função na etapa ativa.
- `supabase/atomic_submission.sql`: envio/atualização antes do encerramento.

As três funções foram aplicadas no projeto Flow e verificadas com
`supabase/test_atomic_operations.sql`, executado como `service_role`.
O teste verifica sucesso, conflitos, idempotência e atualização, e reverte
todas as suas linhas ao final. As permissões de execução de `anon` e
`authenticated` foram verificadas como negadas.

Suíte Python: 146 testes aprovados, sem xfail. Os testes de concorrência
do Flask simulam intercalações no transporte; não substituem teste de carga
com conexões PostgreSQL simultâneas, que ainda não foi executado.

Para outro ambiente, aplicar os três SQLs aditivos depois de `schema.sql`
e antes de iniciar este backend. Não repetir o schema inicial num banco existente.
Nenhuma dependência nova, contrato HTTP ou arquivo de frontend foi alterado.

## Conclusão da revisão anterior

Os oito endpoints funcionam no percurso sequencial. A suíte revisada contém
147 testes aprovados e quatro casos de concorrência marcados como `xfail`
com `strict=True`. Esses quatro casos continuam falhando: não são correções
nem evidência de aprovação de concorrência.

A entrada simultânea de alunos precisa de correção antes de testar com uma
turma inteira: foi reproduzido um grupo com três integrantes apesar de
`group_size=2`. Desabilitar botões no frontend não resolve entradas vindas
de aparelhos diferentes.

## Corrigido nesta revisão

- JSON com aninhamento excessivo (~20 KB no reprodutor) escapava do parser e
  produzia erro HTML ou exceção no modo de desenvolvimento. As quatro rotas
  com corpo agora devolvem `400 VALIDATION_ERROR`.
- Textos com NUL ou surrogate Unicode isolado eram aceitos pela validação,
  embora não possam ser persistidos em PostgreSQL/UTF-8. São rejeitados com
  `400 VALIDATION_ERROR`, antes de acessar o banco.
- Tokens Unicode que não podem ser codificados agora geram `401` com o
  código de token inválido correspondente, em vez de falha interna.
- Exceções inesperadas nos handlers dos oito endpoints agora usam o envelope
  `500 INTERNAL_ERROR`. Erros HTTP de roteamento continuam fora desse fallback;
  uma URL errada ou resposta de proxy ainda pode não ser JSON.

Evidência: os 24 testes novos em `tests/test_http_regressions.py` falharam
antes das correções e passaram depois. A suíte anterior tinha 123 testes.

## Falhas e riscos ainda abertos

### Prioridade alta: distribuição concorrente de alunos

Em `backend/services/sessions.py`, `join_session` consulta a quantidade de
participantes e só depois faz o INSERT. Dois pedidos podem ler a mesma
quantidade e ocupar a mesma posição de grupo/função. Reprodução: grupo de
tamanho dois com um aluno; duas entradas intercaladas resultam em três
integrantes no primeiro grupo, em vez de dois no primeiro e um no segundo.

Teste: `test_concurrent_joins_respect_group_size`.

### Operações sobrepostas à mudança de estado

A validação de estado e a gravação estão em pedidos distintos ao banco:

- Uma entrada iniciada em `waiting` pode terminar depois de `/start`, e a
  resposta ainda dizer `waiting`.
- Uma conclusão da função iniciada na etapa atual pode ser persistida depois
  de `/next` selecionar outra etapa.
- Um envio iniciado em `conclusion` pode ser persistido depois de `finished`,
  alterando os resultados depois do encerramento.

São janelas reproduzidas de consistência em operações sobrepostas. O contrato
não define um instante de corte transacional; o caso de lotação acima do limite
é um defeito inequívoco. Os três testes restantes registram a expectativa de
rejeitar gravações quando a mudança de estado já venceu a disputa.

Evidência: `tests/test_concurrency_regressions.py` intercala chamadas reais de
rotas no transporte PostgREST simulado. Não houve teste de carga concorrente
no Supabase real nesta revisão.

### Correção técnica recomendada para a próxima etapa

Executar autorização/validação, contagem/atribuição e gravação em transações
no PostgreSQL, coordenadas pelo registro da sessão. Uma função interna para
entrada deve bloquear a sessão, conferir `waiting`, contar, atribuir e inserir
antes de liberar o bloqueio. Conclusão/submissão devem validar etapa e gravar
sob a mesma coordenação usada nas transições do professor.

Um mutex somente no Python não resolve múltiplos processos ou instâncias.
A implementação pode preservar o contrato HTTP, mas exige uma mudança interna
no banco, testes transacionais e aplicação coordenada. Nenhuma alteração de
esquema foi feita nesta revisão.

## Limitações do contrato relevantes para o frontend

- `/results` funciona em `waiting`, `active` e `finished`, mas não informa
  `current_stage`, a lista de etapas ou o total delas. Depois de perder uma
  resposta de `/next`, recarregar a tela ou usar outro dispositivo, o professor
  não consegue confirmar a etapa atual por uma consulta autenticada existente.
  Um snapshot local é apenas o último estado conhecido.
- `/state` não retorna a submissão do grupo. Um aluno não consegue carregar
  pelo GET o texto que outro colega enviou. O último POST do grupo substitui
  o conteúdo anterior; não existe controle de versão colaborativo.
- `completed_stage_count` é acumulado; não identifica quem concluiu uma etapa
  específica. `/next` não exige conclusão de todos os alunos.
- Não existe recuperação de tokens. `create`, `join` e `next` não são
  idempotentes; um timeout não autoriza repetir automaticamente a ação.
- A criação usa inserções separadas e exclusão compensatória em caso de falha.
  Uma falha também na compensação pode deixar sessão incompleta. Essa limitação
  foi observada no código, não reproduzida em falha real de infraestrutura.

Qualquer ampliação de campos ou endpoints precisa de aprovação antes de
alterar `docs/api.md`. A integração visual pode avançar seguindo o contrato
existente, sem apresentar essas limitações como funcionalidades disponíveis.

## Validação e limites

Comando: `.venv/bin/python -m pytest -q -rx`.
Resultado: **147 passed, 4 xfailed**.

Os testes cobrem fluxo completo, autenticação e isolamento por sessão,
idempotência da conclusão, atualização da submissão, paginação, validação,
falhas de banco simuladas e os intercalamentos descritos acima.

Na etapa anterior, o fluxo sequencial dos oito endpoints foi exercitado no
Supabase real na sessão sintética `RTBCG`, que ficou finalizada. Nesta revisão
não foram criados nem alterados registros no Supabase. Não houve teste visual
de navegador: os arquivos `frontend/js/api.js`, `aluno.js` e `professor.js`
ainda estavam como placeholders no checkout revisado.
