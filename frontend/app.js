const thread = document.getElementById("thread");
const form = document.getElementById("composer");
const input = document.getElementById("message");
const submit = document.getElementById("submit");
const teamEl = document.getElementById("team");
const newChatBtn = document.getElementById("new-chat");
const sidebarToggle = document.getElementById("sidebar-toggle");
const showToolsInput = document.getElementById("show-tools");
const toolsPanel = document.getElementById("tools-panel");
const toolsPanelWrap = document.getElementById("tools-panel-wrap");
const toolsSettingsToggle = document.getElementById("tools-settings-toggle");
const themeToggle = document.getElementById("theme-toggle");
const tabChat = document.getElementById("tab-chat");
const tabCalendar = document.getElementById("tab-calendar");
const tabHistory = document.getElementById("tab-history");
const chatView = document.getElementById("chat-view");
const calendarView = document.getElementById("calendar-view");
const historyView = document.getElementById("history-view");
const historyList = document.getElementById("history-list");
const historyRefresh = document.getElementById("history-refresh");
const calendarPrev = document.getElementById("calendar-prev");
const calendarNext = document.getElementById("calendar-next");
const calendarToday = document.getElementById("calendar-today");
const calendarLabel = document.getElementById("calendar-label");
const calendarLegend = document.getElementById("calendar-legend");
const calendarGrid = document.getElementById("calendar-grid");
const calendarDetail = document.getElementById("calendar-day-detail");
const calendarDetailTitle = document.getElementById("calendar-detail-title");
const calendarDetailList = document.getElementById("calendar-detail-list");
const calendarDetailClose = document.getElementById("calendar-detail-close");

const SHOW_TOOLS_KEY = "le-bras:show-tools";
let showTools = localStorage.getItem(SHOW_TOOLS_KEY) === "1";
showToolsInput.checked = showTools;

// Chaque tour garde sa trace en mémoire pour pouvoir l'afficher/masquer
// rétroactivement quand on bascule le réglage, sans redemander au back.
const turnTraces = new Map();

const STATUS_LABELS = {
  PROPOSEE: "Proposée",
  APPROUVEE: "Approuvée",
  EXECUTEE: "Exécutée",
  REFUSEE: "Refusée",
  BLOQUEE: "Bloquée",
};

const TOOL_LABELS = {
  create_calendar_event: { icon: "📅", label: "Nouvel événement" },
  send_email: { icon: "✉️", label: "Email" },
  register_employee: { icon: "👤", label: "Nouvel employé" },
  delete_employee: { icon: "🗑️", label: "Suppression employé" },
  delete_calendar_event: { icon: "🗑️", label: "Suppression événement" },
};

const DATE_FMT = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric" });
const TIME_FMT = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" });

function formatDate(isoDate) {
  if (!isoDate) return "—";
  const d = new Date(isoDate);
  return Number.isNaN(d.getTime()) ? isoDate : DATE_FMT.format(d);
}

function formatDateRange(startIso, endIso) {
  if (!startIso) return "—";
  const start = new Date(startIso);
  if (Number.isNaN(start.getTime())) return startIso;
  const startText = `${DATE_FMT.format(start)} à ${TIME_FMT.format(start)}`;
  if (!endIso) return startText;
  const end = new Date(endIso);
  if (Number.isNaN(end.getTime())) return startText;
  return `${startText} → ${TIME_FMT.format(end)}`;
}

// Réutilise la Map "employeeNames" (id -> nom) alimentée par
// renderCalendarLegend() côté calendrier — un seul annuaire côté front.
function employeeName(id) {
  return employeeNames.get(id) || id;
}

function namesOf(ids) {
  if (!ids || ids.length === 0) return "—";
  return ids.map(employeeName).join(", ");
}

// Best-effort : calendarEvents n'est peuplé qu'après un passage par l'onglet
// Calendrier. Si l'event_id n'y est pas (pas encore chargé, ou déjà
// supprimé), on retombe sur l'id brut plutôt que de planter l'affichage.
function eventById(id) {
  return calendarEvents.find((ev) => String(ev.id) === String(id));
}

