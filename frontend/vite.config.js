import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "path";
import fs from "fs";

const FRAPPE_BACKEND = "https://test1-erp.batchprojects.com";
// Local bp-gateway-dev stack (Caddy on 8080 → gateway:8001 → this same
// Frappe backend). /api/* must go through here now that
// bp_gateway_shared_secret is live: gateway_guard.py's verify_gateway_request()
// rejects any batch_projects API call missing a valid X-BP-Gateway-Sig, and
// only the gateway's own proxy.Director signs that header. Everything else
// (login/logout/app/assets/files/private/storage, socket.io) isn't
// gateway-guarded at all, so it stays pointed straight at Frappe.
const GATEWAY_BACKEND = "http://127.0.0.1:8080";

// Billing (checkout/plans/subscriptions/portal) genuinely needs bp-license's
// Django backend, which can't run in every dev environment — mocked here.
// Everything else under /v1 (session bootstrap, realtime) is proxied to the
// real local bp-gateway-dev stack below instead of being mocked, so dev
// testing exercises the actual gateway (auth, signing, SSE) not a fake.
//
// IMPORTANT: registered via configureServer's direct (non-returned)
// server.middlewares.use() calls, which Vite runs BEFORE its own internal
// middlewares (including the `proxy` option below) — this is the real Vite
// plugin API. The previous version of this file used a `setupMiddlewares`
// key inside `server: {...}`, which is a webpack-dev-server option, not a
// Vite one — Vite silently ignored it, so none of these mocks (including
// the old session-bootstrap one) ever actually ran, and bootstrapBridge()
// always fell through to its "no gateway JWT returned" rejection, which
// meant connectRealtime() was never called in local dev. Found 2026-07-26
// while verifying the realtime patch fixes below.
function bpDevBillingMocksPlugin() {
  return {
    name: "bp-dev-billing-mocks",
    configureServer(server) {
      server.middlewares.use("/v1/billing/checkout", (req, res, next) => {
        if (req.method !== "POST") return next();
        res.setHeader("Content-Type", "application/json");
        res.end(JSON.stringify({
          checkout_url: "/workspace/pricing?checkout=mock-success",
          session_id: "dev_mock_" + Date.now(),
        }));
      });
      server.middlewares.use("/v1/billing/plans", (req, res, next) => {
        if (req.method !== "GET") return next();
        const plans = fs.readFileSync(path.resolve(__dirname, "public/plans.json"), "utf-8");
        res.setHeader("Content-Type", "application/json");
        res.end(plans);
      });
      server.middlewares.use("/v1/billing/subscriptions", (req, res, next) => {
        if (req.method !== "GET") return next();
        res.setHeader("Content-Type", "application/json");
        res.end("[]");
      });
      server.middlewares.use("/v1/billing/portal", (req, res, next) => {
        if (req.method !== "POST") return next();
        res.setHeader("Content-Type", "application/json");
        res.end(JSON.stringify({
          portal_url: null,
          detail: "No billing portal in dev mode — this needs a real Dodo customer via the live gateway.",
        }));
      });
    },
  };
}

export default defineConfig(({ command }) => ({
  plugins: [vue(), bpDevBillingMocksPlugin()],
  base: command === "build" ? "/assets/batch_projects/frontend/" : "/",
  define: {
    // Expose backend URL for direct socket connection in dev
    "import.meta.env.VITE_FRAPPE_BACKEND": JSON.stringify(FRAPPE_BACKEND),
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  build: {
    outDir: "../batch_projects/public/frontend",
    emptyOutDir: true,
    target: "es2015",
    rollupOptions: {
      output: {
        // Entry stays a fixed name because www/workspace.html references it
        // directly (cache-busted with ?v=<mtime> there). Lazy-loaded route
        // chunks + their CSS are content-hashed so they can never be served
        // stale — index.js references the hashed names automatically.
        entryFileNames: "assets/index.js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: (info) =>
          info.name === "index.css"
            ? "assets/index.css"
            : "assets/[name]-[hash][extname]",
      },
    },
  },
  server: {
    port: 8090,
    proxy: {
      "^/api": {
        target: GATEWAY_BACKEND,
        changeOrigin: true,
        secure: false,
        cookieDomainRewrite: "localhost",
      },
      "^/(assets|files|private|storage|login|logout|app)": {
        target: FRAPPE_BACKEND,
        changeOrigin: true,
        secure: false,
        cookieDomainRewrite: "localhost",
      },
      // Socket.IO namespace (/sitename) is sent in the WS handshake, not the URL path.
      // The actual HTTP/WS connection always goes to /socket.io — proxy that.
      "/socket.io": {
        target: FRAPPE_BACKEND,
        changeOrigin: true,
        secure: false,
        ws: true,
        cookieDomainRewrite: "localhost",
      },
      // Bridge plane (session bootstrap, realtime SSE, entitlements, license
      // refresh, ...) — real local gateway. The billing sub-paths above are
      // intercepted by bpDevBillingMocksPlugin() before requests reach here
      // (see its comment for why: bp-license can't run in every dev env).
      "^/v1": {
        target: GATEWAY_BACKEND,
        changeOrigin: true,
        secure: false,
        cookieDomainRewrite: "localhost",
        // /v1/realtime/subscribe is a long-lived, mostly-idle SSE stream.
        // Caddy's gzip encoder would otherwise try to compress it because
        // Chromium advertises Accept-Encoding — pointless for a stream with
        // no fixed end, and a real risk of it buffering for a compressible
        // block instead of flushing each event promptly. Stripping the
        // header makes Caddy skip compression negotiation for this proxy
        // target entirely (harmless for the small JSON /v1 responses too).
        configure: (proxy) => {
          proxy.on("proxyReq", (proxyReq) => {
            proxyReq.removeHeader("accept-encoding");
          });
        },
      },
    },
  },
}));
