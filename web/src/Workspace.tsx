import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Activity, AlertCircle, ArrowDown, ArrowUpRight, Camera, Check, Clock3, FileImage, History, ImagePlus, Play, RefreshCw, ScanLine, Sparkles, Square, Upload, X } from "lucide-react";
import { apiRequest, inspectImage, type EventRecord, type EventsResponse, type HealthResponse, type InspectionResult, type MetricReport, type MetricsResponse, type ModelResponse, type Sample, type SamplesResponse } from "./api";
import { BottleScene, EmptyInspection, EvidenceOverlay, PassChip, ScoreScale, SignalStat, StatusBadge } from "./components";

// Keep source modes explicit so the displayed image and saved event always match the origin.
type SourceMode = "upload" | "replay" | "camera";
const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));
const timeLabel = (value: string) => new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const numberLabel = (value: number | undefined, digits = 1) => Number.isFinite(value) ? `${(Number(value) * 100).toFixed(digits)}%` : "—";

export function Workspace({ onStatus }: { onStatus: (ready: boolean | null) => void }) {
  const [ready, setReady] = useState<boolean | null>(null);
  const [model, setModel] = useState<ModelResponse | null>(null);
  const [report, setReport] = useState<MetricReport>({});
  const [samples, setSamples] = useState<Sample[]>([]);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [eventTotal, setEventTotal] = useState(0);
  const [alertTotal, setAlertTotal] = useState(0);
  const [mode, setMode] = useState<SourceMode>("upload");
  const [selectedSample, setSelectedSample] = useState("");
  const [result, setResult] = useState<InspectionResult | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [caption, setCaption] = useState("Ready for the first image");
  const [showEvidence, setShowEvidence] = useState(true);
  const [busy, setBusy] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [replayActive, setReplayActive] = useState(false);
  const [notice, setNotice] = useState("");
  const [noticeError, setNoticeError] = useState(true);
  const [sampleFailure, setSampleFailure] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const tokenRef = useRef(0);
  const busyRef = useRef(false);
  const modeRef = useRef<SourceMode>(mode);

  // Stop captures/replay when the component leaves or a user selects another source.
  const stopSources = useCallback(() => {
    tokenRef.current += 1;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraActive(false);
    setReplayActive(false);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [health, modelInfo, metrics, sampleData] = await Promise.all([
          apiRequest<HealthResponse>("/api/health"),
          apiRequest<ModelResponse>("/api/model"),
          apiRequest<MetricsResponse>("/api/metrics"),
          apiRequest<SamplesResponse>("/api/samples"),
        ]);
        if (cancelled) return;
        setReady(health.model_loaded);
        onStatus(health.model_loaded);
        setModel(modelInfo);
        setReport(metrics.available ? metrics.report : {});
        setSamples(sampleData.samples);
        setSelectedSample(sampleData.samples[0]?.id ?? "");
        setSampleFailure(sampleData.count === 0);
        if (!health.model_loaded) {
          setNotice("The model is not loaded. Prepare the trained artifact and restart the service to enable inspection.");
          setNoticeError(false);
        }
        await refreshEvents(cancelled);
      } catch (error) {
        if (cancelled) return;
        setReady(false);
        onStatus(false);
        setNotice(`Could not reach the inspection service: ${error instanceof Error ? error.message : "Unknown error"}`);
        setNoticeError(true);
      }
    };
    void load();
    return () => { cancelled = true; stopSources(); };
  }, [stopSources]);

  // Pull the bounded local decision log after each result and on explicit refresh.
  const refreshEvents = useCallback(async (cancelled = false) => {
    try {
      const data = await apiRequest<EventsResponse>("/api/events?limit=8");
      if (cancelled) return;
      setEvents(data.events);
      setEventTotal(data.retained_total);
      setAlertTotal(data.retained_alerts);
    } catch (error) {
      if (!cancelled) setNotice(`History is unavailable: ${error instanceof Error ? error.message : "Unknown error"}`);
    }
  }, []);

  // Release any object URL when a new preview replaces it.
  const setImagePreview = useCallback((blob: Blob) => {
    const nextUrl = URL.createObjectURL(blob);
    setPreviewUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return nextUrl;
    });
  }, []);

  const runInspection = useCallback(async (blob: Blob, filename: string, source: SourceMode, frameId?: string, imageAlreadyVisible = false) => {
    if (busyRef.current) return null;
    busyRef.current = true;
    setBusy(true);
    setNotice("");
    if (!imageAlreadyVisible && source !== "camera") setImagePreview(blob);
    try {
      const response = await inspectImage(blob, filename, source === "replay" ? "dataset-replay" : source, frameId);
      setResult(response);
      setCaption(source === "upload" ? `Uploaded image · ${filename}` : source === "replay" ? `Benchmark replay · ${filename}` : `Camera · sampled frame ${frameId}`);
      await refreshEvents();
      return response;
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "The inspection could not be completed.");
      setNoticeError(true);
      return null;
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, [refreshEvents, setImagePreview]);

  const switchMode = (next: SourceMode) => {
    stopSources();
    modeRef.current = next;
    setMode(next);
    setResult(null);
    setPreviewUrl("");
    setCaption(next === "upload" ? "Ready for the first image" : next === "replay" ? "Select a held-out benchmark sample" : "Camera access starts only when you choose it");
  };

  const uploadFile = async (file?: File) => {
    if (!file) return;
    switchMode("upload");
    const maxBytes = model?.max_image_bytes ?? 8 * 1024 * 1024;
    if (file.size > maxBytes) {
      setNotice(`Choose an image no larger than ${(maxBytes / (1024 * 1024)).toFixed(0)} MiB.`);
      setNoticeError(true);
      return;
    }
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
      setNotice("Choose a PNG, JPEG, or WebP image.");
      setNoticeError(true);
      return;
    }
    await runInspection(file, file.name, "upload");
  };

  const loadSampleBlob = async (sample: Sample) => {
    const response = await fetch(sample.image_url, { cache: "no-store" });
    if (!response.ok) throw new Error("The dataset sample could not be loaded.");
    return response.blob();
  };

  const inspectSample = async () => {
    const sample = samples.find((entry) => entry.id === selectedSample);
    if (!sample) {
      setNotice("No held-out images are available. Follow the dataset acquisition steps in the project documentation, then restart the service.");
      setNoticeError(false);
      return;
    }
    try {
      const blob = await loadSampleBlob(sample);
      await runInspection(blob, sample.filename, "replay", sample.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not load that sample.");
      setNoticeError(true);
    }
  };

  const startReplay = async () => {
    if (!ready || !samples.length || busyRef.current) return;
    stopSources();
    const token = tokenRef.current;
    setReplayActive(true);
    let index = Math.max(0, samples.findIndex((entry) => entry.id === selectedSample));
    while (token === tokenRef.current) {
      const sample = samples[index % samples.length];
      setSelectedSample(sample.id);
      try {
        const blob = await loadSampleBlob(sample);
        if (token !== tokenRef.current) break;
        await runInspection(blob, sample.filename, "replay", sample.id);
      } catch (error) {
        if (token === tokenRef.current) {
          setNotice(error instanceof Error ? error.message : "Replay stopped because a sample could not be loaded.");
          setNoticeError(true);
        }
        stopSources();
        break;
      }
      if (token !== tokenRef.current) break;
      index += 1;
      await sleep(1400);
    }
  };

  const startCamera = async () => {
    if (!ready || !navigator.mediaDevices?.getUserMedia) {
      setNotice("Camera access requires a supported browser on localhost or HTTPS.");
      setNoticeError(true);
      return;
    }
    stopSources();
    const token = tokenRef.current;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
      if (token !== tokenRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      setCameraActive(true);
      await sleep(100);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      const canvas = document.createElement("canvas");
      canvasRef.current = canvas;
      let frame = 0;
      while (token === tokenRef.current) {
        const video = videoRef.current;
        if (video && video.readyState >= 2 && video.videoWidth) {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          canvas.getContext("2d")?.drawImage(video, 0, 0);
          const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
          if (blob && token === tokenRef.current) {
            frame += 1;
            await runInspection(blob, `camera-${frame}.jpg`, "camera", String(frame), true);
          }
        }
        await sleep(1200);
      }
    } catch (error) {
      setNotice(`Camera could not start: ${error instanceof Error ? error.message : "Permission was not granted."}`);
      setNoticeError(true);
      stopSources();
    }
  };

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

  const headline = result ? (result.is_anomaly ? "A closer look is needed." : "Below the fixed threshold.") : "Awaiting an image.";
  const isAnomaly = result?.is_anomaly ?? false;
  const shortSource = mode === "upload" ? "FILE UPLOAD" : mode === "replay" ? "DATASET REPLAY" : "SAMPLED CAMERA";

  return (
    <div className="workspace-page">
      <section className="dashboard-heading">
        <div><span className="kicker"><Sparkles size={13}/> VISUAL QUALITY · BOTTLE STUDY</span><h1>See what’s <em>different.</em></h1><p>Inspect bottle images with a model that learns the look of normal.</p></div>
        <div className="heading-status"><StatusBadge ready={ready}/><span>CPU inference <i/> normal-only fit</span></div>
      </section>

      {notice && <div className={`notice-banner ${noticeError ? "notice-error" : "notice-info"}`} role={noticeError ? "alert" : "status"}><AlertCircle size={16}/><span>{notice}</span><button type="button" aria-label="Dismiss message" onClick={() => setNotice("")}><X size={15}/></button></div>}

      <section className="benchmark-bento" aria-label="Frozen benchmark indicators">
        <SignalStat label="IMAGE AUROC" value={numberLabel(report.auroc, 2)} note="Held-out MVTec AD test · ranking" />
        <SignalStat label="DEFECT RECALL" value={numberLabel(report.recall, 2)} note="At the frozen threshold · 53 of 63" accent />
        <SignalStat label="MODEL INFERENCE" value="139 ms" note="Benchmark median · CPU only" />
        <SignalStat label="INSPECTION LOG" value={eventTotal.toLocaleString()} note={`${alertTotal} flagged · local metadata`} />
      </section>

      <div className="workbench-layout">
        <section className="inspection-card panel-card" aria-labelledby="inspection-heading">
          <div className="panel-head"><div><span className="panel-index">01 / INSPECT</span><h2 id="inspection-heading">Inspection view</h2></div><span className="source-indicator"><i/>{shortSource}</span></div>
          <div className="source-switcher" role="group" aria-label="Choose image source">
            <button className={mode === "upload" ? "active" : ""} type="button" aria-pressed={mode === "upload"} onClick={() => switchMode("upload")}><Upload size={15}/>Upload</button>
            <button className={mode === "replay" ? "active" : ""} type="button" aria-pressed={mode === "replay"} onClick={() => switchMode("replay")}><ImagePlus size={15}/>Replay</button>
            <button className={mode === "camera" ? "active" : ""} type="button" aria-pressed={mode === "camera"} onClick={() => switchMode("camera")}><Camera size={15}/>Camera</button>
          </div>

          <div className={`inspection-stage ${busy ? "is-busy" : ""}`} onDragOver={(event) => { event.preventDefault(); event.currentTarget.classList.add("is-dragging"); }} onDragLeave={(event) => event.currentTarget.classList.remove("is-dragging")} onDrop={(event) => { event.preventDefault(); event.currentTarget.classList.remove("is-dragging"); void uploadFile(event.dataTransfer.files[0]); }}>
            <div className="stage-grid" aria-hidden="true"/>
            <div className="stage-topline"><span><i className={ready ? "" : "offline"}/>{ready ? "INSPECTION SERVICE READY" : ready === false ? "MODEL NOT READY" : "CONNECTING TO SERVICE"}</span><span>FIXED VIEW · 192 × 192</span></div>
            {mode === "camera" && cameraActive ? <div className="preview-image camera-frame"><video ref={videoRef} autoPlay muted playsInline aria-label="Live camera preview"/><EvidenceOverlay result={showEvidence ? result : null}/></div> : previewUrl ? <div className="preview-image"><img src={previewUrl} alt="Current bottle image submitted for inspection"/><EvidenceOverlay result={showEvidence ? result : null}/></div> : <EmptyInspection/>}
            <div className="stage-bottomline"><span><i className={result ? (result.is_anomaly ? "flag" : "pass") : ""}/>{caption}</span><span>{result ? `${result.width} × ${result.height} px` : "Drop image to inspect"}</span></div>
            {busy && <div className="scan-overlay" role="status"><span className="scan-spinner"/><span>Scoring the image</span></div>}
          </div>

          {mode === "upload" && <div className="source-actions"><input ref={fileRef} className="visually-hidden" type="file" accept="image/png,image/jpeg,image/webp" aria-label="Choose an image file" onChange={(event) => { void uploadFile(event.target.files?.[0]); event.currentTarget.value = ""; }}/><button className="button button--primary" type="button" disabled={!ready || busy} onClick={() => fileRef.current?.click()}><Upload size={15}/> Choose image</button><p>Use a centered bottle view with stable lighting. Maximum {(model?.max_image_bytes ?? 8 * 1024 * 1024) / (1024 * 1024)} MiB, 4 megapixels.</p></div>}
          {mode === "replay" && <div className="source-actions source-actions--replay"><label className="visually-hidden" htmlFor="sample-select">Select an official held-out sample</label><select id="sample-select" value={selectedSample} disabled={busy || replayActive || !samples.length} onChange={(event) => setSelectedSample(event.target.value)}><option value="">{samples.length ? "Choose a held-out sample" : "No sample images available"}</option>{samples.map((sample) => <option key={sample.id} value={sample.id}>{sample.defect_type.replaceAll("_", " ")} · {sample.filename}</option>)}</select>{replayActive ? <button type="button" className="button button--stop" onClick={stopSources}><Square size={14}/> Stop replay</button> : <><button className="button button--primary" type="button" disabled={!ready || busy || !samples.length} onClick={() => void inspectSample()}><ScanLine size={15}/> Inspect sample</button><button className="button button--soft" type="button" disabled={!ready || busy || !samples.length} onClick={() => void startReplay()}><Play size={14}/> Play replay</button></>}{sampleFailure && <p className="action-note action-note--wide">Replay uses the held-out images, which are not redistributed in the source checkout. See the Dataset page for the acquisition instructions.</p>}</div>}
          {mode === "camera" && <div className="source-actions">{cameraActive ? <button type="button" className="button button--stop" onClick={stopSources}><Square size={14}/> Stop camera</button> : <button type="button" className="button button--primary" disabled={!ready || busy} onClick={() => void startCamera()}><Camera size={15}/> Start camera</button>}<p>One frame at a time · about every 1.2 seconds. Camera use requires localhost or HTTPS.</p><span className="action-note action-note--wide">Sampled camera frames are not a validated conveyor feed or a factory reject signal.</span></div>}
          <div className="evidence-control"><label className="switch-control"><input type="checkbox" checked={showEvidence} onChange={(event) => setShowEvidence(event.target.checked)}/><span className="switch-track"/><span>Patch evidence overlay</span></label><span>Coarse evidence · not segmentation</span></div>
        </section>

        <aside className="decision-column">
          <section className={`decision-card panel-card ${result ? (isAnomaly ? "decision-card--alert" : "decision-card--pass") : ""}`} aria-live="polite">
            <div className="panel-head"><div><span className="panel-index">02 / DECISION</span><h2>Inspection result</h2></div><span className={`decision-light ${result ? (isAnomaly ? "is-alert" : "is-pass") : ""}`}/></div>
            <div className="decision-content"><div className={`decision-emblem ${result ? (isAnomaly ? "emblem-alert" : "emblem-pass") : ""}`}>{result ? (isAnomaly ? <AlertCircle/> : <Check/>) : <ScanLine/>}</div><span className="kicker">{result ? (isAnomaly ? "FLAGGED FOR HUMAN REVIEW" : "BELOW THE FIXED THRESHOLD") : "AWAITING INSPECTION"}</span><h3>{headline}</h3><p>{result ? (isAnomaly ? "This image differs from the learned normal reference. Review the image and coarse evidence before taking action." : "The score is below threshold. That does not guarantee a defect-free product.") : "Each inspection returns a score, a fixed threshold, and a reason to review."}</p></div>
            <div className="score-summary"><span>Anomaly score</span><b>{result ? result.score.toFixed(4) : "—"}</b></div>
            <ScoreScale score={result?.score ?? null} threshold={result?.threshold ?? model?.threshold ?? null} anomaly={isAnomaly}/>
            <div className="threshold-info"><span>Calibrated threshold</span><b>{result ? result.threshold.toFixed(4) : model?.threshold?.toFixed(4) ?? "—"}</b><span>Model inference</span><b>{result ? `${result.inference_ms.toFixed(1)} ms` : "—"}</b></div>
            <div className="decision-footnote"><Activity size={14}/><span>Scores are not probabilities. A flag invites review; it does not control line equipment.</span></div>
          </section>

          <section className="model-card panel-card"><div className="model-card-top"><div className="model-symbol"><Sparkles size={18}/></div><div><span className="panel-index">UNDER THE SURFACE</span><h3>Normal is the reference.</h3></div></div><p>Spatial image features describe local changes. Isolation trees flag patterns that separate quickly from normal examples.</p><div className="model-meta"><span>MODEL VERSION</span><code title={model?.model_version ?? "Not loaded"}>{model?.model_version ?? "Not loaded"}</code></div><a href="#/architecture">Explore how it works <ArrowUpRight size={14}/></a></section>
        </aside>
      </div>

      <section className="history-card panel-card">
        <div className="panel-head history-head"><div><span className="panel-index">03 / LOCAL EVENT LOG</span><h2><History size={17}/> Recent inspections</h2><p>{model?.history_mode === "temporary" ? "Temporary demo history; records may reset between requests." : "Local metadata only · up to 1,000 records · images are not stored in the event log."}</p></div><button type="button" className="button button--outline" onClick={() => void refreshEvents()}><RefreshCw size={14}/> Refresh</button></div>
        <div className="history-table-wrap"><table className="history-table"><thead><tr><th>TIME</th><th>SOURCE</th><th>IMAGE / FRAME</th><th>SCORE</th><th>DECISION</th><th>INFERENCE</th></tr></thead><tbody>{events.length ? events.map((event) => <tr key={event.id}><td><span className="table-time"><Clock3 size={13}/>{timeLabel(event.timestamp)}</span></td><td><span className="source-tag">{event.source_id.replace("dataset-replay", "replay")}</span></td><td className="filename-cell" title={event.filename || event.frame_id || "image"}>{event.filename || event.frame_id || "image"}</td><td className="score-cell">{event.score.toFixed(4)}</td><td><span className={`decision-tag ${event.is_anomaly ? "tag-alert" : "tag-pass"}`}>{event.is_anomaly ? "Review required" : "Below threshold"}</span></td><td>{event.inference_ms.toFixed(1)} ms</td></tr>) : <tr><td colSpan={6} className="empty-row"><div><History size={18}/><span>No inspections yet</span><small>Your first result will appear here.</small></div></td></tr>}</tbody></table></div>
      </section>

      <section className="scope-ribbon"><div className="scope-ribbon-icon"><ArrowDown size={17}/></div><div><b>A controlled study, not an automatic reject system.</b><p>New cameras, lighting, products, and defect rates need independent validation and fresh calibration before operational use.</p></div><a href="#/dataset">Dataset limits <ArrowUpRight size={14}/></a></section>
      <div className="benchmark-footnote">Benchmark metrics use the frozen MVTec AD bottle test set (83 images). Performance is not a production guarantee.</div>
    </div>
  );
}
