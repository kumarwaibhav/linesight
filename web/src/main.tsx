import React from "react";
import { createRoot } from "react-dom/client";
import { MotionConfig } from "framer-motion";
import "@fontsource-variable/manrope";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./styles.css";
import App from "./App";

// Mount the accessible application at Vite's static root element.
const root = document.getElementById("root");
if (!root) throw new Error("Missing #root mount point.");
createRoot(root).render(<MotionConfig reducedMotion="user"><React.StrictMode><App/></React.StrictMode></MotionConfig>);
