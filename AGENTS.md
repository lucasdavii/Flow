# HACKTUDO 2026

Aplicação para organizar o uso de smartphones em atividades de sala. Priorize simplicidade, estabilidade e mudanças pequenas e testáveis.

## Stack e arquitetura

- Frontend: HTML, CSS e JavaScript vanilla em `frontend/`.
- Backend: Python e Flask em `backend/`.
- Banco: Supabase/PostgreSQL, acessado somente pelo Flask.
- Um único deploy: o Flask também serve os arquivos estáticos do frontend.

## Responsabilidades

- Codex: `backend/**`, `tests/**` e `supabase/**`. Não altere `frontend/**` sem autorização explícita.
- Claude Code: somente `frontend/**`, salvo autorização explícita. Nunca acesse Supabase diretamente.
- `docs/api.md` e `docs/architecture.md` são contratos compartilhados.

Antes de implementar qualquer endpoint, leia `docs/api.md`. Não invente endpoints, campos ou formatos diferentes do contrato. Se uma mudança de contrato for necessária, pare, explique e aguarde aprovação humana antes de editar `docs/api.md`.

## Comandos

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 -m backend.app
pytest
```

## Segurança e qualidade

- Nunca coloque segredos, tokens ou chaves reais no Git ou no frontend.
- O frontend consome somente `/api/**`; a chave de serviço do Supabase fica no backend.
- Não execute SQL destrutivo automaticamente.
- Evite novos frameworks e arquitetura desnecessária.
- Faça alterações pequenas, compreensíveis e cobertas por testes proporcionais ao risco.
