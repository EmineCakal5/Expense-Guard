import React, { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getTimeline } from "../api/client";

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const anomalies = payload.find((p) => p.dataKey === "total_anomalies")?.value;
  const total = payload.find((p) => p.dataKey === "total_transactions")?.value;
  return (
    <div className="rounded-lg bg-[var(--bg-overlay)] shadow-[var(--shadow-elevated)] border border-[var(--border-default)] px-3 py-2 text-xs text-[var(--text-primary)]">
      <div className="font-semibold mb-1">{label}</div>
      <div className="flex justify-between gap-4">
        <span className="text-[var(--risk-high)]">Anomali</span>
        <span className="eg-mono">{Number(anomalies || 0).toLocaleString("tr-TR")}</span>
      </div>
      <div className="flex justify-between gap-4">
        <span className="text-[var(--text-secondary)]">Toplam</span>
        <span className="eg-mono">{Number(total || 0).toLocaleString("tr-TR")}</span>
      </div>
    </div>
  );
};

export default function TimelineChart() {
  const [raw, setRaw] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getTimeline("month")
      .then((r) => setRaw(r))
      .catch(() => setRaw({ data: [] }))
      .finally(() => setLoading(false));
  }, []);

  const data = useMemo(() => {
    const d = raw?.data || [];
    return (Array.isArray(d) ? d : []).slice(-36);
  }, [raw]);

  if (loading) {
    return <div className="h-[260px] flex items-center justify-center text-[var(--text-secondary)]">Yükleniyor…</div>;
  }
  if (!data.length) {
    return <div className="h-[260px] flex items-center justify-center text-[var(--text-secondary)]">Veri yok</div>;
  }

  return (
    <div className="h-[280px]">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="egAnom" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#F87171" stopOpacity={0.15} />
              <stop offset="100%" stopColor="#F87171" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--border-subtle)" strokeWidth={0.5} vertical={false} />
          <XAxis
            dataKey="period"
            tick={{ fill: "var(--text-muted)", fontSize: 11, fontFamily: "var(--font-mono)" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "var(--text-muted)", fontSize: 11, fontFamily: "var(--font-mono)" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="total_anomalies"
            stroke="var(--risk-high)"
            strokeWidth={2}
            fill="url(#egAnom)"
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
