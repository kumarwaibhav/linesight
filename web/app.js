/* LineSight inspection workspace. Kumar Waibhav Akshat <kwa.waibhav@gmail.com>. */
"use strict";
const $ = (id) => document.getElementById(id);
const state = {mode: "upload", ready: false, busy: false, samples: [], stream: null, running: false, generation: 0, frame: 0, objectUrl: null, heatmap: null};
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const percent = (value) => Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(1)}%` : "—";
function showNotice(message, isError = true) {
  const notice = $("notice");
  notice.textContent = message;
  notice.classList.toggle("hidden", !message);
  notice.setAttribute("role", isError ? "alert" : "status");
}
async function api(path, options = {}) {
  const response = await fetch(path, {...options, cache: "no-store"});
  let result;
  try { result = await response.json(); } catch { throw new Error(`Service returned HTTP ${response.status}.`); }
  if (!response.ok) {
    const detail = typeof result.detail === "string" ? result.detail : "The request could not be processed.";
    throw new Error(detail);
  }
  return result;
}
function setBusy(value) {
  state.busy = value;
  $("processing").classList.toggle("hidden", !value);
  for (const id of ["chooseImage", "inspectSample", "startCamera", "startReplay"]) $(id).disabled = value || !state.ready;
  $("sampleSelect").disabled = value || state.running;
}
function stopSources() {
  state.generation += 1;
  state.running = false;
  if (state.stream) state.stream.getTracks().forEach((track) => track.stop());
  state.stream = null;
  $("cameraVideo").srcObject = null;
  $("cameraVideo").classList.add("hidden");
  $("stopCamera").classList.add("hidden");
  $("stopReplay").classList.add("hidden");
  $("startCamera").classList.remove("hidden");
  $("startReplay").classList.remove("hidden");
  $("sampleSelect").disabled = state.busy;
}
function selectMode(mode) {
  stopSources();
  state.mode = mode;
  state.heatmap = null;
  drawHeatmap();
  for (const entry of ["upload", "replay", "camera"]) {
    const suffix = entry.charAt(0).toUpperCase() + entry.slice(1);
    $("tab" + suffix).classList.toggle("active", entry === mode);
    $(entry + "Controls").classList.toggle("hidden", entry !== mode);
  }
  $("sourceLabel").textContent = ({upload: "IMAGE UPLOAD", replay: "RECORDED DATASET", camera: "SAMPLED CAMERA"})[mode];
  $("viewTag").textContent = ({upload: "FIXED-VIEW INSPECTION", replay: "DATASET REPLAY · NOT LIVE", camera: "CAMERA · LAST SAMPLED FRAME"})[mode];
  if (mode === "camera") {
    state.heatmap = null;
    drawHeatmap();
    $("imageStage").classList.add("hidden");
    $("emptyState").classList.remove("hidden");
  } else if (state.objectUrl) {
    $("inspectionImage").classList.remove("hidden");
    $("imageStage").classList.remove("hidden");
    $("emptyState").classList.add("hidden");
  }
}
function drawHeatmap() {
  const canvas = $("heatmapCanvas");
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  if (!state.heatmap || !$("showHeatmap").checked) return;
  const map = state.heatmap;
  if (!Array.isArray(map) || !map.length || !Array.isArray(map[0])) return;
  const rows = map.length, columns = map[0].length;
  if (!rows || !columns) return;
  canvas.width = columns * 12;
  canvas.height = rows * 12;
  const source = $("inspectionImage");
  const width = source.videoWidth || source.naturalWidth || 192;
  const height = source.videoHeight || source.naturalHeight || 192;
  const stage = $("imageStage");
  const scale = Math.min(stage.clientWidth / width, stage.clientHeight / height);
  canvas.style.width = `${Math.round(width * scale)}px`;
  canvas.style.height = `${Math.round(height * scale)}px`;
  const values = map.flat().filter(Number.isFinite);
  if (!values.length) return;
  const low = Math.min(...values), high = Math.max(...values);
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < columns; x++) {
      const normalized = high > low ? (map[y][x] - low) / (high - low) : 0;
      if (normalized < 0.55) continue;
      context.fillStyle = `rgba(255, ${Math.round(194 - normalized * 120)}, 48, ${(normalized - 0.5) * 1.8})`;
      context.fillRect(x * 12, y * 12, 12, 12);
    }
  }
}
async function previewBlob(blob, keepCamera = false) {
  if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);
  state.objectUrl = URL.createObjectURL(blob);
  const image = $("inspectionImage");
  await new Promise((resolve, reject) => {
    image.onload = resolve;
    image.onerror = () => reject(new Error("The browser could not preview this image."));
    image.src = state.objectUrl;
  });
  image.classList.remove("hidden");
  $("cameraVideo").classList.toggle("hidden", !keepCamera);
  $("cameraVideo").classList.toggle("camera-preview", keepCamera);
  $("imageStage").classList.remove("hidden");
  $("emptyState").classList.add("hidden");
  state.heatmap = null;
  drawHeatmap();
}
function renderResult(result, caption) {
  const anomaly = Boolean(result.is_anomaly);
  const card = document.querySelector(".decision-card");
  card.classList.toggle("anomaly", anomaly);
  card.classList.toggle("nominal", !anomaly);
  $("decisionIcon").textContent = anomaly ? "!" : "✓";
  $("decisionEyebrow").textContent = anomaly ? "FLAGGED FOR HUMAN REVIEW" : "BELOW THE FIXED THRESHOLD";
  $("decisionTitle").textContent = anomaly ? "A closer look is needed." : "Nominal observation.";
  $("decisionDescription").textContent = anomaly ? "This image differs from the learned normal reference. Review the image and patch evidence before taking action." : "The model did not flag this image. A below-threshold score does not guarantee a defect-free product.";
  const score = Number(result.score), threshold = Number(result.threshold);
  $("scoreValue").textContent = score.toFixed(4);
  $("thresholdValue").textContent = threshold.toFixed(4);
  $("latencyValue").textContent = `${Number(result.inference_ms).toFixed(1)} ms`;
  // Negative IsolationForest.score_samples values use a stable [0,1] anomaly-score scale.
  // The value is an isolation score, never a defect probability.
  const lower = 0;
  const upper = 1;
  $("scoreFill").style.width = `${Math.max(0, Math.min(100, (score - lower) / (upper - lower) * 100))}%`;
  $("scoreFill").style.background = anomaly ? "#ce864d" : "#4baf92";
  $("thresholdMark").style.left = `${(threshold - lower) / (upper - lower) * 100}%`;
  $("thresholdMark").style.display = "block";
  $("modelVersion").textContent = result.model_version;
  $("modelVersion").title = result.model_version;
  $("viewerCaption").textContent = caption;
  $("dimensions").textContent = `${result.width} × ${result.height} px`;
  state.heatmap = result.heatmap;
  drawHeatmap();
}
async function inspectBlob(blob, filename, sourceId, frameId, caption, generation = state.generation) {
  if (state.busy || generation !== state.generation) return;
  setBusy(true);
  showNotice("");
  try {
    const form = new FormData();
    form.append("file", blob, filename);
    form.append("source_id", sourceId);
    if (frameId) form.append("frame_id", String(frameId));
    const result = await api("/api/inspect", {method: "POST", body: form});
    if (generation === state.generation) renderResult(result, caption);
    await refreshEvents();
  } catch (error) {
    showNotice(error.message);
    if (state.running) stopSources();
  } finally { setBusy(false); }
}
async function uploadFile(file) {
  if (!file || state.busy) return;
  selectMode("upload");
  if (file.size > 8 * 1024 * 1024) return showNotice("Choose an image smaller than 8 MiB.");
  if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) return showNotice("Choose a PNG, JPEG, or WebP image.");
  try {
    await previewBlob(file);
    await inspectBlob(file, file.name, "upload", null, `Uploaded image · ${file.name}`);
  } catch (error) { showNotice(error.message); }
}
async function inspectSelectedSample(generation = state.generation) {
  const sample = state.samples.find((row) => row.id === $("sampleSelect").value);
  if (!sample) { showNotice("No dataset images are available. Prepare the dataset and restart the service."); return; }
  const response = await fetch(sample.image_url);
  if (!response.ok) throw new Error("The dataset sample could not be loaded.");
  const blob = await response.blob();
  if (generation !== state.generation) return;
  await previewBlob(blob);
  await inspectBlob(blob, sample.filename, "dataset-replay", sample.id,
    `Replay · annotation: ${sample.defect_type} · ${sample.filename}`, generation);
}
async function startReplay() {
  if (!state.samples.length || state.busy || !state.ready) return;
  stopSources();
  state.running = true;
  const generation = state.generation;
  $("startReplay").classList.add("hidden");
  $("stopReplay").classList.remove("hidden");
  $("sampleSelect").disabled = true;
  try {
    while (state.running && generation === state.generation) {
      await inspectSelectedSample(generation);
      if (!state.running || generation !== state.generation) break;
      await sleep(1400);
      if (!state.running || generation !== state.generation) break;
      $("sampleSelect").selectedIndex = ($("sampleSelect").selectedIndex + 1) % state.samples.length;
    }
  } catch (error) { showNotice(error.message); stopSources(); }
}
async function startCamera() {
  if (state.busy || !state.ready) return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return showNotice("Camera access requires a supported browser on localhost or HTTPS.");
  stopSources();
  const generation = state.generation;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({video: {width: {ideal: 640}, height: {ideal: 480}}, audio: false});
    if (generation !== state.generation) { stream.getTracks().forEach((track) => track.stop()); return; }
    state.stream = stream;
    state.running = true;
    const video = $("cameraVideo");
    video.srcObject = stream;
    await video.play();
    video.classList.remove("hidden");
    video.classList.remove("camera-preview");
    $("inspectionImage").classList.add("hidden");
    $("imageStage").classList.remove("hidden");
    $("emptyState").classList.add("hidden");
    $("startCamera").classList.add("hidden");
    $("stopCamera").classList.remove("hidden");
    const canvas = document.createElement("canvas");
    while (state.running && generation === state.generation) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      if (canvas.width && canvas.height) {
        canvas.getContext("2d").drawImage(video, 0, 0);
        const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
        if (blob && generation === state.generation) {
          state.frame += 1;
          await previewBlob(blob, true);
          await inspectBlob(blob, `camera-${state.frame}.jpg`, "camera", String(state.frame), `Camera · inspected frame ${state.frame} · live source inset`, generation);
        }
      }
      await sleep(1200);
    }
  } catch (error) { showNotice(`Camera could not start: ${error.message}`); stopSources(); }
}
async function refreshEvents() {
  try {
    const data = await api("/api/events?limit=8");
    $("metricInspections").textContent = data.retained_total.toLocaleString();
    $("metricAlerts").textContent = data.retained_alerts.toLocaleString();
    const body = $("eventsBody");
    body.replaceChildren();
    if (!data.events.length) {
      const row = body.insertRow(), cell = row.insertCell();
      cell.colSpan = 6; cell.className = "empty-table";
      cell.textContent = "No inspections yet. Your first result will appear here.";
      return;
    }
    data.events.forEach((event) => {
      const row = body.insertRow();
      const time = new Date(event.timestamp);
      row.insertCell().textContent = time.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"});
      const source = document.createElement("span"); source.className = "event-source"; source.textContent = event.source_id;
      row.insertCell().append(source);
      const name = row.insertCell(); name.textContent = event.filename || event.frame_id || "image"; name.className = "event-file"; name.title = name.textContent;
      const score = row.insertCell(); score.textContent = Number(event.score).toFixed(4); score.className = "event-score";
      const decision = document.createElement("span"); decision.className = `event-decision${event.is_anomaly ? " alert" : ""}`;
      decision.textContent = event.is_anomaly ? "Review required" : "Below threshold";
      row.insertCell().append(decision);
      row.insertCell().textContent = `${Number(event.inference_ms).toFixed(1)} ms`;
      row.title = `Model ${event.model_version} · ${event.timestamp}`;
    });
  } catch (error) { showNotice(`History unavailable: ${error.message}`); }
}
async function initialize() {
  try {
    const [health, model, metrics, sampleData] = await Promise.all([api("/api/health"), api("/api/model"), api("/api/metrics"), api("/api/samples")]);
    state.ready = health.model_loaded;
    const status = $("serviceStatus");
    status.classList.toggle("ready", state.ready); status.classList.toggle("unready", !state.ready);
    const dot = document.createElement("span"); dot.className = "status-dot";
    status.replaceChildren(dot, document.createTextNode(state.ready ? "Model ready" : "Model unavailable"));
    if (!state.ready) showNotice("The model is not loaded. Run the training pipeline, then restart the service to enable inspection.", false);
    if (model.model_version) { $("modelVersion").textContent = model.model_version; $("modelVersion").title = model.model_version; }
    if (Number.isFinite(model.threshold)) $("thresholdValue").textContent = model.threshold.toFixed(4);
    if (metrics.available) {
      const report = metrics.report;
      $("metricAuroc").textContent = percent(report.auroc);
      $("metricRecall").textContent = percent(report.recall);
    }
    state.samples = sampleData.samples;
    const select = $("sampleSelect"); select.replaceChildren();
    if (!state.samples.length) { const option = document.createElement("option"); option.textContent = "No dataset samples available"; select.append(option); }
    state.samples.forEach((sample) => { const option = document.createElement("option"); option.value = sample.id; option.textContent = `${sample.defect_type.replaceAll("_", " ")} · ${sample.filename}`; select.append(option); });
    setBusy(false);
    await refreshEvents();
  } catch (error) {
    $("serviceStatus").textContent = "Service unavailable";
    showNotice(`Could not reach the inspection service: ${error.message}`);
    setBusy(false);
  }
}
$("tabUpload").addEventListener("click", () => selectMode("upload"));
$("tabReplay").addEventListener("click", () => selectMode("replay"));
$("tabCamera").addEventListener("click", () => selectMode("camera"));
$("chooseImage").addEventListener("click", () => $("fileInput").click());
$("fileInput").addEventListener("change", (event) => uploadFile(event.target.files[0]));
$("inspectSample").addEventListener("click", () => inspectSelectedSample().catch((error) => showNotice(error.message)));
$("startReplay").addEventListener("click", startReplay);
$("stopReplay").addEventListener("click", stopSources);
$("startCamera").addEventListener("click", startCamera);
$("stopCamera").addEventListener("click", stopSources);
$("showHeatmap").addEventListener("change", drawHeatmap);
$("refreshEvents").addEventListener("click", refreshEvents);
$("viewer").addEventListener("dragover", (event) => { event.preventDefault(); $("viewer").classList.add("dragging"); });
$("viewer").addEventListener("dragleave", () => $("viewer").classList.remove("dragging"));
$("viewer").addEventListener("drop", (event) => { event.preventDefault(); $("viewer").classList.remove("dragging"); uploadFile(event.dataTransfer.files[0]); });
window.addEventListener("resize", drawHeatmap);
window.addEventListener("pagehide", () => { stopSources(); if (state.objectUrl) URL.revokeObjectURL(state.objectUrl); });
$("heatmapCanvas").title = "Patch evidence colors are normalized within each image; compare raw image scores for decisions.";
initialize();
