"use strict";

const state = {mode: "direct", language: "auto", messages: [], busy: false, courseId: null, courses: [], chunks: [], configured: false, authenticated: false};
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const apiUrl = (path) => new URL(path.replace(/^\//, ""), document.baseURI).toString();
const conversation = $("#conversation");
const input = $("#input");
const sendButton = $("#send-button");

async function api(path, options = {}) {
  const response = await fetch(apiUrl(path), options);
  const payload = response.status === 204 ? null : await response.json().catch(() => null);
  if (response.status === 401) setInstructor(false);
  if (!response.ok) throw new Error(payload?.detail || "Anfrage fehlgeschlagen");
  return payload;
}

function setStatus(text, busy = false) {
  $("#status").textContent = text;
  $("#status-dot").classList.toggle("busy", busy);
}

function setBusy(value) {
  state.busy = value;
  $("#student-course-select").disabled = value;
  $("#course-select").disabled = value;
  input.disabled = value;
  sendButton.disabled = value || !input.value.trim();
}

function showAuth(login) {
  $("#auth-screen").hidden = false;
  $(".app-shell").setAttribute("aria-hidden", "true");
  $("#auth-title").textContent = login ? "Dozent anmelden" : "Dozentenkonto einrichten";
  $("#auth-description").textContent = login ? "Diese Installation besitzt genau ein Dozentenkonto." : "Der erste eingerichtete Zugang ist das einzige Konto dieser Installation und verwaltet alle Kurse.";
  $("#auth-submit").textContent = login ? "Anmelden" : "Konto einrichten";
  $("#auth-password").autocomplete = login ? "current-password" : "new-password";
  state.configured = login;
}

function hideAuth() {
  $("#auth-screen").hidden = true;
  $(".app-shell").removeAttribute("aria-hidden");
  $("#auth-error").textContent = "";
}

function setInstructor(authenticated) {
  state.authenticated = authenticated;
  $("#data-button").hidden = !authenticated;
  $("#logout-button").hidden = !authenticated;
  $("#instructor-button").hidden = authenticated;
  if (!authenticated) {
    $("#data-panel").hidden = true;
    $("#teacher-api-key").value = "";
    $("#provider-url").value = "";
    $("#model").value = "";
    $("#model-select").replaceChildren();
  }
}

function addMessage(role, content, sources = []) {
  state.messages.push({role, content});
  const article = document.createElement("article"); article.className = `message ${role}`;
  const author = document.createElement("div"); author.className = "message-author";
  if (role === "assistant") author.innerHTML = '<span class="tutor-avatar">T</span><strong>Course Tutor</strong>'; else author.textContent = "Du";
  const body = document.createElement("div"); body.className = "message-body";
  content.split("\n").forEach((line) => {
    if (!line) return body.appendChild(document.createElement("br"));
    const paragraph = document.createElement("p"); paragraph.textContent = line; body.appendChild(paragraph);
  });
  if (sources.length) {
    const button = document.createElement("button"); button.className = "source-link"; button.type = "button";
    button.textContent = `${sources.length} Kursquellen anzeigen`; button.addEventListener("click", () => showSources(sources)); body.appendChild(button);
  }
  article.append(author, body); conversation.appendChild(article); conversation.scrollTop = conversation.scrollHeight;
}

function showSources(sources) {
  const stack = $("#source-stack"); stack.replaceChildren();
  $("#empty-evidence").hidden = Boolean(sources.length); stack.hidden = !sources.length;
  $("#evidence-count").textContent = sources.length ? `${sources.length} Quellen` : "Keine Quelle";
  sources.forEach((source, index) => {
    const details = document.createElement("details"); const summary = document.createElement("summary");
    summary.innerHTML = '<span class="source-number"></span><span><strong></strong><small></small></span><span class="score"></span>';
    summary.querySelector(".source-number").textContent = String(index + 1).padStart(2, "0");
    summary.querySelector("strong").textContent = source.title; summary.querySelector("small").textContent = source.section;
    summary.querySelector(".score").textContent = Number(source.score).toFixed(2);
    const text = document.createElement("p"); text.textContent = source.text;
    const footer = document.createElement("footer"); footer.textContent = source.source_file;
    details.append(summary, text, footer); stack.appendChild(details);
  });
}

function resetConversation() {
  state.messages = []; conversation.replaceChildren(); showSources([]); $("#suggestions").hidden = false;
  const name = state.courses.find((item) => item.id === state.courseId)?.name || "aktiven Kurs";
  addMessage("assistant", `Willkommen im Course Tutor für „${name}“. ${state.mode === "socratic" ? "Ich unterstütze dich mit Hinweisen und Leitfragen" : "Ich erkläre dir die Kursinhalte"} anhand der eingebundenen Materialien und zeige die verwendeten Quellen.`);
  state.messages = [];
}

async function loadModels() {

  setBusy(true); setStatus("Modelle werden abgefragt …", true);
  try {
    const payload = await api("models", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({base_url: $("#provider-url").value, api_key: $("#auth-mode").value === "none" ? "" : $("#teacher-api-key").value, provider: $("#provider").value})});
    const select = $("#model-select");
    select.replaceChildren(...payload.models.map((item) => { const option = document.createElement("option"); option.value = item.id; option.textContent = item.name; return option; }));
    const preferred = payload.models.find((item) => `${item.name} ${item.id}`.toLowerCase().includes("standard coding"));
    if (preferred) select.value = preferred.id;
    select.value = payload.models.some(item => item.id === $("#model").value) ? $("#model").value : select.value; select.hidden = !payload.models.length; if (payload.models.length) $("#model").value = select.value; setStatus(`${payload.models.length} Modelle gefunden`);
  } catch (error) { setStatus(error.message); } finally { setBusy(false); }
}

function currentModel() { return $("#model").value; }

async function send(question) {
  question = question.trim();
  if (!question || state.busy || !state.courseId) return;
  if (state.requiresApiKey && !$("#api-key").value) { $("#connection-panel").hidden = false; return setStatus("API-Key erforderlich"); }
  addMessage("user", question); $("#suggestions").hidden = true; input.value = ""; setBusy(true); setStatus("Kursmaterial wird durchsucht …", true);
  try {
    const payload = await api("tutor", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({message: question, course_id: state.courseId, language: state.language, api_key: $("#api-key").value, messages: state.messages.slice(0, -1).slice(-10)})});
    addMessage("assistant", payload.answer, payload.sources); showSources(payload.sources); $("#retrieval-label").textContent = payload.retrieval;
    $("#provider-label").textContent = "Kursgebundener Tutor"; setStatus(`${payload.sources.length} Quellen · ${payload.retrieval}`);
  } catch (error) { addMessage("assistant", `Die Anfrage konnte nicht ausgeführt werden: ${error.message}`); setStatus("Verbindungsfehler"); } finally { setBusy(false); }
}

