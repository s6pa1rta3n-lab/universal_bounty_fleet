import type { Overseer } from "../api";
import { escapeHtml } from "../format";

export function renderOps(data: Overseer): string {
  const sprint = data.sprint || {};
  const days = sprint.days || [];
  const max = Math.max(1, ...days.map((day) => day.opened));
  const repos = (sprint.repos || []).slice(0, 12);
  return `
    <section class="hero compact">
      <p class="kicker">Ops  ·  ${escapeHtml(data.meta?.window || "this sprint")}</p>
      <h1 class="page-title">Most of the pile is waiting on humans.</h1>
      <p class="lede">${escapeHtml(data.meta?.rule || "")}</p>
    </section>
    <div class="stats">
      ${stat("Opened", sprint.opened ?? 0)}
      ${stat("Waiting", sprint.waiting ?? 0, "pending")}
      ${stat("Merged", sprint.merged ?? 0, "ok")}
      ${stat("Closed", sprint.closed ?? 0, "hot")}
    </div>
    <div class="split">
      <section class="card">
        <h2>Opened by day</h2>
        <div class="bars">
          ${days
            .map((day) => {
              const pct = Math.round((day.opened / max) * 100);
              return `<div class="bar-row"><span>${escapeHtml(day.day.slice(5))}</span><i style="width:${pct}%"></i><b>${day.opened}</b></div>`;
            })
            .join("")}
        </div>
      </section>
      <section class="card">
        <h2>By repo</h2>
        <table class="grid-table">
          <thead><tr><th>Repo</th><th>Open</th><th>Wait</th><th>Merged</th></tr></thead>
          <tbody>
            ${repos
              .map(
                (repo) => `<tr>
                  <td>${escapeHtml(repo.repo.split("/")[1] || repo.repo)}</td>
                  <td>${repo.opened}</td>
                  <td>${repo.waiting}</td>
                  <td>${repo.merged}</td>
                </tr>`,
              )
              .join("")}
          </tbody>
        </table>
      </section>
    </div>`;
}

function stat(label: string, value: number, tone = ""): string {
  return `<div class="stat ${tone}"><b>${value}</b><span>${label}</span></div>`;
}
