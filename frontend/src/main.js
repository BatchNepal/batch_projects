import { createApp } from "vue";
import { createPinia } from "pinia";
import router from "./router";
import App from "./App.vue";
import { Toaster } from "vue-sonner";
import VueApexCharts from "vue3-apexcharts";
import "./tokens.css"; // ← first
import "./index.css";
import { initDensity } from "./composables/useDensity";

// Apply the saved interface density immediately (before mount) to avoid a
// flash of the wrong UI scale.
initDensity();

async function bootstrap() {
  // Frappe injects window.csrf_token via Jinja in production.
  // In Vite dev mode the HTML is served by Vite so we fetch it manually.
  if (!window.csrf_token) {
    try {
      const res = await fetch(
        "/api/method/batch_projects.api.board.get_session_info",
      );
      if (res.status === 403 || res.status === 401) {
        window.location.href = "/login?redirect-to=/batch-projects";
        return;
      }
      const data = await res.json();
      const info = data.message;
      if (!info || info.user === "Guest") {
        window.location.href = "/login?redirect-to=/batch-projects";
        return;
      }
      window.csrf_token = info.csrf_token;
      window.frappe_sitename = info.sitename;
    } catch {
      // If the fetch itself fails (network down, no proxy) mount anyway
      // so the user sees an error rather than a blank page.
    }
  }

  const app = createApp(App);
  app.use(createPinia());
  app.use(router);
  app.use(VueApexCharts);
  app.component("Toaster", Toaster);
  app.mount("#app");
}

bootstrap();
