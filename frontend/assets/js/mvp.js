/**
 * Integra a experiência FlowRoom aos endpoints documentados em docs/api.md.
 * Os tokens ficam na sessionStorage da aba e nunca são enviados ao Supabase.
 */
(function () {
  "use strict";

  const stages = [
    { position: 1, title: "Pesquisa orientada", type: "digital",
      instructions: "Pesquise fontes confiáveis e registre uma evidência para o grupo." },
    { position: 2, title: "Discussão do grupo", type: "presential",
      instructions: "Guardem os aparelhos e comparem as descobertas do grupo." },
    { position: 3, title: "Conclusão", type: "conclusion",
      instructions: "Registrem juntos a síntese da atividade." },
  ];
  const roles = [
    { name: "pesquisador", type: "digital",
      description: "Localiza informações no smartphone." },
    { name: "relator", type: "presential",
      description: "Organiza a síntese falada do grupo." },
  ];
  const state = {
    code: null, teacherToken: null, participantToken: null, student: null,
    stopStudentPoll: null, teacherTimer: null, teacherLoading: false,
  };
  const app = document.querySelector("#flowApp");
  const page = (name) => document.querySelector(`.app-page[data-page="${name}"]`);

  function show(name) {
    document.querySelectorAll(".app-page").forEach((item) => {
      item.classList.toggle("active", item.dataset.page === name);
    });
    app.classList.add("open");
    app.scrollTop = 0;
    document.body.style.overflow = "hidden";
  }

  function notice(target, text, isError = false) {
    const container = page(target);
    let node = container.querySelector(".mvp-message");
    if (!node) {
      node = document.createElement("p");
      node.className = "mvp-message";
      node.setAttribute("role", "status");
      node.style.cssText = "font-weight:700;margin-top:16px";
      container.querySelector(".form-actions, .screen-actions")?.after(node);
    }
    node.style.color = isError ? "#b42318" : "var(--teal)";
    node.textContent = text;
  }

  function teacherToken() {
    return state.teacherToken || (state.code && FlowAPI.tokens.getTeacher(state.code));
  }

  function participantToken() {
    return state.participantToken ||
      (state.code && FlowAPI.tokens.getParticipant(state.code));
  }

  function setBusy(form, busy) {
    const button = form.querySelector("button[type='submit'],button:not([type])");
    if (button) button.disabled = busy;
  }

  function renderLobby(results) {
    const lobby = page("teacher-lobby");
    const groups = results.groups || [];
    lobby.querySelector(".room-code").textContent = results.session.code;
    lobby.querySelector(".flow-status").textContent =
      `${groups.reduce((total, group) => total + group.members.length, 0)} aluno(s) conectado(s)`;
    const grid = lobby.querySelector(".group-grid");
    grid.textContent = "";
    if (!groups.length) {
      const note = document.createElement("p");
      note.className = "app-note";
      note.textContent = "Aguardando a entrada dos alunos.";
      grid.append(note);
      return;
    }
    groups.forEach((group) => {
      const card = document.createElement("div");
      card.className = "group-box";
      const heading = document.createElement("strong");
      heading.textContent = `Grupo ${group.number} `;
      const count = document.createElement("span");
      count.textContent = `${group.members.length} participante(s)`;
      heading.append(count);
      const names = document.createElement("small");
      names.textContent = group.members.map((member) => member.name).join(" · ");
      card.append(heading, names);
      grid.append(card);
    });
  }

  function renderResults(results) {
    const result = page("teacher-results");
    const groups = results.groups || [];
    const participants = groups.reduce((sum, group) => sum + group.members.length, 0);
    const submissions = groups.filter((group) => group.submission).length;
    [groups.length, participants, submissions].forEach((value, index) => {
      result.querySelectorAll(".result-stat b")[index].textContent = value;
    });
    const card = result.querySelector(".app-card");
    card.textContent = "";
    groups.forEach((group) => {
      const heading = document.createElement("span");
      heading.className = "app-kicker";
      heading.textContent = `Grupo ${group.number}`;
      const content = document.createElement("p");
      content.style.cssText =
        "color:var(--deep);font-family:'Space Grotesk';font-size:1.2rem;margin:14px 0 22px";
      content.textContent = group.submission ?
        group.submission.content : "Ainda não enviou uma conclusão.";
      card.append(heading, content);
    });
    if (!groups.length) card.textContent = "Ainda não há participantes nesta sessão.";
  }

  async function refreshTeacher() {
    if (state.teacherLoading || !state.code || !teacherToken()) return;
    state.teacherLoading = true;
    const result = await FlowAPI.getResults(state.code, teacherToken());
    state.teacherLoading = false;
    if (result.ok) renderLobby(result.data);
  }

  function startTeacherRefresh() {
    if (state.teacherTimer) clearInterval(state.teacherTimer);
    refreshTeacher();
    state.teacherTimer = setInterval(refreshTeacher, 2000);
  }

  function renderStudent(data) {
    state.student = data;
    const { session, participant, group } = data;
    const wait = page("student-wait");
    wait.querySelector("#studentGroupHeading").textContent = `Grupo ${group.number}`;
    wait.querySelector(".app-note[style*='font-size']").textContent =
      `Sua função: ${participant.role.name}`;
    const members = wait.querySelector(".member-list");
    members.textContent = "";
    group.members.forEach((member) => {
      const item = document.createElement("div");
      item.className = "member";
      const name = document.createElement("b");
      name.textContent = member.name;
      const detail = document.createElement("small");
      detail.textContent = member.role_name;
      item.append(name, detail);
      members.append(item);
    });
    if (session.status === "waiting") return show("student-wait");
    if (session.status === "finished") return show("student-final");
    const stage = session.current_stage;
    if (!stage) return;
    if (stage.type === "conclusion") {
      page("student-conclusion").querySelector("h2").textContent = stage.title;
      page("student-conclusion").querySelector(".app-copy").textContent = stage.instructions;
      return show("student-conclusion");
    }
    if (stage.type === "presential") {
      page("student-presential").querySelector("h2").textContent = stage.title;
      page("student-presential").querySelector(".app-copy").textContent = stage.instructions;
      return show("student-presential");
    }
    page("student-role").querySelector("h2").textContent = participant.role.name;
    page("student-role").querySelector(".app-copy").textContent = stage.instructions;
    page("student-role").querySelector(".role-tag").textContent =
      participant.role.type.toUpperCase();
    if (!participant.current_stage_completed) {
      show("student-role");
    } else {
      show("student-done");
    }
  }

  function startStudentPoll() {
    if (state.stopStudentPoll) state.stopStudentPoll();
    state.stopStudentPoll = FlowAPI.pollState(
      state.code, participantToken(), (result) => {
        if (result.ok) renderStudent(result.data);
        else notice("student-wait", FlowAPI.describeError(result), true);
      },
    );
  }

  async function createSession(form) {
    const title = document.querySelector("#activityTitle").value.trim();
    const groupSize = Number.parseInt(document.querySelector("#groupSize").value, 10);
    setBusy(form, true);
    const result = await FlowAPI.createSession({
      activityTitle: title, groupSize, stages, roles,
    });
    setBusy(form, false);
    if (!result.ok) return notice("teacher-config", FlowAPI.describeError(result), true);
    state.code = result.data.session.code;
    state.teacherToken = result.data.teacher_token;
    FlowAPI.tokens.setTeacher(state.code, state.teacherToken);
    notice("teacher-lobby", `Sala ${state.code} criada. Compartilhe este código com a turma.`);
    show("teacher-lobby");
    startTeacherRefresh();
  }

  async function joinSession(form) {
    const code = document.querySelector("#roomInput").value.trim().toUpperCase();
    const name = document.querySelector("#nameInput").value.trim();
    setBusy(form, true);
    const result = await FlowAPI.joinSession(code, name);
    setBusy(form, false);
    if (!result.ok) return notice("student-login", FlowAPI.describeError(result), true);
    state.code = code;
    state.participantToken = result.data.participant_token;
    FlowAPI.tokens.setParticipant(code, state.participantToken);
    startStudentPoll();
    show("student-wait");
  }

  async function startSession() {
    const result = await FlowAPI.startSession(state.code, teacherToken());
    if (!result.ok) return notice("teacher-lobby", FlowAPI.describeError(result), true);
    show("teacher-dashboard");
  }

  async function advanceSession() {
    const result = await FlowAPI.nextStage(state.code, teacherToken());
    if (!result.ok) return notice("teacher-dashboard", FlowAPI.describeError(result), true);
    const session = result.data.session;
    if (session.status === "finished") {
      const results = await FlowAPI.getResults(state.code, teacherToken());
      if (results.ok) renderResults(results.data);
      return show("teacher-results");
    }
    show(session.current_stage.type === "presential" ?
      "teacher-presential" : "teacher-conclusion");
  }

  async function completeRole() {
    const stage = state.student?.session.current_stage;
    if (!stage) return;
    const result = await FlowAPI.completeRole(state.code, stage.id, participantToken());
    if (!result.ok) return notice("student-role", FlowAPI.describeError(result), true);
    show("student-done");
  }

  async function submitConclusion() {
    const content = document.querySelector("#answerInput").value.trim();
    const result = await FlowAPI.submitConclusion(state.code, content, participantToken());
    if (!result.ok) return notice("student-conclusion", FlowAPI.describeError(result), true);
    show("student-final");
  }

  document.addEventListener("submit", (event) => {
    const form = event.target.closest("form[data-form]");
    if (!form) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (form.dataset.form === "student") joinSession(form);
    else if (form.dataset.form === "activity") show("teacher-config");
    else if (form.dataset.form === "teacher") createSession(form);
    else if (form.dataset.form === "teacher-login" || form.dataset.form === "teacher-register") show("teacher-create");
  }, true);

  document.addEventListener("click", (event) => {
    const element = event.target.closest("[data-go], [data-open-app]");
    if (!element) return;
    const destination = element.dataset.go || element.dataset.openApp;
    const simulatedStudentSteps = new Set([
      "student-role", "student-presential", "student-conclusion",
    ]);
    if (simulatedStudentSteps.has(destination)) {
      // A etapa exibida deve vir do estado da sessão, nunca de um botão demonstrativo antigo.
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }
    const actions = {
      "teacher-dashboard": startSession,
      "teacher-presential": advanceSession,
      "teacher-conclusion": advanceSession,
      "teacher-results": advanceSession,
      "student-done": completeRole,
      "student-final": submitConclusion,
    };
    if (destination === "teacher-login" || destination === "teacher-register" ||
        destination === "teacher-activity") {
      event.preventDefault();
      event.stopImmediatePropagation();
      show("teacher-create");
    } else if (actions[destination]) {
      event.preventDefault();
      event.stopImmediatePropagation();
      actions[destination]();
    }
  }, true);

  // A opção A usa somente o contrato atual: título, grupo, etapas e funções.
  // Os campos de autenticação, matéria e dispositivos continuam fora do MVP.
  const hideField = (selector) => {
    const input = document.querySelector(selector);
    if (input) {
      // Um campo oculto não pode continuar obrigatório, pois impediria o envio do formulário.
      input.required = false;
      input.closest(".field").hidden = true;
    }
  };
  hideField("#activitySubject");
  hideField("#activityStages");
  hideField("#maxStudents");
  hideField("#deviceCount");
  const teacherCreate = page("teacher-create");
  const teacherCreateHeading = teacherCreate.querySelector("h1");
  teacherCreateHeading.textContent = "Crie uma atividade para a turma.";
  let teacherCopy = teacherCreate.querySelector(".app-copy");
  if (!teacherCopy) {
    // A tela original não possui texto auxiliar; criamos apenas o necessário para o novo fluxo.
    teacherCopy = document.createElement("p");
    teacherCopy.className = "app-copy";
    teacherCreateHeading.after(teacherCopy);
  }
  teacherCopy.textContent = "Defina um título. Na próxima tela, escolha o tamanho dos grupos.";
  page("teacher-config").querySelector(".app-kicker").textContent =
    "Configuração da sessão";

  page("teacher-conclusion").querySelector(".app-btn").textContent =
    "Encerrar atividade e ver resultados →";
})();
