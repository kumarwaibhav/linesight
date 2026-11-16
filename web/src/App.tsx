import { useEffect, useState } from "react";
import { ArrowRight, BookOpen, ChevronRight, FileText, Layers3 } from "lucide-react";
import { BrandMark, StatusBadge } from "./components";
import { ArchitecturePage } from "./Architecture";
import { DatasetPage } from "./Dataset";
import { Workspace } from "./Workspace";

type Page = "workspace" | "architecture" | "dataset";
const pageFromHash = (): Page => {
  const path = window.location.hash.replace(/^#\/?/, "").split("/")[0];
  return path === "architecture" || path === "dataset" ? path : "workspace";
};

// Hash navigation keeps new content shareable without changing the existing FastAPI routes.
export default function App() {
  const [page, setPage] = useState<Page>(pageFromHash);
  const [serviceReady, setServiceReady] = useState<boolean | null>(null);
  useEffect(() => {
    const update = () => setPage(pageFromHash());
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  const pageTitle = page === "architecture" ? "System architecture" : page === "dataset" ? "Dataset profile" : "Inspection workspace";

  return (
    <div className="site-shell">
      <header className="topbar">
        <BrandMark/>
        <div className="topbar-divider"/>
        <div className="workspace-title"><span className="workspace-pulse"/>{pageTitle}</div>
        <nav className="main-nav" aria-label="Primary navigation">
          <a href="#/" className={page === "workspace" ? "nav-active" : ""}>Workspace</a>
          <a href="#/architecture" className={page === "architecture" ? "nav-active" : ""}>Architecture</a>
          <a href="#/dataset" className={page === "dataset" ? "nav-active" : ""}>Dataset</a>
        </nav>
        <div className="topbar-actions"><StatusBadge ready={serviceReady}/><a className="docs-link" href="/docs">API & docs <ChevronRight size={14}/></a></div>
      </header>
      <main id="main-content" tabIndex={-1}>
        {page === "workspace" && <Workspace onStatus={setServiceReady}/>}
        {page === "architecture" && <ArchitecturePage/>}
        {page === "dataset" && <DatasetPage/>}
      </main>
      <footer className="site-footer"><div className="footer-main"><BrandMark compact/><span>Visual anomaly detection for a controlled bottle view.</span></div><div className="footer-links"><a href="#/architecture"><Layers3 size={13}/> Architecture</a><a href="#/dataset"><BookOpen size={13}/> Dataset</a><a href="/docs"><FileText size={13}/> API reference</a></div><div className="footer-credit">Built by <a href="mailto:kwa.waibhav@gmail.com">Kumar Waibhav Akshat</a><span>·</span><span>Software: MIT · Dataset: non-commercial</span></div></footer>
      <a className="skip-link" href="#main-content">Skip to content <ArrowRight size={14}/></a>
    </div>
  );
}
