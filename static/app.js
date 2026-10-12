const $ = (id) => document.getElementById(id);
const form = $("form");
let lastPredictionId = null;
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
let riskChart = null;

const NUMERIC = ["age", "gender", "bmi", "systolic_bp", "diastolic_bp", "glucose",
  "cholesterol", "heart_rate", "spo2", "exercise_days"];
const CHECKS = ["smoker", "alcohol", "family_history"];

function collect() {
  const f = form.elements;
  const payload = { name: f.name.value.trim() };
  NUMERIC.forEach((k) => (payload[k] = f[k].value));
  CHECKS.forEach((k) => (payload[k] = f[k].checked ? 1 : 0));
  payload.contact = {
    name: f.c_name.value.trim(),
    phone: f.c_phone.value.trim(),
    email: f.c_email.value.trim(),
    consent: f.alert_consent.checked,
  };
  return payload;
}

function fillList(id, items) {
  const ul = $(id);
  ul.replaceChildren(...items.map((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    return li;
  }));
}

function clearErrors() {
  form.querySelectorAll(".err").forEach((e) => e.remove());
  form.querySelectorAll(".invalid").forEach((e) => e.classList.remove("invalid"));
}

function showErrors(errors) {
  Object.entries(errors).forEach(([key, msg]) => {
    const input = form.elements[key];
    if (!input) return;
    input.classList.add("invalid");
    const span = document.createElement("span");
    span.className = "err";
    span.textContent = msg;
    input.parentElement.appendChild(span);
  });
  const first = form.querySelector(".invalid");
  if (first) first.focus();
}

function describeDelivery(delivery) {
  if (delivery?.simulated) return `Simulation only — no message was sent (${delivery.simulated})`;
  return Object.entries(delivery).map(([ch, st]) => `${ch}: ${st}`).join(" | ");
}

function render(r) {
  $("empty").hidden = true;
  $("output").hidden = false;
  $("result").dataset.level = r.risk_level;
  $("level").textContent = r.risk_level;

  const ecg = document.querySelector(".ecg");
  ecg.classList.remove("draw");
  void ecg.getBoundingClientRect(); // restart the animation
  ecg.classList.add("draw");

  $("bars").replaceChildren(...Object.entries(r.probabilities).map(([name, p]) => {
    const row = document.createElement("div"); row.className = "bar";
    const label = document.createElement("span"); label.textContent = name;
    const track = document.createElement("div"); track.className = "track";
    const fill = document.createElement("div"); fill.className = "fill";
    fill.style.width = `${Math.round(p * 100)}%`;
    track.appendChild(fill);
    const pct = document.createElement("span"); pct.className = "pct";
    pct.textContent = `${Math.round(p * 100)}%`;
    row.append(label, track, pct);
    return row;
  }));

  fillList("up", r.risk_factors);
  fillList("down", r.protective_factors);
  fillList("advice", r.advice);

  const box = $("emergency");
  box.hidden = !r.emergency;
  $("alert-status").textContent = "";
  $("alert-status").style.color = "";
  if (r.emergency) {
    fillList("flags", r.red_flags.length ? r.red_flags : ["The model rates your risk as very high"]);
    $("alert-status").textContent = r.alert?.delivery
      ? "Contact alert status: " + describeDelivery(r.alert.delivery)
      : (r.alert?.message || "Add an emergency contact above to alert someone automatically.");
    box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearErrors();
  const btn = $("submit");
  btn.disabled = true; btn.textContent = "Checking...";
  try {
    const res = await fetch("/api/predict", {
      method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify(collect()),
    });
    const data = await res.json();
    if (res.status === 401) { window.location.assign("/login?next=%2F"); return; }
    if (!res.ok) {
      if (data.errors) showErrors(data.errors);
      else alert(data.error || "The assessment could not be completed. Please try again.");
      return;
    }
    lastPredictionId = data.prediction_id;
    render(data);
    loadHistory();
  } catch (err) {
    alert("Could not reach the server. Make sure the Flask app is running.");
  } finally {
    btn.disabled = false; btn.textContent = "Check my risk";
  }
});

