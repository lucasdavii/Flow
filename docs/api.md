# Contrato oficial da API

Este arquivo é a fonte de verdade entre frontend e backend. Mudanças devem ser discutidas e aprovadas antes da implementação.

## Convenções

- Base: `/api`.
- Corpo e respostas: `application/json`.
- Nomes JSON: `snake_case`.
- IDs: strings no formato UUID.
- Datas: strings ISO 8601 em UTC, por exemplo `2026-09-11T18:30:00Z`.
- Código de sessão: cinco caracteres, normalizado para maiúsculas e sem `0`, `O`, `1` ou `I`.
- Status de sessão: `waiting`, `active` ou `finished`.
- Tipo de etapa: `digital`, `presential` ou `conclusion`.
- Tipo de função: `digital` ou `presential`.

Toda resposta usa um destes envelopes:

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Mensagem compreensível"
  }
}
```

Erros HTTP comuns: `400` para entrada inválida, `401` para token ausente ou inválido, `404` para sessão inexistente, `409` para conflito de estado e `500` para falha inesperada.

Falhas inesperadas usam o código `INTERNAL_ERROR`. Esse código único permite que o frontend mostre uma mensagem estável quando banco ou servidor estiverem indisponíveis, sem receber detalhes internos que poderiam expor a infraestrutura.

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Não foi possível concluir a operação. Tente novamente."
  }
}
```

## Autorização simples

- Ao criar uma sessão, o backend gera um `teacher_token`, devolve o valor bruto uma única vez e salva somente seu hash.
- Ao entrar, o backend gera `participant_id` e `participant_token`, devolve o token bruto uma única vez e salva somente seu hash.
- Operações do professor usam `X-Teacher-Token`.
- Operações do aluno usam `X-Participant-Token`.
- O frontend guarda o token correspondente localmente e nunca o inclui em logs ou URLs.

## Modelos compartilhados

Uma etapa tem esta forma:

```json
{
  "id": "d75df973-6948-44f2-91c6-53f30448eb1b",
  "position": 1,
  "title": "Pesquisa orientada",
  "type": "digital",
  "instructions": "Pesquise duas fontes sobre o tema."
}
```

Uma função tem esta forma:

```json
{
  "id": "ef6beabb-03ab-455a-8f1c-77e63d8fcb12",
  "name": "pesquisador",
  "type": "digital",
  "description": "Usa o smartphone para localizar informações."
}
```

## POST `/api/sessions`

Cria uma sessão em estado `waiting`, suas etapas e funções. Chamado pelo professor; não exige token anterior.

### Request

```json
{
  "activity_title": "Uso consciente da água",
  "group_size": 4,
  "stages": [
    {
      "position": 1,
      "title": "Pesquisa orientada",
      "type": "digital",
      "instructions": "Encontre duas fontes confiáveis."
    },
    {
      "position": 2,
      "title": "Discussão do grupo",
      "type": "presential",
      "instructions": "Guardem os aparelhos e discutam as descobertas."
    },
    {
      "position": 3,
      "title": "Conclusão",
      "type": "conclusion",
      "instructions": "Registrem a conclusão do grupo."
    }
  ],
  "roles": [
    {
      "name": "pesquisador",
      "type": "digital",
      "description": "Localiza informações no smartphone."
    },
    {
      "name": "relator",
      "type": "presential",
      "description": "Organiza a síntese falada do grupo."
    }
  ]
}
```

Regras: `activity_title` é obrigatório; `group_size` é inteiro entre 2 e 8; deve haver pelo menos uma etapa e uma função; `position` começa em 1, sem lacunas nem repetição; nomes de função não se repetem na mesma sessão.

### Response `201`

```json
{
  "ok": true,
  "data": {
    "session": {
      "id": "cc9fa8ec-69a8-45a4-b32c-aeead18fe58d",
      "code": "K7P2X",
      "activity_title": "Uso consciente da água",
      "status": "waiting",
      "current_stage": null,
      "participant_count": 0,
      "created_at": "2026-09-11T18:30:00Z"
    },
    "teacher_token": "token-aleatorio-retornado-uma-vez"
  },
  "error": null
}
```

Erros: `VALIDATION_ERROR` (`400`) e `SESSION_CODE_GENERATION_FAILED` (`500`).

## POST `/api/sessions/{code}/join`

