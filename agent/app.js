"use strict";
const goal = document.getElementById("goal");
const run = document.getElementById("run");
const result = document.getElementById("result");
const working = document.getElementById("working");
const files = document.getElementById("files");
const zipLink = document.getElementById("download-all");
let active = false;
let activeTask = null;

function setStatus(text) { working.textContent = text; }
function show(text, error = false) {
  result.hidden = false;
  result.className = "result" + (error ? " error" : "");
  result.replaceChildren(document.createTextNode(text));
}
async function readJson(url, opts) {
  const res = await fetch(url, {cache: "no-store", ...opts});
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || "Request failed (" + res.status + ")");
  return body;
}
function selectedFiles() {
  return Array.from(files.querySelectorAll("input[type=checkbox]:checked")).map(el => el.value);
}
async function refreshFiles() {
  try {
    const info = await readJson("/api/files");
    files.replaceChildren();
    if (!info.files.length) {
      const p = document.createElement("p");
      p.className = "empty";
      p.textContent = "Your generated files appear here.";
      files.append(p);
    }
    for (const item of info.files) {
      const row = document.createElement("div"); row.className = "file";
      const label = document.createElement("label");
      const ck = document.createElement("input"); ck.type = "checkbox"; ck.value = item.path;
      const link = document.createElement("a");
      link.href = "/download/" + item.path.split("/").map(encodeURIComponent).join("/");
      link.textContent = item.path;
      link.download = item.path.split("/").pop();
      const bytes = document.createElement("span"); bytes.className = "size";
      bytes.textContent = item.size + " bytes";
      label.append(ck, link); row.append(label, bytes); files.append(row);
    }
    zipLink.hidden = !info.files.length;
  } catch (e) { show(e.message, true); }
}
async function poll(taskId) {
  const started = Date.now();
  while (active && activeTask === taskId) {
    const info = await readJson("/api/tasks/" + taskId);
    if (info.status === "complete") {
      setStatus("Finished in " + info.duration_seconds + " seconds");
      show(info.message + "\n\nCreated or updated " + info.created.length + " file(s). Download them below.");
      await refreshFiles();
      return;
    }
    if (info.status === "failed") {
      setStatus("Task failed");
      show(info.message || "The model could not complete this task.", true);
      return;
    }
    setStatus("Agent creating files… " + Math.round((Date.now()-started)/1000) + "s");
    await new Promise(resolve => setTimeout(resolve, 1800));
  }
}
run.addEventListener("click", async () => {
  if (active) return;
  if (!goal.value.trim()) { show("Describe the files you'd like to create.", true); goal.focus(); return; }
  const requested = selectedFiles();
  active = true; run.disabled = true; setStatus("Starting local model…");
  result.hidden = true;
  try {
    const r = await readJson("/api/tasks", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({goal: goal.value.trim(), selected: requested})
    });
    activeTask = r.id;
    await poll(r.id);
  } catch (e) {
    show(e.message, true); setStatus("Task failed");
  } finally {
    active = false; activeTask = null; run.disabled = false;
  }
});
document.getElementById("refresh").addEventListener("click", refreshFiles);
document.querySelectorAll("button[data-prompt]").forEach(btn => btn.addEventListener("click", () => {
  goal.value = btn.dataset.prompt;
  goal.focus();
}));
refreshFiles();
