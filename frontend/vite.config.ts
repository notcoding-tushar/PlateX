import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ". ", "");
  const proxy = { "/api": env.PLATEX_API_PROXY_TARGET || "http://127.0.0.1:8000" };
  return {
  plugins: [react()],
  server: { proxy },
  preview: { proxy },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom/client"],
        },
      },
    },
  },
  };
});