Insere um aluno na sessão e atribui `group_number` e função. Chamado pelo aluno enquanto a sessão está em `waiting`; não exige token anterior.

### Request

```json
{
  "name": "Ana Souza"
}
```

### Response `201`

```json
{
  "ok": true,
  "data": {
    "participant": {
      "id": "f5168159-a39a-4c93-aa57-4e65fbf61224",
      "name": "Ana Souza",
      "group_number": 1,
      "role": {
        "id": "ef6beabb-03ab-455a-8f1c-77e63d8fcb12",
        "name": "pesquisador",
        "type": "digital",
        "description": "Localiza informações no smartphone."
      }
    },
    "participant_token": "token-aleatorio-retornado-uma-vez",
    "session_status": "waiting"
  },
  "error": null
}
```

Erros: `VALIDATION_ERROR` (`400`), `SESSION_NOT_FOUND` (`404`) e `SESSION_ALREADY_STARTED` (`409`).

## GET `/api/sessions/{code}/state`

Retorna ao aluno o estado atual, etapa, grupo, colegas, função e sua conclusão na etapa. Chamado pelo aluno com `X-Participant-Token`.

### Request

Sem corpo.

### Response `200`

```json
{
  "ok": true,
  "data": {
    "session": {
      "id": "cc9fa8ec-69a8-45a4-b32c-aeead18fe58d",
      "code": "K7P2X",
      "activity_title": "Uso consciente da água",
      "status": "active",
      "current_stage": {
        "id": "d75df973-6948-44f2-91c6-53f30448eb1b",
        "position": 1,
        "title": "Pesquisa orientada",
        "type": "digital",
        "instructions": "Encontre duas fontes confiáveis."
      }
    },
    "participant": {
      "id": "f5168159-a39a-4c93-aa57-4e65fbf61224",
      "name": "Ana Souza",
      "group_number": 1,
      "role": {
        "id": "ef6beabb-03ab-455a-8f1c-77e63d8fcb12",
        "name": "pesquisador",
        "type": "digital",
        "description": "Localiza informações no smartphone."
      },
      "current_stage_completed": false
    },
    "group": {
      "number": 1,
      "members": [
        {
          "id": "f5168159-a39a-4c93-aa57-4e65fbf61224",
          "name": "Ana Souza",
          "role_name": "pesquisador"
        }
      ]
    }
  },
  "error": null
}
```

Quando `status` for `waiting` ou `finished`, `current_stage` pode ser `null`. Erros: `PARTICIPANT_TOKEN_REQUIRED` (`401`), `INVALID_PARTICIPANT_TOKEN` (`401`) e `SESSION_NOT_FOUND` (`404`).

### Polling

O frontend do aluno consulta este endpoint a cada 1,5–2 segundos enquanto a tela estiver ativa. Requisições não devem se sobrepor; em falhas temporárias, o frontend espera antes de tentar de novo. WebSocket e Supabase Realtime ficam fora da beta.

## POST `/api/sessions/{code}/start`

Inicia a sessão e seleciona a primeira etapa. Chamado pelo professor com `X-Teacher-Token`.

### Request

Sem corpo.

### Response `200`

```json
{
  "ok": true,
  "data": {
    "session": {
      "id": "cc9fa8ec-69a8-45a4-b32c-aeead18fe58d",
      "code": "K7P2X",
      "status": "active",
      "current_stage": {
        "id": "d75df973-6948-44f2-91c6-53f30448eb1b",
        "position": 1,
        "title": "Pesquisa orientada",
        "type": "digital",
        "instructions": "Encontre duas fontes confiáveis."
      }
    }
  },
  "error": null
}
```

Erros: `TEACHER_TOKEN_REQUIRED` (`401`), `INVALID_TEACHER_TOKEN` (`401`), `SESSION_NOT_FOUND` (`404`), `SESSION_ALREADY_STARTED` (`409`) e `SESSION_HAS_NO_PARTICIPANTS` (`409`).

## POST `/api/sessions/{code}/next`

Avança para a próxima etapa; depois da última, muda a sessão para `finished` e define `current_stage` como `null`. Chamado pelo professor com `X-Teacher-Token`.

### Request

Sem corpo.

### Response `200`

