import { loadFleet } from "./api";
import {
  renderBanner,
  renderBounty,
  renderClock,
  renderGcp,
  renderHealth,
  renderRegistry,
  renderTimeline,
} from "./render";
import { startUniverse } from "./universe";
import "./style.css";

const canvas = document.getElementById("universe");
if (canvas instanceof HTMLCanvasElement) {
  startUniverse(canvas);
}

async function tick(): Promise<void> {
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
  } catch {
    renderHealth(false, "offline");
  }
}

tick();
setInterval(tick, 2000);
