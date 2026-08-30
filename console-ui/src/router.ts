export type Route = "live" | "ops" | "history" | "claims" | "archive";

const ROUTES: Route[] = ["live", "ops", "history", "claims", "archive"];

export function currentRoute(): Route {
  const path = window.location.pathname.replace(/\/+$/, "") || "/console";
  const rest = path.replace(/^\/console\/?/, "");
  return ROUTES.includes(rest as Route) ? (rest as Route) : "live";
}

export function hrefFor(route: Route): string {
  return route === "live" ? "/console" : `/console/${route}`;
}

export function navigate(route: Route): void {
  const next = hrefFor(route);
  if (window.location.pathname.replace(/\/+$/, "") === next) return;
  window.history.pushState({ route }, "", next);
  window.dispatchEvent(new Event("routechange"));
}

export function bindRouting(onChange: () => void): void {
  window.addEventListener("popstate", onChange);
  window.addEventListener("routechange", onChange);
  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const link = target.closest("a[data-route]");
    if (!(link instanceof HTMLAnchorElement)) return;
    const route = link.dataset.route;
    if (!route || !ROUTES.includes(route as Route)) return;
    event.preventDefault();
    navigate(route as Route);
  });
}

export function markActive(route: Route): void {
  document.querySelectorAll("a[data-route]").forEach((node) => {
    node.classList.toggle("active", node.getAttribute("data-route") === route);
  });
}
