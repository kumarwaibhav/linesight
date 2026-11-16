import { motion } from "framer-motion";
import { ArrowUpRight, Check, CircleHelp, ScanLine } from "lucide-react";
import type { InspectionResult } from "./api";

// The small custom mark echoes a bottle inside a focused inspection aperture.
export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <a className={`brand ${compact ? "brand--compact" : ""}`} href="/" aria-label="LineSight workspace">
      <span className="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 48 48" fill="none">
          <path d="M9 17V9h8M39 17V9h-8M9 31v8h8M39 31v8h-8" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
          <path d="M20 13h8v6l4 5v11a2 2 0 0 1-2 2H18a2 2 0 0 1-2-2V24l4-5v-6Z" fill="#D8F16C" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
          <path d="M20 13h8M17 27h14" stroke="#0C3D32" strokeWidth="1.7" strokeLinecap="round" />
        </svg>
      </span>
      <span className="brand-word">LineSight<span className="brand-period">.</span></span>
    </a>
  );
}

export function StatusBadge({ ready, label }: { ready: boolean | null; label?: string }) {
  const text = label ?? (ready === null ? "Connecting" : ready ? "Model online" : "Model unavailable");
  return <span className={`status-badge ${ready ? "is-ready" : ready === false ? "is-offline" : "is-loading"}`}><i />{text}</span>;
}

// The decorative stage is native SVG, so it stays sharp without an external asset request.
export function BottleScene({ active = false }: { active?: boolean }) {
  return (
    <div className={`bottle-scene ${active ? "is-active" : ""}`} aria-hidden="true">
      <div className="scene-halo" />
      <div className="scene-grid" />
      <div className="scan-orbit orbit-a" /><div className="scan-orbit orbit-b" />
      <motion.svg className="bottle-art" viewBox="0 0 260 360" initial={{ y: 7, rotateY: -9 }} animate={{ y: [7, -2, 7], rotateY: [-9, -5, -9] }} transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}>
        <defs>
          <linearGradient id="glass" x1="0" x2="1"><stop stopColor="#F5F7E7" stopOpacity=".22"/><stop offset=".38" stopColor="#C4E6CC" stopOpacity=".82"/><stop offset=".72" stopColor="#6DAB91" stopOpacity=".56"/><stop offset="1" stopColor="#F6F8E7" stopOpacity=".27"/></linearGradient>
          <linearGradient id="label" x1="0" x2="1"><stop stopColor="#E8F484"/><stop offset="1" stopColor="#BDEB79"/></linearGradient>
          <filter id="glow"><feGaussianBlur stdDeviation="7" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        </defs>
        <ellipse cx="130" cy="326" rx="77" ry="16" fill="#011D17" opacity=".34"/>
        <path d="M96 30c0-9 7-16 16-16h36c9 0 16 7 16 16v24l14 19c7 9 11 21 11 33v176c0 15-12 27-27 27H98c-15 0-27-12-27-27V106c0-12 4-24 11-33l14-19V30Z" fill="url(#glass)" stroke="#D8F2D9" strokeWidth="2.2"/>
        <path d="M96 54h68M81 95c19 9 80 9 98 0" stroke="#ECF8E9" strokeOpacity=".7" strokeWidth="2"/>
        <path d="M99 17h42v27H99z" fill="#C9E867" stroke="#E4F2C1" strokeWidth="2"/>
        <path d="M89 132c24-8 59-8 83 0v80H89z" fill="url(#label)" opacity=".93"/>
        <path d="M104 158h53M104 170h41" stroke="#28634E" strokeWidth="3" strokeLinecap="round" opacity=".75"/>
        <path d="M104 191h28" stroke="#4F765B" strokeWidth="2" strokeLinecap="round"/>
        <path d="M87 108c-3 18-3 123 0 177" stroke="#F9FFF1" strokeOpacity=".58" strokeWidth="5" strokeLinecap="round"/>
        <path d="M176 112c4 40 4 124 1 168" stroke="#4B8A74" strokeOpacity=".37" strokeWidth="4" strokeLinecap="round"/>
        <circle cx="131" cy="235" r="17" fill="#D7F36B" filter="url(#glow)" opacity=".75"/>
        <path d="M128 226v18m-5-13c1-3 3-4 7-4 4 0 7 2 7 5s-3 5-7 5-7 2-7 5 3 5 7 5 6-2 7-4" stroke="#134A38" strokeWidth="2.2" strokeLinecap="round"/>
      </motion.svg>
      <div className="scene-label label-top"><span className="scene-pulse"/> FIXED VIEW <b>192 × 192</b></div>
      <div className="scene-label label-bottom"><ScanLine size={13}/> REFERENCE / BOTTLE <span className="scene-value">READY</span></div>
      <div className="scene-crosshair crosshair-left"/><div className="scene-crosshair crosshair-right"/>
    </div>
  );
}

