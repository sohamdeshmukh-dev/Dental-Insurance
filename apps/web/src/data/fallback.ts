import type { Provider, Timeline, Rewards } from "../lib/api";

export const ZIP_CENTROIDS: Record<string, [number, number]> = {
  "19122": [39.978, -75.137], "19103": [39.9526, -75.1745], "19104": [39.957, -75.198],
  "19125": [39.97, -75.125], "19146": [39.937, -75.183],
};

type RawProvider = Omit<Provider, "network_status" | "distance_miles"> & { network_status: Provider["network_status"] };
export const PROVIDERS: RawProvider[] = [
  { provider_id: "P001", name: "Fishtown Family Dental", specialty: "General Dentist", address: "1200 Frankford Ave", phone: "215-555-0101", latitude: 39.9702, longitude: -75.134, accepting_new_patients: true, network_status: "VERIFIED_IN_NETWORK" },
  { provider_id: "P002", name: "Temple Endodontics", specialty: "Endodontist", address: "3223 N Broad St", phone: "215-555-0102", latitude: 40.01, longitude: -75.153, accepting_new_patients: true, network_status: "VERIFIED_IN_NETWORK" },
  { provider_id: "P003", name: "Girard Smile Studio", specialty: "General Dentist", address: "1500 W Girard Ave", phone: "215-555-0103", latitude: 39.97, longitude: -75.165, accepting_new_patients: true, network_status: "VERIFIED_IN_NETWORK" },
  { provider_id: "P004", name: "Northern Liberties Dental", specialty: "General Dentist", address: "900 N 2nd St", phone: "215-555-0104", latitude: 39.964, longitude: -75.14, accepting_new_patients: true, network_status: "VERIFIED_IN_NETWORK" },
  { provider_id: "P005", name: "Center City Premier Dentistry", specialty: "General Dentist", address: "1800 Walnut St", phone: "215-555-0105", latitude: 39.95, longitude: -75.172, accepting_new_patients: true, network_status: "OUT_OF_NETWORK" },
  { provider_id: "P006", name: "Kensington Endodontic Care", specialty: "Endodontist", address: "2500 E Allegheny Ave", phone: "215-555-0106", latitude: 39.986, longitude: -75.1, accepting_new_patients: false, network_status: "OUT_OF_NETWORK" },
];

export function haversine(a: number, b: number, c: number, d: number): number {
  const R = 3958.8, p1 = (a * Math.PI) / 180, p2 = (c * Math.PI) / 180;
  const dp = ((c - a) * Math.PI) / 180, dl = ((d - b) * Math.PI) / 180;
  const x = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
}

export const TIMELINE_FALLBACK: Timeline = {
  annual_maximum: 1500, benefits_used: 550, benefits_pending: 0, benefits_remaining: 950, percent_used: 36.7,
  deductible_individual: 50, deductible_remaining: 50, plan_year_end: "2026-12-31",
  by_category: { preventive: 310, basic: 240 },
  months: [["Jan", 0, 0, 1500], ["Feb", 125, 125, 1375], ["Mar", 90, 215, 1285], ["Apr", 0, 215, 1285],
    ["May", 120, 335, 1165], ["Jun", 0, 335, 1165], ["Jul", 0, 335, 1165], ["Aug", 215, 550, 950],
    ["Sep", 0, 550, 950], ["Oct", 0, 550, 950], ["Nov", 0, 550, 950], ["Dec", 0, 550, 950]]
    .map((m) => ({ label: m[0] as string, paid_in_month: m[1] as number, cumulative_used: m[2] as number, remaining: m[3] as number })),
  note: "$950 of your $1,500 annual maximum is still available with 89 days left in the plan year — unused benefits do not roll over.",
};

export const REWARDS_FALLBACK: Rewards = {
  tier: "Gold", tier_multiplier: 1.25, points_balance: 2292, lifetime_points: 2070, next_tier: "Platinum",
  points_to_next_tier: 1430, tier_progress_pct: 28.5, sweepstakes_entries: 2,
  earn_rules: ["Routine exam — 50 pts", "Cleaning — 100 pts", "X-rays — 40 pts", "Fluoride / sealant — 60–80 pts",
    "In-network visit — +25 pts", "Both recommended cleanings in a year — +200 pts", "Complete dentist-recommended follow-up care — +150 pts"],
  ledger: [
    { event_date: "2026-08-07", description: "Preventive streak: both recommended cleanings this year", points: 200 },
    { event_date: "2026-08-07", description: "Cleaning completed", points: 100 },
    { event_date: "2026-08-07", description: "Completed recommended care (Resin filling)", points: 150 },
    { event_date: "2026-05-20", description: "Completed recommended care (Resin filling)", points: 150 },
    { event_date: "2026-03-12", description: "Cleaning completed", points: 100 },
  ],
  catalog: [
    { id: "gc-amazon-25", name: "$25 Amazon gift card", type: "gift_card", cost_points: 2500, value: "$25", detail: "Digital gift card by email (demo).", affordable: false },
    { id: "gc-target-50", name: "$50 Target gift card", type: "gift_card", cost_points: 4800, value: "$50", detail: "Digital gift card by email (demo).", affordable: false },
    { id: "disc-sealants", name: "10% off your next visit", type: "discount", cost_points: 1500, value: "10% off", detail: "At your selected in-network dentist (demo).", affordable: true },
    { id: "disc-whitening", name: "20% off cosmetic whitening", type: "discount", cost_points: 2200, value: "20% off", detail: "At your selected in-network dentist (demo).", affordable: true },
    { id: "swp-500", name: "Quarterly $500 cash sweepstakes entry", type: "cash_sweepstakes", cost_points: 500, value: "1 entry", detail: "Entry into the quarterly $500 cash drawing (demo).", affordable: true },
    { id: "swp-grand", name: "Annual $5,000 grand-prize sweepstakes entry", type: "cash_sweepstakes", cost_points: 1000, value: "1 entry", detail: "Entry into the annual grand-prize drawing (demo).", affordable: true },
    { id: "swp-spa", name: "Wellness spa-day sweepstakes entry", type: "sweepstakes", cost_points: 400, value: "1 entry", detail: "Entry into the wellness experience drawing (demo).", affordable: true },
  ],
  disclaimer: "Prototype rewards for demonstration only — not a live financial product. Points, prizes, sweepstakes, and discounts are illustrative. Clinical urgency always comes first; rewards never depend on getting care you don't need.",
};