// Traduit les args techniques d'une action en résumé lisible pour un RH —
// plus de JSON brut dans la carte de validation. Filet de sécurité pour un
// outil non reconnu : on affiche quand même ses args plutôt que rien.
function describeAction(action) {
  const meta = TOOL_LABELS[action.tool] || { icon: "⚙️", label: action.tool };
  const args = action.args || {};
  const lines = [];

  if (action.tool === "create_calendar_event") {
    lines.push({ label: "Titre", value: args.title || "—" });
    lines.push({ label: "Quand", value: formatDateRange(args.start, args.end) });
    lines.push({ label: "Avec", value: namesOf(args.employee_ids) });
    if (args.description) lines.push({ label: "Détails", value: args.description });
  } else if (action.tool === "send_email") {
    lines.push({ label: "Objet", value: args.subject || "—" });
    lines.push({ label: "À", value: namesOf(args.employee_ids) });
    if (args.body) {
      lines.push({ label: "Message", value: args.body.length > 160 ? `${args.body.slice(0, 160)}…` : args.body });
    }
  } else if (action.tool === "register_employee") {
    lines.push({ label: "Nom", value: args.name || "—" });
    lines.push({ label: "Poste", value: [args.role, args.department].filter(Boolean).join(" · ") || "—" });
    lines.push({ label: "Manager", value: args.manager_id ? employeeName(args.manager_id) : "Aucun" });
    lines.push({ label: "Arrivée", value: formatDate(args.start_date) });
  } else if (action.tool === "delete_employee") {
    lines.push({ label: "Employé", value: employeeName(args.employee_id) });
    lines.push({ label: "Conséquence", value: "Supprime aussi tous ses événements de calendrier." });
  } else if (action.tool === "delete_calendar_event") {
    const event = eventById(args.event_id);
    lines.push({ label: "Événement", value: event ? event.title : `#${args.event_id}` });
    if (event) {
      lines.push({ label: "Quand", value: formatDateRange(event.start, event.end) });
      lines.push({ label: "Employé", value: event.employee_name || employeeName(event.employee_id) });
    }
  } else {
    lines.push({ label: "Détails", value: JSON.stringify(args) });
  }

  return { meta, lines };
}

// La conversation elle-même est persistée côté serveur (SQLite, voir
// backend/conversations.py) : ici on ne garde qu'un pointeur vers laquelle
// est "en cours", pas son contenu. localStorage plutôt que "la plus récente
// en base" : sinon "Nouvelle conversation" + F5 rouvrirait l'ancienne, rien
// de plus récent n'ayant encore été créé côté serveur à ce moment-là.
const CONVERSATION_KEY = "le-bras:conversation-id";
let conversationId = Number(localStorage.getItem(CONVERSATION_KEY)) || null;

// ---------------------------------------------------------------------------
// Calendrier fictif — voir SPEC.md (hors scope) : agenda mocké en SQLite,
// navigable sur une année complète pour visualiser les événements sans
// devoir demander à l'agent "montre-moi le calendrier".
// ---------------------------------------------------------------------------

const CALENDAR_PALETTE = [
  "#2563eb", "#db2777", "#16a34a", "#d97706",
  "#7c3aed", "#0891b2", "#dc2626", "#4d7c0f",
];
const WEEKDAY_LABELS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
const MONTH_LABELS = [
  "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
];
const DAY_LABELS_LONG = [
  "Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi",
];

const CALENDAR_MONTH_KEY = "le-bras:calendar-month";

let calendarEvents = [];
let employeeColors = new Map();
let employeeNames = new Map();
let calendarMonth = new Date();
let hiddenEmployees = new Set();
let selectedDayKey = null;

// Date -> "AAAA-MM-JJ" en heure locale. Ne JAMAIS utiliser toISOString()
// ici : ça convertit en UTC et décale la date d'un jour dans les fuseaux
// derrière UTC (ex. minuit local le 1er devient 31 la veille en UTC).
function toDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function colorForEmployee(employeeId) {
  if (!employeeColors.has(employeeId)) {
    employeeColors.set(employeeId, CALENDAR_PALETTE[employeeColors.size % CALENDAR_PALETTE.length]);
  }
  return employeeColors.get(employeeId);
}

function renderCalendarLegend(employees) {
  calendarLegend.innerHTML = "";
  for (const emp of employees) {
    employeeNames.set(emp.id, emp.name);

    const item = document.createElement("button");
    item.type = "button";
    item.className = "calendar__legend-item";
    item.title = `Afficher/masquer les événements de ${emp.name}`;
    const dot = document.createElement("span");
    dot.className = "calendar__legend-dot";
    dot.style.background = colorForEmployee(emp.id);
    item.appendChild(dot);
    item.append(emp.name);

    item.addEventListener("click", () => {
      if (hiddenEmployees.has(emp.id)) hiddenEmployees.delete(emp.id);
      else hiddenEmployees.add(emp.id);
      item.classList.toggle("calendar__legend-item--off", hiddenEmployees.has(emp.id));
      renderCalendarGrid();
      if (selectedDayKey) openDayDetail(selectedDayKey);
    });

    calendarLegend.appendChild(item);
  }
}

function eventsForDay(key) {
  return calendarEvents
    .filter((event) => event.start.slice(0, 10) === key && !hiddenEmployees.has(event.employee_id))
    .sort((a, b) => a.start.localeCompare(b.start));
}

