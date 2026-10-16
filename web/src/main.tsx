import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles/index.css";

// ?demo=1 / ?demo=0 toggles fabricated demo data (handy for screenshots / E2E without API)
const dq = new URLSearchParams(location.search).get("demo");
if (dq === "1" || dq === "0") localStorage.setItem("labledger.demo", dq);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
