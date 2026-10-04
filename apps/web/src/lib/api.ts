// Thin API client. Every call falls back to embedded demo data so the UI works offline.
export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
export const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || "";

export type Network = "in" | "out";

export interface Provider {
  provider_id: string; name: string; specialty: string; address: string; phone: string;
  latitude: number; longitude: number; accepting_new_patients: boolean;
  network_status: "VERIFIED_IN_NETWORK" | "OUT_OF_NETWORK"; distance_miles: number;
}
export interface Coverage {
  code: string; network: Network; covered: boolean; provider_charge: number; allowed_amount: number;
  deductible_applied: number; coinsurance_pct: number; plan_payment: number; member_payment: number;
  annual_max_applied: boolean; disclaimer: string; steps: { rule: string; description: string }[];
}
export interface ProcedureMatch {
  procedure: string; selected_code: string; possible_codes: string[]; confidence: number; requires_confirmation: boolean;
}
export interface AgentResponse {
  status: string; explanation?: string; message?: string;
  procedures?: ProcedureMatch[];
  comparisons?: Record<string, { in: Coverage; out: Coverage }>;
}
export interface FundingMonth { label: string; paid_in_month: number; cumulative_used: number; remaining: number; }
export interface Timeline {
  annual_maximum: number; benefits_used: number; benefits_pending: number; benefits_remaining: number;
  percent_used: number; deductible_individual: number; deductible_remaining: number; plan_year_end: string;
  months: FundingMonth[]; by_category: Record<string, number>; note: string;
}
export interface RewardItem {
  id: string; name: string; type: "gift_card" | "discount" | "cash_sweepstakes" | "sweepstakes";
  cost_points: number; value: string; detail: string; affordable: boolean;
}
export interface Rewards {
  tier: string; tier_multiplier: number; points_balance: number; lifetime_points: number;
  next_tier: string | null; points_to_next_tier: number; tier_progress_pct: number; sweepstakes_entries: number;
  earn_rules: string[]; ledger: { event_date: string; description: string; points: number }[];
  catalog: RewardItem[]; disclaimer: string;
}

async function getJSON<T>(path: string, ms = 2000): Promise<T | null> {
  try {
    const r = await fetch(`${API_BASE}${path}`, { signal: AbortSignal.timeout(ms) });
    return r.ok ? ((await r.json()) as T) : null;
  } catch { return null; }
}
async function postJSON<T>(path: string, body: unknown, ms = 4000): Promise<T | null> {
  try {
    const r = await fetch(`${API_BASE}${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body), signal: AbortSignal.timeout(ms),
    });
    return r.ok ? ((await r.json()) as T) : null;
  } catch { return null; }
}

export interface ClinicServiceEstimate { code: string; name: string; category: string; allowed_amount: number; member_pays: number; covered: boolean; }
export interface ClinicEstimates { provider_id: string; provider_name: string; network: Network; services: ClinicServiceEstimate[]; disclaimer: string; }
export type Urgency = "routine" | "soon" | "urgent";
export interface PreAuth {
  id: string; status: "submitted" | "approved" | "denied"; procedure_name: string; provider_name: string;
  estimated_cost: number; requested_amount: number; urgency: Urgency; reason: string; decision_note: string; submitted_at: string;
}

export type Relationship = "guardian" | "dependent";
export interface MemberSummary {
  member_id: string; name: string; relationship: Relationship; age: number | null;
  annual_maximum: number; benefits_used: number; benefits_remaining: number; percent_used: number;
  state: "plenty_remaining" | "moderate_utilization" | "near_annual_maximum";
}
export interface Account { account_id: string; employer: string; plan_name: string; guardian_id: string; members: MemberSummary[]; }

export const api = {
  account: () => getJSON<Account>("/api/v1/account"),
  agent: (message: string, member = "demo") => postJSON<AgentResponse>("/api/v1/agent/message", { message, member_id: member }),
  providers: (zip: string) =>
    getJSON<{ providers: { provider: Omit<Provider, "network_status" | "distance_miles">; network_status: Provider["network_status"]; distance_miles: number }[] }>(
      `/api/v1/providers?zip_code=${zip}&radius=15&include_out_of_network=true`,
    ),
  timeline: (member = "demo") => getJSON<Timeline>(`/api/v1/benefits/timeline?member_id=${member}`),
  rewards: (member = "demo") => getJSON<Rewards>(`/api/v1/rewards?member_id=${member}`),
  redeem: (item_id: string, member = "demo") =>
    postJSON<{ ok: boolean; message: string; points_balance: number; sweepstakes_entries: number }>(
      "/api/v1/rewards/redeem", { item_id, member_id: member }, 2000,
    ),
  clinicEstimates: (providerId: string, member = "demo") =>
    getJSON<ClinicEstimates>(`/api/v1/providers/${providerId}/estimates?member_id=${member}`),
  preauthCreate: (body: { member_id: string; provider_id: string; code: string; estimated_cost: number; requested_amount: number; urgency: Urgency; reason: string }) =>
    postJSON<PreAuth>("/api/v1/preauth", body, 3000),
  preauthDecide: (id: string) => postJSON<PreAuth>(`/api/v1/preauth/${id}/decide`, {}, 3000),
};

export const money = (n: number) => "$" + Math.round(n).toLocaleString();
