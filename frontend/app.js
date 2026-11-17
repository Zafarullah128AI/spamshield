/* SpamShield frontend: API client + views. Token lives in localStorage. */

let token = localStorage.getItem("spamshield_token") || null;
let user = null;
let currentFilter = "all";

function esc(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function api(path, method = "GET", body = null, auth = false) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(path, {
    method, headers, body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || ("Request failed (" + res.status + ")"));
  return data;
}

function showMsg(text, kind = "") {
  const el = document.getElementById("msg");
  el.textContent = text;
  el.className = "msg " + kind;
  el.style.display = "block";
  setTimeout(() => { el.style.display = "none"; }, 5000);
}

function showView(name) {
  document.querySelectorAll(".view").forEach(v => v.style.display = "none");
  document.getElementById("view-" + name).style.display = "block";
  document.querySelectorAll(".navbtn").forEach(b =>
    b.classList.toggle("active", b.dataset.view === name));
  if (name === "dashboard") loadDashboard();
  if (name === "dataset") loadDataset(currentFilter);
  if (name === "admin") loadAdmin();
}

document.querySelectorAll(".navbtn").forEach(b =>
  b.addEventListener("click", () => showView(b.dataset.view)));
document.getElementById("loginBtn").addEventListener("click", () => showView("auth"));
document.getElementById("logoutBtn").addEventListener("click", () => {
  token = null; user = null;
  localStorage.removeItem("spamshield_token");
  refreshAuthArea(); showView("check"); showMsg("Logged out.", "ok");
});

function refreshAuthArea() {
  document.getElementById("loginBtn").style.display = user ? "none" : "inline-block";
  document.getElementById("logoutBtn").style.display = user ? "inline-block" : "none";
  const chip = document.getElementById("userChip");
  chip.style.display = user ? "inline" : "none";
  chip.textContent = user ? user.name + " (" + user.role + ")" : "";
  document.getElementById("adminNav").style.display =
    user && user.role === "admin" ? "inline-block" : "none";
  document.getElementById("uploadBox").style.display =
    user && user.role === "admin" ? "block" : "none";
}

function showRegister() {
  document.getElementById("registerBox").style.display = "block";
}

async function doLogin() {
  try {
    const data = await api("/api/login", "POST", {
      email: document.getElementById("loginEmail").value,
      password: document.getElementById("loginPass").value,
    });
    token = data.token; user = data.user;
    localStorage.setItem("spamshield_token", token);
    refreshAuthArea(); showMsg("Welcome, " + user.name + "!", "ok"); showView("check");
  } catch (e) { showMsg(e.message, "err"); }
}

async function doRegister() {
  try {
    const data = await api("/api/register", "POST", {
      name: document.getElementById("regName").value,
      email: document.getElementById("regEmail").value,
      password: document.getElementById("regPass").value,
    });
    token = data.token; user = data.user;
    localStorage.setItem("spamshield_token", token);
    refreshAuthArea(); showMsg("Account created. Welcome, " + user.name + "!", "ok");
    showView("check");
  } catch (e) { showMsg(e.message, "err"); }
}

async function loadMe() {
  if (!token) return;
  try { user = await api("/api/me"); } catch (e) { token = null; user = null; }
  refreshAuthArea();
}

/* ---------------- Check ---------------- */

function tryExample(text) {
  document.getElementById("smsInput").value = text;
  checkSms();
}

function renderResult(r, container) {
  const pct = Math.round(r.spam_probability * 100);
  const spamWords = r.spam_words.map(w => `<span class="word">${esc(w)}</span>`).join(" ") || "—";
  const hamWords = r.ham_words.map(w => `<span class="word ham">${esc(w)}</span>`).join(" ") || "—";
  container.innerHTML = `<div class="result">
    <span class="badge ${r.label}">${r.label.toUpperCase()}</span>
    <p><b>Spam probability: ${pct}%</b> · Ham probability: ${Math.round(r.ham_probability * 100)}%</p>
    <div class="bar ${r.label}"><div style="width:${pct}%"></div></div>
    <p class="small">Words pushing toward <b>spam</b>: ${spamWords}</p>
    <p class="small">Words pushing toward <b>ham</b>: ${hamWords}</p>
  </div>`;
}

async function checkSms() {
  const text = document.getElementById("smsInput").value.trim();
  if (!text) { showMsg("Please type a message first.", "err"); return; }
  try {
    const r = await api("/api/predict", "POST", { text });
    renderResult(r, document.getElementById("checkResult"));
  } catch (e) { showMsg(e.message, "err"); }
}

async function bulkCheck() {
  const lines = document.getElementById("bulkInput").value
    .split("\n").map(s => s.trim()).filter(Boolean);
  if (!lines.length) { showMsg("Please enter at least one message.", "err"); return; }
  try {
    const data = await api("/api/predict_bulk", "POST", { texts: lines });
    const rows = data.results.map(r =>
      `<tr><td>${esc(r.text)}</td><td><span class="badge ${r.label}" style="font-size:13px;padding:3px 10px">${r.label}</span></td><td>${Math.round(r.spam_probability * 100)}%</td></tr>`).join("");
    const spamCount = data.results.filter(r => r.label === "spam").length;
    document.getElementById("bulkResult").innerHTML =
      `<p><b>${data.results.length}</b> messages checked · <b>${spamCount}</b> spam · <b>${data.results.length - spamCount}</b> ham</p>` +
      `<table><tr><th>Message</th><th>Result</th><th>Spam %</th></tr>${rows}</table>`;
  } catch (e) { showMsg(e.message, "err"); }
}

/* ---------------- Dashboard ---------------- */

async function loadDashboard() {
  if (!user) {
    document.getElementById("dashStats").innerHTML =
      `<p>Please <a href="#" onclick="showView('auth');return false;">login</a> to see your dashboard.</p>`;
    document.getElementById("dashHistory").innerHTML = "";
    return;
  }
  try {
    const s = await api("/api/stats");
    const m = s.model || {};
    const rate = s.mine.total ? Math.round(s.mine.spam / s.mine.total * 100) : 0;
    document.getElementById("dashStats").innerHTML = `
      <div class="card"><div class="num">${s.mine.total}</div><div class="lbl">My checks</div></div>
      <div class="card"><div class="num">${s.mine.spam}</div><div class="lbl">Spam caught</div></div>
      <div class="card"><div class="num">${rate}%</div><div class="lbl">My spam rate</div></div>
      <div class="card"><div class="num">${s.dataset.total}</div><div class="lbl">Dataset messages</div></div>
      <div class="card"><div class="num">${Math.round((m.accuracy || 0) * 100)}%</div><div class="lbl">Model accuracy (hold-out)</div></div>
      ${s.all_predictions ? `<div class="card"><div class="num">${s.all_predictions.total}</div><div class="lbl">All users' checks</div></div>` : ""}`;
    const hist = await api("/api/history");
    document.getElementById("dashHistory").innerHTML = hist.length
      ? `<table><tr><th>Message</th><th>Result</th><th>Spam %</th><th>Checked</th></tr>` +
        hist.slice(0, 20).map(r =>
          `<tr><td>${esc(r.text)}</td><td>${r.label}</td><td>${Math.round(r.spam_probability * 100)}%</td><td class="small">${esc(r.created_at)}</td></tr>`).join("") + `</table>`
      : `<p class="small">No checks yet. Try the Check SMS page.</p>`;
  } catch (e) { showMsg(e.message, "err"); }
}

/* ---------------- Dataset ---------------- */

async function loadDataset(filter) {
  currentFilter = filter;
  const q = document.getElementById("dsSearch").value.trim();
  const params = new URLSearchParams({ limit: 200 });
  if (filter !== "all") params.set("label", filter);
  if (q) params.set("q", q);
  try {
    const data = await api("/api/dataset?" + params.toString());
    document.getElementById("dsCounts").innerHTML =
      `<span class="small">Showing ${data.messages.length} of ${data.total} · Ham: ${data.counts.ham} · Spam: ${data.counts.spam} · Total: ${data.counts.total}</span>`;
    document.getElementById("dsTable").innerHTML =
      `<table><tr><th>Label</th><th>Message</th>${user && user.role === "admin" ? "<th></th>" : ""}</tr>` +
      data.messages.map(m =>
        `<tr><td><span class="badge ${m.label}" style="font-size:12px;padding:2px 9px">${m.label}</span></td><td>${esc(m.text)}</td>` +
        (user && user.role === "admin"
          ? `<td><button class="del" title="Delete" onclick="deleteMessage(${m.id})">✕</button></td>` : "") +
        `</tr>`).join("") + `</table>`;
  } catch (e) { showMsg(e.message, "err"); }
}

async function addMessage() {
  if (!user) { showMsg("Please login to add a message.", "err"); showView("auth"); return; }
  const label = document.getElementById("addLabel").value;
  const text = document.getElementById("addText").value.trim();
  if (!text) { showMsg("Please type a message.", "err"); return; }
  try {
    const r = await api("/api/dataset", "POST", { label, text });
    showMsg(`Added as ${label}. Model retrained — accuracy now ${Math.round(r.metrics.accuracy * 100)}%.`, "ok");
    document.getElementById("addText").value = "";
    loadDataset(currentFilter);
  } catch (e) { showMsg(e.message, "err"); }
}

async function deleteMessage(id) {
  if (!confirm("Delete this message and retrain the model?")) return;
  try {
    await api("/api/dataset/" + id, "DELETE");
    showMsg("Deleted and model retrained.", "ok");
    loadDataset(currentFilter);
  } catch (e) { showMsg(e.message, "err"); }
}

async function uploadCsv() {
  const file = document.getElementById("csvFile").files[0];
  if (!file) { showMsg("Please choose a CSV file first.", "err"); return; }
  const form = new FormData();
  form.append("file", file);
  try {
    const headers = token ? { "Authorization": "Bearer " + token } : {};
    const res = await fetch("/api/dataset/upload", { method: "POST", headers, body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed.");
    showMsg(`Uploaded: ${data.added} added, ${data.skipped} skipped. Model retrained — accuracy ${Math.round(data.metrics.accuracy * 100)}%.`, "ok");
    loadDataset(currentFilter);
  } catch (e) { showMsg(e.message, "err"); }
}

/* ---------------- Evaluate ---------------- */

async function runEvaluation() {
  if (!user) { showMsg("Please login to run the evaluation.", "err"); showView("auth"); return; }
  try {
    const data = await api("/api/evaluate");
    const rows = data.results.map(r =>
      `<tr><td>${esc(r.text)}</td><td>${r.expected}</td><td>${r.predicted}</td><td>${r.correct ? "✅" : "❌"}</td><td>${Math.round(r.spam_probability * 100)}%</td></tr>`).join("");
    document.getElementById("evalResult").innerHTML = `
      <div class="cards"><div class="card"><div class="num">${data.correct}/${data.total}</div><div class="lbl">Correct</div></div>
      <div class="card"><div class="num">${Math.round(data.accuracy * 100)}%</div><div class="lbl">Test accuracy</div></div></div>
      <table><tr><th>Message</th><th>Expected</th><th>Predicted</th><th>OK</th><th>Spam %</th></tr>${rows}</table>`;
  } catch (e) { showMsg(e.message, "err"); }
}

/* ---------------- Admin ---------------- */

async function loadAdmin() {
  if (!user || user.role !== "admin") {
    document.getElementById("adminMetrics").innerHTML = `<p>Admin only. Please login as admin.</p>`;
    document.getElementById("adminMatrix").innerHTML = "";
    return;
  }
  try {
    const data = await api("/api/metrics");
    const m = data.metrics;
    const cm = (m.confusion_matrix && m.confusion_matrix.matrix) || [[0, 0], [0, 0]];
    document.getElementById("adminMetrics").innerHTML = `
      <div class="card"><div class="num">${Math.round(m.accuracy * 100)}%</div><div class="lbl">Accuracy</div></div>
      <div class="card"><div class="num">${Math.round(m.precision_spam * 100)}%</div><div class="lbl">Spam precision</div></div>
      <div class="card"><div class="num">${Math.round(m.recall_spam * 100)}%</div><div class="lbl">Spam recall</div></div>
      <div class="card"><div class="num">${Math.round(m.f1_spam * 100)}%</div><div class="lbl">Spam F1</div></div>
      <div class="card"><div class="num">${m.train_size}</div><div class="lbl">Train messages</div></div>
      <div class="card"><div class="num">${m.test_size}</div><div class="lbl">Hold-out test</div></div>`;
    document.getElementById("adminMatrix").innerHTML = `
      <h2>Confusion matrix (hold-out test)</h2>
      <table style="max-width:420px"><tr><th></th><th>Predicted ham</th><th>Predicted spam</th></tr>
      <tr><td><b>Actual ham</b></td><td>${cm[0][0]}</td><td>${cm[0][1]}</td></tr>
      <tr><td><b>Actual spam</b></td><td>${cm[1][0]}</td><td>${cm[1][1]}</td></tr></table>`;
  } catch (e) { showMsg(e.message, "err"); }
}

async function retrain() {
  try {
    const data = await api("/api/train", "POST", {});
    showMsg(`Retrained — accuracy ${Math.round(data.metrics.accuracy * 100)}%.`, "ok");
    loadAdmin();
  } catch (e) { showMsg(e.message, "err"); }
}

/* ---------------- init ---------------- */
loadMe();
