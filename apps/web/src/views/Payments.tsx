import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api, type ClinicServiceEstimate, type PaymentPlan, type Provider } from "../lib/api";
import { PROVIDERS, haversine } from "../data/fallback";
import { useProfile } from "../lib/profile";

const money = (n: number) => "$" + Math.round(n).toLocaleString();
const fmtDate = (s: string) => new Date(s + "T12:00:00").toLocaleDateString("en-US", { month: "short", year: "numeric" });
const TERMS = [6, 12, 24];

export function Payments() {
  const { activeId, active } = useProfile();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [providerId, setProviderId] = useState("P001");
  const [services, setServices] = useState<ClinicServiceEstimate[]>([]);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [term, setTerm] = useState(12);
  const [plan, setPlan] = useState<PaymentPlan | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.providers("19122").then((r) => {
      const list = r ? r.providers.map((p) => ({ ...p.provider, network_status: p.network_status, distance_miles: p.distance_miles }))
        : PROVIDERS.map((p) => ({ ...p, distance_miles: +haversine(39.978, -75.137, p.latitude, p.longitude).toFixed(1) }));
      setProviders(list.filter((p) => p.network_status === "VERIFIED_IN_NETWORK"));
    });
  }, []);

  useEffect(() => {
    setPicked(new Set()); setPlan(null);
    api.clinicEstimates(providerId, activeId).then((e) => setServices((e?.services ?? []).filter((s) => s.covered && s.member_pays > 0)));
  }, [providerId, activeId]);

  const total = useMemo(() => services.filter((s) => picked.has(s.code)).reduce((a, s) => a + s.member_pays, 0), [services, picked]);
  const monthly = total > 0 ? total / term : 0;

  function toggle(code: string) {
    setPicked((p) => { const n = new Set(p); n.has(code) ? n.delete(code) : n.add(code); return n; });
  }

  async function createAndSend() {
    if (picked.size === 0) return;
    setBusy(true);
    const created = await api.paymentPlanCreate({ member_id: activeId, provider_id: providerId, codes: [...picked], term_months: term });
    const sent = created ? await api.paymentPlanSend(created.id) : null;
    setBusy(false);
    setPlan(sent ?? created);
  }
  async function decide(approve: boolean) {
    if (!plan) return;
    setBusy(true);
    const out = await api.paymentPlanDecide(plan.id, approve);
    setBusy(false);
    if (out) setPlan(out);
  }

  const provider = providers.find((p) => p.provider_id === providerId);

  return (
    <motion.div className="view" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="demo-banner">⚠️ Simulated payment agreement — demo only. No real money moves and nothing is a binding contract.</div>
      <div className="d-head"><div>
        <div className="d-title">Set up a payment plan</div>
        <div className="d-sub">Build an itinerary of what {active.name} wants done at one dentist, choose a term, and send it to the office to approve.</div>
      </div></div>

      {!plan ? (
        <>
          <div className="panel-lite">
            <div className="pl-title">1 · Choose your dentist</div>
            <select className="pp-select" value={providerId} onChange={(e) => setProviderId(e.target.value)}>
              {providers.map((p) => <option key={p.provider_id} value={p.provider_id}>{p.name} · {p.specialty} · {p.distance_miles} mi</option>)}
            </select>
          </div>

          <div className="panel-lite">
            <div className="pl-title">2 · Pick the procedures (your estimated share)</div>
            {services.length === 0 ? <div className="earn-foot">No priced services for this clinic.</div> : services.map((s) => (
              <label className={`pp-srv${picked.has(s.code) ? " on" : ""}`} key={s.code}>
                <input type="checkbox" checked={picked.has(s.code)} onChange={() => toggle(s.code)} />
                <span className="pp-srv-name">{s.name}<span>{s.code}</span></span>
                <span className="pp-srv-cost">{money(s.member_pays)}</span>
              </label>
            ))}
          </div>

          <div className="panel-lite">
            <div className="pl-title">3 · Choose a term</div>
            <div className="pp-terms">{TERMS.map((t) => (
              <button key={t} className={`pp-term${term === t ? " on" : ""}`} onClick={() => setTerm(t)}>{t} months</button>
            ))}</div>
            <div className="pp-summary">
              <div><span>Amount financed</span><b>{money(total)}</b></div>
              <div><span>Monthly payment</span><b style={{ color: "var(--brand)" }}>{money(monthly)}/mo</b></div>
              <div><span>At</span><b>{provider?.name ?? "—"}</b></div>
            </div>
            <button className="rwd-btn" style={{ width: "100%", padding: 11, marginTop: 4 }} disabled={busy || picked.size === 0} onClick={createAndSend}>
              {busy ? "Sending…" : "Create & send to dentist →"}
            </button>
          </div>
        </>
      ) : (
        <AnimatePresence mode="wait">
          <motion.div key={plan.status} className="panel-lite" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <div className="pp-plan-head">
              <div><div className="pp-plan-id">Plan {plan.id}</div><div className="earn-foot">{plan.provider_name}</div></div>
              <span className="pp-status" data-s={plan.status}>{plan.status.replace(/_/g, " ")}</span>
            </div>
            <div className="pp-summary">
              <div><span>Amount financed</span><b>{money(plan.total)}</b></div>
              <div><span>Term</span><b>{plan.term_months} months</b></div>
              <div><span>Monthly</span><b style={{ color: "var(--brand)" }}>{money(plan.monthly_amount)}/mo</b></div>
            </div>

            <div className="pl-title" style={{ marginTop: 14 }}>Procedures</div>
            <ul className="ledger">{plan.items.map((i) => <li key={i.code}><span>{i.name} · {i.code}</span><b style={{ color: "var(--ink)" }}>{money(i.cost)}</b></li>)}</ul>

            <div className="pl-title" style={{ marginTop: 14 }}>Payment schedule</div>
            <div className="pp-sched">{plan.schedule.slice(0, 6).map((r) => (
              <div className="pp-sched-row" key={r.n}><span>#{r.n} · {fmtDate(r.due_date)}</span><b>{money(r.amount)}</b></div>
            ))}{plan.schedule.length > 6 && <div className="earn-foot">+ {plan.schedule.length - 6} more payments</div>}</div>

            {plan.status === "sent_to_doctor" && (
              <div className="pp-actions">
                <button className="rwd-btn" disabled={busy} onClick={() => decide(true)}>Simulate dentist approval</button>
                <button className="pp-decline" disabled={busy} onClick={() => decide(false)}>Decline</button>
              </div>
            )}
            {plan.status === "active" && <div className="note" style={{ marginTop: 14 }}><b>Agreement active (simulated).</b> Your dentist approved the plan. This is a demo — no funds are collected.</div>}
            {plan.status === "declined" && <div className="note" style={{ marginTop: 14 }}>The dentist declined this plan (demo). You can start a new one.</div>}

            <div className="pl-title" style={{ marginTop: 14 }}>Audit trail</div>
            <ul className="ledger">{plan.audit.map((a, i) => <li key={i}><span>{a.event}</span><b style={{ color: "var(--faint)", fontWeight: 500 }}>{new Date(a.at).toLocaleTimeString()}</b></li>)}</ul>

            <button className="cta" style={{ marginLeft: 0, marginTop: 14 }} onClick={() => setPlan(null)}>← Build another plan</button>
          </motion.div>
        </AnimatePresence>
      )}
    </motion.div>
  );
}
