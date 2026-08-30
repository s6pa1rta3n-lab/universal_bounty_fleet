import type { Overseer } from "../api";
import { escapeHtml, linkHtml, outcomeClass, repoIssue } from "../format";

export function renderArchive(data: Overseer): string {
  const rows = data.archive || [];
  return `
    <section class="hero compact">
      <p class="kicker">Archive  ·  parked before 24 Aug</p>
      <h1 class="page-title">Older work, kept off the sprint tape.</h1>
      <p class="lede">These ${rows.length} rows opened before this run. They are here so judges can see the full ledger without inflating the 24–28 Aug count.</p>
    </section>
    <section class="card table-card">
      <table class="grid-table wide">
        <thead><tr><th>PR</th><th>Title</th><th>State</th><th>Opened</th></tr></thead>
        <tbody>
          ${rows
            .map(
              (item) => `<tr>
                <td>${item.url ? linkHtml(item.url) : escapeHtml(repoIssue(item.repo, item.number))}</td>
                <td>${escapeHtml(item.title || "—")}</td>
                <td><span class="pill ${outcomeClass(item.state)}">${escapeHtml(item.state || "—")}</span></td>
                <td class="mono">${escapeHtml(item.opened || "—")}</td>
              </tr>`,
            )
            .join("")}
        </tbody>
      </table>
    </section>`;
}
