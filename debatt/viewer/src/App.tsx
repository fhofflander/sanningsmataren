// App shell: brand header + routes. The per-debate experience lives in
// components/DebateView.tsx; data loading in lib/data.ts.

import { Link, Navigate, Route, Routes } from "react-router-dom";
import { DebatePage } from "./routes/DebatePage";
import { GranskaPage } from "./routes/GranskaPage";
import { IndexPage } from "./routes/IndexPage";

export default function App() {
  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>
            <Link to="/" className="brand-link">
              Sanningsmätaren <span className="header-module">Debattanalys</span>
            </Link>
          </h1>
        </div>
        <nav className="header-nav">
          <Link to="/granska">Förhandsgranska</Link>
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<IndexPage />} />
        <Route path="/debatt/:id" element={<DebatePage />} />
        <Route path="/granska" element={<GranskaPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