async function loadCourses(preferred = state.courseId) {
  const payload = await api("courses"); state.courses = payload.courses;
  const select = $("#course-select");
  select.replaceChildren(...state.courses.map((course) => { const option = document.createElement("option"); option.value = course.id; option.textContent = `${course.name} (${course.chunks})`; return option; }));
  state.courseId = state.courses.some((item) => item.id === preferred) ? preferred : state.courses[0]?.id || null;
  const studentSelect = $("#student-course-select");
  studentSelect.replaceChildren(...state.courses.map(course => { const option = document.createElement("option"); option.value = course.id; option.textContent = course.name; return option; }));
  studentSelect.value = state.courseId || "";
  studentSelect.hidden = state.courses.length < 2;
  if (state.courseId) { select.value = state.courseId; await loadCourseInfo(); }
  else { $("#settings-button").hidden = true; $("#connection-panel").hidden = true; $("#api-key").value = ""; $("#module-list").replaceChildren(); $("#course-index").replaceChildren(); $("#course-name").textContent = "Noch kein Kurs"; $("#course-description").textContent = "Öffnen Sie „Kursdaten“ und legen Sie den ersten Kurs an."; $("#chunk-count").textContent = "0"; resetConversation(); }
}

async function loadCourseInfo() {
  if (!state.courseId) return;
  const info = await api(`course-info?course_id=${encodeURIComponent(state.courseId)}`);
  state.requiresApiKey = info.requires_api_key;
  state.mode = info.mode;
  $("#settings-button").hidden = !info.requires_api_key;
  if (!info.requires_api_key) { $("#connection-panel").hidden = true; $("#api-key").value = ""; }
  $("#mode-label").textContent = info.mode === "socratic" ? "Sokratischer Tutor" : "Erklärender Tutor";
  $("#top-k-label").textContent = info.top_k;
  $("#provider-label").textContent = info.requires_api_key ? "Persönlicher API-Key erforderlich" : "Kursgebundener Tutor · ohne API-Key";
  input.placeholder = info.mode === "socratic" ? "Wobei soll ich dich mit Hinweisen unterstützen?" : "Frage zum aktiven Kurs stellen …";
  if (state.authenticated) await loadSettings();
  $("#course-name").textContent = info.name; $("#course-description").textContent = info.description || "Für diesen Kurs wurde noch keine Beschreibung hinterlegt."; $("#chunk-count").textContent = info.chunks;
  const modules = $("#module-list"); modules.replaceChildren();
  info.modules.slice(0, 6).forEach((module, index) => {
    const item = document.createElement("button"); item.className = "module active"; item.disabled = true;
    item.innerHTML = `<span class="module-number">${String(index + 1).padStart(2, "0")}</span><span><strong></strong><small>erschlossener Themenbereich</small></span><span class="module-state">aktiv</span>`;
    item.querySelector("strong").textContent = module; modules.appendChild(item);
  });
  const index = $("#course-index"); index.replaceChildren(); const label = document.createElement("span"); label.textContent = "Kursindex"; index.appendChild(label);
  info.titles.slice(0, 10).forEach((title) => { const item = document.createElement("small"); item.textContent = title; index.appendChild(item); }); resetConversation();
}

