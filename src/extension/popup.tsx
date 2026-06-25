import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ExtensionPopup } from "./ExtensionPopup";
import "../index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ExtensionPopup />
  </StrictMode>,
);
