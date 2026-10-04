import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Logo } from "./components/bits";
import { ProfileProvider, useProfile } from "./lib/profile";
import { Assistant } from "./views/Assistant";
import { Dashboard } from "./views/Dashboard";
import { Rewards } from "./views/Rewards";
import { Care } from "./views/Care";
import { Payments } from "./views/Payments";
import { Radar } from "./components/Radar";

type View = "assistant" | "dashboard" | "rewards" | "care" | "payments";
const NAV: { id: View; label: string }[] = [
  { id: "assistant", label: "Ask the AI" },
  { id: "dashboard", label: "Dashboard" },
  { id: "rewards", label: "Rewards" },
  { id: "care", label: "Care Plan" },
  { id: "payments", label: "Payments" },
];

const initials = (name: string) => name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();

function ProfileSwitcher() {
  const { account, active, activeId, setActiveId } = useProfile();
  const [open, setOpen] = useState(false);
  return (
    <div className="switcher">
      <button className="user" onClick={() => setOpen((v) => !v)} aria-haspopup="menu" aria-expanded={open}>
        <div className="ava">{initials(active.name)}</div>
        <div className="who"><b>{active.name}</b><br /><span>{active.relationship === "guardian" ? `${account.employer} · ${account.plan_name}` : `Dependent · age ${active.age}`}</span></div>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--muted)" strokeWidth="2" style={{ marginLeft: 2 }}><path d="M6 9l6 6 6-6" /></svg>
      </button>
      <AnimatePresence>
        {open && (
          <>
            <div className="switcher-scrim" onClick={() => setOpen(false)} />
            <motion.div className="switcher-menu" role="menu" initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}>
              <div className="sm-label">Switch profile</div>
              {account.members.map((m) => (
                <button key={m.member_id} className={`sm-item${m.member_id === activeId ? " on" : ""}`} role="menuitem"
                  onClick={() => { setActiveId(m.member_id); setOpen(false); }}>
                  <div className="ava sm">{initials(m.name)}</div>
                  <div className="sm-meta">
                    <b>{m.name}</b>
                    <span>{m.relationship === "guardian" ? "You · guardian" : `Dependent · age ${m.age}`}</span>
                  </div>
                  <div className="sm-rem">${Math.round(m.benefits_remaining).toLocaleString()}<span>left</span></div>
                </button>
              ))}
              <div className="sm-foot">Guardians can view each dependent's benefits.</div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

function Shell() {
  const [view, setView] = useState<View>("assistant");
  const [radar, setRadar] = useState(false);
  return (
    <>
      <header className="hdr">
        <div className="brandwrap">
          <a className="logo" onClick={() => setView("assistant")} style={{ cursor: "pointer" }}><Logo /></a>
          <span className="sub">Dental Benefits Assistant</span>
          <nav>
            {NAV.map((n) => (
              <button key={n.id} className={`navlink${view === n.id ? " active" : ""}`} onClick={() => setView(n.id)}>
                {n.label}
                {view === n.id && <motion.span layoutId="nav-underline" className="navink-underline" />}
              </button>
            ))}
          </nav>
        </div>
        <ProfileSwitcher />
      </header>

      <AnimatePresence mode="wait">
        <motion.div key={view} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}>
          {view === "assistant" && <Assistant onOpenRadar={() => setRadar(true)} />}
          {view === "dashboard" && <Dashboard />}
          {view === "rewards" && <Rewards />}
          {view === "care" && <Care />}
          {view === "payments" && <Payments />}
        </motion.div>
      </AnimatePresence>

      <footer>
        <div className="l"><span className="dot" />Dental benefits administered by <strong style={{ color: "var(--brand)", fontWeight: 600, marginLeft: 3 }}>Lincoln Financial</strong></div>
        <div className="r">Estimates are illustrative only; actual claim processing determines final benefits.</div>
      </footer>

      <AnimatePresence>{radar && <Radar onClose={() => setRadar(false)} />}</AnimatePresence>
    </>
  );
}

export default function App() {
  return (
    <ProfileProvider>
      <Shell />
    </ProfileProvider>
  );
}
