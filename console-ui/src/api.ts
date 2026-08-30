export type Escrow = {
  verified?: boolean;
  amount_usd?: number;
  source?: string;
};

export type BountyEvent = {
  t?: string;
  type?: string;
  detail?: string;
};

export type GcpMeta = {
  project?: string;
  region?: string;
  firestore_doc?: string;
  trace_id?: string;
};

export type Bounty = {
  bounty_id?: string;
  title?: string;
  issue_url?: string;
  pr_url?: string;
  audit_status?: string;
  merge_allowed?: boolean;
  cheat_detected?: string | null;
  source?: string;
  escrow?: Escrow;
  events?: BountyEvent[];
  gcp?: GcpMeta;
  agents?: Record<string, string>;
};

export type AgentCard = {
  id: string;
  name: string;
  version?: string;
  identity?: string;
  status?: string;
  tool_scope?: string[];
};

export type Registry = {
  agents?: AgentCard[];
  track?: string;
};

export type Health = {
  service?: string;
  status?: string;
};

export async function fetchJson<T>(path: string): Promise<T> {
  const resp = await fetch(path);
  if (!resp.ok) {
    throw new Error(`${path} ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

export type HistoryPr = {
  wait_on?: string;
  outcome?: string;
  repo?: string;
  number?: string;
  title?: string;
  url?: string;
  opened?: string;
  closed?: string | null;
  hours_open?: number | null;
};

export type HistoryRepo = {
  repo: string;
  opened: number;
  waiting: number;
  merged: number;
  closed: number;
  merge_rate?: string;
};

export type HistoryClaim = {
  wait_on?: string;
  repo?: string;
  number?: string;
  title?: string;
  url?: string;
  platform?: string;
  status?: string;
  payout_usd?: number;
  payout_note?: string;
};

export type HistoryArchive = {
  why_parked?: string;
  state?: string;
  repo?: string;
  number?: string;
  title?: string;
  url?: string;
  opened?: string;
};

export type Overseer = {
  meta?: {
    source?: string;
    snapshot?: string;
    window?: string;
    rule?: string;
    money?: string;
  };
  sprint?: {
    opened?: number;
    waiting?: number;
    merged?: number;
    closed?: number;
    days?: { day: string; opened: number }[];
    repos?: HistoryRepo[];
    prs?: HistoryPr[];
  };
  claims?: HistoryClaim[];
  archive?: HistoryArchive[];
};

export function loadFleet() {
  return Promise.all([
    fetchJson<Health>("/health"),
    fetchJson<Registry>("/api/registry"),
    fetchJson<{ bounty: Bounty | null }>("/api/bounties/latest"),
  ]);
}

export function loadHistory() {
  return fetchJson<Overseer>("/api/history");
}
