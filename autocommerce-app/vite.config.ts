import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

/**
 * Configuration de livraison du frontend clinique.
 * Aucun collecteur de diagnostic, runtime de prévisualisation ni marqueur de
 * localisation de source n’est injecté dans le bundle produit.
 */
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "client", "src"),
      "@shared": path.resolve(import.meta.dirname, "shared"),
      "@assets": path.resolve(import.meta.dirname, "attached_assets"),
    },
  },
  envDir: path.resolve(import.meta.dirname),
  root: path.resolve(import.meta.dirname, "client"),
  build: {
    outDir: path.resolve(import.meta.dirname, "dist", "public"),
    emptyOutDir: true,
    chunkSizeWarningLimit: 500,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ["react", "react-dom", "wouter"],
          ui: ["lucide-react", "sonner"],
          charts: ["recharts"],
        },
        chunkFileNames: "assets/[name]-[hash].js",
        entryFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash].[ext]",
      },
    },
  },
  server: {
    port: 3000,
    strictPort: false,
    host: true,
    proxy: {
      "/api": {
        target: process.env.AESTHETIC_API_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
    allowedHosts: [
      ".manuspre.computer",
      ".manus.computer",
      ".manus-asia.computer",
      ".manuscomputer.ai",
      ".manusvm.computer",
      "localhost",
      "127.0.0.1",
    ],
    fs: {
      strict: true,
      deny: ["**/.*"],
    },
  },
});
