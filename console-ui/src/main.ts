import { loadFleet, loadHistory, type Overseer } from "./api";
import { renderArchive } from "./pages/archive";
import { renderClaims } from "./pages/claims";
import { bindHistoryFilters, renderHistory } from "./pages/history";
import { liveTemplate } from "./pages/live";
import { renderOps } from "./pages/ops";
import {
  renderBanner,
  renderBounty,
  renderClock,
  renderGcp,
  renderHealth,
  renderRegistry,
  renderTimeline,
} from "./render";
import { bindRouting, currentRoute, markActive, type Route } from "./router";
import { startUniverse } from "./universe";
import "./style.css";

const canvas = document.getElementById("universe");
if (canvas instanceof HTMLCanvasElement) {
  startUniverse(canvas);
}

const app = document.getElementById("app");
let historyCache: Overseer | null = null;
let liveTimer: number | null = null;

async function historyData(): Promise<Overseer> {
  if (!historyCache) historyCache = await loadHistory();
  return historyCache;
}

async function tickLive(): Promise<void> {
  renderClock();
  try {
    const [health, registry, latest] = await loadFleet();
    renderHealth(true, "live");
    const bounty = latest.bounty || null;
    renderBanner(bounty);
    renderBounty(bounty);
    renderTimeline(bounty?.events);
    renderRegistry(registry.agents || [], bounty);
    renderGcp(bounty);
    void health;
  } catch {
    renderHealth(false, "offline");
  }
}

function stopLive(): void {
  if (liveTimer !== null) {
    window.clearInterval(liveTimer);
    liveTimer = null;
  }
}

async function renderRoute(): Promise<void> {
  if (!app) return;
  const route: Route = currentRoute();
  markActive(route);
  stopLive();
  if (route === "live") {
    app.innerHTML = liveTemplate();
    await tickLive();
    liveTimer = window.setInterval(tickLive, 2000);
    return;
  }
  const data = await historyData();
  if (route === "ops") app.innerHTML = renderOps(data);
  if (route === "history") {
    app.innerHTML = renderHistory(data);
    bindHistoryFilters(app, data);
  }
  if (route === "claims") app.innerHTML = renderClaims(data);
  if (route === "archive") app.innerHTML = renderArchive(data);
  const footer = document.getElementById("gcp");
  if (footer) {
    footer.textContent = [data.meta?.source, data.meta?.snapshot, data.meta?.window].filter(Boolean).join(" · ");
  }
}

bindRouting(() => {
  void renderRoute();
});
void renderRoute();