function renderChunks() {
  const needle = $("#chunk-filter").value.trim().toLowerCase();
  const chunks = state.chunks.filter((chunk) => !needle || `${chunk.title} ${chunk.section} ${chunk.text}`.toLowerCase().includes(needle));
  $("#chunk-summary").textContent = `${state.chunks.length} Chunks · ${state.chunks.filter((item) => item.quality_flags?.length).length} mit Prüfhinweis`;
  const list = $("#chunk-list"); list.replaceChildren();
  chunks.slice(0, 200).forEach((chunk) => {
    const article = document.createElement("article"); article.className = "chunk-card";
    const flags = (chunk.quality_flags || []).map((flag) => `<span>${flag.replaceAll("_", " ")}</span>`).join("");
    article.innerHTML = `<header><div><strong></strong><small></small></div><div class="chunk-flags">${flags}</div></header><label>Abschnitt<input class="chunk-section"></label><label>Inhalt<textarea rows="6" class="chunk-text"></textarea></label><footer><span></span><button class="chunk-save" type="button">Speichern</button><button class="chunk-delete" type="button">Löschen</button></footer>`;
    article.querySelector("strong").textContent = chunk.title; article.querySelector("small").textContent = chunk.source_file; article.querySelector(".chunk-section").value = chunk.section; article.querySelector(".chunk-text").value = chunk.text; article.querySelector("footer span").textContent = `${chunk.text.length} Zeichen · ${chunk.id}`;
    article.querySelector(".chunk-save").addEventListener("click", async () => { try { await api(`courses/${state.courseId}/chunks/${chunk.id}`, {method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify({title: chunk.title, section: article.querySelector(".chunk-section").value, text: article.querySelector(".chunk-text").value, module: chunk.module || "Material", topic: chunk.topic || "Allgemein"})}); setDataStatus("Chunk gespeichert; Index wurde ungültig gemacht."); await loadChunks(); await loadCourseInfo(); } catch (error) { setDataStatus(error.message, true); } });
    article.querySelector(".chunk-delete").addEventListener("click", async () => { if (!confirm("Diesen Chunk wirklich löschen?")) return; try { await api(`courses/${state.courseId}/chunks/${chunk.id}`, {method: "DELETE"}); setDataStatus("Chunk gelöscht."); await loadChunks(); await loadCourseInfo(); } catch (error) { setDataStatus(error.message, true); } });
    list.appendChild(article);
  });
}