function openDayDetail(key) {
  selectedDayKey = key;
  const [year, month, day] = key.split("-").map(Number);
  const date = new Date(year, month - 1, day);

  calendarDetailTitle.textContent = `${DAY_LABELS_LONG[date.getDay()]} ${date.getDate()} ${MONTH_LABELS[date.getMonth()].toLowerCase()} ${year}`;
  calendarDetailList.innerHTML = "";

  const dayEvents = eventsForDay(key);
  if (dayEvents.length === 0) {
    calendarDetailList.innerHTML = `<p class="calendar__detail-empty">Aucun événement ce jour-là.</p>`;
  } else {
    for (const event of dayEvents) {
      const item = document.createElement("div");
      item.className = "calendar__detail-item";

      const dot = document.createElement("span");
      dot.className = "calendar__detail-dot";
      dot.style.background = colorForEmployee(event.employee_id);
      item.appendChild(dot);

      const time = document.createElement("span");
      time.className = "calendar__detail-time";
      time.textContent = `${event.start.slice(11, 16)}–${event.end.slice(11, 16)}`;
      item.appendChild(time);

      const body = document.createElement("div");
      body.className = "calendar__detail-body";
      body.innerHTML = `
        <div class="calendar__detail-name">${event.employee_name}</div>
        <div class="calendar__detail-title">${event.title}</div>
      `;
      item.appendChild(body);

      calendarDetailList.appendChild(item);
    }
  }

  calendarDetail.hidden = false;
  for (const cell of calendarGrid.querySelectorAll(".calendar__day")) {
    cell.classList.toggle("calendar__day--selected", cell.dataset.key === key);
  }
}

function closeDayDetail() {
  selectedDayKey = null;
  calendarDetail.hidden = true;
  for (const cell of calendarGrid.querySelectorAll(".calendar__day--selected")) {
    cell.classList.remove("calendar__day--selected");
  }
}

function renderCalendarGrid() {
  const year = calendarMonth.getFullYear();
  const month = calendarMonth.getMonth();
  calendarLabel.textContent = `${MONTH_LABELS[month]} ${year}`;
  localStorage.setItem(CALENDAR_MONTH_KEY, `${year}-${String(month + 1).padStart(2, "0")}`);

  const firstOfMonth = new Date(year, month, 1);
  const startOffset = (firstOfMonth.getDay() + 6) % 7; // grille du lundi
  const gridStart = new Date(year, month, 1 - startOffset);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const totalCells = Math.ceil((startOffset + daysInMonth) / 7) * 7;

  const todayKey = toDateKey(new Date());

  calendarGrid.innerHTML = "";
  for (const label of WEEKDAY_LABELS) {
    const cell = document.createElement("div");
    cell.className = "calendar__weekday";
    cell.textContent = label;
    calendarGrid.appendChild(cell);
  }

  for (let i = 0; i < totalCells; i++) {
    const date = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + i);
    const key = toDateKey(date);
    const outside = date.getMonth() !== month;
    const weekend = date.getDay() === 0 || date.getDay() === 6;

    const cell = document.createElement("div");
    cell.className = "calendar__day";
    cell.dataset.key = key;
    if (outside) cell.classList.add("calendar__day--outside");
    if (weekend) cell.classList.add("calendar__day--weekend");
    if (key === todayKey) cell.classList.add("calendar__day--today");
    if (key === selectedDayKey) cell.classList.add("calendar__day--selected");
    cell.addEventListener("click", () => openDayDetail(key));

    const number = document.createElement("span");
    number.className = "calendar__day-number";
    number.textContent = date.getDate();
    cell.appendChild(number);

    const dayEvents = eventsForDay(key);
    const visible = dayEvents.slice(0, 3);
    for (const event of visible) {
      const chip = document.createElement("span");
      chip.className = "calendar__event";
      chip.style.background = colorForEmployee(event.employee_id);
      const time = event.start.slice(11, 16);
      chip.title = `${event.employee_name} · ${time} · ${event.title}`;
      chip.textContent = `${time} ${event.title}`;
      cell.appendChild(chip);
    }
    if (dayEvents.length > visible.length) {
      const more = document.createElement("span");
      more.className = "calendar__more";
      more.textContent = `+${dayEvents.length - visible.length} de plus`;
      cell.appendChild(more);
    }

    calendarGrid.appendChild(cell);
  }
}

