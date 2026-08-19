const thread = document.getElementById("thread");
const form = document.getElementById("composer");
const input = document.getElementById("message");
const submit = document.getElementById("submit");
const teamEl = document.getElementById("team");
const newChatBtn = document.getElementById("new-chat");
const sidebarToggle = document.getElementById("sidebar-toggle");
const showToolsInput = document.getElementById("show-tools");
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
  REFUSEE: "Refusée",
  BLOQUEE: "Bloquée",
};

// Mémoire de conversation côté client : renvoyée au back à chaque tour pour
// que l'agent garde le fil (le back n'a pas d'état de session serveur).
let history = [];

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
  historyList.innerHTML = `<p class="calendar__empty">Chargement…</p>`;
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
      const card = document.createElement("div");
      card.className = "history__item";

      const head = document.createElement("div");
      head.className = "history__head";

      const tool = document.createElement("span");
      tool.className = "history__tool";
      tool.textContent = `#${item.id} · ${item.tool}`;
      head.appendChild(tool);

      const status = document.createElement("span");
      const statusKey = (item.status || "").toLowerCase();
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
        meta.textContent = `Exécutée le ${item.executed_at.replace("T", " à ")}`;
        card.appendChild(meta);
      }

      const args = document.createElement("pre");
      args.className = "history__args";
      args.textContent = JSON.stringify(item.result ? { args: item.args, result: item.result } : item.args, null, 2);
      card.appendChild(args);

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
    <img src="/static/assets/logo.png" alt="" class="thread__empty-logo" />
    <p>Décris ce que tu veux faire, l'agent proposera un plan à valider.</p>
  `;
  thread.appendChild(empty);
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
    const card = document.createElement("div");
    card.className = "action";
    card.dataset.actionId = action.id;

    const head = document.createElement("div");
    head.className = "action__head";

    const tool = document.createElement("span");
    tool.className = "action__tool";
    tool.textContent = action.tool;
    head.appendChild(tool);

    const status = document.createElement("span");
    const statusKey = (action.status || "").toLowerCase();
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

    const args = document.createElement("pre");
    args.className = "action__args";
    args.textContent = JSON.stringify(action.args, null, 2);
    card.appendChild(args);

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

    statusEl.className = `status status--${data.status.toLowerCase()}`;
    statusEl.textContent = STATUS_LABELS[data.status] || data.status;

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
  if (thread.querySelector(".thread__empty")) thread.innerHTML = "";

  const turn = addUserBubble(message);
  const pending = addPendingBubble();
  turn.appendChild(pending);
  thread.scrollTop = thread.scrollHeight;

  submit.disabled = true;
  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });

    if (!res.ok) {
      throw new Error(`Erreur ${res.status}`);
    }

    const data = await res.json();

    pending.className = "bubble bubble--agent";
    pending.textContent = data.message || "(pas de réponse)";

    const planEl = renderPlan(data.plan);
    if (planEl) turn.appendChild(planEl);

    const usageEl = renderUsage(data.usage);
    if (usageEl) turn.appendChild(usageEl);

    turnTraces.set(turn, data.trace);
    applyToolsVisibility(turn);

    history.push({ role: "user", content: message });
    history.push({ role: "assistant", content: data.message || "" });
  } catch (err) {
    pending.className = "bubble bubble--error";
    pending.textContent = `Une erreur est survenue : ${err.message}`;
  } finally {
    submit.disabled = false;
    thread.scrollTop = thread.scrollHeight;
  }
}

function resetConversation() {
  history = [];
  turnTraces.clear();
  renderEmptyState();
  input.value = "";
  input.style.height = "auto";
  input.focus();
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

showToolsInput.addEventListener("change", () => {
  showTools = showToolsInput.checked;
  localStorage.setItem(SHOW_TOOLS_KEY, showTools ? "1" : "0");
  for (const turn of turnTraces.keys()) applyToolsVisibility(turn);
});

const appEl = document.querySelector(".app");

sidebarToggle.addEventListener("click", () => {
  appEl.classList.toggle("app--sidebar-open");
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

renderEmptyState();
loadTeam();
loadCalendar();
