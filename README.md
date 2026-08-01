<p align="center">
  <a href="https://batchprojects.com">
    <img src="frontend/public/images/bp-logo-new.png" alt="BatchProjects Logo" width="80" height="80">
  </a>
</p>

<h1 align="center">BatchProjects</h1>

<p align="center">
  <b>Enterprise-grade project management, built natively into ERPNext.</b>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue.svg" alt="License: AGPL v3"></a>
  <a href="https://frappeframework.com"><img src="https://img.shields.io/badge/Frappe-v15-0089FF.svg" alt="Frappe v15"></a>
  <a href="https://github.com/BatchNepal/batch_projects/stargazers"><img src="https://img.shields.io/github/stars/BatchNepal/batch_projects?style=flat" alt="GitHub Stars"></a>
  <a href="CONTRIBUTING.md"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
</p>

---

<p align="center">
  <img src="frontend/public/images/bp-hero.png" alt="BatchProjects Board View" width="100%">
</p>

## Overview

Meet BatchProjects, an open-source project management app for your team built natively for ERPNext.

Experience the freedom of managing your projects in a fast, modern, and collaborative interface while keeping all your financials, timesheets, and accounting inside ERPNext. No more exporting, no more manual syncing, and no more context switching between multiple tools.

---

## Key Features

### 🚀 Modern Delivery Experience *(Efficiency in mind)*

* **Board, Views & Tasks:** Drag-and-drop Kanban boards, Listview, Gantt Chart, backlogs, sprint cycles, and Projects templates feature. Shareable boards, saved view states, and real-time multi-user sync for live collaboration. Support for both opt-in Agile/Scrum (sprints, story points) and structured Waterfall/Kanban workflows.
* **Infinitely Customizable Records:** Create per-project custom fields, custom statuses, and role-based access rules without touching the underlying Frappe schemas.
* **Timesheets & Costing:** Log time against tasks to generate timesheets and monitor project margins and utilization in real time.
* **Automations and Workflows:** Trigger webhooks, push notifications, and custom workflows based on task events. Visual rule builder for automating task events, with webhook triggers and push notifications.
* **Dashboards & Reportings:** Scheduled or realtime reports and customize dashboard widgets to track project progress, profitability, and utilization.
* **Scalable and Performant by Design:** Gateway powered, horizontally scalable, and built with Golang to support lots of concurrent users without dropping a sweat.
* **Enterprise Integrations:** Seamlessly connect with other enterprise tools and services for a unified workflow.
* **Interactive Views:** Switch seamlessly between Kanban Boards, Backlogs, Sprints, and Gantt charts with saved view states.
* **Fast Frontend:** Built on Vue 3 and Pinia for near-instant rendering and snappy interaction.
* **Real-Time & Collaboration:** WebSocket-based multi-user sync for live updates across all connected clients.
* **Projects Templates:** Create and reuse project templates with pre-defined tasks, workflows, and custom fields for faster project setup. Leverage templates to standardize processes and ensure consistency across projects.
* **Self-Hosted Gateway:** Deploy on your own infrastructure for full control over your data and security.

### 💼 Native ERP Financial Engine

* **First-Class ERP Links:** Attach tasks directly to Sales Orders, Purchase Orders, Expense Claims, and Accounting Dimensions.
* **Real-Time Margin Tracking:** Log time against tasks and roll it up automatically into project profitability and budget vs. actual reports.
* **Native Timesheets:** Billable hours sync straight into ERPNext Payroll and Sales Invoices with zero export/import steps.
* **One Source of Truth:** Delivery teams work in a high-speed UI while accounting teams get precise financial visibility in ERPNext.
* **Customizable Costing:** Track labor, materials, and overhead costs per project with flexible accounting dimensions.
* **Automated Billing:** Generate invoices based on logged time and linked Sales Orders, reducing manual billing errors.
* **Budget Monitoring:** Monitor project budgets in real time, with alerts for overruns and underutilization.
* **Direct ERPNext Integration:** Leverage ERPNext's robust accounting and inventory management features for comprehensive project oversight.

---

