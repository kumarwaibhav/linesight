import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowUpRight, Check, CircleHelp, Code2, FileImage, HeartPulse, LockKeyhole, RefreshCw, Upload } from "lucide-react";
import { apiRequest, type HealthResponse } from "./api";
import { BrandMark, StatusBadge } from "./components";

interface SchemaResponse { paths?: Record<string, Record<string, { summary?: string; description?: string; responses?: Record<string, unknown> }>> }

// This page documents and exercises the same-origin API; it does not load third-party scripts.
export default function ApiDocs() {
  const [ready, setReady] = useState<boolean | null>(null);
  const [endpoints, setEndpoints] = useState<SchemaResponse["paths"]>(undefined);
  const [output, setOutput] = useState("Choose an endpoint to inspect its response.");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void apiRequest<SchemaResponse>("/openapi.json").then((schema) => setEndpoints(schema.paths ?? {})).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not read OpenAPI schema."));
    void apiRequest<HealthResponse>("/api/health").then((health) => setReady(health.model_loaded)).catch(() => setReady(false));
  }, []);

  const showRequest = async (path: string, options?: RequestInit) => {
    setWorking(true); setError(""); setOutput("Request in progress…");
    try {
      const response = await fetch(path, { ...options, cache: "no-store" });
      const body = await response.json();
      if (Array.isArray(body.heatmap)) body.heatmap = `[${body.heatmap.length} × ${body.heatmap[0]?.length ?? 0} coarse patch scores omitted]`;
      setOutput(`HTTP ${response.status}\n${JSON.stringify(body, null, 2)}`);
      if (!response.ok) setError(typeof body.detail === "string" ? body.detail : "The request could not be processed.");
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "The request failed.";
      setOutput(message); setError(message);
    } finally { setWorking(false); }
  };

  const inspectFile = (file?: File) => {
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
      setError("Choose a PNG, JPEG, or WebP image."); setOutput("Upload not sent. Select a supported image file."); return;
    }
    const form = new FormData(); form.append("file", file); form.append("source_id", "api-reference");
    void showRequest("/api/inspect", { method: "POST", body: form });
  };

  const list = Object.entries(endpoints ?? {}).flatMap(([path, methods]) => Object.entries(methods).map(([method, operation]) => ({ path, method, operation })));

  return (
    <div className="api-page">
      <header className="topbar docs-topbar"><BrandMark/><div className="topbar-divider"/><div className="workspace-title">API reference</div><nav className="main-nav docs-nav" aria-label="Documentation navigation"><a href="/#/architecture">Architecture</a><a href="/#/dataset">Dataset</a><a href="/docs" className="nav-active">API reference</a></nav><div className="topbar-actions"><StatusBadge ready={ready}/><a className="docs-link" href="/"><ArrowLeft size={14}/> Workspace</a></div></header>
      <main className="api-main">
        <section className="api-intro"><div><span className="kicker"><Code2 size={14}/> LOCAL INSPECTION SERVICE</span><h1>Clear inputs.<br/><em>Traceable outputs.</em></h1><p>Use the same-origin API to inspect an image, read model metadata, and review the bounded local decision log.</p><div className="api-intro-actions"><a className="button button--primary" href="/openapi.json" target="_blank" rel="noreferrer">OpenAPI JSON <ArrowUpRight size={14}/></a><button className="button button--outline" type="button" disabled={working} onClick={() => void showRequest("/api/health")}><HeartPulse size={15}/> Check service health</button></div></div><div className="api-intro-art"><div className="api-orbit orbit-one"/><div className="api-orbit orbit-two"/><div className="api-code-tile"><span>POST</span><b>/api/inspect</b><small>image → score → review flag</small></div><div className="api-check"><Check/></div></div></section>

        <section className="api-caps-grid"><article><div><Upload/></div><b>Same-origin only</b><span>No API keys or third-party scripts</span></article><article><div><FileImage/></div><b>Bounded input</b><span>PNG · JPEG · WebP · up to 8 MiB</span></article><article><div><LockKeyhole/></div><b>CPU-first model</b><span>One inspection in flight at a time</span></article><article><div><CircleHelp/></div><b>Honest score</b><span>Anomaly score is not a probability</span></article></section>

        <div className="api-layout">
          <section className="api-card panel-card"><div className="panel-head"><div><span className="panel-index">TRY IT SAFELY</span><h2>Inspect an image</h2></div><span className="api-method-pill">POST</span></div><p className="api-card-intro">Select a bottle image to send it to <code>/api/inspect</code>. The response includes its score, frozen threshold, decision, coarse evidence, and measured model inference time.</p><div className="try-image-panel"><input ref={fileRef} className="visually-hidden" type="file" accept="image/png,image/jpeg,image/webp" aria-label="Select an image to inspect" onChange={(event) => { inspectFile(event.target.files?.[0]); event.currentTarget.value = ""; }}/><div className="try-drop-icon"><FileImage/></div><div><b>Choose an image file</b><span>PNG, JPEG, or WebP · maximum 8 MiB / 4 MP</span></div><button className="button button--primary" type="button" disabled={working} onClick={() => fileRef.current?.click()}><Upload size={14}/> Browse</button></div><button className="json-refresh" type="button" disabled={working} onClick={() => void showRequest("/api/health")}><RefreshCw size={13}/> GET /api/health</button><div className={`response-header ${error ? "response-header--error" : ""}`}><span><i/>{working ? "REQUEST RUNNING" : error ? "REQUEST NEEDS ATTENTION" : "LATEST RESPONSE"}</span><span>JSON</span></div><pre className="api-response" aria-live="polite">{output}</pre>{error && <p className="api-error" role="alert">{error}</p>}</section>

          <aside className="api-aside"><section className="api-card panel-card"><div className="panel-head"><div><span className="panel-index">CONTRACTS</span><h2>Endpoints</h2></div><span className="endpoint-count">{list.length || "…"}</span></div><p className="api-card-intro">Generated from the service's live OpenAPI schema. GET routes can be tried without sending image data.</p><div className="endpoint-list">{list.length ? list.map(({ path, method, operation }) => <article className="endpoint-row" key={`${method}-${path}`}><span className={`endpoint-verb verb-${method}`}>{method.toUpperCase()}</span><div><code>{path}</code><p>{operation.summary || operation.description || "LineSight service endpoint."}</p>{method.toLowerCase() === "get" && !path.includes("{") && <button type="button" className="endpoint-try" disabled={working} onClick={() => void showRequest(path)}>Try request <ArrowUpRight size={12}/></button>}</div></article>) : <p className="endpoint-loading">{error || "Loading the current OpenAPI schema…"}</p>}</div></section>
            <section className="api-callout"><span className="kicker">DECISION SEMANTICS</span><h3>Higher means more unusual.</h3><p>LineSight flags an image only when <code>score &gt; threshold</code>. The score ranks unusual appearance; it is not calibrated defect confidence.</p><a href="/#/architecture">Read the architecture <ArrowUpRight size={14}/></a></section></aside>
        </div>

        <section className="api-limits"><div><LockKeyhole size={16}/><b>Request limits</b></div><span>Max 8 MiB</span><span>Max 4 megapixels</span><span>Max 4096 px edge</span><span>Min 32 px edge</span><span>Four bounded request slots</span></section>
        <p className="api-scope">Self-hosted reference. Images are processed by this service; the event log retains inspection metadata, not uploaded image files. Use a separately validated environment for any operational workflow.</p>
      </main>
      <footer className="site-footer"><div className="footer-main"><BrandMark compact/><span>LineSight · local inspection API</span></div><div className="footer-credit"><a href="/#/dataset">Dataset terms</a><span>·</span><a href="/#/architecture">System architecture</a></div></footer>
    </div>
  );
}