async function loadCalendar() {
  try {
    const res = await fetch("/calendar");
    if (!res.ok) throw new Error(`Erreur ${res.status}`);
    calendarEvents = await res.json();

    const savedMonth = localStorage.getItem(CALENDAR_MONTH_KEY);
    if (savedMonth) {
      const [year, month] = savedMonth.split("-").map(Number);
      calendarMonth = new Date(year, month - 1, 1);
    } else if (calendarEvents.length > 0) {
      calendarMonth = new Date(calendarEvents[0].start.slice(0, 10));
    }
    renderCalendarGrid();
  } catch (err) {
    calendarGrid.innerHTML = `<p class="calendar__empty">Calendrier indisponible.</p>`;
  }
}

const HISTORY_STATUS_LABELS = {
  PROPOSEE: "Proposée",
  APPROUVEE: "Approuvée",
  EXECUTEE: "Exécutée",
  REFUSEE: "Refusée",
  BLOQUEE: "Bloquée",
};

async function loadHistory() {
  historyList.innerHTML = `
    <div class="skeleton skeleton--card"></div>
    <div class="skeleton skeleton--card"></div>
    <div class="skeleton skeleton--card"></div>
  `;
  try {
    const res = await fetch("/actions");
    if (!res.ok) throw new Error(`Erreur ${res.status}`);
    const items = await res.json();

    if (items.length === 0) {
      historyList.innerHTML = `<p class="calendar__empty">Aucune action proposée pour l'instant.</p>`;
      return;
    }

    historyList.innerHTML = "";
    for (const item of items) {
      const statusKey = (item.status || "").toLowerCase();
      const card = document.createElement("div");
      card.className = `history__item history__item--${statusKey}`;

      const head = document.createElement("div");
      head.className = "history__head";

      const { meta: toolMeta, lines } = describeAction(item);

      const tool = document.createElement("span");
      tool.className = "history__tool";
      tool.textContent = `#${item.id} · ${toolMeta.icon} ${toolMeta.label}`;
      head.appendChild(tool);

      const status = document.createElement("span");
      status.className = `status status--${statusKey}`;
      status.textContent = HISTORY_STATUS_LABELS[item.status] || item.status;
      head.appendChild(status);

      card.appendChild(head);

      if (item.reason) {
        const reason = document.createElement("p");
        reason.className = "history__reason";
        reason.textContent = item.reason;
        card.appendChild(reason);
      }

      if (item.executed_at) {
        const meta = document.createElement("p");
        meta.className = "history__meta";
        meta.textContent = `Exécutée le ${formatDateRange(item.executed_at)}`;
        card.appendChild(meta);
      }

      const summary = document.createElement("dl");
      summary.className = "action__summary";
      for (const { label, value } of lines) {
        const dt = document.createElement("dt");
        dt.textContent = label;
        const dd = document.createElement("dd");
        dd.textContent = value;
        summary.appendChild(dt);
        summary.appendChild(dd);
      }
      card.appendChild(summary);

      historyList.appendChild(card);
    }
  } catch (err) {
    historyList.innerHTML = `<p class="calendar__empty">Historique indisponible.</p>`;
  }
}

function switchView(view) {
  chatView.hidden = view !== "chat";
  calendarView.hidden = view !== "calendar";
  historyView.hidden = view !== "history";
  tabChat.setAttribute("aria-selected", String(view === "chat"));
  tabCalendar.setAttribute("aria-selected", String(view === "calendar"));
  tabHistory.setAttribute("aria-selected", String(view === "history"));
  if (view === "history") loadHistory();
}

function renderEmptyState() {
  thread.innerHTML = "";
  const empty = document.createElement("div");
  empty.className = "thread__empty";
  empty.innerHTML = `
    <svg class="thread__empty-logo" viewBox="0 0 600 100" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Tauturu">
      <text x="300" y="62" text-anchor="middle" font-family="-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif" font-weight="600" font-size="34" letter-spacing="8" fill="currentColor">TAU<tspan fill="#2563eb">TURU</tspan><tspan fill="#2563eb" letter-spacing="0">.</tspan></text>
    </svg>
    <p class="thread__empty-title">Bienvenue</p>
  `;
  thread.appendChild(empty);
  // Composeur centré à l'écran tant qu'aucun message n'a été envoyé (comme
  // une page d'accueil) ; redescend en bas dès le premier message, voir
  // sendMessage().
  chatView.classList.add("chat-view--empty");
}

function addUserBubble(text) {
  const turn = document.createElement("div");
  turn.className = "turn";
  const bubble = document.createElement("div");
  bubble.className = "bubble bubble--user";
  bubble.textContent = text;
  turn.appendChild(bubble);
  thread.appendChild(turn);
  thread.scrollTop = thread.scrollHeight;
  return turn;
}

function addPendingBubble() {
  const bubble = document.createElement("div");
  bubble.className = "bubble bubble--agent bubble--pending";
  bubble.innerHTML = `<span class="typing"><span></span><span></span><span></span></span>`;
  return bubble;
}