## Open Core & Architecture

We believe in full transparency regarding how BatchProjects is built and licensed. We use an **Open Core** model so the open-source community gets a fully functional ERP project system while supporting sustainable ongoing development.

### What's included?

| Feature | Open Core (`AGPL-3.0`) | BP Gateway (`bp-gateway`) |
| :--- | :---: | :---: |
| **Kanban Boards, Backlogs, Gantt & Sprints** | ✅ | ✅ |
| **ERPNext Document Linking (SO, PO, Timesheets)** | ✅ | ✅ |
| **Custom Fields & Project Workflows** | ✅ | ✅ |
| **Profitability & Utilization Reporting** | ✅ | ✅ |
| **Real-time Multi-user WebSocket Sync** | ❌ | ✅ |
| **Visual Automation Rule Builder** | ❌ | ✅ |
| **Workflow Webhooks & Push Notifications** | ❌ | ✅ |

* **BatchProjects Core** is 100% free, AGPL-v3 licensed, and fully functional standalone.
* **bp-gateway** is an optional proprietary companion service available as a self-hostable Docker container. Installing it unlocks real-time sync, automations, all premium features. You can host it yourself for full control over your data and security.

---

## Use Cases

* **Agencies & Consultancies:** Track project execution alongside Sales Orders, ensuring billable hours hit client invoices accurately.
* **Construction & Engineering:** Tie task progress to Purchase Orders and subcontractor expenses for precise budget monitoring.
* **Manufacturing & Operations:** Manage delivery phases tied to ERPNext production schedules and procurement.
* **Software Development Teams:** Use Agile/Scrum or Waterfall workflows with real-time collaboration and automated reporting.
* **Professional Services:** Monitor project profitability, resource utilization, and automate client billing directly from ERPNext.
* **Education & Research:** Manage research projects, grant budgets, and academic collaborations with integrated financial tracking.
* **Nonprofits & NGOs:** Track program delivery, donor-funded projects, and grant compliance with real-time financial visibility.

---

## Quick Start (Core App)

BatchProjects runs as a standard Frappe app on **Frappe v15 / ERPNext v15**.

```bash
# Navigate to your bench directory
cd ~/frappe-bench

# Get the app
bench get-app https://github.com/BatchNepal/batch_projects --branch version-15

# Install on your site
bench --site your-site.local install-app batch_projects

# Run migrations
bench --site your-site.local migrate

That's the entire community version install — no Node, no build step, no external
service. The `version-15` branch tracks ERPNext v15; see
[`deploy/README.md`](deploy/README.md) for the full version-compatibility
story and how branch naming maps to ERPNext versions going forward.

For local frontend development, see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Built with

[Frappe Framework](https://frappeframework.com) · [ERPNext](https://erpnext.com) · [Vue 3](https://vuejs.org) · [Pinia](https://pinia.vuejs.org) · Python

## The optional but recommended add-on

Realtime updates, automation rules, ERP integration, and other 
premium features run through a small companion service (**bp-gateway**) that sits between frontend and backend of batch_projects app and handles heavy lifting required to handle premium features — it can run on same or dedicated server and provides you full control over your data and security. 

If you only need the community version, skip this gateway entirely — BatchProjects runs standalone on community plan.

See [`deploy/README.md`](deploy/README.md) for the install guide.

## License

BatchProjects — the Frappe app and the Vue frontend, everything in this
repo — is licensed under the **GNU Affero General Public License v3.0**
(AGPL-3.0-only). See [`LICENSE`](LICENSE).

The practical implication of AGPL: if you modify this app and run it as a
network service for others (e.g. offer it as SaaS), you must make your
modified source available to those users. Just self-hosting it for your own
company, unmodified or modified, carries no such obligation beyond attribution.

The optional `bp-gateway` add-on is separate, proprietary addon,
distributed as a signed container image under its own license — using it is
optional and doesn't change the license of BatchProjects itself.

## Contributing

PRs welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md) for the branch model,
dev setup, and CI requirements. Security issues: see
[`SECURITY.md`](SECURITY.md), please don't file those as public issues.

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md).
