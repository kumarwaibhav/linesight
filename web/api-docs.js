"use strict";
const result = document.getElementById("docsResult");
async function showRequest(path, options = {}) {
  result.textContent = "Request in progress…";
  try {
    const response = await fetch(path, options);
    const body = await response.json();
    if (Array.isArray(body.heatmap)) body.heatmap = `[${body.heatmap.length} × ${body.heatmap[0].length} patch scores; omitted from this preview]`;
    result.textContent = `HTTP ${response.status}\n${JSON.stringify(body, null, 2)}`;
  } catch (error) { result.textContent = error.message; }
}
document.getElementById("tryHealth").addEventListener("click", () => showRequest("/api/health"));
document.getElementById("docsInspectForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const file = document.getElementById("docsImage").files[0];
  if (!file) return;
  const data = new FormData(); data.append("file", file); data.append("source_id", "api-reference");
  showRequest("/api/inspect", {method: "POST", body: data});
});
fetch("/openapi.json").then((response) => response.json()).then((schema) => {
  const list = document.getElementById("endpointList"); list.replaceChildren();
  for (const [path, methods] of Object.entries(schema.paths)) {
    for (const [method, operation] of Object.entries(methods)) {
      const row = document.createElement("article"); row.className = "endpoint";
      const verb = document.createElement("span"); verb.className = "endpoint-method"; verb.textContent = method.toUpperCase();
      const text = document.createElement("div");
      const code = document.createElement("code"); code.textContent = path; text.append(code);
      const description = document.createElement("p"); description.textContent = operation.description || operation.summary || ""; text.append(description);
      if (method === "get" && !path.includes("{")) { const button = document.createElement("button"); button.className = "button secondary"; button.textContent = "Try request"; button.addEventListener("click", () => showRequest(path)); text.append(button); }
      const responses = document.createElement("div"); responses.className = "endpoint-errors"; responses.textContent = `Schema responses: ${Object.keys(operation.responses || {}).join(", ")}`; text.append(responses);
      row.append(verb, text); list.append(row);
    }
  }
}).catch((error) => { document.getElementById("endpointList").textContent = error.message; });
