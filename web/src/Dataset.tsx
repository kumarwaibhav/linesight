import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, BadgeCheck, Boxes, FileCheck2, Fingerprint, Image, Scale, ShieldCheck } from "lucide-react";

const splitRows = [
  { name: "Fit", value: 125, detail: "Learn the normal reference", tone: "fit" },
  { name: "Tune", value: 42, detail: "Choose a candidate", tone: "tune" },
  { name: "Calibration", value: 42, detail: "Set the decision threshold", tone: "calibration" },
  { name: "Official test", value: 83, detail: "20 normal + 63 defects", tone: "test" },
];
const defectGroups = [{ name: "Large break", value: 20, color: "#0C3D32" }, { name: "Small break", value: 22, color: "#A9CC4B" }, { name: "Contamination", value: 21, color: "#D87955" }];

// The split visualization represents all 292 source images; widths are derived from the documented counts.
export function DatasetPage() {
  return (
    <motion.div className="content-page" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
      <section className="page-hero dataset-hero">
        <div className="page-hero-copy"><span className="kicker"><Boxes size={14}/> DATASET PROFILE</span><h1>One category.<br/><em>Clear boundaries.</em></h1><p>LineSight uses MVTec AD's bottle category to study image-level anomaly detection under a controlled view. The benchmark is evidence for a research demo—not a proxy for every factory line.</p><div className="dataset-hero-stats"><div><b>292</b><span>source images</span></div><div><b>229</b><span>normal bottles</span></div><div><b>63</b><span>defective bottles</span></div></div></div>
        <div className="dataset-art" role="img" aria-label="Illustration of normal bottle images forming a reference, with a smaller set of anomalous bottles reserved for final evaluation.">
          <div className="dataset-art-glow"/><div className="dataset-bottle bottle-a"/><div className="dataset-bottle bottle-b"/><div className="dataset-bottle bottle-c"/><div className="dataset-dots dots-one"/><div className="dataset-dots dots-two"/><div className="dataset-art-label"><Fingerprint size={15}/><span>traceable split</span><b>seed 42</b></div>
        </div>
      </section>

      <section className="section-heading"><div><span className="kicker">SPLIT DESIGN</span><h2>Each image has a job.</h2></div><p>Source roles never overlap. Official test images remain untouched until the model and threshold are frozen.</p></section>
      <section className="dataset-split-card panel-card">
        <div className="split-card-heading"><div><span className="kicker">292 SOURCE IMAGES</span><h3>Normal-only learning · held-out test</h3></div><span className="split-total">229 normal <i/> 63 anomalous</span></div>
        <div className="split-bar" aria-label="Image split: 125 fit normals, 42 tune normals, 42 calibration normals, and 83 official test images, including 20 normal and 63 anomalous.">
          {splitRows.map((row) => <div key={row.name} className={`split-segment split-${row.tone}`} style={{ width: `${row.value / 292 * 100}%` }}><span>{row.value}</span></div>)}
        </div>
        <div className="split-legend">{splitRows.map((row) => <div key={row.name}><i className={`legend-${row.tone}`}/><b>{row.name}</b><span>{row.value}</span><small>{row.detail}</small></div>)}</div>
        <div className="test-detail"><div className="test-detail-heading"><span>OFFICIAL TEST · 83 IMAGES</span><small>20 normal + 63 anomalous</small></div><div className="defect-bars">{defectGroups.map((group) => <div key={group.name} className="defect-bar-row"><span>{group.name}</span><div><i style={{ width: `${group.value / 63 * 100}%`, background: group.color }}/></div><b>{group.value}</b></div>)}</div></div>
      </section>

      <section className="dataset-facts-grid">
        <article className="fact-card"><div className="fact-icon"><Image/></div><span className="kicker">TASK</span><h3>Image-level review flag</h3><p>The model scores the whole image. Defect names are evaluation groups—not classes that it learns to identify.</p></article>
        <article className="fact-card"><div className="fact-icon fact-icon--lime"><FileCheck2/></div><span className="kicker">TRACEABILITY</span><h3>Manifest + hashes</h3><p>Paths, split roles, labels, defect types, and SHA-256 image hashes live in <code>data/manifest.csv</code>.</p></article>
        <article className="fact-card"><div className="fact-icon fact-icon--coral"><ShieldCheck/></div><span className="kicker">LEAKAGE CONTROL</span><h3>Test stays held out</h3><p>Calibration uses normal images only; official test defects do not fit the model, select a candidate, or set its threshold.</p></article>
      </section>

      <section className="provenance-card"><div className="provenance-icon"><BadgeCheck/></div><div className="provenance-copy"><span className="kicker">PROVENANCE & TERMS</span><h2>Know the source. Respect the license.</h2><p>The prepared snapshot was acquired from the XavierZXY/MvT-tar mirror at a pinned revision and checked against a recorded archive checksum. MVTec AD remains the original dataset source and rights holder.</p><div className="provenance-tags"><span><Fingerprint size={14}/> Seed 42 split</span><span><FileCheck2 size={14}/> 292 verified images</span><span><Scale size={14}/> CC BY-NC-SA 4.0</span></div></div><div className="license-callout"><AlertTriangle size={17}/><b>Non-commercial dataset</b><p>MVTec AD excludes commercial use. The project's MIT software license does not change dataset terms.</p><a href="https://www.mvtec.com/research-teaching/datasets/mvtec-ad" target="_blank" rel="noreferrer">Official dataset source <ArrowRight size={14}/></a></div></section>

      <section className="dataset-bottom"><div><span className="kicker">LIMITS TO KEEP IN VIEW</span><h2>A benchmark is a starting point.</h2><p>The test set contains only 20 normal bottles, so each false alarm changes its observed rate by five percentage points. Real production has different cameras, lighting, product mixes, and defect prevalence. Validate independently before any operational decision.</p></div><a href="#/architecture" className="button button--light">View the architecture <ArrowRight size={15}/></a></section>
    </motion.div>
  );
}