$("sos").addEventListener("click", async () => {
  const btn = $("sos"), status = $("alert-status");
  btn.disabled = true;
  try {
    const res = await fetch("/api/alert", {
      method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify({ ...collect(), prediction_id: lastPredictionId }),
    });
    const data = await res.json();
    status.style.color = res.ok ? "" : "var(--signal)";
    status.textContent = res.ok ? "Alert result: " + describeDelivery(data.delivery) : data.error;
    if (res.ok) loadHistory();
  } catch (err) {
    status.textContent = "Could not send the alert. Call 108 or 112 directly.";
  } finally { btn.disabled = false; }
});

const SAMPLES = {
  sample: { name: "Sample User", age: 58, gender: 1, bmi: 31.4, systolic_bp: 152, diastolic_bp: 96,
    glucose: 142, cholesterol: 232, heart_rate: 88, spo2: 96, exercise_days: 1,
    c_name: "", c_phone: "", alert_consent: 0, smoker: 1, alcohol: 0, family_history: 1 },
  "sample-urgent": { name: "Sample User", age: 62, gender: 1, bmi: 29, systolic_bp: 190, diastolic_bp: 124,
    glucose: 180, cholesterol: 250, heart_rate: 118, spo2: 88, exercise_days: 0,
    c_name: "", c_phone: "", alert_consent: 0, smoker: 1, alcohol: 0, family_history: 1 },
};
Object.entries(SAMPLES).forEach(([id, v]) => {
  $(id).addEventListener("click", () => {
    Object.entries(v).forEach(([k, val]) => {
      const el = form.elements[k] || form.elements[{ c_name: "c_name", c_phone: "c_phone", c_email: "c_email" }[k]];
      if (!el) return;
      if (el.type === "checkbox") el.checked = !!val; else el.value = val;
    });
  });
});

function li(parts) { const el = document.createElement("li"); el.append(...parts); return el; }
function strong(t) { const s = document.createElement("strong"); s.textContent = t; return s; }
const stamp = (iso) => iso.replace("T", " ").slice(0, 16);

async function loadHistory() {
  try {
    const [h, a] = await Promise.all([fetch("/api/history"), fetch("/api/alerts")]);
    if (h.status === 401) return;
    const hist = await h.json(), alertsList = await a.json();
    $("hist").replaceChildren(...hist.map((r) => {
      const tag = document.createElement("span");
      tag.className = `tag ${r.risk_level}`; tag.textContent = r.risk_level;
      return li([strong(r.name || "Anonymous"), " - ", tag, r.emergency ? " (urgent)" : "", ` - ${stamp(r.created_at)}`]);
    }));
    $("alert-log").replaceChildren(...alertsList.map((r) =>
      li([strong(r.contact_name || "Contact"), ` - ${r.trigger} - ${Object.keys(r.delivery).join(", ")} - ${stamp(r.created_at)}`])));
    if (!hist.length) $("hist").textContent = "No checks yet.";
    if (!alertsList.length) $("alert-log").textContent = "No alerts yet.";
    if (window.Chart && $("riskChart")) {
      const counts = { Low: 0, Moderate: 0, High: 0 };
      hist.forEach((r) => { if (Object.hasOwn(counts, r.risk_level)) counts[r.risk_level] += 1; });
      if (riskChart) riskChart.destroy();
      riskChart = new Chart($("riskChart"), {
        type: "bar",
        data: { labels: Object.keys(counts), datasets: [{ data: Object.values(counts), backgroundColor: ["#347555", "#9c6c18", "#b83f48"], borderRadius: 3, maxBarThickness: 34 }] },
        options: { responsive: true, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.raw} screening${ctx.raw === 1 ? "" : "s"}` } } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#e9ede5" } }, x: { grid: { display: false } } } },
      });
    }
  } catch (_) { /* history is optional */ }
}
loadHistory();
