import { TurnaroundGenerator } from "./components/TurnaroundGenerator";

export default function App() {
  return (
    <main className="studio-shell current-workflow-only">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true"><span>AS</span></div>
          <div>
            <p className="eyebrow">LOCAL ART ASSET SUPPLY LAB</p>
            <h1>AssetsStudio</h1>
          </div>
        </div>
        <div className="topbar-meta">
          <span className="build-pill">CURRENT MODULAR WORKFLOW</span>
          <small>StyleProfile → Style Seed → Actor Core → Slot Asset → Recipe</small>
        </div>
      </header>
      <TurnaroundGenerator />
    </main>
  );
}