async function loadChunks() { if (!state.courseId) { state.chunks = []; return renderChunks(); } const payload = await api(`courses/${state.courseId}/chunks`); state.chunks = payload.chunks; renderChunks(); }
function setDataStatus(message, error = false) { $("#data-status").textContent = message; $("#data-status").classList.toggle("error-text", error); }

$("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault(); $("#auth-error").textContent = "";
  try { await api(state.configured ? "auth/login" : "auth/setup", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({username: $("#auth-username").value, password: $("#auth-password").value})}); state.configured = true; $("#auth-password").value = ""; hideAuth(); setInstructor(true); await loadCourses(); setStatus("Dozent angemeldet"); }
  catch (error) { $("#auth-error").textContent = error.message; }
});
$("#auth-cancel").addEventListener("click", hideAuth);
$("#instructor-button").addEventListener("click", () => showAuth(state.configured));
$("#logout-button").addEventListener("click", async () => { await api("auth/logout", {method: "POST"}); state.messages = []; $("#api-key").value = ""; setInstructor(false); resetConversation(); setStatus("Tutor bereit"); });
$("#settings-button").addEventListener("click", () => { $("#connection-panel").hidden = !$("#connection-panel").hidden; });
$("#models-button").addEventListener("click", loadModels); $("#clear-button").addEventListener("click", resetConversation);
$("#model-select").addEventListener("change", () => { $("#model").value = $("#model-select").value; });
$("#language").addEventListener("change", (event) => { state.language = event.target.value; });
input.addEventListener("input", () => { sendButton.disabled = state.busy || !input.value.trim(); });
input.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(input.value); } });
$("#composer").addEventListener("submit", (event) => { event.preventDefault(); send(input.value); });
$$("#suggestions button").forEach((button) => button.addEventListener("click", () => send(button.textContent.replace("↗", "").trim())));
$("#data-button").addEventListener("click", async () => { $("#data-panel").hidden = false; try { await loadChunks(); } catch (error) { setDataStatus(error.message, true); } });
$("#data-close").addEventListener("click", () => { $("#data-panel").hidden = true; });
$("#new-course-toggle").addEventListener("click", () => { $("#new-course-form").hidden = !$("#new-course-form").hidden; });
$("#course-select").addEventListener("change", async (event) => { $("#api-key").value = ""; $("#teacher-api-key").value = ""; state.courseId = event.target.value; $("#student-course-select").value = state.courseId; await loadCourseInfo(); if (state.authenticated) await loadChunks(); });
$("#chunk-filter").addEventListener("input", renderChunks);
$("#new-course-form").addEventListener("submit", async (event) => { event.preventDefault(); try { const course = await api("courses", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({name: $("#new-course-name").value, description: $("#new-course-description").value, tutor_role: $("#new-course-role").value, language: "de"})}); await loadCourses(course.id); await loadChunks(); event.target.reset(); $("#new-course-form").hidden = true; setDataStatus(`Kurs „${course.name}“ wurde angelegt.`); } catch (error) { setDataStatus(error.message, true); } });
$("#upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const files = [...$("#document-file").files], courseId = state.courseId;
  if (!files.length || !courseId) return;
  const controls = [...$("#data-panel").querySelectorAll("input, select, button")];
  const disabled = controls.map(control => control.disabled);
  controls.forEach(control => { control.disabled = true; });
  const results = []; let failures = 0;
  try {
    for (let index = 0; index < files.length; index++) {
      const file = files[index];
      setDataStatus(`Datei ${index + 1}/${files.length}: ${file.name} wird verarbeitet …`);
      try {
        if (file.size > 25 * 1024 * 1024) throw new Error("Datei ist größer als 25 MB");
        const form = new FormData(); form.append("file", file);
        const result = await api(`courses/${courseId}/documents`, {method: "POST", body: form});
        results.push(`${file.name}: ${result.chunks_added} Chunks, ${result.quality_flags} Prüfhinweise`);
      } catch (error) { failures++; results.push(`${file.name}: FEHLER – ${error.message}`); }
    }
    event.target.reset();
    await loadCourses(courseId); if (state.authenticated) await loadChunks();
    setDataStatus(`${files.length - failures}/${files.length} Dateien importiert.\n${results.join("\n")}`, failures > 0);
  } catch (error) { setDataStatus(`${results.join("\n")}\n${error.message}`, true); }
  finally { controls.forEach((control, index) => { control.disabled = disabled[index]; }); }
});