export function EmptyInspection() {
  return (
    <div className="empty-inspection">
      <BottleScene />
      <div className="empty-copy"><span className="kicker"><CircleHelp size={13}/> START WITH A CONTROLLED VIEW</span><h3>One image.<br/>A closer look.</h3><p>Drop a bottle image here, choose a file, or explore held-out benchmark samples.</p><small>PNG · JPEG · WebP · up to 8 MiB / 4 MP</small></div>
    </div>
  );
}

export function EvidenceOverlay({ result }: { result: InspectionResult | null }) {
  if (!result?.heatmap?.length || !result.heatmap[0]?.length) return null;
  const values = result.heatmap.flat().filter(Number.isFinite);
  const min = Math.min(...values); const max = Math.max(...values);
  const columns = result.heatmap[0].length; const rows = result.heatmap.length;
  return (
    <svg className="evidence-overlay" viewBox={`0 0 ${columns} ${rows}`} preserveAspectRatio="none" role="img" aria-label="Coarse normalized patch evidence overlay. Bright regions indicate unusual visual evidence, not a pixel-level defect mask.">
      <title>Coarse patch evidence, not segmentation</title>
      {result.heatmap.flatMap((row, y) => row.map((value, x) => {
        const normalized = max > min ? (value - min) / (max - min) : 0;
        return normalized < 0.5 ? null : <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" fill="#D9F36C" opacity={0.18 + normalized * 0.58} />;
      }))}
    </svg>
  );
}

export function ScoreScale({ score, threshold, anomaly }: { score: number | null; threshold: number | null; anomaly?: boolean }) {
  const safeScore = score === null ? 0 : Math.max(0, Math.min(1, score));
  const safeThreshold = threshold === null ? 0 : Math.max(0, Math.min(1, threshold));
  return (
    <div className="score-scale" role="img" aria-label={score === null ? "No score available" : `Anomaly score ${score.toFixed(4)}. Calibrated threshold ${threshold?.toFixed(4) ?? "not available"}.`}>
      <div className="score-scale-track"><motion.div className={`score-scale-fill ${anomaly ? "is-anomaly" : ""}`} animate={{ width: `${safeScore * 100}%` }} transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }} /><span className="threshold-tick" style={{ left: `${safeThreshold * 100}%` }} /></div>
      <div className="score-scale-labels"><span>Closer to normal</span><span>More unusual</span></div>
    </div>
  );
}

export function SignalStat({ value, label, note, accent = false }: { value: string; label: string; note: string; accent?: boolean }) {
  return <motion.article className={`signal-stat ${accent ? "signal-stat--accent" : ""}`} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}><span className="signal-label">{label}</span><strong>{value}</strong><small>{note}</small><ArrowUpRight className="signal-arrow" size={15}/></motion.article>;
}

export function PassChip({ children }: { children: React.ReactNode }) {
  return <span className="pass-chip"><Check size={13}/>{children}</span>;
}
