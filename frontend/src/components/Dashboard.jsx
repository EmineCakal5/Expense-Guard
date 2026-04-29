import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, FileText, Gauge, TrendingUp } from "lucide-react";
import { getDashboard } from "../api/client";
import DeptChart from "./DeptChart";
import TimelineChart from "./TimelineChart";
import RiskGauge from "./RiskGauge";
import FileUpload from "./FileUpload";
import AnomalyTable from "./AnomalyTable";

function avgRiskFromDistribution(dist = {}) {
  // Heuristic score per bucket (0..1), used only for UI KPI/gauge.
  const w = { low: 0.2, medium: 0.55, high: 0.85 };
  const low = Number(dist.low || 0);
  const med = Number(dist.medium || 0);
  const high = Number(dist.high || 0);
  const total = low + med + high;
  if (!total) return 0;
  return (low * w.low + med * w.medium + high * w.high) / total;
}

const KpiCard = ({ icon: Icon, label, value, sub, iconBg, iconColor, delayMs = 0 }) => {
  return (
    <div
      className="fade-up rounded-[12px] bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--shadow-card)] p-5"
      style={{ animationDelay: `${delayMs}ms` }}
    >
      <div className="flex items-start gap-3">
        <div
          className="h-9 w-9 rounded-full flex items-center justify-center"
          style={{ background: iconBg, color: iconColor }}
        >
          <Icon className="h-[18px] w-[18px]" />
        </div>
        <div className="flex-1">
          <div className="text-[13px] font-medium text-[var(--text-secondary)]">{label}</div>
          <div className="mt-2 text-[28px] leading-none font-bold eg-mono text-[var(--text-primary)]">
            {value}
          </div>
          {sub ? <div className="mt-2 text-[12px] text-[var(--text-muted)]">{sub}</div> : null}
        </div>
      </div>
    </div>
  );
};

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await getDashboard();
      setData(d);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Dashboard yüklenemedi.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  useEffect(() => {
    const handler = () => fetchDashboard();
    window.addEventListener("expenseguard:refresh", handler);
    return () => window.removeEventListener("expenseguard:refresh", handler);
  }, [fetchDashboard]);

  const avgRisk = useMemo(
    () => avgRiskFromDistribution(data?.risk_distribution || {}),
    [data],
  );

  const totalTx = data?.total_transactions ?? 0;
  const anom = data?.flagged_anomalies ?? 0;
  const anomRate = Number(data?.anomaly_rate ?? 0);

  return (
    <div className="max-w-[1600px] mx-auto flex flex-col gap-4">
      <div className="flex justify-end">
        <div className="w-full lg:max-w-[720px]">
          <FileUpload onSuccess={fetchDashboard} />
        </div>
      </div>

      {error ? (
        <div className="rounded-[12px] bg-[var(--risk-high-bg)] border border-[rgba(248,113,113,0.25)] px-4 py-3 text-sm text-[var(--risk-high)]">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="loading-overlay">
          <div className="spinner" />
          <div>Yükleniyor…</div>
        </div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              icon={FileText}
              label="Toplam İşlem"
              value={Number(totalTx).toLocaleString("tr-TR")}
              sub="Tüm kayıtlar"
              iconBg="rgba(76, 158, 235, 0.10)"
              iconColor="var(--accent-blue)"
              delayMs={0}
            />
            <KpiCard
              icon={AlertTriangle}
              label="Tespit Edilen Anomali"
              value={Number(anom).toLocaleString("tr-TR")}
              sub={`Oran: %${(anomRate * 100).toFixed(2)}`}
              iconBg="rgba(248, 113, 113, 0.10)"
              iconColor="var(--risk-high)"
              delayMs={40}
            />
            <KpiCard
              icon={Gauge}
              label="Ort. Risk Skoru"
              value={`${Math.round(avgRisk * 100)}`}
              sub="0–100"
              iconBg="rgba(251, 191, 36, 0.10)"
              iconColor="var(--risk-medium)"
              delayMs={80}
            />
            <KpiCard
              icon={TrendingUp}
              label="Anomali Oranı"
              value={`${(anomRate * 100).toFixed(2)}%`}
              sub="Flagged / Total"
              iconBg="rgba(34, 211, 238, 0.10)"
              iconColor="var(--accent-cyan)"
              delayMs={120}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <section className="lg:col-span-2 rounded-[12px] bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--shadow-card)] p-5">
              <div className="mb-3 text-[16px] font-semibold text-[var(--text-primary)]">
                Aylık Anomali Trendi
              </div>
              <TimelineChart />
            </section>

            <section className="lg:col-span-1 rounded-[12px] bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--shadow-card)] p-6">
              <div className="mb-3 text-[16px] font-semibold text-[var(--text-primary)]">
                Risk Göstergesi
              </div>
              <RiskGauge value={avgRisk} distribution={data?.risk_distribution || {}} />
            </section>
          </div>

          <section className="rounded-[12px] bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--shadow-card)] p-5">
            <div className="mb-3 text-[16px] font-semibold text-[var(--text-primary)]">
              Departman Harcama Karşılaştırması
            </div>
            <DeptChart />
          </section>

          <section className="rounded-[12px] bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--shadow-card)]">
            <AnomalyTable />
          </section>
        </>
      )}
    </div>
  );
}