$("#reindex-button").addEventListener("click", async () => { if (!state.courseId) return; try { const result = await api(`courses/${state.courseId}/reindex`, {method: "POST"}); setDataStatus(`${result.chunks} Chunks indexbereit. ${result.note}`); } catch (error) { setDataStatus(error.message, true); } });
$("#delete-course-button").addEventListener("click", async () => { const course = state.courses.find((item) => item.id === state.courseId); if (!course || !confirm(`Kurs „${course.name}“ einschließlich Quellen und Chunks endgültig löschen?`)) return; try { await api(`courses/${state.courseId}`, {method: "DELETE"}); state.courseId = null; await loadCourses(); await loadChunks(); setDataStatus("Kurs gelöscht."); } catch (error) { setDataStatus(error.message, true); } });

$("#student-course-select").addEventListener("change", async event => {
  if (state.busy) return;
  $("#api-key").value = ""; $("#teacher-api-key").value = "";
  state.courseId = event.target.value; $("#course-select").value = state.courseId;
  try { await loadCourseInfo(); if (state.authenticated) await loadChunks(); }
  catch (error) { setStatus(error.message); }
});
async function loadSettings() {
  const settings = await api(`courses/${state.courseId}/settings`);
  const fields = {mode: "teacher-mode", provider: "provider", base_url: "provider-url", model: "model", auth_mode: "auth-mode", top_k: "top-k", temperature: "temperature", max_tokens: "max-tokens", history_messages: "history-messages"};
  for (const [key, id] of Object.entries(fields)) $("#" + id).value = settings[key];
  $("#model-select").hidden = true;
  const link = new URL(location.href); link.search = ""; link.hash = ""; link.searchParams.set("course", state.courseId);
  $("#student-link").value = link.toString();
  $("#settings-status").textContent = "Gespeicherte Kurseinstellungen geladen.";
}
$("#course-settings-form").addEventListener("submit", async event => {
  event.preventDefault(); if (!state.courseId) return;
  const settings = {mode: $("#teacher-mode").value, provider: $("#provider").value, base_url: $("#provider-url").value, model: currentModel(), auth_mode: $("#auth-mode").value, top_k: Number($("#top-k").value), temperature: Number($("#temperature").value), max_tokens: Number($("#max-tokens").value), history_messages: Number($("#history-messages").value)};
  try {
    await api(`courses/${state.courseId}/settings`, {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(settings)});
    $("#api-key").value = "";
    await loadCourseInfo();
    $("#settings-status").textContent = "Dauerhaft gespeichert. Die Vorgaben gelten jetzt für alle Teilnehmer.";
  } catch (error) { $("#settings-status").textContent = error.message; }
});
$("#provider").addEventListener("change", () => {
  if ($("#provider").value === "ollama") { $("#provider-url").value = "http://localhost:11434"; $("#auth-mode").value = "none"; $("#model").value = ""; }
  $("#model-select").hidden = true;
});
async function start() {
  try { const status = await api("auth/status"); state.configured = status.configured; $("#provider-url").value = status.default_api_url; setInstructor(status.authenticated); hideAuth(); await loadCourses(new URL(location.href).searchParams.get("course")); setStatus(status.authenticated ? "Dozent angemeldet" : "Tutor bereit"); }
  catch (error) { setInstructor(false); setStatus(error.message); }
}

start();
