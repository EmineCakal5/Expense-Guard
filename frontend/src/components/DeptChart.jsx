import React, { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getDepartments } from "../api/client";

const fmtMoney = (v) =>
  `$${Number(v || 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const total = payload.find((p) => p.dataKey === "total_amount")?.value;
  const anomaly = payload.find((p) => p.dataKey === "anomaly_amount")?.value;
  return (
    <div className="rounded-lg bg-[var(--bg-overlay)] shadow-[var(--shadow-elevated)] border border-[var(--border-default)] px-3 py-2 text-xs text-[var(--text-primary)]">
      <div className="font-semibold mb-1">{label}</div>
      <div className="flex justify-between gap-4">
        <span className="text-[rgba(76,158,235,0.95)]">Toplam</span>
        <span className="eg-mono">{fmtMoney(total)}</span>
      </div>
      <div className="flex justify-between gap-4">
        <span className="text-[var(--risk-high)]">Anomali</span>
        <span className="eg-mono">{fmtMoney(anomaly)}</span>
      </div>
    </div>
  );
};

export default function DeptChart() {
  const [raw, setRaw] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getDepartments()
      .then((d) => setRaw(Array.isArray(d) ? d : []))
      .catch(() => setRaw([]))
      .finally(() => setLoading(false));
  }, []);

  const data = useMemo(() => {
    // Backend returns: department, total_amount, total_anomalies, total_transactions
    // We don't have anomaly_amount directly, approximate: avg_amount * total_anomalies.
    return (raw || [])
      .map((r) => {
        const avg = Number(r.avg_amount || 0);
        const anomCount = Number(r.total_anomalies || 0);
        const anomalyAmount = avg * anomCount;
        return {
          department: r.department,
          total_amount: Number(r.total_amount || 0),
          anomaly_amount: anomalyAmount,
        };
      })
      .sort((a, b) => b.total_amount - a.total_amount)
      .slice(0, 12);
  }, [raw]);

  if (loading) {
    return (
      <div className="h-[280px] flex items-center justify-center text-[var(--text-secondary)]">
        Yükleniyor…
      </div>
    );
  }

  if (!data.length) {
    return (
      <div className="h-[280px] flex items-center justify-center text-[var(--text-secondary)]">
        Veri yok
      </div>
    );
  }

  return (
    <div className="h-[320px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
          <CartesianGrid stroke="var(--border-subtle)" strokeWidth={0.5} vertical={false} />
          <XAxis
            dataKey="department"
            tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            angle={-45}
            textAnchor="end"
            height={52}
          />
          <YAxis
            tick={{ fill: "var(--text-muted)", fontSize: 11, fontFamily: "var(--font-mono)" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `${Math.round(v / 1000)}k`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            verticalAlign="top"
            align="right"
            iconType="circle"
            wrapperStyle={{ paddingBottom: 8, fontSize: 12, color: "var(--text-secondary)" }}
          />
          <Bar name="Toplam harcama" dataKey="total_amount" fill="rgba(76, 158, 235, 0.70)" radius={[4, 4, 0, 0]} />
          <Bar name="Anomali tutarı" dataKey="anomaly_amount" fill="rgba(248, 113, 113, 0.80)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
