import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

// Keep the existing API origin during development while exposing the docs entry at /docs.
const projectRoot = fileURLToPath(new URL(".", import.meta.url));

function docsAlias(): Plugin {
  return {
    name: "linesight-docs-alias",
    configureServer(server) {
      server.middlewares.use((request, _response, next) => {
        if (request.url === "/docs" || request.url === "/docs/") request.url = "/api.html";
        next();
      });
    },
  };
}

export default defineConfig({
  root: resolve(projectRoot, "web"),
  base: "/",
  plugins: [react(), docsAlias()],
  build: {
    outDir: resolve(projectRoot, "web/dist"),
    emptyOutDir: true,
    assetsDir: "assets",
    rollupOptions: {
      input: {
        main: resolve(projectRoot, "web/index.html"),
        api: resolve(projectRoot, "web/api.html"),
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 4173,
    strictPort: true,
    allowedHosts: [".sg2.manus.computer"],
    proxy: {
      "^/api(?:/|$)": "http://127.0.0.1:8000",
      "/openapi.json": "http://127.0.0.1:8000",
    },
  },
});
