import type { AgentCard, Bounty } from "./api";
import { escapeHtml, linkHtml, shortClock } from "./format";

const $ = (id: string) => document.getElementById(id);

export function bannerCopy(bounty: Bounty | null): { title: string; cls: string; sub: string } {
  if (!bounty) {
    return { title: "PENDING", cls: "PENDING", sub: "Waiting for fleet state." };
  }
  const status = bounty.audit_status || "PENDING";
  if (status === "FAIL") {
    const cheat = bounty.cheat_detected ? ` · ${bounty.cheat_detected}` : "";
    return {
      title: "BLOCKED",
      cls: "BLOCKED",
      sub: `Merge denied${cheat}. Auditor holds the gate until the cheat is gone.`,
    };
  }
  if (status === "PASS" && bounty.merge_allowed) {
    return { title: "CLEARED", cls: "CLEARED", sub: "Auditor approved. Merge is allowed." };
  }
  return { title: "PENDING", cls: "PENDING", sub: "Fleet in flight. Waiting for the next GitHub state change." };
}

export function renderBounty(bounty: Bounty | null): void {
  const root = $("bounty");
  if (!root) return;
  if (!bounty) {
    root.className = "empty";
    root.textContent = "No bounty in Memory Bank.";
    return;
  }
  const escrow = bounty.escrow || {};
  const mergeCls = bounty.merge_allowed ? "ok" : "hot";
  root.className = "";
  root.innerHTML = `
    <p class="bounty-title">${escapeHtml(bounty.title || bounty.bounty_id || "Untitled bounty")}</p>
    <div class="kv">
      <b>issue</b><div>${linkHtml(bounty.issue_url)}</div>
      <b>draft pr</b><div>${linkHtml(bounty.pr_url)}</div>
      <b>escrow</b><div>${
        escrow.verified
          ? `verified $${escapeHtml(String(escrow.amount_usd ?? 0))} ${escrow.source ? `<span class="pill">${escapeHtml(escrow.source)}</span>` : ""}`
          : "not verified"
      }</div>
    </div>
    <div class="pills">
      ${bounty.cheat_detected ? `<span class="pill hot">${escapeHtml(bounty.cheat_detected)}</span>` : `<span class="pill ok">cheat none</span>`}
      <span class="pill ${mergeCls}">${bounty.merge_allowed ? "merge allowed" : "merge blocked"}</span>
    </div>`;
}

export function renderTimeline(events: Bounty["events"]): void {
  const root = $("timeline");
  if (!root) return;
  if (!events || !events.length) {
    root.className = "empty";
    root.textContent = "No events yet.";
    return;
  }
  const shown = events.slice(-6);
  root.className = "";
  root.innerHTML = shown
    .map((event) => {
      const type = event.type || "event";
      return `<div class="event ${escapeHtml(type)}">
        <div class="t">${escapeHtml(shortClock(event.t))} · ${escapeHtml(type)}</div>
        <div>${escapeHtml(event.detail || "")}</div>
      </div>`;
    })
    .join("");
}

export function renderRegistry(agents: AgentCard[], live?: Bounty | null): void {
  const root = $("registry");
  if (!root) return;
  const liveAgents = live?.agents || {};
  root.innerHTML = agents
    .map((agent) => {
      const status = liveAgents[agent.id] || agent.status || "idle";
      const pillCls = status === "active" || status === "pass" ? "ok" : status === "fail" ? "hot" : "";
      return `<div class="agent">
        <div class="agent-head">
          <strong>${escapeHtml(agent.name)}</strong>
          <span class="pill ${pillCls}">${escapeHtml(status)}</span>
        </div>
        <div class="scope">${escapeHtml((agent.tool_scope || []).join(" · "))}</div>
      </div>`;
    })
    .join("");
}

export function renderGcp(bounty: Bounty | null): void {
  const root = $("gcp");
  if (!root) return;
  const gcp = bounty?.gcp || {};
  root.textContent = [gcp.project, gcp.region, gcp.firestore_doc].filter(Boolean).join(" · ");
}

export function renderClock(): void {
  const root = $("clock");
  if (root) root.textContent = new Date().toISOString().slice(11, 19) + "Z";
}

export function renderHealth(ok: boolean, label: string): void {
  const dot = $("health-dot");
  const text = $("health-label");
  if (dot) dot.className = ok ? "dot ok" : "dot bad";
  if (text) text.textContent = label;
}

export function renderBanner(bounty: Bounty | null): void {
  const banner = $("banner");
  const sub = $("banner-sub");
  const copy = bannerCopy(bounty);
  if (banner) {
    banner.className = `status ${copy.cls}`;
    banner.textContent = copy.title;
  }
  if (sub) sub.textContent = copy.sub;
}
