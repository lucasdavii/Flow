# Fluxo de trabalho

## Branches

- `main`: base estável e integrada.
- `backend-dev`: trabalho do backend com Codex.
- `frontend-dev`: trabalho do frontend com Claude Code.

Não é preciso criar outras branches agora. Antes de começar um bloco, atualize sua branch a partir de `main`. Faça commits pequenos e com uma única intenção.

Exemplos:

```text
chore: bootstrap project structure
feat: create session endpoint
feat: join session
fix: validate session code
```

## Contrato compartilhado

`docs/api.md` é a fonte de verdade. Backend e frontend podem implementar cada lado em paralelo usando seus exemplos JSON. Se qualquer campo ou endpoint precisar mudar:

1. pare a implementação dependente;
2. explique o motivo;
3. mostre a alteração proposta;
4. espere aprovação humana;
5. altere o contrato somente depois da aprovação.

## Checkpoints de integração

Integre na `main` em blocos pequenos:

1. professor cria sessão e recebe código;
2. aluno entra;
3. aluno recebe grupo e função;
4. professor avança etapa;
5. aluno percebe a mudança por polling;
6. grupo envia conclusão;
7. professor vê resultados.

Depois de cada checkpoint: execute a aplicação, rode os testes, corrija problemas, faça um commit e envie ao remote. Não espere frontend e backend ficarem completos para testar juntos.

## Divisão prática

- Codex altera `backend/**`, `tests/**` e `supabase/**`.
- Claude Code altera `frontend/**`.
- Mudanças em arquivos compartilhados devem ser pequenas, visíveis e combinadas.
- Ao integrar, quem estiver responsável revisa `git diff`, resolve conflitos conscientemente e testa o fluxo afetado.
