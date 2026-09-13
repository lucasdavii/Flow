# FlowRoom — tecnologia com propósito em sala de aula

O FlowRoom ajuda professores a decidir quando, por quem e para qual finalidade smartphones são usados durante uma atividade, alternando pesquisa digital e colaboração presencial.

> **Status atual:** MVP funcional publicado, com fluxo integrado entre professor, alunos, Flask e Supabase. Projeto desenvolvido durante o HACKTUDO 2026 e mantido como portfólio.

[**Acessar o FlowRoom publicado**](https://flowroom-7vml.onrender.com)

## O problema

Na sala de aula, o smartphone costuma ocupar dois extremos: distração constante ou proibição total. As duas opções desperdiçam a possibilidade de usar a tecnologia com intenção pedagógica e sem substituir a conversa presencial.

## A solução

O professor cria uma atividade, compartilha um código e distribui funções complementares entre os alunos. A tecnologia entra apenas quando uma função precisa dela e sai de cena quando o grupo precisa discutir.

O fluxo acontece em três momentos:

1. **Investigar:** pesquisadores e verificadores usam o celular para buscar e avaliar evidências.
2. **Confrontar:** questionadores e relatores ajudam o grupo a comparar ideias sem depender da tela.
3. **Concluir:** o grupo registra uma única síntese construída coletivamente.

## Diferencial

O objetivo não é entregar um celular para cada aluno nem apenas digitalizar uma lista de exercícios. Cada participante recebe uma responsabilidade diferente, e a resposta final depende da combinação dessas contribuições.

- Funções complementares: pesquisador, verificador, questionador e relator.
- Alternância explícita entre etapas digitais e presenciais.
- Sala acessada por código, sem cadastro obrigatório do aluno.
- Acompanhamento do professor e síntese final por grupo.
- Aplicação real integrada e publicada, não apenas telas estáticas.

## Experimente o fluxo

1. Abra o link publicado e escolha **Professor**.
2. Digite o tema, escolha grupos de quatro pessoas e crie a sala.
3. Copie o código exibido.
4. Em outras abas ou dispositivos, escolha **Aluno** e entre com quatro nomes diferentes.
5. Inicie a atividade, acompanhe as funções distribuídas e avance pelas três etapas.
6. Envie a síntese do grupo e confira o resultado na visão do professor.

> No plano gratuito do Render, a primeira abertura após um período sem acessos pode levar alguns segundos.

## Arquitetura e segurança

O Flask serve o frontend e a API no mesmo deploy. O navegador acessa somente `/api/**`; apenas o backend conversa com o Supabase. Tokens de professor e participante ficam na sessão do navegador, enquanto o banco armazena somente seus hashes. A chave secreta do Supabase nunca é enviada ao frontend ou ao Git.

```text
Navegador (HTML/CSS/JS) -> Flask (/api) -> Supabase/PostgreSQL
```

## Decisões de produto

- **Entrada simples:** alunos acessam a atividade por código, sem criar conta.
- **Tecnologia como etapa:** o fluxo sinaliza quando pesquisar no celular e quando voltar à discussão presencial.
- **Participação distribuída:** funções complementares reduzem a concentração da atividade em uma única pessoa.
- **Um deploy:** o Flask entrega a API e o frontend, simplificando a publicação e evitando configuração de CORS entre serviços.

## Estado do projeto

O MVP cobre o ciclo completo de uma atividade: criação da sala, entrada dos participantes, distribuição de funções, avanço das etapas, envio da síntese e visualização dos resultados. Como próximos passos, o projeto pode receber autenticação persistente de professores, histórico de turmas e métricas pedagógicas.

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

Preencha o `.env` local com as credenciais do projeto Supabase. Nunca envie esse arquivo ao Git. A chave `SUPABASE_SECRET_KEY` é exclusiva do backend e jamais deve aparecer em `frontend/`.

## Executar

```bash
python3 -m backend.app
```

Abra `http://127.0.0.1:5000`. As páginas do frontend ficam em `frontend/` e são servidas pelo Flask.

Para executar os testes:

```bash
pytest
```

## Autores

- [Lucas Davi](https://github.com/lucasdavii) — backend, API, banco de dados, integração e deploy.
- [Belles-hub](https://github.com/Belles-hub) — frontend, experiência de uso e identidade visual.

Construído em colaboração para o HACKTUDO 2026 e continuado como projeto de portfólio.
