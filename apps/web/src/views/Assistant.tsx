import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api, type Coverage, type ProcedureMatch, type ResearchBrief } from "../lib/api";
import { MiniMap } from "../components/MiniMap";
import { Icon } from "../components/bits";

const money = (n: number) => "$" + Math.round(n).toLocaleString();
const md = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\n\n/g, "<br/><br/>");
const catOf = (c: Coverage) => (c.coinsurance_pct >= 1 ? "Preventive" : c.coinsurance_pct >= 0.8 ? "Basic service" : "Major service");

interface Receipt { proc: ProcedureMatch; cmp: { in: Coverage; out: Coverage }; }
type Msg = { role: "user" } & { text: string } | { role: "ai"; text: string; receipts?: Receipt[] };

const SEED: Msg[] = [
  { role: "user", text: "I need a crown on my back molar — how much will that actually cost me?" },
  {
    role: "ai",
    text: "A ceramic crown on a molar is a **major service** under your plan. Here's what it likely looks like — and since a cracked or infected tooth can get worse, don't delay care just to optimize timing.",
    receipts: [{
      proc: { procedure: "Porcelain crown · tooth #30", selected_code: "D2740", possible_codes: ["D2740"], confidence: 0.8, requires_confirmation: true },
      cmp: {
        in: { code: "D2740", network: "in", covered: true, provider_charge: 1100, allowed_amount: 1100, deductible_applied: 50, coinsurance_pct: 0.5, plan_payment: 525, member_payment: 575, annual_max_applied: false, disclaimer: "This is an estimate, not a guarantee of payment. Actual claim processing by Lincoln Financial determines your final benefits.", steps: [{ rule: "Allowed amount", description: "In-network allowed amount is $1,100." }, { rule: "Deductible", description: "$50 remaining deductible applied." }, { rule: "Coinsurance", description: "Plan pays 50% of $1,050 = $525." }] },
        out: { code: "D2740", network: "out", covered: true, provider_charge: 1300, allowed_amount: 1100, deductible_applied: 50, coinsurance_pct: 0.4, plan_payment: 420, member_payment: 880, annual_max_applied: false, disclaimer: "", steps: [] },
      },
    }],
  },
];

const CHIPS = ["I need a root canal and a crown on tooth 14", "Is a cleaning fully covered?", "What will a deep cleaning cost?"];

export function Assistant({ onOpenRadar, brief }: { onOpenRadar: () => void; brief: ResearchBrief | null }) {
  const [msgs, setMsgs] = useState<Msg[]>(SEED);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const toEnd = () => requestAnimationFrame(() => scroller.current?.scrollIntoView({ behavior: "smooth" }));

  useEffect(() => { if (brief) toEnd(); }, [brief]);

  async function ask(text: string) {
    setMsgs((m) => [...m, { role: "user", text }]);
    setTyping(true); toEnd();
    const out = await api.agent(text);
    setTyping(false);
    if (!out) {
      setMsgs((m) => [...m, { role: "ai", text: "I'm the demo assistant. Start the backend (**uvicorn main:app**) for a live estimate with your Lincoln Financial coverage and verified providers. Until then, try the sample above or browse dentists on the right." }]);
      toEnd(); return;
    }
    if (out.research_pending) void api.runResearch();
    const receipts: Receipt[] = (out.procedures ?? []).flatMap((p) => {
      const cmp = out.comparisons?.[p.selected_code];
      return cmp ? [{ proc: p, cmp }] : [];
    });
    setMsgs((m) => [...m, { role: "ai", text: out.explanation || out.message || "I couldn't find an estimate for that.", receipts }]);
    toEnd();
  }

  const submit = (e: React.FormEvent) => { e.preventDefault(); const v = input.trim(); if (!v) return; setInput(""); ask(v); };

  return (
    <div className="wrap">
      <main className="chat">
        <div className="intro">
          <div className="t">Ask about any procedure</div>
          <div className="d">Describe what you need in plain English — I'll translate your Lincoln Financial plan and local costs into a clear estimate. Clinical urgency always comes first.</div>
        </div>

        <div className="msgs">
          <AnimatePresence initial={false}>
            {msgs.map((m, i) => (
              <motion.div key={i} layout initial={{ opacity: 0, y: 14, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ type: "spring", stiffness: 380, damping: 30 }}
                className={m.role === "user" ? "u" : "a"}>
                {m.role === "user" ? m.text : <AiMessage msg={m} />}
              </motion.div>
            ))}
          </AnimatePresence>
          {brief && (
            <div className="a" aria-label="Research brief">
              <AiMessage msg={{ role: "ai", text: `**While you were away, I looked into your ${(brief.procedures || brief.codes || []).join(", ").toLowerCase()}:**\n\n${brief.brief || ""}\n\n${brief.disclaimer || ""}` }} />
            </div>
          )}
          {typing && (
            <motion.div className="a" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <div className="row"><div className="badge-ai"><Icon.Sparkle /></div><div className="bubble typing"><span /><span /><span /></div></div>
            </motion.div>
          )}
          <div ref={scroller} />
        </div>

        <div style={{ flex: 1 }} />
        <div className="chips">
          {CHIPS.map((c) => <button className="chip" key={c} onClick={() => ask(c)}>{c}</button>)}
        </div>
        <form className="ask" onSubmit={submit}>
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder='Describe a procedure, e.g. "I need a root canal"' autoComplete="off" />
          <button className="send-btn" type="submit" aria-label="Send"><Icon.Send /></button>
        </form>
      </main>

      <aside className="aside">
        <MiniMap onOpenFull={onOpenRadar} />
        <div className="note">
          <b>Annual maximum:</b> you have up to approximately <b>$950</b> of your $1,500 remaining this benefit year. In-network dentists accept Lincoln's allowed amount as full payment, so your share is usually lower.
        </div>
      </aside>
    </div>
  );
}