function renderPlan(plan) {
  if (!plan || plan.length === 0) return null;

  const container = document.createElement("div");
  container.className = "plan";

  for (const action of plan) {
    const statusKey = (action.status || "").toLowerCase();
    const card = document.createElement("div");
    card.className = `action action--${statusKey}`;
    card.dataset.actionId = action.id;

    const head = document.createElement("div");
    head.className = "action__head";

    const { meta, lines } = describeAction(action);

    const tool = document.createElement("span");
    tool.className = "action__tool";
    tool.textContent = `${meta.icon} ${meta.label}`;
    head.appendChild(tool);

    const status = document.createElement("span");
    status.className = `status status--${statusKey}`;
    status.textContent = STATUS_LABELS[action.status] || action.status;
    head.appendChild(status);

    card.appendChild(head);

    if (action.reason) {
      const reason = document.createElement("p");
      reason.className = "action__reason";
      reason.textContent = action.reason;
      card.appendChild(reason);
    }

    const summary = document.createElement("dl");
    summary.className = "action__summary";
    for (const { label, value } of lines) {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = value;
      summary.appendChild(dt);
      summary.appendChild(dd);
    }
    card.appendChild(summary);

    if (action.status === "PROPOSEE") {
      const controls = document.createElement("div");
      controls.className = "action__controls";

      const approveBtn = document.createElement("button");
      approveBtn.type = "button";
      approveBtn.className = "action__btn action__btn--approve";
      approveBtn.textContent = "Approuver";
      approveBtn.addEventListener("click", () => decideAction(action, "approve", card, status));

      const rejectBtn = document.createElement("button");
      rejectBtn.type = "button";
      rejectBtn.className = "action__btn action__btn--reject";
      rejectBtn.textContent = "Refuser";
      rejectBtn.addEventListener("click", () => decideAction(action, "reject", card, status));

      controls.appendChild(approveBtn);
      controls.appendChild(rejectBtn);
      card.appendChild(controls);
    }

    container.appendChild(card);
  }

  return container;
}

// Approuver déclenche l'exécution réelle (idempotente) de l'action via
// l'exécuteur ; refuser bloque en cascade tout ce qui en dépendait.
async function decideAction(action, decision, card, statusEl) {
  const controls = card.querySelector(".action__controls");
  const buttons = controls ? controls.querySelectorAll("button") : [];
  for (const btn of buttons) btn.disabled = true;

  try {
    const res = await fetch(`/actions/${action.id}/${decision}`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `Erreur ${res.status}`);

    const newStatusKey = data.status.toLowerCase();
    statusEl.className = `status status--${newStatusKey}`;
    statusEl.textContent = STATUS_LABELS[data.status] || data.status;
    card.className = `action action--${newStatusKey}`;

    const confirmation = document.createElement("p");
    confirmation.className =
      data.status === "REFUSEE" ? "action__confirmation action__confirmation--reject" : "action__confirmation";
    confirmation.textContent = data.message;
    card.appendChild(confirmation);

    if (controls) controls.remove();

    if (data.status === "EXECUTEE" && action.tool === "create_calendar_event") {
      await loadCalendar();
      if (action.args && action.args.start) {
        calendarMonth = new Date(action.args.start.slice(0, 10));
        closeDayDetail();
        renderCalendarGrid();
      }
    }

    if (data.status === "EXECUTEE" && action.tool === "delete_calendar_event") {
      await loadCalendar();
      closeDayDetail();
      renderCalendarGrid();
    }

    if (data.status === "EXECUTEE" && action.tool === "delete_employee") {
      await Promise.all([loadTeam(), loadCalendar()]);
      closeDayDetail();
      renderCalendarGrid();
    }
  } catch (err) {
    const error = document.createElement("p");
    error.className = "action__confirmation action__confirmation--reject";
    error.textContent = `Erreur : ${err.message}`;
    card.appendChild(error);
    for (const btn of buttons) btn.disabled = false;
  }
}

