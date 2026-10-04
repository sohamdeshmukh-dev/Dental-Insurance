import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api, type Rewards as RewardsData } from "../lib/api";
import { REWARDS_FALLBACK } from "../data/fallback";
import { AnimatedNumber } from "../components/bits";

const TYPE_ICON: Record<string, string> = { gift_card: "🎁", discount: "🏷️", cash_sweepstakes: "💵", sweepstakes: "🎟️" };
const TYPE_LABEL: Record<string, string> = { gift_card: "Gift card", discount: "Discount", cash_sweepstakes: "Cash sweepstakes", sweepstakes: "Sweepstakes" };

export function Rewards() {
  const [d, setD] = useState<RewardsData | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => { api.rewards().then((r) => setD(r ?? REWARDS_FALLBACK)); }, []);

  async function redeem(id: string) {
    if (!d) return;
    const res = await api.redeem(id);
    if (res?.ok) {
      setD({
        ...d, points_balance: res.points_balance, sweepstakes_entries: res.sweepstakes_entries,
        catalog: d.catalog.map((it) => ({ ...it, affordable: res.points_balance >= it.cost_points })),
      });
      setToast(res.message);
    } else {
      setToast(res?.message ?? "Redemption is a demo — connect the backend to apply it.");
    }
    setTimeout(() => setToast(null), 2800);
  }

  if (!d) return <div className="view"><div className="loading">Loading your rewards…</div></div>;
  const toNext = d.next_tier ? `${d.points_to_next_tier.toLocaleString()} pts to ${d.next_tier}` : "Top tier reached";

  return (
    <motion.div className="view" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="demo-banner">⚠️ Prototype loyalty program — illustrative rewards, not a live financial product.</div>

      <div className="hero">
        <motion.div className="hero-l" initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} transition={{ type: "spring", stiffness: 260, damping: 26 }}>
          <div className="tier-badge">{d.tier} tier · {d.tier_multiplier}× points</div>
          <div className="pts"><AnimatedNumber value={d.points_balance} /><span>points available</span></div>
          <div className="tier-prog"><motion.div className="tier-prog-fill" initial={{ width: 0 }} animate={{ width: `${d.next_tier ? d.tier_progress_pct : 100}%` }} transition={{ duration: 1, delay: 0.2 }} /></div>
          <div className="tier-cap"><span>{d.lifetime_points.toLocaleString()} lifetime pts</span><span>{toNext}</span></div>
        </motion.div>
        <motion.div className="hero-r" initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} transition={{ type: "spring", stiffness: 260, damping: 26, delay: 0.08 }}>
          <div className="entry-k">Sweepstakes entries</div>
          <div className="entry-v">🎟️ <AnimatedNumber value={d.sweepstakes_entries} duration={0.6} /></div>
          <div className="entry-note">Earned by preventive-care activity</div>
        </motion.div>
      </div>

      <div className="rwd-grid">
        <div className="panel-lite">
          <div className="pl-title">How you earn points</div>
          <ul className="earn">{d.earn_rules.map((r) => <li key={r}>{r}</li>)}</ul>
          <div className="earn-foot">Rewards are tied to preventive &amp; dentist-recommended care only — never to getting care you don't need.</div>
        </div>
        <div className="panel-lite">
          <div className="pl-title">Recent points activity</div>
          <ul className="ledger">{d.ledger.slice(0, 6).map((e, i) => (
            <motion.li key={i} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 + i * 0.05 }}>
              <span>{e.description}</span><b>+{e.points}</b>
            </motion.li>
          ))}</ul>
        </div>
      </div>

      <div className="pl-title" style={{ margin: "22px 0 2px" }}>Redeem your points</div>
      <div className="catalog">
        {d.catalog.map((it, i) => (
          <motion.div className={`rwd${it.affordable ? "" : " locked"}`} key={it.id}
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05, type: "spring", stiffness: 300, damping: 26 }}
            whileHover={it.affordable ? { y: -3 } : undefined}>
            <div className="rwd-top"><span className="rwd-ic">{TYPE_ICON[it.type]}</span><span className="rwd-type">{TYPE_LABEL[it.type]}</span></div>
            <div className="rwd-name">{it.name}</div>
            <div className="rwd-detail">{it.detail}</div>
            <div className="rwd-foot">
              <span className="rwd-cost">{it.cost_points.toLocaleString()} pts</span>
              <button className="rwd-btn" disabled={!it.affordable} onClick={() => redeem(it.id)}>
                {it.affordable ? (it.type.includes("sweepstakes") ? "Enter" : "Redeem") : "Locked"}
              </button>
            </div>
          </motion.div>
        ))}
      </div>
      <div className="note" style={{ marginTop: 18 }}>{d.disclaimer}</div>

      <AnimatePresence>
        {toast && (
          <motion.div className="toast" initial={{ opacity: 0, y: 40, x: "-50%" }} animate={{ opacity: 1, y: 0, x: "-50%" }} exit={{ opacity: 0, y: 40, x: "-50%" }}>
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
