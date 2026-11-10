import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./index.css";
import { SessionProvider } from "./lib/session";
import Layout from "./components/Layout";
import Landing from "./pages/Landing";
import Projects from "./pages/Projects";
import OverviewPage from "./pages/Overview";
import SourcesPage from "./pages/Sources";
import EvidencePage from "./pages/Evidence";
import ClaimsPage from "./pages/Claims";
import GapsPage from "./pages/Gaps";
import ReviewPage from "./pages/Review";
import HandoverPage from "./pages/Handover";
import AuditPage from "./pages/Audit";
import NotFound from "./pages/NotFound";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/p/:pid" element={<Layout />}>
            <Route index element={<OverviewPage />} />
            <Route path="sources" element={<SourcesPage />} />
            <Route path="evidence" element={<EvidencePage />} />
            <Route path="claims" element={<ClaimsPage />} />
            <Route path="gaps" element={<GapsPage />} />
            <Route path="review" element={<ReviewPage />} />
            <Route path="handover" element={<HandoverPage />} />
            <Route path="audit" element={<AuditPage />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  </React.StrictMode>,
);
