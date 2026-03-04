import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiPort = process.env.VITE_API_PORT || "8001";
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || `http://127.0.0.1:${apiPort}`;

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) {
            return;
          }
          if (id.includes("/node_modules/react/") || id.includes("/node_modules/react-dom/") || id.includes("/node_modules/react-router-dom/")) {
            return "react_vendor";
          }
          if (id.includes("/node_modules/@tanstack/react-query/")) {
            return "query_vendor";
          }
          if (id.includes("/node_modules/axios/")) {
            return "network_vendor";
          }
          if (id.includes("/node_modules/@ant-design/icons/")) {
            return "antd_icons";
          }
          if (id.includes("/node_modules/antd/")) {
            return "antd_core";
          }
          if (id.includes("/node_modules/rc-") || id.includes("/node_modules/@rc-component/")) {
            return "antd_rc";
          }
          if (id.includes("/node_modules/dayjs/")) {
            return "dayjs_vendor";
          }
          return;
        }
      }
    }
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true
      }
    }
  }
});
