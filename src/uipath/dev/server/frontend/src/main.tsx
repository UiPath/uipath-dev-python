import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { initToken, installAuthenticatedFetch } from "./api/token";
import "./styles/global.css";

initToken();
installAuthenticatedFetch();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
