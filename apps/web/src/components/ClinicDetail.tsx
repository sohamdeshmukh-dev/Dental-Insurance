import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { api, type ClinicEstimates, type PreAuth, type Provider, type ServiceComparison, type Urgency } from "../lib/api";

const money = (n: number) => "$" + Math.round(n).toLocaleString();

export function ClinicDetail({ provider, memberId, onClose }: { provider: Provider; memberId: string; onClose: () => void }) {
  const inNet = provider.network_status === "VERIFIED_IN_NETWORK";
  const [est, setEst] = useState<ClinicEstimates | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [picked, setPicked] = useState<Set<string>>(new Set());

  useEffect(() => {
    setEst(null); setPicked(new Set());
    api.clinicEstimates(provider.provider_id, memberId).then((e) => {
      setEst(e);
      if (e) setPicked(new Set(e.services.map((s) => s.code)));  // start with everything selected
    });
  }, [provider.provider_id, memberId]);

  const toggle = (code: string) =>
    setPicked((p) => { const n = new Set(p); n.has(code) ? n.delete(code) : n.add(code); return n; });

  return (
    <motion.div className="clinic-scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
      <motion.div className="clinic-modal" onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, y: 20, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 20, scale: 0.97 }}
        transition={{ type: "spring", stiffness: 300, damping: 28 }}>
        <button className="cm-close" onClick={onClose} aria-label="Close">×</button>
        <div className="cm-head">
          <div>
            <div className="cm-name">{provider.name}</div>
            <div className="cm-sub">{provider.specialty} · {provider.distance_miles} mi · {provider.phone}</div>
          </div>
          <span className={`cm-badge ${inNet ? "in" : "out"}`}>{inNet ? "✓ In network" : "Out of network"}</span>
        </div>

        <div className="cm-section-title">Pick the services you need</div>
        {!est ? <div className="cm-loading">Estimating…</div> : (
          <div className="cm-services">
            {est.services.map((s) => (
              <label className={`cm-srv pick${picked.has(s.code) ? " on" : ""}`} key={s.code}>
                <input type="checkbox" checked={picked.has(s.code)} onChange={() => toggle(s.code)} />
                <div className="cm-srv-name">{s.name}<span>{s.code}</span></div>
                <div className="cm-srv-pay">{s.covered ? `${money(s.member_pays)}` : "Not covered"}<span>you pay {provider.network_status === "VERIFIED_IN_NETWORK" ? "in-network" : "out-of-network"}</span></div>
              </label>
            ))}
            <div className="cm-disc">{est.disclaimer}</div>
          </div>
        )}

        {est && est.services.length > 0 && (
          <ComparePanel codes={[...picked]} memberId={memberId} />
        )}

        {!inNet && (
          <div className="cm-oon">
            {!showForm ? (
              <>
                <div className="cm-oon-note">This clinic is <b>out of network</b>, so your share is usually higher. You can request <b>pre-authorization</b> from Lincoln Financial before treatment.</div>
                <button className="cm-btn" onClick={() => setShowForm(true)}>Request pre-authorization →</button>
              </>
            ) : (
              <PreAuthForm provider={provider} memberId={memberId} est={est} />
            )}
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}

function ComparePanel({ codes, memberId }: { codes: string[]; memberId: string }) {
  const [open, setOpen] = useState(false);
  const [cmp, setCmp] = useState<ServiceComparison | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open || codes.length === 0) { setCmp(null); return; }
    let live = true;
    setBusy(true);
    api.compareServices(codes, memberId).then((c) => { if (live) { setCmp(c); setBusy(false); } });
    return () => { live = false; };
  }, [open, codes.join(","), memberId]);

  if (codes.length === 0)
    return <div className="cm-cmp-hint">Select at least one service to compare in-network vs out-of-network cost.</div>;

  return (
    <div className="cm-cmp">
      <button className="cm-cmp-toggle" onClick={() => setOpen((v) => !v)}>
        {open ? "Hide" : "Compare"} in-network vs out-of-network ({codes.length} service{codes.length > 1 ? "s" : ""})
      </button>
      {open && (busy || !cmp ? <div className="cm-loading">Comparing…</div> : (
        <motion.div className="cm-cmp-body" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
          <div className="cm-cmp-row head"><span>Service</span><span>In-network</span><span>Out-of-network</span></div>
          {cmp.rows.map((r) => (
            <div className="cm-cmp-row" key={r.code}>
              <span className="cm-cmp-name">{r.name}<i>{r.code}</i></span>
              <span>{r.in_covered ? money(r.in_member_pays) : "—"}</span>
              <span>{r.out_covered ? money(r.out_member_pays) : "—"}</span>
            </div>
          ))}
          <div className="cm-cmp-row total">
            <span>Total you pay</span><span>{money(cmp.in_total)}</span><span>{money(cmp.out_total)}</span>
          </div>
          <div className="cm-cmp-save">Staying in-network saves about <b>{money(cmp.savings_total)}</b> on these services.</div>
          <div className="cm-disc">{cmp.disclaimer}</div>
        </motion.div>
      ))}
    </div>
  );
}

