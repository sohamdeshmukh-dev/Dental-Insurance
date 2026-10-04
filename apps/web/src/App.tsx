import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Logo } from "./components/bits";
import { Assistant } from "./views/Assistant";
import { Dashboard } from "./views/Dashboard";
import { Rewards } from "./views/Rewards";
import { Care } from "./views/Care";
import { Radar } from "./components/Radar";

type View = "assistant" | "dashboard" | "rewards" | "care";
const NAV: { id: View; label: string }[] = [
  { id: "assistant", label: "Ask the AI" },
  { id: "dashboard", label: "Dashboard" },
  { id: "rewards", label: "Rewards" },
  { id: "care", label: "Care Plan" },
];

export default function App() {
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
        <div className="user">
          <div className="ava">JL</div>
          <div className="who"><b>Jordan Lee</b><br /><span>Acme Co · PPO Family Plan</span></div>
        </div>
      </header>

      <AnimatePresence mode="wait">
        <motion.div key={view} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}>
          {view === "assistant" && <Assistant onOpenRadar={() => setRadar(true)} />}
          {view === "dashboard" && <Dashboard />}
          {view === "rewards" && <Rewards />}
          {view === "care" && <Care />}
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
