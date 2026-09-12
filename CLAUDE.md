# Orientações para Claude Code

1. Leia `AGENTS.md` e depois `docs/api.md` antes de começar.
2. Trabalhe somente em `frontend/**`, salvo autorização explícita do responsável humano.
3. Não conecte o frontend diretamente ao Supabase e não coloque chaves no JavaScript.
4. Consuma exclusivamente a API Flask em `/api/**`.
5. Mantenha dados simulados exatamente compatíveis com os campos, tipos e envelopes JSON definidos em `docs/api.md`.
6. Não crie endpoints nem altere o contrato da API por conta própria.
7. Se o contrato parecer insuficiente, pare, explique a mudança proposta e espere aprovação humana.
8. Preserve HTML, CSS e JavaScript vanilla; não adicione framework sem aprovação.