function PreAuthForm({ provider, memberId, est }: { provider: Provider; memberId: string; est: ClinicEstimates | null }) {
  const services = est?.services ?? [];
  const [code, setCode] = useState(services[0]?.code ?? "");
  const [amount, setAmount] = useState<number>(0);
  const [urgency, setUrgency] = useState<Urgency>("routine");
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<PreAuth | null>(null);
  const [busy, setBusy] = useState(false);

  const svc = useMemo(() => services.find((s) => s.code === code), [services, code]);
  const estCost = svc ? Math.round(svc.allowed_amount * 1.25) : 0; // typical out-of-network charge
  useEffect(() => { setAmount(estCost); }, [estCost]);

  async function submit() {
    if (!code) return;
    setBusy(true);
    const pa = await api.preauthCreate({ member_id: memberId, provider_id: provider.provider_id, code, estimated_cost: estCost, requested_amount: amount, urgency, reason });
    setBusy(false);
    setResult(pa ?? null);
  }
  async function decide() {
    if (!result) return;
    setBusy(true);
    const pa = await api.preauthDecide(result.id);
    setBusy(false);
    if (pa) setResult(pa);
  }

  if (result) {
    const color = result.status === "approved" ? "var(--in)" : result.status === "denied" ? "#ff6b5e" : "var(--me)";
    return (
      <div className="cm-pa-result">
        <div className="cm-pa-id">Pre-auth {result.id} · <span style={{ color }}>{result.status.toUpperCase()}</span></div>
        <div className="cm-pa-line">{result.procedure_name} at {result.provider_name}</div>
        <div className="cm-pa-line">Requested {money(result.requested_amount)} · {result.urgency}</div>
        {result.status === "submitted" ? (
          <>
            <div className="cm-pa-note">Submitted to Lincoln Financial — pending review (demo).</div>
            <button className="cm-btn" onClick={decide} disabled={busy}>{busy ? "…" : "Simulate Lincoln decision"}</button>
          </>
        ) : <div className="cm-pa-note">{result.decision_note}</div>}
      </div>
    );
  }

  return (
    <div className="cm-form">
      <div className="cm-form-title">Pre-authorization request</div>
      <label>Procedure
        <select value={code} onChange={(e) => setCode(e.target.value)}>
          {services.map((s) => <option key={s.code} value={s.code}>{s.name} ({s.code})</option>)}
        </select>
      </label>
      <div className="cm-form-row">
        <label>Estimated cost<input value={money(estCost)} readOnly /></label>
        <label>Requested amount<input type="number" value={amount} onChange={(e) => setAmount(+e.target.value)} /></label>
      </div>
      <label>Urgency
        <select value={urgency} onChange={(e) => setUrgency(e.target.value as Urgency)}>
          <option value="routine">Routine</option><option value="soon">Soon</option><option value="urgent">Urgent</option>
        </select>
      </label>
      <label>Reason (optional)<input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. specialist only available out of network" /></label>
      <button className="cm-btn" onClick={submit} disabled={busy || !code}>{busy ? "Submitting…" : "Submit to Lincoln Financial"}</button>
      <div className="cm-disc">Simulated pre-authorization for demo — no request is sent to a real payer.</div>
    </div>
  );
}
