import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, type PTOBalance, type PTORequest, type WorkSchedule } from "../lib/api";
import { useProfile } from "../lib/profile";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const hrs = (n: number) => `${Math.round(n * 10) / 10}h`;
const clock = (h: number) => {
  const H = Math.floor(h), m = Math.round((h - H) * 60);
  return `${((H + 11) % 12) + 1}${m ? ":" + String(m).padStart(2, "0") : ""}${H < 12 ? "am" : "pm"}`;
};
const STATUS_COLOR: Record<PTORequest["status"], string> = {
  submitted: "#B8860B", approved: "var(--in)", denied: "var(--accent)",
};

export function Employee() {
  const { activeId, isGuardian } = useProfile();
  const [bal, setBal] = useState<PTOBalance | null>(null);
  const [sched, setSched] = useState<WorkSchedule | null>(null);
  const [reqs, setReqs] = useState<PTORequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);

  async function load() {
    setLoading(true);
    const [b, s, r] = await Promise.all([
      api.ptoBalance(activeId), api.employeeSchedule(activeId), api.ptoRequests(activeId),
    ]);
    setBal(b); setSched(s); setReqs(r?.requests ?? []); setEditing(false); setLoading(false);
  }
  useEffect(() => { void load(); }, [activeId]);

  if (loading) return <div className="loading">Loading time off…</div>;
  if (!bal || !sched)
    return (
      <div className="note" style={{ marginTop: 8 }}>
        <b>No HR profile on file.</b> Emergency time off is managed for the enrolled employee
        {isGuardian ? "." : " — switch to the employee (guardian) profile to view it."}
      </div>
    );

  const out = bal.used_hours + bal.pending_hours;
  const usedPct = bal.accrued_hours ? Math.round((out / bal.accrued_hours) * 100) : 0;

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="wd">
      <div className="wd-head">
        <div>
          <div className="d-title">Emergency time off</div>
          <div className="d-sub">{bal.employer} · managed with your dental visits</div>
        </div>
        <span className="wd-chip">Powered by Workday · demo</span>
      </div>

      <div className="wd-grid">
        <section className="wd-card">
          <div className="wd-card-t">PTO balance <span className="wd-asof">as of {sched && bal.as_of}</span></div>
          <div className="wd-bal"><b>{hrs(bal.available_hours)}</b><span>available</span></div>
          <div className="gauge" style={{ marginTop: 12 }}>
            <motion.div className="gauge-fill wd-fill" initial={{ width: 0 }} animate={{ width: `${usedPct}%` }} transition={{ duration: 0.8 }} />
          </div>
          <div className="wd-legend">
            <span><i className="wd-dot used" />Used {hrs(bal.used_hours)}</span>
            <span><i className="wd-dot pend" />Pending {hrs(bal.pending_hours)}</span>
            <span><i className="wd-dot acc" />Accrued {hrs(bal.accrued_hours)}</span>
          </div>
        </section>

        <section className="wd-card">
          <div className="wd-card-t">
            Work schedule
            {!editing && <button className="wd-link" onClick={() => setEditing(true)}>Edit</button>}
          </div>
          {!editing ? (
            <>
              <div className="wd-days">
                {DAYS.map((d, i) => (
                  <span key={d} className={`wd-day${sched.work_days.includes(i) ? " on" : ""}`}>{d[0]}</span>
                ))}
              </div>
              <dl className="wd-dl">
                <div><dt>Hours</dt><dd>{clock(sched.start_hour)} – {clock(sched.end_hour)}</dd></div>
                <div><dt>Time zone</dt><dd>{sched.timezone}</dd></div>
                <div><dt>Manager</dt><dd>{sched.manager}</dd></div>
              </dl>
            </>
          ) : (
            <ScheduleEditor sched={sched} onCancel={() => setEditing(false)} onSaved={() => void load()} />
          )}
        </section>
      </div>

      <section className="wd-card" style={{ marginTop: 16 }}>
        <div className="wd-card-t">Time-off requests</div>
        {reqs.length === 0 ? (
          <div className="wd-empty">No requests yet. In an emergency, the assistant can draft one for you around your work hours.</div>
        ) : (
          <div className="wd-reqs">
            {reqs.map((r) => (
              <div className="wd-req" key={r.id}>
                <div className="wd-req-main">
                  <b>{r.id}</b><span>{hrs(r.hours)} · {r.date_needed}</span>
                  <span className="wd-req-reason">{r.reason}</span>
                </div>
                <span className="wd-status" style={{ color: STATUS_COLOR[r.status] }}>{r.status.toUpperCase()}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="note" style={{ marginTop: 16 }}>
        <b>Demo only.</b> No real HR system is contacted. Approved requests draw down this simulated
        balance; clinical care always comes first and is never gated on approval.
      </div>
    </motion.div>
  );
}

function ScheduleEditor({ sched, onCancel, onSaved }: { sched: WorkSchedule; onCancel: () => void; onSaved: () => void }) {
  const [days, setDays] = useState<number[]>(sched.work_days);
  const [start, setStart] = useState(sched.start_hour);
  const [end, setEnd] = useState(sched.end_hour);
  const [manager, setManager] = useState(sched.manager);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const toggle = (i: number) => setDays((d) => (d.includes(i) ? d.filter((x) => x !== i) : [...d, i].sort()));

  async function save() {
    if (end <= start) { setErr("End time must be after start time."); return; }
    if (days.length === 0) { setErr("Pick at least one working day."); return; }
    setBusy(true); setErr(null);
    const r = await api.employeeScheduleUpdate({
      member_id: sched.member_id, work_days: days, start_hour: start, end_hour: end, manager,
    });
    setBusy(false);
    if (r) onSaved(); else setErr("Couldn't save — please try again.");
  }

  return (
    <div className="wd-edit">
      <label className="wd-f">Working days
        <div className="wd-days edit">
          {DAYS.map((d, i) => (
            <button type="button" key={d} className={`wd-day${days.includes(i) ? " on" : ""}`} onClick={() => toggle(i)}>{d[0]}</button>
          ))}
        </div>
      </label>
      <div className="wd-f-row">
        <label className="wd-f">Start
          <input type="number" min={0} max={24} step={0.5} value={start} onChange={(e) => setStart(+e.target.value)} />
        </label>
        <label className="wd-f">End
          <input type="number" min={0} max={24} step={0.5} value={end} onChange={(e) => setEnd(+e.target.value)} />
        </label>
      </div>
      <label className="wd-f">Manager
        <input type="text" value={manager} onChange={(e) => setManager(e.target.value)} />
      </label>
      {err && <div className="wd-err">{err}</div>}
      <div className="wd-actions">
        <button className="wd-btn ghost" onClick={onCancel} disabled={busy}>Cancel</button>
        <button className="wd-btn" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save schedule"}</button>
      </div>
    </div>
  );
}
