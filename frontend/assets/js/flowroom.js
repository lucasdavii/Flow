window.FLOWROOM_SUBJECTS = {
  history: {
    icon: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="8.6" stroke="currentColor" stroke-width="1.6"/><line class="rp-needle" x1="12" y1="12" x2="12" y2="5.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/></svg>',
    label: "História",
    color: "#f3c852",
    description: "Perspectivas diferentes se encontram para explicar uma decisão.",
    scene: "O mapa da crise está se formando",
    sceneText: "Linhas do tempo, documentos e decisões se conectam.",
    visual: "orbit",
  },
  science: {
    icon: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M10 3h4M10 3v5.2l-5.1 8.7A2 2 0 0 0 6.6 20h10.8a2 2 0 0 0 1.7-3.1L14 8.2V3" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><circle class="rp-bubble" cx="10" cy="16" r="1" fill="currentColor"/><circle class="rp-bubble" cx="13.2" cy="17.6" r="1.3" fill="currentColor"/><circle class="rp-bubble" cx="14.6" cy="14.6" r=".8" fill="currentColor"/></svg>',
    label: "Ciências",
    color: "#9dd8c2",
    description: "Hipóteses, evidências e descobertas circulam pelo grupo.",
    scene: "O laboratório da turma está ligado",
    sceneText: "Cada pista vira uma hipótese para testar em conjunto.",
    visual: "particles",
  },
  math: {
    icon: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><g class="rp-shape"><rect x="3.6" y="3.6" width="7" height="7" rx="1.4" stroke="currentColor" stroke-width="1.6"/><circle cx="17" cy="7.2" r="3.4" stroke="currentColor" stroke-width="1.6"/><path d="M4 20.4l6.4-9 6.6 9H4Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></g></svg>',
    label: "Matemática",
    color: "#b9a9ee",
    description: "Cada pessoa encontra uma parte do raciocínio e completa o problema.",
    scene: "O problema ganhou novas formas",
    sceneText: "Padrões diferentes se encaixam até revelar a solução.",
    visual: "grid",
  },
  language: {
    icon: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 5.6A2.5 2.5 0 0 1 6.5 3.1h11A2.5 2.5 0 0 1 20 5.6v7.8A2.5 2.5 0 0 1 17.5 16H10l-4.6 3.9v-3.9H6.5A2.5 2.5 0 0 1 4 13.4V5.6Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><circle class="rp-dot" cx="9" cy="9.5" r="1.1" fill="currentColor"/><circle class="rp-dot" cx="12.6" cy="9.5" r="1.1" fill="currentColor"/><circle class="rp-dot" cx="16.2" cy="9.5" r="1.1" fill="currentColor"/></svg>',
    label: "Língua Portuguesa",
    color: "#f5a6be",
    description: "Leitura, repertório e autoria se transformam em uma ideia comum.",
    scene: "As palavras encontraram um fio",
    sceneText: "Ideias, vozes e repertórios começam a conversar.",
    visual: "words",
  },
};
const go = (url) => {
  window.location.href = url;
};
document.querySelectorAll("[data-go]").forEach((el) => {
  if (el.dataset.go.includes(".htm") || el.dataset.go.includes("://"))
    el.addEventListener("click", () => go(el.dataset.go));
});
document.querySelectorAll("form[data-next]").forEach((form) =>
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    go(form.dataset.next);
  }),
);
const imgBase = location.pathname.includes("/pages/") ? "../img/" : "img/";
const logoStyle = document.createElement("style");
logoStyle.textContent = ".brand-logo{display:block;height:3em;width:auto}";
document.head.append(logoStyle);
const paintLogos = () => {
  const dark = document.documentElement.dataset.theme === "dark";
  const src = imgBase + (dark ? "logo_modoescuro.png" : "logo_modoclaro.png");
  document.querySelectorAll(".brand").forEach((brand) => {
    let img = brand.querySelector(".brand-logo");
    if (!img) {
      brand.innerHTML = "";
      img = document.createElement("img");
      img.className = "brand-logo";
      img.alt = "FlowRoom";
      brand.append(img);
      brand.setAttribute("aria-label", "FlowRoom");
    }
    img.src = src;
  });
};
const THEME_KEY = "flowroom-theme";
const applyTheme = (theme) => {
  document.documentElement.dataset.theme = theme;
  paintLogos();
};
applyTheme(localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light");
const style = document.createElement("style");
style.textContent =
  '.access-launcher{align-items:center;background:linear-gradient(145deg,#38bdf8,#2563eb);border:3px solid #fff;border-radius:16px 0 0 16px;bottom:32px;box-shadow:0 8px 22px #082f6b55;color:#fff;display:flex;height:64px;justify-content:center;position:fixed;right:0;top:auto;width:64px;z-index:20}.access-launcher:focus-visible{outline:3px solid var(--yellow);outline-offset:4px}.access-glyph{height:42px;width:42px}.access-panel{background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:0 18px 45px #123b3a30;display:none;max-height:min(74vh,600px);overflow-y:auto;padding:17px;position:fixed;bottom:108px;right:18px;width:min(330px,calc(100vw - 36px));z-index:19}.access-panel.open{display:block}.access-panel h2{font-family:"Space Grotesk";font-size:1.1rem;margin:0 0 4px}.access-panel p{color:var(--muted);font-size:.78rem;margin:0 0 14px}.access-option{align-items:center;background:#f4f8f3;border:1px solid var(--line);border-radius:11px;color:var(--ink);display:flex;gap:10px;margin-top:8px;padding:10px;text-align:left;width:100%}.access-option b{font-size:.82rem}.access-option small{color:var(--muted);display:block;font-size:.7rem}.access-option[aria-pressed="true"]{background:var(--ink);color:#fff}.access-option[aria-pressed="true"] small{color:#d7eee0}.access-symbol{align-items:center;background:var(--yellow);border-radius:8px;display:flex;font-size:1.05rem;height:30px;justify-content:center;width:30px}.live-region{color:var(--teal);display:block;font-size:.75rem;font-weight:700;min-height:18px;margin-top:10px}.large-text{font-size:18px}.high-contrast{--paper:#fff;--ink:#000;--muted:#263332;--line:#777;--mint:#d4f5df}.calm-mode *{animation:none!important;transition:none!important}.focus-mode .site-header,.focus-mode .access-launcher{opacity:.5}.focus-mode main>*:not(.access-panel){filter:drop-shadow(0 0 14px #23958b30)}.underline-links a{text-decoration:underline;text-decoration-thickness:2px;text-underline-offset:3px}.wide-spacing{line-height:1.85;letter-spacing:.02em}.large-cursor,.large-cursor *{cursor:zoom-in!important}.grayscale{filter:grayscale(1)}.keyboard-mode *:focus-visible{outline:4px solid #f59e0b!important;outline-offset:4px}.reading-guide{background:#f59e0b55;border-top:2px solid #d97706;border-bottom:2px solid #d97706;height:42px;left:0;pointer-events:none;position:fixed;right:0;transform:translateY(-50%);z-index:18}@media(max-width:560px){.access-launcher{bottom:22px}.access-panel{bottom:96px;right:16px}}';
document.head.append(style);
const button = document.createElement("button");
button.className = "access-launcher";
button.type = "button";
button.setAttribute("aria-label", "Abrir acessibilidade");
button.setAttribute("aria-expanded", "false");
button.title = "Abrir acessibilidade";
button.innerHTML =
  '<svg class="access-glyph" viewBox="0 0 48 48" aria-hidden="true"><defs><linearGradient id="accessBlue" x1="6" y1="4" x2="42" y2="44" gradientUnits="userSpaceOnUse"><stop stop-color="#38bdf8"/><stop offset="1" stop-color="#2563eb"/></linearGradient></defs><circle cx="24" cy="24" r="23" fill="url(#accessBlue)"/><circle cx="24" cy="13" r="3.5" fill="#fff"/><rect x="21" y="18" width="6" height="14" rx="3" fill="#fff"/><rect x="9" y="19" width="30" height="5" rx="2.5" fill="#fff"/><path d="M23 29 17 40M25 29l6 11" fill="none" stroke="#fff" stroke-linecap="round" stroke-width="4"/></svg>';
document.body.append(button);
const panel = document.createElement("section");
panel.className = "access-panel";
panel.setAttribute("aria-label", "Painel de acessibilidade");
panel.innerHTML =
  '<h2>Acessibilidade</h2><p>Ative uma opção e observe a diferença na tela.</p><button class="access-option" data-access="dark" aria-pressed="false"><span class="access-symbol">☾</span><span><b>Modo escuro</b><small>Alterna entre claro e escuro</small></span></button><button class="access-option" data-access="text" aria-pressed="false"><span class="access-symbol">Aa</span><span><b>Texto maior</b><small>Leitura mais confortável</small></span></button><button class="access-option" data-access="contrast" aria-pressed="false"><span class="access-symbol">◐</span><span><b>Alto contraste</b><small>Mais diferença entre cores</small></span></button><button class="access-option" data-access="motion" aria-pressed="false"><span class="access-symbol">II</span><span><b>Reduzir movimento</b><small>Tela mais calma</small></span></button><button class="access-option" data-access="focus" aria-pressed="false"><span class="access-symbol">◎</span><span><b>Modo foco</b><small>Destaca o conteúdo principal</small></span></button><button class="access-option" data-access="links" aria-pressed="false"><span class="access-symbol">↗</span><span><b>Sublinhar links</b><small>Navegação mais clara</small></span></button><button class="access-option" data-access="spacing" aria-pressed="false"><span class="access-symbol">↕</span><span><b>Mais espaçamento</b><small>Texto mais arejado</small></span></button><button class="access-option" data-access="cursor" aria-pressed="false"><span class="access-symbol">⌁</span><span><b>Cursor ampliado</b><small>Mais fácil de acompanhar</small></span></button><button class="access-option" data-access="guide" aria-pressed="false"><span class="access-symbol">—</span><span><b>Guia de leitura</b><small>Acompanha a linha atual</small></span></button><button class="access-option" data-access="gray" aria-pressed="false"><span class="access-symbol">◑</span><span><b>Escala de cinza</b><small>Reduz estímulos de cor</small></span></button><button class="access-option" data-access="keyboard" aria-pressed="false"><span class="access-symbol">Tab</span><span><b>Foco de teclado</b><small>Destaca onde você está</small></span></button><button class="access-option" data-access="vlibras"><span class="access-symbol">L</span><span><b>Ativar VLibras</b><small>Tradução para Libras</small></span></button><span class="live-region" aria-live="polite"></span>';
document.body.append(panel);
panel
  .querySelector('[data-access="dark"]')
  .setAttribute("aria-pressed", document.documentElement.dataset.theme === "dark");
button.addEventListener("click", () => {
  const open = panel.classList.toggle("open");
  button.setAttribute("aria-expanded", open);
});
const guide = document.createElement("div");
guide.className = "reading-guide";
guide.hidden = true;
document.body.append(guide);
document.addEventListener("mousemove", (event) => {
  if (!guide.hidden) guide.style.top = event.clientY + "px";
});
const announce = (message) => {
  panel.querySelector(".live-region").textContent = message;
};
const toggle = (name, enabled) => {
  const classes = {
    text: "large-text",
    contrast: "high-contrast",
    motion: "calm-mode",
    focus: "focus-mode",
    links: "underline-links",
    spacing: "wide-spacing",
    cursor: "large-cursor",
    gray: "grayscale",
    keyboard: "keyboard-mode",
  };
  if (name === "guide") guide.hidden = !enabled;
  else if (name === "dark") {
    applyTheme(enabled ? "dark" : "light");
    localStorage.setItem(THEME_KEY, enabled ? "dark" : "light");
  } else document.body.classList.toggle(classes[name], enabled);
  const control = panel.querySelector(`[data-access="${name}"]`);
  control.setAttribute("aria-pressed", enabled);
  announce((enabled ? "Ativado: " : "Desativado: ") + control.textContent.trim());
};
panel.querySelectorAll("[data-access]").forEach((control) =>
  control.addEventListener("click", () => {
    const name = control.dataset.access;
    if (name === "vlibras") {
      loadVlibras();
      announce("VLibras ativado e disponível na tela.");
      return;
    }
    toggle(name, !control.matches('[aria-pressed="true"]'));
  }),
);
function loadVlibras() {
  if (window.VLibras) {
    new window.VLibras.Widget("https://vlibras.gov.br/app");
    return;
  }
  if (document.querySelector("#vlibras-script")) return;
  const script = document.createElement("script");
  script.id = "vlibras-script";
  script.src = "https://vlibras.gov.br/app/vlibras-plugin.js";
  script.onload = () => {
    const widget = document.createElement("div");
    widget.innerHTML =
      '<div vw class="enabled"><div vw-access-button class="active"></div><div vw-plugin-wrapper><div class="vw-plugin-top-wrapper"></div></div></div>';
    document.body.append(widget);
    new window.VLibras.Widget("https://vlibras.gov.br/app");
  };
  document.head.append(script);
}
const ambientLayers = [
  { selector: ".ambient-dust i", depth: 2 },
  { selector: ".ambient-sparkle", depth: 5 },
  { selector: ".ambient-ring", depth: 9 },
  { selector: ".ambient-glass", depth: 13 },
  { selector: ".ambient-orb", depth: 20 },
];
const ambientEntries = ambientLayers
  .map((layer) => ({ depth: layer.depth, els: document.querySelectorAll(layer.selector) }))
  .filter((entry) => entry.els.length);
if (ambientEntries.length && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  document.addEventListener("mousemove", (event) => {
    const relX = event.clientX / window.innerWidth - 0.5;
    const relY = event.clientY / window.innerHeight - 0.5;
    ambientEntries.forEach(({ depth, els }) => {
      const x = (-relX * depth).toFixed(2);
      const y = (-relY * depth).toFixed(2);
      els.forEach((el) => {
        el.style.translate = `${x}px ${y}px`;
      });
    });
  });
}
