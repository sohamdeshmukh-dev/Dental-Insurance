import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, type Timeline } from "../lib/api";
import { TIMELINE_FALLBACK } from "../data/fallback";
import { Money } from "../components/bits";
import { useProfile } from "../lib/profile";
import { Employee } from "./Employee";

const CAT_COLORS: Record<string, string> = { preventive: "var(--in)", basic: "var(--brand-600)", major: "var(--accent)", ortho: "#8A5A00" };
const STATE_LABEL: Record<string, [string, string]> = {
  plenty_remaining: ["Plenty remaining", "var(--in)"], moderate_utilization: ["Moderate", "#B8860B"], near_annual_maximum: ["Near max", "var(--accent)"],
};

export function Dashboard() {
  const { account, active, activeId, isGuardian, setActiveId } = useProfile();
  const [d, setD] = useState<Timeline | null>(null);
  const [tab, setTab] = useState<"funding" | "timeoff">("funding");
  useEffect(() => { setD(null); api.timeline(activeId).then((t) => setD(t ?? TIMELINE_FALLBACK)); }, [activeId]);

  const tabs = (
    <div className="subtabs">
      <button className={`subtab${tab === "funding" ? " on" : ""}`} onClick={() => setTab("funding")}>Funding</button>
      <button className={`subtab${tab === "timeoff" ? " on" : ""}`} onClick={() => setTab("timeoff")}>Time Off</button>
    </div>
  );

  if (tab === "timeoff") return <div className="view">{tabs}<Employee /></div>;

  const family = isGuardian && account.members.length > 1 && (
    <div className="panel-lite" style={{ marginTop: 0, marginBottom: 18 }}>
      <div className="pl-title">Your family · benefits monitoring</div>
      <div className="family-grid">
        {account.members.map((m) => {
          const [lbl, col] = STATE_LABEL[m.state];
          return (
            <button className={`fam${m.member_id === activeId ? " on" : ""}`} key={m.member_id} onClick={() => setActiveId(m.member_id)}>
              <div className="fam-top"><div className="ava sm">{m.name.split(" ").map((w) => w[0]).slice(0, 2).join("")}</div>
                <div><b>{m.name}</b><span>{m.relationship === "guardian" ? "You" : `Dependent · ${m.age}`}</span></div>
                <span className="fam-state" style={{ color: col }}>{lbl}</span></div>
              <div className="gauge" style={{ height: 8 }}><motion.div className="gauge-fill" initial={{ width: 0 }} animate={{ width: `${m.percent_used}%` }} transition={{ duration: 0.8 }} /></div>
              <div className="fam-cap"><span><Money value={m.benefits_remaining} /> of <Money value={m.annual_maximum} /> left</span></div>
            </button>
          );
        })}
      </div>
    </div>
  );

  if (!d) return <div className="view">{tabs}{family}<div className="loading">Loading benefits…</div></div>;

  const pctUsed = Math.round(d.percent_used);
  const state = pctUsed < 50 ? ["Plenty remaining", "var(--in)"] : pctUsed < 80 ? ["Moderate utilization", "#B8860B"] : ["Near annual maximum", "var(--accent)"];
  const cats = Object.entries(d.by_category);
  const catMax = Math.max(1, ...cats.map((c) => c[1]));
  const endDate = new Date(d.plan_year_end + "T12:00:00").toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" });

  const W = 620, H = 160, P = 10, max = d.annual_maximum;
  const pts = d.months.map((m, i) => [P + (i * (W - 2 * P)) / 11, H - P - (m.remaining / max) * (H - 2 * P)] as [number, number]);
  const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  const area = `M${pts[0][0].toFixed(1)} ${H - P} ` + pts.map((p) => "L" + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ") + ` L${pts[11][0].toFixed(1)} ${H - P} Z`;

  return (
    <motion.div className="view" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      {tabs}
      {family}
      <div className="d-head">
        <div><div className="d-title">{isGuardian ? "Your Lincoln Financial funding" : `${active.name}'s dental funding`}</div><div className="d-sub">Plan year ends {endDate}</div></div>
        <span className="pill-state" style={{ color: state[1], borderColor: state[1] }}>{state[0]}</span>
      </div>

      <div className="stat-row">
        <Stat k="Annual maximum" v={d.annual_maximum} />
        <Stat k="Used + pending" v={d.benefits_used + d.benefits_pending} />
        <Stat k="Available now" v={d.benefits_remaining} hi />
        <Stat k="Deductible left" v={d.deductible_remaining} />
      </div>

      <div className="gauge">
        <motion.div className="gauge-fill" initial={{ width: 0 }} animate={{ width: `${pctUsed}%` }} transition={{ duration: 1, ease: [0.2, 0.8, 0.2, 1] }} />
      </div>
      <div className="gauge-cap"><span><Money value={d.benefits_used + d.benefits_pending} /> used ({pctUsed}%)</span><span><Money value={d.benefits_remaining} /> available</span></div>

      <div className="panel-lite">
        <div className="pl-title">Funding available through the year</div>
        <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="none" aria-label="Remaining funding by month">
          <defs><linearGradient id="g" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="var(--accent)" stopOpacity="0.22" /><stop offset="1" stopColor="var(--accent)" stopOpacity="0" /></linearGradient></defs>
          <motion.path d={area} fill="url(#g)" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }} />
          <motion.path d={line} fill="none" stroke="var(--accent)" strokeWidth={2.5} strokeLinejoin="round"
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.1, ease: "easeInOut" }} />
          {pts.map((p, i) => (
            <motion.circle key={i} cx={p[0].toFixed(1)} cy={p[1].toFixed(1)} r={d.months[i].paid_in_month > 0 ? 3 : 1.6} fill="var(--accent)"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 + i * 0.04 }} />
          ))}
        </svg>
        <div className="chart-x">{d.months.map((m) => <span key={m.label}>{m.label[0]}</span>)}</div>
      </div>

      <div className="panel-lite">
        <div className="pl-title">Where your benefits went</div>
        {cats.map(([k, v], i) => (
          <div className="cat-row" key={k}>
            <span className="cat-k">{k[0].toUpperCase() + k.slice(1)}</span>
            <div className="cat-bar">
              <motion.div initial={{ width: 0 }} animate={{ width: `${(v / catMax) * 100}%` }} transition={{ delay: 0.3 + i * 0.1, duration: 0.8, ease: [0.2, 0.8, 0.2, 1] }}
                style={{ background: CAT_COLORS[k] || "var(--muted)" }} />
            </div>
            <span className="cat-v"><Money value={v} /></span>
          </div>
        ))}
      </div>

      <div className="note" style={{ marginTop: 16 }}><b>Heads up:</b> {d.note}</div>
    </motion.div>
  );
}

function Stat({ k, v, hi }: { k: string; v: number; hi?: boolean }) {
  return (
    <motion.div className={`stat${hi ? " hi" : ""}`} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ type: "spring", stiffness: 300, damping: 26 }}>
      <div className="stat-k">{k}</div>
      <div className="stat-v" style={hi ? { color: "var(--in)" } : undefined}><Money value={v} /></div>
    </motion.div>
  );
}
