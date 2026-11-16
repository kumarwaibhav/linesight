import React from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/manrope";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./styles.css";
import ApiDocs from "./ApiDocs";

// Mount the interactive API reference into its dedicated Vite entry.
const root = document.getElementById("root");
if (!root) throw new Error("Missing #root mount point.");
createRoot(root).render(<React.StrictMode><ApiDocs/></React.StrictMode>);
