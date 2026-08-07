import { createRouter, createWebHistory } from "vue-router";

const routes = [
  // Root
  { path: "/", redirect: "/workspace" },

  // Public, view-only share link (no auth, no app shell)
  {
    path: "/share/:token",
    name: "SharedView",
    component: () => import("@/pages/SharedView.vue"),
    props: true,
    meta: { public: true },
  },

  // Public intake form (no auth, no app shell — bare page)
  {
    path: "/intake/:token",
    name: "IntakeForm",
    component: () => import("@/pages/IntakeForm.vue"),
    props: true,
    meta: { public: true },
  },

  // Static workspace routes FIRST (before any :key dynamic routes)
  {
    path: "/workspace",
    name: "Dashboard",
    component: () => import("@/pages/Dashboard.vue"),
  },
  {
    path: "/workspace/my-tasks",
    name: "MyTasks",
    component: () => import("@/pages/MyTasks.vue"),
  },
  {
    path: "/workspace/triage",
    name: "Triage",
    component: () => import("@/pages/Triage.vue"),
  },
  {
    path: "/workspace/new-project",
    name: "NewProject",
    component: () => import("@/pages/CreateProjectFlow.vue"),
  },
  {
    path: "/workspace/invite/:token",
    name: "AcceptInvitation",
    component: () => import("@/pages/AcceptInvitation.vue"),
  },

  {
    path: "/workspace/settings/:tab?",
    name: "WorkspaceSettings",
    component: () => import("@/pages/WorkspaceSettings.vue"),
    props: true,
  },
  {
    path: "/workspace/automations/canvas/:workflowId?",
    name: "AutomationCanvas",
    component: () => import("@/pages/AutomationCanvas.vue"),
    props: true,
  },
  {
    path: "/workspace/account",
    name: "AccountSettings",
    component: () => import("@/pages/AccountSettings.vue"),
  },
  {
    path: "/workspace/pricing",
    name: "Pricing",
    component: () => import("@/pages/Billing.vue"),
  },
  {
    path: "/workspace/projects/tree",
    name: "ProjectTree",
    component: () => import("@/pages/ProjectTree.vue"),
  },
  {
    path: "/workspace/all",
    name: "Projects",
    component: () => import("@/pages/Projects.vue"),
  },
  {
    path: "/workspace/teams",
    name: "Teams",
    component: () => import("@/pages/Teams.vue"),
  },
  {
    path: "/workspace/people",
    name: "People",
    component: () => import("@/pages/People.vue"),
  },
  // ── Sidebar nav stubs (full pages in later sprints) ──
  {
    path: "/workspace/timesheets",
    name: "Timesheets",
    component: () => import("@/pages/Timesheets.vue"),
  },
  {
    path: "/workspace/portfolio",
    name: "Portfolio",
    component: () => import("@/pages/Portfolio.vue"),
  },
  {
    path: "/workspace/goals",
    name: "Goals",
    component: () => import("@/pages/Goals.vue"),
  },
  // ── Reports: saved-report list + resizable chart-card builder ──
  {
    path: "/workspace/reports",
    redirect: "/workspace/reports/dashboard",
  },
  {
    path: "/workspace/reports/dashboard",
    name: "ReportsDashboard",
    component: () => import("@/pages/ReportsDashboard.vue"),
  },
  {
    path: "/workspace/reports/:reportId",
    name: "ReportView",
    component: () => import("@/pages/ReportView.vue"),
  },
  // Old single dashboard builder is superseded by the Reports surface.
  {
    path: "/workspace/dashboard",
    redirect: "/workspace/reports/dashboard",
  },
  // ── Dashboards: Wrike-style live/glance boards — separate from Reports
  // above (scheduled/exportable, BP Report). See BP Dashboard. ──
  {
    path: "/workspace/dashboards",
    redirect: "/workspace/dashboards/dashboard",
  },
  {
    path: "/workspace/dashboards/dashboard",
    name: "Dashboards",
    component: () => import("@/pages/Dashboards.vue"),
  },
  {
    path: "/workspace/dashboards/:dashboardId",
    name: "DashboardView",
    component: () => import("@/pages/DashboardView.vue"),
  },
  {
    path: "/workspace/dashboards/:dashboardId/widget/:widgetId",
    name: "WidgetPage",
    component: () => import("@/pages/WidgetPage.vue"),
  },
  {
    path: "/workspace/workload",
    name: "Workload",
    component: () => import("@/pages/Workload.vue"),
  },
  {
    path: "/workspace/margin",
    name: "MarginReport",
    component: () => import("@/pages/MarginReport.vue"),
  },
  {
    path: "/workspace/batch-invoicing",
    name: "BatchInvoicing",
    component: () => import("@/pages/BatchInvoicing.vue"),
  },
  {
    path: "/workspace/utilization",
    name: "Utilization",
    component: () => import("@/pages/Utilization.vue"),
  },

  // Dynamic project routes AFTER static ones
  {
    path: "/workspace/:key",
    name: "ProjectIndex",
    component: () => import("@/pages/ProjectIndex.vue"),
    props: true,
  },
  {
    path: "/workspace/:key/summary",
    name: "ProjectSummary",
    component: () => import("@/pages/ProjectSummary.vue"),
    props: true,
  },
  {
    path: "/workspace/:key/board",
    name: "Board",
    component: () => import("@/pages/Board.vue"),
    props: true,
  },
  {
    path: "/workspace/:key/list",
    name: "ListView",
    component: () => import("@/pages/ListView.vue"),
    props: true,
  },
  {
    path: "/workspace/:key/backlog",
    name: "Backlog",
    component: () => import("@/pages/Backlog.vue"),
    props: true,
  },
  {
    path: "/workspace/:key/sprint/:sprintId",
    name: "SprintDetail",
    component: () => import("@/pages/SprintDetail.vue"),
    props: true,
  },
  {
    path: "/workspace/:key/sprints-overview",
    name: "SprintsOverview",
    component: () => import("@/pages/SprintsOverview.vue"),
    props: true,
  },
  {
    path: "/workspace/:key/gantt",
    name: "Gantt",
    component: () => import("@/pages/Gantt.vue"),
    props: true,
  },
  {
    path: "/workspace/:key/reports",
    name: "Reports",
    component: () => import("@/pages/Reports.vue"),
    props: true,
  },
  {
    path: "/workspace/:key/files",
    name: "ProjectFiles",
    component: () => import("@/pages/ProjectFiles.vue"),
    props: true,
  },
  {
    path: "/workspace/:key/notes",
    name: "ProjectNotes",
    component: () => import("@/pages/Notes.vue"),
    props: true,
  },
  {
    path: "/workspace/:key/draw",
    name: "ProjectDraw",
    component: () => import("@/pages/Draw.vue"),
    props: true,
  },
  {
    path: "/workspace/:key/draw/:drawingId",
    name: "ProjectDrawCanvas",
    component: () => import("@/pages/DrawCanvas.vue"),
    props: true,
  },
  {
    path: "/workspace/:key/money",
    name: "ProjectMoney",
    component: () => import("@/pages/ProjectMoney.vue"),
    props: true,
  },
  {
    path: "/workspace/:key/settings/:tab?",
    name: "ProjectSettings",
    component: () => import("@/pages/ProjectSettings.vue"),
    props: true,
  },

  // ── Team routes ──
  {
    path: "/workspace/team/:key",
    name: "TeamHome",
    component: () => import("@/pages/TeamHome.vue"),
    props: true,
  },
  {
    path: "/workspace/team/:key/settings",
    redirect: (to) => ({ path: `/workspace/team/${to.params.key}`, query: { tab: "settings" } }),
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// ─── Auth guard ────────────────────────────────────────────────────────────────
// The SPA template is served to logged-out visitors too (so public /share links
// and the invite-accept page work). For every *non-public* route we require a
// real session — otherwise every authenticated API call 403s with "Login to
// access" and the app renders broken. Redirect to Frappe login instead, with a
// redirect-to back to where they were headed.
function isPublicRoute(to) {
  return to.meta?.public === true ||
    to.path.startsWith("/share/") ||
    to.path.startsWith("/workspace/invite/");
}

router.beforeEach((to) => {
  if (isPublicRoute(to)) return true;
  // Only enforce when the server actually injected a session (the production
  // workspace.html template sets window.frappe.session). The Vite dev server
  // serves its own index.html with no session — never bounce dev to /login
  // (which the dev proxy would forward to the canonical production host).
  const session = (typeof window !== "undefined") ? window.frappe?.session : null;
  if (session && (!session.user || session.user === "Guest")) {
    const back = encodeURIComponent(to.fullPath);
    window.location.href = `/login?redirect-to=${back}`;
    return false;
  }
  return true;
});

export default router;
