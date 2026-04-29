import React, { useEffect, useMemo, useState } from "react";

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

function toneForPct(pct) {
  if (pct >= 60) return { color: "var(--risk-high)" };
  if (pct >= 30) return { color: "var(--risk-medium)" };
  return { color: "var(--risk-low)" };
}

export default function RiskGauge({ value = 0, distribution = {} }) {
  // value: 0..1
  const targetPct = clamp(Math.round((Number(value) || 0) * 100), 0, 100);
  const [pct, setPct] = useState(0);

  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const from = 0;
    const to = targetPct;
    const dur = 800;

    const tick = (t) => {
      const p = clamp((t - start) / dur, 0, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setPct(Math.round(from + (to - from) * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [targetPct]);

  const style = useMemo(() => toneForPct(pct), [pct]);

  const trackLen = 283;
  const dash = (pct / 100) * trackLen;

  const low = Number(distribution?.low || 0);
  const med = Number(distribution?.medium || 0);
  const high = Number(distribution?.high || 0);

  return (
    <div className="w-full">
      <div className="w-full flex items-center justify-center">
        <div className="relative w-[280px] h-[168px]">
          <svg width="280" height="168" viewBox="0 0 240 150">
            <defs>
              <linearGradient id="egGaugeGrad" x1="0" y1="0" x2="240" y2="0">
                <stop offset="0%" stopColor="var(--risk-low)" />
                <stop offset="50%" stopColor="var(--risk-medium)" />
                <stop offset="100%" stopColor="var(--risk-high)" />
              </linearGradient>
            </defs>

            <path
              d="M30 125 A90 90 0 0 1 210 125"
              fill="none"
              stroke="var(--bg-elevated)"
              strokeWidth="12"
              strokeLinecap="round"
            />
            <path
              d="M30 125 A90 90 0 0 1 210 125"
              fill="none"
              stroke="url(#egGaugeGrad)"
              strokeWidth="12"
              strokeLinecap="round"
              strokeDasharray={`${dash} ${trackLen}`}
            />
          </svg>

          <div className="absolute inset-x-0 top-[56px] text-center">
            <div className="eg-mono font-bold text-[36px] leading-none" style={{ color: style.color }}>
              {pct}
            </div>
            <div className="mt-1 eg-mono text-[14px] text-[var(--text-muted)]">/ 100</div>
          </div>
        </div>
      </div>

      <div className="mt-2 border border-[var(--border-subtle)] rounded-[12px] overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 bg-[var(--bg-elevated)]">
          <div className="text-[13px] text-[var(--text-secondary)]">Düşük Risk</div>
          <div className="eg-mono text-[13px] text-[var(--text-primary)]">
            <span className="inline-block h-2 w-2 rounded-full bg-[var(--risk-low)] mr-2 align-middle" />
            {low.toLocaleString("tr-TR")}
          </div>
        </div>
        <div className="h-px bg-[var(--border-subtle)]" />
        <div className="flex items-center justify-between px-4 py-3 bg-[var(--bg-surface)]">
          <div className="text-[13px] text-[var(--text-secondary)]">Orta Risk</div>
          <div className="eg-mono text-[13px] text-[var(--text-primary)]">
            <span className="inline-block h-2 w-2 rounded-full bg-[var(--risk-medium)] mr-2 align-middle" />
            {med.toLocaleString("tr-TR")}
          </div>
        </div>
        <div className="h-px bg-[var(--border-subtle)]" />
        <div className="flex items-center justify-between px-4 py-3 bg-[var(--bg-surface)]">
          <div className="text-[13px] text-[var(--text-secondary)]">Yüksek Risk</div>
          <div className="eg-mono text-[13px] text-[var(--text-primary)]">
            <span className="inline-block h-2 w-2 rounded-full bg-[var(--risk-high)] mr-2 align-middle" />
            {high.toLocaleString("tr-TR")}
          </div>
        </div>
      </div>
    </div>
  );
}