// La séquence d'outils appelés reste disponible pour l'oral ("montrez-moi la
// trace") mais n'apparaît nulle part tant que le réglage "Afficher les
// outils utilisés" n'est pas activé (voir applyToolsVisibility).
function renderTrace(trace) {
  if (!trace || trace.length === 0) return null;

  const details = document.createElement("details");
  details.className = "trace";

  const summary = document.createElement("summary");
  const failures = trace.filter((call) => !call.ok).length;
  summary.textContent = failures
    ? `Détails des appels d'outils (${trace.length}, ${failures} en échec)`
    : `Détails des appels d'outils (${trace.length})`;
  details.appendChild(summary);

  for (const call of trace) {
    const row = document.createElement("div");
    row.className = "trace__row";

    const head = document.createElement("div");
    head.className = "trace__head";

    const tool = document.createElement("span");
    tool.className = "trace__tool";
    tool.textContent = call.tool;
    head.appendChild(tool);

    const status = document.createElement("span");
    status.className = `trace__status ${call.ok ? "trace__status--ok" : "trace__status--error"}`;
    status.textContent = call.ok ? "OK" : "Échec";
    head.appendChild(status);

    const duration = document.createElement("span");
    duration.className = "trace__duration";
    duration.textContent = `${call.duration_ms} ms`;
    head.appendChild(duration);

    row.appendChild(head);

    if (call.args) {
      const args = document.createElement("pre");
      args.className = "trace__args";
      args.textContent = JSON.stringify(call.args);
      row.appendChild(args);
    }

    if (!call.ok && call.error) {
      const error = document.createElement("p");
      error.className = "trace__error";
      error.textContent = call.error;
      row.appendChild(error);
    }

    details.appendChild(row);
  }

  return details;
}

// Tokens / coût / latence : toujours visible (carte bonus "coût affiché"),
// contrairement à la trace détaillée qui reste repliée.
function renderUsage(usage) {
  if (!usage || !usage.total_tokens) return null;

  const parts = [`${usage.total_tokens} tokens`, `${usage.total_duration_ms} ms`];
  if (usage.total_cost_usd !== null && usage.total_cost_usd !== undefined) {
    parts.push(`$${usage.total_cost_usd.toFixed(6)}`);
  }

  const p = document.createElement("p");
  p.className = "usage";
  p.textContent = parts.join(" · ");
  return p;
}

function applyToolsVisibility(turn) {
  const existing = turn.querySelector(".trace");
  if (existing) existing.remove();

  if (!showTools) return;

  const trace = turnTraces.get(turn);
  const traceEl = renderTrace(trace);
  if (traceEl) turn.appendChild(traceEl);
}

async function sendMessage(message) {
  if (thread.querySelector(".thread__empty")) {
    thread.innerHTML = "";
    chatView.classList.remove("chat-view--empty");
  }

  const turn = addUserBubble(message);
  const pending = addPendingBubble();
  turn.appendChild(pending);
  thread.scrollTop = thread.scrollHeight;

  submit.disabled = true;
  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, conversation_id: conversationId }),
    });

    if (!res.ok) {
      throw new Error(`Erreur ${res.status}`);
    }

    const data = await res.json();
    conversationId = data.conversation_id;
    localStorage.setItem(CONVERSATION_KEY, String(conversationId));

    pending.className = "bubble bubble--agent";
    pending.textContent = data.message || "(pas de réponse)";

    const planEl = renderPlan(data.plan);
    if (planEl) turn.appendChild(planEl);

    const usageEl = renderUsage(data.usage);
    if (usageEl) turn.appendChild(usageEl);

    turnTraces.set(turn, data.trace);
    applyToolsVisibility(turn);
  } catch (err) {
    pending.className = "bubble bubble--error";
    pending.textContent = `Une erreur est survenue : ${err.message}`;
  } finally {
    submit.disabled = false;
    thread.scrollTop = thread.scrollHeight;
  }
}

function resetConversation() {
  conversationId = null;
  localStorage.removeItem(CONVERSATION_KEY);
  turnTraces.clear();
  renderEmptyState();
  input.value = "";
  input.style.height = "auto";
  input.focus();
}

// "get_employee_availability" est trop long pour la largeur du popover et
// déborde sans retour à la ligne naturel (nom en un seul mot, monospace) :
// on force la coupure après le 2e "_" plutôt que de laisser le switch
// se faire pousser hors du panneau.
function displayToolName(name) {
  if (name === "get_employee_availability") return "get_employee_<br>availability";
  return name;
}

