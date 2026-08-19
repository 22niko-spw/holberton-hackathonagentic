const thread = document.getElementById("thread");
const form = document.getElementById("composer");
const input = document.getElementById("message");
const submit = document.getElementById("submit");

const STATUS_LABELS = {
  PROPOSEE: "Proposée",
  APPROUVEE: "Approuvée",
  REFUSEE: "Refusée",
  BLOQUEE: "Bloquée",
};

function renderEmptyState() {
  const empty = document.createElement("p");
  empty.className = "thread__empty";
  empty.textContent = "Décris ce que tu veux faire, l'agent proposera un plan à valider.";
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
  bubble.textContent = "Le Bras réfléchit…";
  return bubble;
}

function renderPlan(plan) {
  if (!plan || plan.length === 0) return null;

  const container = document.createElement("div");
  container.className = "plan";

  for (const action of plan) {
    const card = document.createElement("div");
    card.className = "action";

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

    container.appendChild(card);
  }

  return container;
}

function renderTrace(trace) {
  if (!trace || trace.length === 0) return null;

  const details = document.createElement("details");
  details.className = "trace";

  const summary = document.createElement("summary");
  const failures = trace.filter((call) => !call.ok).length;
  summary.textContent = failures
    ? `Trace d'exécution (${trace.length} appel${trace.length > 1 ? "s" : ""}, ${failures} en échec)`
    : `Trace d'exécution (${trace.length} appel${trace.length > 1 ? "s" : ""})`;
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

async function sendMessage(message) {
  const turn = addUserBubble(message);
  const pending = addPendingBubble();
  turn.appendChild(pending);
  thread.scrollTop = thread.scrollHeight;

  submit.disabled = true;
  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    if (!res.ok) {
      throw new Error(`Erreur ${res.status}`);
    }

    const data = await res.json();

    pending.className = "bubble bubble--agent";
    pending.textContent = data.message || "(pas de réponse)";

    const planEl = renderPlan(data.plan);
    if (planEl) turn.appendChild(planEl);

    const traceEl = renderTrace(data.trace);
    if (traceEl) turn.appendChild(traceEl);
  } catch (err) {
    pending.className = "bubble bubble--error";
    pending.textContent = `Une erreur est survenue : ${err.message}`;
  } finally {
    submit.disabled = false;
    thread.scrollTop = thread.scrollHeight;
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

renderEmptyState();
