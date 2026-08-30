import type { HistoryPr, Overseer } from "../api";
import { escapeHtml, linkHtml, outcomeClass, repoIssue } from "../format";

export function renderHistory(data: Overseer, filter = "all", query = ""): string {
  const prs = data.sprint?.prs || [];
  const q = query.trim().toLowerCase();
  const shown = prs.filter((pr) => {
    if (filter === "waiting" && pr.outcome !== "Waiting on human") return false;
    if (filter === "merged" && pr.outcome !== "Merged") return false;
    if (filter === "closed" && pr.outcome !== "Closed, not merged") return false;
    if (!q) return true;
    return [pr.repo, pr.title, pr.number, pr.outcome].some((part) => String(part || "").toLowerCase().includes(q));
  });
  return `
    <section class="hero compact">
      <p class="kicker">History  ·  ${prs.length} sprint PRs</p>
      <h1 class="page-title">Everything the fleet opened this run.</h1>
      <p class="lede">24–28 Aug 2026. Filter to waiting, merged, or closed. The agent already did its part on the waiting rows.</p>
    </section>
    <div class="toolbar">
      ${chip("all", "All", filter)}
      ${chip("waiting", "Waiting", filter)}
      ${chip("merged", "Merged", filter)}
      ${chip("closed", "Closed", filter)}
      <input id="history-q" class="search" type="search" placeholder="Filter repo or title" value="${escapeHtml(query)}" />
    </div>
    <section class="card table-card">
      <table class="grid-table wide">
        <thead><tr><th>PR</th><th>Title</th><th>Outcome</th><th>Opened</th></tr></thead>
        <tbody>${shown.map(row).join("") || `<tr><td colspan="4" class="empty">No rows match.</td></tr>`}</tbody>
      </table>
    </section>`;
}

function chip(id: string, label: string, active: string): string {
  return `<button class="chip ${id === active ? "active" : ""}" data-filter="${id}" type="button">${label}</button>`;
}

function row(pr: HistoryPr): string {
  return `<tr>
    <td>${pr.url ? linkHtml(pr.url) : escapeHtml(repoIssue(pr.repo, pr.number))}</td>
    <td>${escapeHtml(pr.title || "—")}</td>
    <td><span class="pill ${outcomeClass(pr.outcome)}">${escapeHtml(pr.outcome || "—")}</span></td>
    <td class="mono">${escapeHtml(pr.opened || "—")}</td>
  </tr>`;
}

export function bindHistoryFilters(root: HTMLElement, data: Overseer): void {
  const apply = () => {
    const active = root.querySelector(".chip.active");
    const filter = active instanceof HTMLElement ? active.dataset.filter || "all" : "all";
    const input = root.querySelector("#history-q");
    const query = input instanceof HTMLInputElement ? input.value : "";
    const body = root.querySelector("tbody");
    if (!body) return;
    const html = renderHistory(data, filter, query);
    const parsed = document.createElement("div");
    parsed.innerHTML = html;
    const next = parsed.querySelector("tbody");
    if (next) body.replaceWith(next);
  };
  root.addEventListener("click", (event) => {
    const btn = (event.target as Element).closest("[data-filter]");
    if (!(btn instanceof HTMLElement) || !btn.dataset.filter) return;
    root.querySelectorAll(".chip").forEach((node) => node.classList.toggle("active", node === btn));
    apply();
  });
  root.addEventListener("input", (event) => {
    if (!(event.target instanceof HTMLInputElement) || event.target.id !== "history-q") return;
    apply();
  });
}