// Débrancher un outil en direct (démo palier 3 : "je débranche un outil et
// je relance la même requête") sans toucher au code ni redémarrer le
// serveur — l'agent renvoie alors un message d'erreur clair au lieu de
// planter ou d'inventer un résultat.
async function loadTools() {
  try {
    const res = await fetch("/tools");
    if (!res.ok) throw new Error(`Erreur ${res.status}`);
    const items = await res.json();

    toolsPanel.innerHTML = "";
    for (const item of items) {
      const label = document.createElement("label");
      label.className = `toggle ${item.enabled ? "" : "toggle--off"}`;

      const text = document.createElement("span");
      text.className = "toggle__label";
      text.innerHTML = `
        ${displayToolName(item.name)}
        <span class="toggle__hint">${item.enabled ? "Disponible" : "Indisponible (désactivé)"}</span>
      `;
      label.appendChild(text);

      const input = document.createElement("input");
      input.type = "checkbox";
      input.className = "toggle__input";
      input.checked = item.enabled;
      label.appendChild(input);

      const switchEl = document.createElement("span");
      switchEl.className = "toggle__switch";
      label.appendChild(switchEl);

      input.addEventListener("change", async () => {
        // On envoie l'état voulu explicitement (enable/disable), jamais un
        // simple "toggle" : si le serveur a redémarré entre-temps, un
        // toggle aveugle peut partir dans le mauvais sens par rapport à ce
        // que le navigateur affiche encore.
        const desired = input.checked;
        input.disabled = true;
        try {
          const res = await fetch(`/tools/${item.name}/${desired ? "enable" : "disable"}`, { method: "POST" });
          if (!res.ok) throw new Error(`Erreur ${res.status}`);
          const updated = await res.json();
          input.checked = updated.enabled;
          label.classList.toggle("toggle--off", !updated.enabled);
          text.querySelector(".toggle__hint").textContent = updated.enabled
            ? "Disponible"
            : "Indisponible (désactivé)";
        } catch (err) {
          input.checked = !desired;
        } finally {
          input.disabled = false;
        }
      });

      toolsPanel.appendChild(label);
    }
  } catch (err) {
    toolsPanel.innerHTML = `<p class="team__loading">Outils indisponibles.</p>`;
  }
}

async function loadTeam() {
  try {
    const res = await fetch("/employees");
    if (!res.ok) throw new Error(`Erreur ${res.status}`);
    const employees = await res.json();

    const groups = new Map();
    for (const emp of employees) {
      if (!groups.has(emp.department)) groups.set(emp.department, []);
      groups.get(emp.department).push(emp);
    }

    teamEl.innerHTML = "";
    for (const [department, members] of groups) {
      const group = document.createElement("div");
      group.className = "team__group";

      const heading = document.createElement("h3");
      heading.className = "team__department";
      heading.textContent = department;
      const count = document.createElement("span");
      count.className = "team__count";
      count.textContent = members.length;
      heading.appendChild(count);
      group.appendChild(heading);

      for (const emp of members) {
        const member = document.createElement("button");
        member.type = "button";
        member.className = "team__member";
        member.title = `Insérer "${emp.id}" dans le message`;
        member.innerHTML = `
          <span class="team__avatar">${emp.name.trim()[0] || "?"}</span>
          <span class="team__info">
            <span class="team__name">${emp.name}</span>
            <span class="team__role">${emp.role}</span>
          </span>
        `;
        member.addEventListener("click", () => {
          const sep = input.value && !input.value.endsWith(" ") ? " " : "";
          input.value += `${sep}${emp.id}`;
          input.focus();
        });
        group.appendChild(member);
      }

      teamEl.appendChild(group);
    }

    renderCalendarLegend(employees);
  } catch (err) {
    teamEl.innerHTML = `<p class="team__loading">Équipe indisponible.</p>`;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  input.style.height = "auto";
  sendMessage(message);
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
});

newChatBtn.addEventListener("click", resetConversation);

// Thème clair/sombre : suit prefers-color-scheme par défaut (voir
// style.css), sauf si l'utilisateur a explicitement choisi via ce bouton
// — mémorisé en localStorage, appliqué avant le premier rendu (script
// inline dans <head>) pour éviter un flash du mauvais thème.
const THEME_KEY = "le-bras:theme";

function currentTheme() {
  const explicit = document.documentElement.getAttribute("data-theme");
  if (explicit) return explicit;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// L'icône affichée est celle du thème vers lequel on bascule si on clique
// (convention usuelle) : soleil visible en mode sombre (clic -> clair),
// lune visible en mode clair (clic -> sombre).
const themeIconSun = document.getElementById("theme-icon-sun");
const themeIconMoon = document.getElementById("theme-icon-moon");

function updateThemeIcon() {
  // Ne pas utiliser .hidden ici : l'attribut HTML "hidden" ne s'applique pas
  // de façon fiable aux <svg> (namespace différent du HTML) dans certains
  // navigateurs — display piloté directement à la place.
  const isDark = currentTheme() === "dark";
  themeIconSun.style.display = isDark ? "" : "none";
  themeIconMoon.style.display = isDark ? "none" : "";
}

themeToggle.addEventListener("click", () => {
  const next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem(THEME_KEY, next);
  updateThemeIcon();
});

// Le thème peut aussi changer sans clic (préférence système modifiée pendant
// que la page est ouverte) si l'utilisateur n'a rien choisi explicitement.
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (!document.documentElement.getAttribute("data-theme")) updateThemeIcon();
});

updateThemeIcon();

function closeToolsPanel() {
  toolsSettingsToggle.setAttribute("aria-expanded", "false");
  toolsPanelWrap.hidden = true;
}

