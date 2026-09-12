# HACKTUDO 2026 — uso orientado de smartphones em aula

Base técnica de uma aplicação que ajuda professores a organizar quando, por quem e para qual finalidade smartphones são usados durante uma atividade. Esta etapa prepara a colaboração; as funcionalidades do produto ainda serão implementadas gradualmente.

## Stack

- Frontend: HTML, CSS e JavaScript vanilla
- Backend: Python e Flask
- Banco: Supabase/PostgreSQL
- Deploy: uma aplicação Flask, servindo também o frontend

## Estrutura

- `backend/`: API, configuração, acesso ao banco e regras de negócio.
- `frontend/`: telas e JavaScript do navegador.
- `docs/`: contrato da API, arquitetura e fluxo de colaboração.
- `supabase/`: modelo inicial do banco.
- `tests/`: testes automatizados.
- `AGENTS.md` e `CLAUDE.md`: limites de atuação dos agentes.

## Preparação local

Requer Python 3.10 ou mais recente.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Se Ubuntu/Debian informar que `ensurepip` não está disponível ao criar o ambiente, instale primeiro o pacote do sistema:

```bash
sudo apt install python3-venv
```

Preencha o `.env` local com as credenciais do projeto Supabase. Nunca envie esse arquivo ao Git. A chave `SUPABASE_SERVICE_ROLE_KEY` é exclusiva do backend e jamais deve aparecer em `frontend/`.

## Executar

```bash
python3 -m backend.app
```

Abra `http://127.0.0.1:5000`. As páginas do frontend ficam em `frontend/` e são servidas pelo Flask.

Para executar os testes:

```bash
pytest
```

## Colaboração

O backend e o frontend podem evoluir em paralelo, mas ambos devem obedecer a `docs/api.md`. Codex trabalha no backend e Claude Code no frontend. Alterações de contrato precisam de aprovação humana. Integre e teste um checkpoint pequeno de cada vez, conforme `docs/workflow.md`.
