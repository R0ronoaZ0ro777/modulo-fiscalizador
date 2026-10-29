import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, /api y /ws se reenvían al backend (evita CORS y mantiene el mismo origen).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