toolsSettingsToggle.addEventListener("click", (event) => {
  event.stopPropagation();
  const expanded = toolsSettingsToggle.getAttribute("aria-expanded") === "true";
  toolsSettingsToggle.setAttribute("aria-expanded", String(!expanded));
  toolsPanelWrap.hidden = expanded;
  if (!expanded) loadTools(); // resynchronise avec le serveur à chaque ouverture
});

// Popover flottant au-dessus de l'icône engrenage : se ferme au clic
// ailleurs, comme n'importe quel menu.
document.addEventListener("click", (event) => {
  if (toolsPanelWrap.hidden) return;
  if (toolsPanelWrap.contains(event.target) || toolsSettingsToggle.contains(event.target)) return;
  closeToolsPanel();
});

showToolsInput.addEventListener("change", () => {
  showTools = showToolsInput.checked;
  localStorage.setItem(SHOW_TOOLS_KEY, showTools ? "1" : "0");
  for (const turn of turnTraces.keys()) applyToolsVisibility(turn);
});

const appEl = document.querySelector(".app");

sidebarToggle.addEventListener("click", () => {
  const open = appEl.classList.toggle("app--sidebar-open");
  sidebarToggle.setAttribute("aria-expanded", String(open));
  sidebarToggle.setAttribute("aria-label", open ? "Masquer l'équipe" : "Afficher l'équipe");
});

document.addEventListener("click", (event) => {
  if (!appEl.classList.contains("app--sidebar-open")) return;
  if (event.target.closest(".sidebar") || event.target.closest("#sidebar-toggle")) return;
  appEl.classList.remove("app--sidebar-open");
});

tabChat.addEventListener("click", () => switchView("chat"));
tabCalendar.addEventListener("click", () => switchView("calendar"));
tabHistory.addEventListener("click", () => switchView("history"));
historyRefresh.addEventListener("click", loadHistory);

calendarPrev.addEventListener("click", () => {
  calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() - 1, 1);
  closeDayDetail();
  renderCalendarGrid();
});

calendarNext.addEventListener("click", () => {
  calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 1);
  closeDayDetail();
  renderCalendarGrid();
});

calendarToday.addEventListener("click", () => {
  calendarMonth = new Date();
  closeDayDetail();
  renderCalendarGrid();
});

calendarDetailClose.addEventListener("click", closeDayDetail);

// Palier 4 — persistance : la conversation entière (pas seulement les
// actions en attente) survit à un rechargement de page, via SQLite côté
// serveur (backend/conversations.py). Le statut de chaque action citée dans
// un message est relu en direct depuis /actions plutôt que figé au moment
// de l'envoi : une action approuvée entre-temps (autre onglet, etc.)
// réapparaît avec son vrai statut, pas l'ancien.
async function restoreConversation() {
  if (!conversationId) {
    renderEmptyState();
    return;
  }

  try {
    const [convRes, actionsRes] = await Promise.all([
      fetch(`/conversations/${conversationId}`),
      fetch("/actions"),
    ]);
    if (!convRes.ok) {
      // conversation_id périmé (ex: base réinitialisée) : on oublie le pointeur.
      localStorage.removeItem(CONVERSATION_KEY);
      throw new Error(`Erreur ${convRes.status}`);
    }
    const conversation = await convRes.json();
    const allActions = actionsRes.ok ? await actionsRes.json() : [];
    const actionsById = new Map(allActions.map((a) => [a.id, a]));

    if (conversation.messages.length === 0) {
      renderEmptyState();
      return;
    }

    conversationId = conversation.conversation_id;
    thread.innerHTML = "";
    chatView.classList.remove("chat-view--empty");

    const messages = conversation.messages;
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i];
      if (msg.role !== "user") continue; // on avance par paire user -> assistant
      const next = messages[i + 1];

      const turn = addUserBubble(msg.content);

      if (next && next.role === "assistant") {
        const bubble = document.createElement("div");
        bubble.className = "bubble bubble--agent";
        bubble.textContent = next.content || "(pas de réponse)";
        turn.appendChild(bubble);

        const plan = (next.action_ids || []).map((id) => actionsById.get(id)).filter(Boolean);
        const planEl = renderPlan(plan);
        if (planEl) turn.appendChild(planEl);

        const usageEl = renderUsage(next.usage);
        if (usageEl) turn.appendChild(usageEl);

        turnTraces.set(turn, next.trace || []);
        applyToolsVisibility(turn);

        i++; // message assistant déjà consommé
      }
    }

    thread.scrollTop = thread.scrollHeight;
  } catch (err) {
    renderEmptyState();
  }
}

restoreConversation();
loadTeam();
loadCalendar();
loadTools();
