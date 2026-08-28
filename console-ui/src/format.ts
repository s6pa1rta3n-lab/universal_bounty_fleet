export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function shortClock(iso?: string): string {
  if (!iso) return "—";
  const match = iso.match(/T(\d{2}:\d{2}:\d{2})/);
  return match ? `${match[1]}Z` : iso;
}

export function shortLink(url?: string | null): { href: string; label: string } | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    const parts = parsed.pathname.replace(/\/+$/, "").split("/").filter(Boolean);
    const repo = parts[1] || parts[0] || parsed.hostname;
    const number = parts[parts.length - 1];
    if (number && /^\d+$/.test(number)) {
      return { href: url, label: `${repo}#${number}` };
    }
    return { href: url, label: repo };
  } catch {
    return { href: url, label: url };
  }
}

export function linkHtml(url?: string | null): string {
  const link = shortLink(url);
  if (!link) return "—";
  return `<a href="${escapeHtml(link.href)}" target="_blank" rel="noreferrer">${escapeHtml(link.label)}</a>`;
}
