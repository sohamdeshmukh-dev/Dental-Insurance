import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CARE_TREATMENTS, CARE_PRODUCTS, amazonSearch, type CareTreatment } from "../data/fallback";

const money = (n: number) => "$" + Math.round(n).toLocaleString();
const careDate = (s: string) => new Date(s + "T00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

function summary(t: CareTreatment) {
  const done = t.sessions.filter((s) => s.done).length;
  const left = t.sessions.length - done;
  const next = t.sessions.find((s) => !s.done);
  return { done, left, balance: Math.max(0, t.fee - t.insurance - t.paid), next };
}

export function Care() {
  const [idx, setIdx] = useState(0);
  const t = CARE_TREATMENTS[idx];
  const { done, left, balance, next } = summary(t);
  const total = t.sessions.length;
  const shown = total > 8 ? t.sessions.filter((s) => !s.done).slice(0, 4) : t.sessions;
  const more = total > 8 ? left - shown.length : 0;
  const pay = balance === 0 ? ["Paid in full. Nothing owed."] : [
    `**Pay in full**: ${money(balance)} today`,
    ...(left > 1 && left <= 6 ? [`**Pay per visit**: about ${money(balance / left)} at each of your ${left} remaining sessions`] : []),
    `**Monthly plan**: ${t.months} payments of about ${money(balance / t.months)} (ask your office about terms)`,
  ];

  return (
    <div className="view">
      <div className="d-head"><div>
        <div className="d-title">Your care &amp; treatment tracker</div>
        <div className="d-sub">Track multi-visit treatments, what you've paid, what's left, and how to care for each one.</div>
      </div></div>

      <AnimatePresence mode="wait">
        <motion.div key={idx} initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }} transition={{ type: "spring", stiffness: 320, damping: 30 }}>
          <div className="d-title" aria-live="polite" style={{ fontSize: 21 }}>{t.name}</div>
          <div className="care-count">Treatment {idx + 1} of {CARE_TREATMENTS.length} · {t.detail}</div>

          <div className="stat-row">
            <div className="stat"><div className="stat-k">Sessions completed</div><div className="stat-v">{done} of {total}</div></div>
            <div className="stat"><div className="stat-k">Sessions left</div><div className="stat-v">{left}</div></div>
            <div className="stat"><div className="stat-k">Paid so far</div><div className="stat-v">{money(t.paid)}</div></div>
            <div className="stat hi"><div className="stat-k">Balance owed</div><div className="stat-v">{money(balance)}</div></div>
          </div>

          <div className="gauge" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done}>
            <motion.div className="gauge-fill" initial={{ width: 0 }} animate={{ width: `${(done / total) * 100}%` }} transition={{ duration: 0.9 }} />
          </div>
          <div className="gauge-cap"><span>{done} of {total} sessions done</span><span>{next ? `Next: ${next.label}, ${careDate(next.date)}` : "All sessions done"}</span></div>

          <div className="rwd-grid">
            <div className="panel-lite">
              <div className="pl-title">{total > 8 ? "Upcoming sessions" : "Sessions"}</div>
              <ul className="ledger">{shown.map((s, i) => (
                <li key={i} className={s.done ? "" : "todo"}><span>{s.label} · {careDate(s.date)}</span><b>{s.done ? "✓ Done" : "Upcoming"}</b></li>
              ))}</ul>
              {total > 8 && <div className="earn-foot">{done} visits completed{more > 0 ? ` and ${more} more after these` : ""}.</div>}
            </div>
            <div className="panel-lite">
              <div className="pl-title">Payment options</div>
              <ul className="earn">{pay.map((p, i) => <li key={i} dangerouslySetInnerHTML={{ __html: p.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>") }} />)}</ul>
              <div className="earn-foot">Total fee {money(t.fee)}, minus estimated insurance {money(t.insurance)}, minus {money(t.paid)} paid. {t.coverage}</div>
            </div>
          </div>

          <div className="panel-lite">
            <div className="pl-title">Care advice</div>
            <ul className="earn">{t.advice.map((a, i) => <li key={i}>{a}</li>)}</ul>
            <div className="earn-foot">General guidance only. Follow your dentist's instructions for your treatment.</div>
          </div>

          {(CARE_PRODUCTS[t.name] ?? []).length > 0 && (
            <div className="panel-lite">
              <div className="pl-title">Suggested for your recovery</div>
              <div className="prod-grid">
                {CARE_PRODUCTS[t.name].map((p, i) => (
                  <motion.a key={i} className="prod" href={amazonSearch(p.query)} target="_blank" rel="noopener noreferrer"
                    initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }} whileHover={{ y: -3 }}>
                    <div className={`prod-ic ${p.kind}`}>{p.emoji}</div>
                    <div className="prod-label">{p.label}</div>
                    <div className="prod-link">View on Amazon →</div>
                  </motion.a>
                ))}
              </div>
              <div className="earn-foot">Suggestions only — not endorsements, and not medical advice. These are general comfort/aftercare items; follow your dentist's instructions, and ask them before taking any medication.</div>
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      <div className="care-dots" role="tablist" aria-label="Choose a treatment">
        {CARE_TREATMENTS.map((x, i) => (
          <button key={i} className={`care-dot${i === idx ? " on" : ""}`} role="tab" aria-selected={i === idx} aria-label={x.name} title={x.name} onClick={() => setIdx(i)} />
        ))}
      </div>
    </div>
  );
}