function AiMessage({ msg }: { msg: Extract<Msg, { role: "ai" }> }) {
  return (
    <>
      <div className="row">
        <div className="badge-ai"><Icon.Sparkle /></div>
        <div className="bubble" dangerouslySetInnerHTML={{ __html: `<p>${md(msg.text)}</p>` }} />
      </div>
      {msg.receipts?.map((r, i) => <ReceiptCard key={i} r={r} />)}
    </>
  );
}

function ReceiptCard({ r }: { r: Receipt }) {
  const { proc, cmp } = r;
  const need = proc.requires_confirmation;
  const best = cmp.in.member_payment <= cmp.out.member_payment ? "in" : "out";
  return (
    <motion.div className="receipt" role="group" aria-label="Cost estimate"
      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12, type: "spring", stiffness: 320, damping: 28 }}>
      <div className="head">
        <div><div className="ttl">{proc.procedure}{proc.selected_code ? ` · ${proc.selected_code}` : ""}</div><div className="cat">{catOf(cmp.in)}</div></div>
        <span className={`tag ${need ? "warn" : "net"}`}>{need ? "NEEDS CONFIRMATION" : "IN NETWORK"}</span>
      </div>
      <div className="compare">
        <div className="ch">&nbsp;</div><div className="ch">In-network</div><div className="ch">Out-of-network</div>
        <Row k="Estimated total cost" a={money(cmp.in.provider_charge)} b={money(cmp.out.provider_charge)} />
        <Row k="Plan covers" a={`− ${money(cmp.in.plan_payment)}`} b={`− ${money(cmp.out.plan_payment)}`} />
        <Row k="You likely owe" a={money(cmp.in.member_payment)} b={money(cmp.out.member_payment)} bold bestCol={best} />
      </div>
      <details className="why">
        <summary>Why this number?</summary>
        <ol>{cmp.in.steps.map((s, i) => <li key={i}><b>{s.rule}:</b> {s.description}</li>)}</ol>
      </details>
      <div className="srcs">
        <span className="src">Source: coverage engine</span>
        <span className="src">Source: FAIR Health cost estimator</span>
        <span className="src">Source: plan document</span>
      </div>
      <div className="disc">{cmp.in.disclaimer || "This is an estimate, not a guarantee of payment. Actual claim processing by Lincoln Financial determines your final benefits."}</div>
    </motion.div>
  );
}

function Row({ k, a, b, bold, bestCol }: { k: string; a: string; b: string; bold?: boolean; bestCol?: "in" | "out" }) {
  return (
    <div className="cr">
      <div className={`cell${bold ? " " : ""}`} style={bold ? { fontWeight: 700 } : undefined}>{k}</div>
      <div className={`cell${bold ? "" : ""}${bestCol === "in" ? " best" : ""}`} style={bold ? { fontWeight: 700 } : undefined}>{a}</div>
      <div className={`cell${bestCol === "out" ? " best" : ""}`} style={bold ? { fontWeight: 700 } : undefined}>{b}</div>
    </div>
  );
}
