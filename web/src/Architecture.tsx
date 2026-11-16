import { motion } from "framer-motion";
import { Activity, ArrowDown, ArrowRight, Camera, Database, Eye, FileImage, Gauge, Layers3, LockKeyhole, ScanSearch, ShieldCheck, Trees } from "lucide-react";

const phases = [
  { n: "01", icon: Database, title: "Build a trusted baseline", text: "Only defect-free fit images teach the normal visual reference. Source paths, roles, and hashes keep the split traceable.", tag: "125 normal · fit" },
  { n: "02", icon: Layers3, title: "Describe local change", text: "Appearance and gradient features summarize each image as 144 spatial patches. No defect labels are used to fit the detector.", tag: "12 × 12 patches" },
  { n: "03", icon: Trees, title: "Isolate the unusual", text: "A CPU-friendly Isolation Forest scores patch patterns. Shorter paths indicate patterns that differ more from normal training images.", tag: "192 trees · CPU" },
  { n: "04", icon: Gauge, title: "Calibrate, then freeze", text: "An independent set of normal bottles sets the score threshold. The model is frozen before its official test evaluation.", tag: "42 calibration normals" },
];

// Small nodes expose the separate research and online-serving paths at a glance.
export function ArchitecturePage() {
  return (
    <motion.div className="content-page" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
      <section className="page-hero architecture-hero">
        <div className="page-hero-copy"><span className="kicker"><ScanSearch size={14}/> SYSTEM MAP</span><h1>From normal images<br/><em>to a human review.</em></h1><p>One frozen detector connects an auditable training path to the same bounded API used by upload, camera samples, and benchmark replay.</p>
          <div className="hero-tags"><span>Offline model development</span><span>Online CPU inference</span><span>Review, never auto-reject</span></div>
        </div>
        <div className="architecture-orbit" role="img" aria-label="Architecture overview: bottle dataset flows to normal reference, Isolation Forest, calibrated threshold, and human review.">
          <div className="orbit-line orbit-line-a"/><div className="orbit-line orbit-line-b"/>
          <div className="orbit-node node-source"><Database/><small>DATA</small></div><div className="orbit-node node-features"><Layers3/><small>PATCHES</small></div><div className="orbit-node node-model"><Trees/><small>FOREST</small></div><div className="orbit-node node-review"><Eye/><small>REVIEW</small></div>
          <div className="orbit-center"><span>LineSight</span><b>one clear path</b><i/></div>
          <span className="orbit-caption caption-one">learn normal</span><span className="orbit-caption caption-two">score unusual</span>
        </div>
      </section>

      <section className="section-heading"><div><span className="kicker">DEVELOPMENT PATH</span><h2>Four deliberate steps.</h2></div><p>The untouched test partition stays out of model selection and threshold setting.</p></section>
      <div className="process-grid">
        {phases.map((phase, index) => <motion.article className="process-card" key={phase.n} initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.07 }}>
          <div className="process-top"><span>{phase.n}</span><phase.icon size={19}/></div><h3>{phase.title}</h3><p>{phase.text}</p><small>{phase.tag}</small>
        </motion.article>)}
      </div>

      <section className="live-path-card">
        <div className="live-path-heading"><div><span className="kicker"><Activity size={13}/> ONLINE INSPECTION</span><h2>Every source reaches the same model.</h2></div><span className="live-note"><i/> Same-origin API</span></div>
        <div className="live-pipeline" role="img" aria-label="Upload, sampled camera, or benchmark replay flows through input checks to the frozen detector; results show score, threshold, coarse evidence and human review flag; event metadata is retained locally.">
          <div className="pipeline-source"><div><FileImage/><span>Upload</span></div><div><Camera/><span>Sampled camera</span></div><div><Database/><span>Dataset replay</span></div></div>
          <div className="pipeline-arrow"><ArrowRight/></div><div className="pipeline-step"><ShieldCheck/><b>Validate</b><small>size · format · pixels</small></div><div className="pipeline-arrow"><ArrowRight/></div><div className="pipeline-step pipeline-step--model"><Trees/><b>Frozen forest</b><small>score + patch evidence</small></div><div className="pipeline-arrow"><ArrowRight/></div><div className="pipeline-step"><Eye/><b>Human review</b><small>local event log</small></div>
        </div>
        <div className="pipeline-boundary"><LockKeyhole size={14}/><span>The score is not a probability. Camera frames are sampled; factory timing and reject control are not validated.</span></div>
      </section>

      <section className="two-column-note"><article className="note-card note-card--mint"><span className="kicker">DATA BOUNDARY</span><h3>Separate fitting from proof.</h3><p>Fit, tune, calibration, and official test roles stay distinct. Test defects measure the frozen model only.</p><a href="#/dataset">Explore the dataset <ArrowRight size={15}/></a></article><article className="note-card note-card--dark"><span className="kicker">OPERATING BOUNDARY</span><h3>Controlled view, honest limits.</h3><p>New products, cameras, lighting, or backgrounds need representative validation and fresh calibration before operational use.</p><a href="/docs">Open the API & docs <ArrowRight size={15}/></a></article></section>

      <section className="architecture-foot"><div className="architecture-foot-icon"><ArrowDown/></div><div><b>Useful next steps</b><p>Review the model card, deployment guide, and technical report in the repository's <code>docs/</code> and <code>reports/</code> folders.</p></div></section>
    </motion.div>
  );
}
