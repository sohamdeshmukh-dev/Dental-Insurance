import { useEffect, useRef, useState } from "react";
import { animate } from "framer-motion";

export function Logo() {
  return (
    <svg className="logo-img" viewBox="90 320 1280 410" width="280" height="90" role="img"
      aria-label="Lincoln DentalConnect — A Lincoln Financial solution">
      {/* Frame the supplied artwork without its outer whitespace; keep the source image intact. */}
      <image href="/brand/lincoln-dental-connect.png" width="1448" height="1086" />
    </svg>
  );
}

/** Count-up number that animates whenever `value` changes. */
export function AnimatedNumber({ value, format = (n) => Math.round(n).toLocaleString(), duration = 0.9 }: {
  value: number; format?: (n: number) => string; duration?: number;
}) {
  const [display, setDisplay] = useState(0);
  const prev = useRef(0);
  useEffect(() => {
    const controls = animate(prev.current, value, {
      duration, ease: [0.2, 0.8, 0.2, 1], onUpdate: (v) => setDisplay(v),
    });
    prev.current = value;
    return () => controls.stop();
  }, [value, duration]);
  return <>{format(display)}</>;
}

export const Money = ({ value }: { value: number }) => (
  <AnimatedNumber value={value} format={(n) => "$" + Math.round(n).toLocaleString()} />
);

export const Icon = {
  Sparkle: (p: { size?: number; color?: string }) => (
    <svg width={p.size ?? 15} height={p.size ?? 15} viewBox="0 0 24 24" fill="none" stroke={p.color ?? "#fff"} strokeWidth={2}>
      <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8L12 2z" />
    </svg>
  ),
  Send: () => (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path d="M22 2L11 13" strokeLinecap="round" /><path d="M22 2l-7 20-4-9-9-4 20-7z" strokeLinejoin="round" />
    </svg>
  ),
  Pin: () => (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path d="M21 10c0 6-9 12-9 12s-9-6-9-12a9 9 0 0118 0z" /><circle cx="12" cy="10" r="3" />
    </svg>
  ),
  Search: () => (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" />
    </svg>
  ),
};
