import type { Overseer } from "../api";
import { escapeHtml, linkHtml, repoIssue } from "../format";

export function renderClaims(data: Overseer): string {
  const claims = data.claims || [];
  return `
    <section class="hero compact">
      <p class="kicker">Claims  ·  ${claims.length} issues</p>
      <h1 class="page-title">Pipeline, not receivables.</h1>
      <p class="lede">${escapeHtml(data.meta?.money || "Payouts are unknown.")}</p>
    </section>
    <section class="card table-card">
      <table class="grid-table wide">
        <thead><tr><th>Issue</th><th>Title</th><th>Status</th><th>Payout</th></tr></thead>
        <tbody>
          ${claims
            .map(
              (claim) => `<tr>
                <td>${claim.url ? linkHtml(claim.url) : escapeHtml(repoIssue(claim.repo, claim.number))}</td>
                <td>${escapeHtml(claim.title || "—")}</td>
                <td>${escapeHtml(claim.status || "—")}</td>
                <td class="mono">unknown</td>
              </tr>`,
            )
            .join("")}
        </tbody>
      </table>
    </section>`;
}