```json
{
  "ok": true,
  "data": {
    "session": {
      "id": "cc9fa8ec-69a8-45a4-b32c-aeead18fe58d",
      "code": "K7P2X",
      "status": "active",
      "current_stage": {
        "id": "3b70e93d-4f83-47cf-8424-8087f262fb75",
        "position": 2,
        "title": "Discussão do grupo",
        "type": "presential",
        "instructions": "Guardem os aparelhos e discutam as descobertas."
      }
    }
  },
  "error": null
}
```

Erros: `TEACHER_TOKEN_REQUIRED` (`401`), `INVALID_TEACHER_TOKEN` (`401`), `SESSION_NOT_FOUND` (`404`) e `SESSION_NOT_ACTIVE` (`409`).

## POST `/api/sessions/{code}/complete-role`

Marca a função do aluno como concluída na etapa ativa. Chamado pelo aluno com `X-Participant-Token`. A operação é idempotente: repetir a mesma conclusão mantém uma única marcação.

### Request

```json
{
  "stage_id": "d75df973-6948-44f2-91c6-53f30448eb1b"
}
```

### Response `200`

```json
{
  "ok": true,
  "data": {
    "completion": {
      "participant_id": "f5168159-a39a-4c93-aa57-4e65fbf61224",
      "stage_id": "d75df973-6948-44f2-91c6-53f30448eb1b",
      "completed_at": "2026-09-11T18:42:00Z"
    }
  },
  "error": null
}
```

Erros: `VALIDATION_ERROR` (`400`), `PARTICIPANT_TOKEN_REQUIRED` (`401`), `INVALID_PARTICIPANT_TOKEN` (`401`), `SESSION_NOT_FOUND` (`404`), `SESSION_NOT_ACTIVE` (`409`) e `STAGE_NOT_CURRENT` (`409`).

## POST `/api/sessions/{code}/submissions`

Envia ou atualiza a conclusão do grupo. Chamado por um integrante com `X-Participant-Token`, somente quando a etapa atual é `conclusion`. Uma sessão mantém uma submissão por grupo.

### Request

```json
{
  "content": "Nosso grupo concluiu que pequenas mudanças reduzem o desperdício de água."
}
```

### Response `200`

```json
{
  "ok": true,
  "data": {
    "submission": {
      "id": "b56d5e11-3475-4278-95fd-bc92d545a52a",
      "group_number": 1,
      "content": "Nosso grupo concluiu que pequenas mudanças reduzem o desperdício de água.",
      "submitted_by": "f5168159-a39a-4c93-aa57-4e65fbf61224",
      "created_at": "2026-09-11T18:50:00Z",
      "updated_at": "2026-09-11T18:50:00Z"
    }
  },
  "error": null
}
```

Erros: `VALIDATION_ERROR` (`400`), `PARTICIPANT_TOKEN_REQUIRED` (`401`), `INVALID_PARTICIPANT_TOKEN` (`401`), `SESSION_NOT_FOUND` (`404`), `SESSION_NOT_ACTIVE` (`409`) e `SUBMISSION_NOT_ALLOWED_IN_CURRENT_STAGE` (`409`).

## GET `/api/sessions/{code}/results`

Retorna participantes, progresso e submissões agrupados para o professor. Chamado pelo professor com `X-Teacher-Token`.

### Request

Sem corpo.

### Response `200`

```json
{
  "ok": true,
  "data": {
    "session": {
      "id": "cc9fa8ec-69a8-45a4-b32c-aeead18fe58d",
      "code": "K7P2X",
      "activity_title": "Uso consciente da água",
      "status": "finished"
    },
    "groups": [
      {
        "number": 1,
        "members": [
          {
            "id": "f5168159-a39a-4c93-aa57-4e65fbf61224",
            "name": "Ana Souza",
            "role_name": "pesquisador",
            "completed_stage_count": 1
          }
        ],
        "submission": {
          "id": "b56d5e11-3475-4278-95fd-bc92d545a52a",
          "content": "Nosso grupo concluiu que pequenas mudanças reduzem o desperdício de água.",
          "submitted_by": "f5168159-a39a-4c93-aa57-4e65fbf61224",
          "updated_at": "2026-09-11T18:50:00Z"
        }
      }
    ]
  },
  "error": null
}
```

`submission` é `null` quando o grupo ainda não enviou a conclusão. Erros: `TEACHER_TOKEN_REQUIRED` (`401`), `INVALID_TEACHER_TOKEN` (`401`) e `SESSION_NOT_FOUND` (`404`).