// --- Care tracker (static demo, ported from the original page) ---
export interface CareSession { label: string; date: string; done: boolean; }
export interface CareTreatment {
  name: string; detail: string; fee: number; insurance: number; paid: number; months: number;
  coverage: string; sessions: CareSession[]; advice: string[];
}
const monthly = (y: number, m: number, d: number, n: number, doneCount: number, label: (i: number) => string): CareSession[] =>
  Array.from({ length: n }, (_, i) => ({ label: label(i + 1), done: i < doneCount, date: new Date(Date.UTC(y, m + i, d)).toISOString().slice(0, 10) }));

export const CARE_TREATMENTS: CareTreatment[] = [
  {
    name: "Teeth whitening", detail: "In-office whitening course, 4 sessions", fee: 480, insurance: 0, paid: 240, months: 3,
    coverage: "Cosmetic whitening is generally not covered by dental plans, so it does not use your annual maximum. The balance is owed to your dental office.",
    sessions: [{ label: "Session 1", date: "2026-09-05", done: true }, { label: "Session 2", date: "2026-09-19", done: true },
      { label: "Session 3", date: "2026-10-17", done: false }, { label: "Session 4", date: "2026-10-31", done: false }],
    advice: ["Avoid sodas, coffee, tea, red wine, and dark sauces for 48 hours after each session. Teeth stain most easily right after whitening.",
      "Sodas and sports drinks are also acidic, which can add to sensitivity. If you do have one, use a straw and rinse with water afterward.",
      "Skip tobacco during the course. It stains quickly and undoes results.",
      "Mild sensitivity for a day or two is common. Use a sensitivity toothpaste and avoid very hot or cold drinks.",
      "Brush gently twice a day with a soft brush and keep up your regular cleanings.",
      "Call your dentist if sensitivity or gum irritation lasts more than a few days."],
  },
  {
    name: "Dental implant", detail: "Single implant, lower molar, 5 stages over about 6 months", fee: 4200, insurance: 950, paid: 1500, months: 12,
    coverage: "Estimated insurance: $950, which is the remaining annual maximum on your plan. Implants are often a major service with limits, so actual claim processing determines final benefits.",
    sessions: [{ label: "Consult and 3D scan", date: "2026-08-12", done: true }, { label: "Extraction and bone graft", date: "2026-08-26", done: true },
      { label: "Implant placement", date: "2026-09-30", done: true }, { label: "Healing check (bone integration)", date: "2026-12-02", done: false },
      { label: "Abutment and crown", date: "2027-01-20", done: false }],
    advice: ["For the first 1 to 2 weeks after surgery, eat soft, cool foods like yogurt, eggs, and mashed potatoes. Avoid crunchy, hard, or very hot foods.",
      "Do not use a straw, spit forcefully, or smoke. Suction and tobacco can dislodge the clot and slow healing.",
      "Starting the day after surgery, rinse gently with warm salt water 2 to 3 times a day. Do not brush the surgical site until your dentist says so.",
      "Swelling often peaks around day 2 or 3. Use a cold pack in the first 24 hours, then warmth, and keep your head elevated when resting.",
      "Take pain medication and any antibiotics exactly as prescribed.",
      "Once the crown is placed, clean around it like a natural tooth. Floss or use an interdental brush daily.",
      "Call your dentist if you have a fever, swelling that keeps getting worse after day 3, bleeding that will not stop, or a loose implant."],
  },
  {
    name: "Braces", detail: "Traditional metal braces, 24 monthly adjustment visits", fee: 5400, insurance: 1000, paid: 1600, months: 18,
    coverage: "Estimated insurance: $1,000, a typical orthodontic lifetime maximum. Orthodontic benefits often have their own limits, so actual claim processing determines final benefits.",
    sessions: monthly(2026, 3, 14, 24, 6, (n) => (n === 1 ? "Braces placed" : n === 24 ? "Braces removed and retainers" : `Adjustment ${n - 1}`)),
    advice: ["Avoid sticky and hard foods such as caramel, taffy, gum, ice, popcorn, and hard candy. They can break brackets and bend wires.",
      "Cut firm foods like apples and carrots into small pieces and chew with your back teeth.",
      "Brush after every meal and before bed. Floss daily using floss threaders, or try a water flosser, to clean around wires.",
      "Limit soda and sugary drinks. Sugar sitting around brackets can leave permanent white spots when the braces come off.",
      "Wear rubber bands (elastics) exactly as instructed. Skipping them adds months to treatment.",
      "Keep orthodontic wax with you for poking wires, and call your orthodontist if a bracket or wire breaks.",
      "Keep your regular cleanings every 6 months, and wear your retainer as directed once the braces come off."],
  },
];
