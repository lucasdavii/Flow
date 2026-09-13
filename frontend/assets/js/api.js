/**
 * Cliente da API do FlowRoom.
 * Segue exatamente docs/api.md: base "/api", envelope {ok,data,error},
 * X-Teacher-Token para o professor e X-Participant-Token para o aluno.
 * Não inventa endpoints, campos ou formatos além do contrato.
 */
(function (global) {
  "use strict";

  const BASE = "/api";

  function tokenKey(kind, code) {
    return `flowroom_${kind}_${String(code || "").toUpperCase()}`;
  }

  // sessionStorage é isolado por aba: evita misturar tokens de alunos
  // diferentes testados em abas separadas do mesmo navegador.
  const tokens = {
    setTeacher(code, token) {
      sessionStorage.setItem(tokenKey("teacher", code), token);
    },
    getTeacher(code) {
      return sessionStorage.getItem(tokenKey("teacher", code));
    },
    setParticipant(code, token) {
      sessionStorage.setItem(tokenKey("participant", code), token);
    },
    getParticipant(code) {
      return sessionStorage.getItem(tokenKey("participant", code));
    },
    clear(code) {
      sessionStorage.removeItem(tokenKey("teacher", code));
      sessionStorage.removeItem(tokenKey("participant", code));
    },
  };

  async function request(path, { method = "GET", body, teacherToken, participantToken } = {}) {
    const headers = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (teacherToken) headers["X-Teacher-Token"] = teacherToken;
    if (participantToken) headers["X-Participant-Token"] = participantToken;

    let response;
    try {
      response = await fetch(BASE + path, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (networkError) {
      // Falha de rede: não simula sucesso, devolve envelope compatível.
      return {
        ok: false,
        data: null,
        error: { code: "CLIENT_NETWORK_ERROR", message: "Não foi possível concluir a operação. Tente novamente." },
        status: 0,
      };
    }

    let envelope;
    try {
      envelope = await response.json();
    } catch (parseError) {
      return {
        ok: false,
        data: null,
        error: { code: "CLIENT_PARSE_ERROR", message: "Não foi possível concluir a operação. Tente novamente." },
        status: response.status,
      };
    }

    envelope.status = response.status;
    return envelope;
  }

  // Mensagem estável por status, conforme orientação do backend (não expor
  // detalhes internos; 400 corrige formulário, 401 acesso inválido,
  // 404 confere sessão, 409 atualiza estado, 500/rede avisa sem repetir).
  function describeError(result) {
    if (!result) return "Não foi possível concluir a operação. Tente novamente.";
    const status = result.status;
    const message = result.error && result.error.message;
    if (status === 400) return message || "Confira os campos preenchidos.";
    if (status === 401) return "Acesso inválido. Entre novamente.";
    if (status === 404) return "Sala não encontrada. Confira o código.";
    if (status === 409) return message || "O estado da sala mudou. Atualize a tela.";
    return "Não foi possível concluir a operação. Tente novamente.";
  }

  const FlowAPI = {
    tokens,
    describeError,

    createSession({ activityTitle, groupSize, stages, roles }) {
      return request("/sessions", {
        method: "POST",
        body: { activity_title: activityTitle, group_size: groupSize, stages, roles },
      });
    },

    joinSession(code, name) {
      return request(`/sessions/${encodeURIComponent(code)}/join`, {
        method: "POST",
        body: { name },
      });
    },

    getState(code, participantToken) {
      return request(`/sessions/${encodeURIComponent(code)}/state`, {
        method: "GET",
        participantToken,
      });
    },

    startSession(code, teacherToken) {
      return request(`/sessions/${encodeURIComponent(code)}/start`, {
        method: "POST",
        teacherToken,
      });
    },

    nextStage(code, teacherToken) {
      return request(`/sessions/${encodeURIComponent(code)}/next`, {
        method: "POST",
        teacherToken,
      });
    },

    completeRole(code, stageId, participantToken) {
      return request(`/sessions/${encodeURIComponent(code)}/complete-role`, {
        method: "POST",
        body: { stage_id: stageId },
        participantToken,
      });
    },

    submitConclusion(code, content, participantToken) {
      return request(`/sessions/${encodeURIComponent(code)}/submissions`, {
        method: "POST",
        body: { content },
        participantToken,
      });
    },

    getResults(code, teacherToken) {
      return request(`/sessions/${encodeURIComponent(code)}/results`, {
        method: "GET",
        teacherToken,
      });
    },

    /**
     * Poll de estado com pausa em aba inativa e espera maior após erro,
     * conforme docs/api.md ("requisições não devem se sobrepor").
     */
    pollState(code, participantToken, onUpdate, { interval = 1800, errorInterval = 4000 } = {}) {
      let stopped = false;
      let inFlight = false;
      let timer = null;

      async function tick() {
        if (stopped || inFlight) return;
        if (document.hidden) {
          timer = setTimeout(tick, interval);
          return;
        }
        inFlight = true;
        const result = await FlowAPI.getState(code, participantToken);
        inFlight = false;
        if (stopped) return;
        onUpdate(result);
        timer = setTimeout(tick, result.ok ? interval : errorInterval);
      }

      document.addEventListener("visibilitychange", () => {
        if (!document.hidden && !inFlight && !stopped) tick();
      });

      tick();
      return () => {
        stopped = true;
        if (timer) clearTimeout(timer);
      };
    },
  };

  global.FlowAPI = FlowAPI;
})(window);
