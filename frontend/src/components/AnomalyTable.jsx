import React, { useEffect, useMemo, useState } from "react";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ChevronDown } from "lucide-react";
import { getAnomalies } from "../api/client";

const columnHelper = createColumnHelper();

function RiskBadge({ level }) {
  const v = (level || "").toString().toLowerCase();
  const map = {
    high: { bg: "var(--risk-high-bg)", fg: "var(--risk-high)", label: "High" },
    medium: { bg: "var(--risk-medium-bg)", fg: "var(--risk-medium)", label: "Medium" },
    low: { bg: "var(--risk-low-bg)", fg: "var(--risk-low)", label: "Low" },
  };
  const t = map[v] || { bg: "var(--bg-elevated)", fg: "var(--text-secondary)", label: (level || "—").toString() };
  return (
    <span
      className="inline-flex items-center rounded-full border border-[var(--border-subtle)] px-2.5 py-0.5 text-[12px] font-medium"
      style={{ background: t.bg, color: t.fg }}
    >
      {t.label}
    </span>
  );
}

function TypeBadge({ value }) {
  const txt = (value || "").toString();
  if (!txt) return <span className="text-[var(--text-muted)]">—</span>;
  return (
    <span className="inline-flex items-center rounded-md bg-[var(--bg-elevated)] border border-[var(--border-subtle)] px-2 py-0.5 text-[11px] eg-mono text-[var(--text-secondary)]">
      {txt}
    </span>
  );
}

function Select({ value, onChange, options, placeholder }) {
  return (
    <div className="relative">
      <select
        value={value || ""}
        onChange={(e) => onChange(e.target.value || "")}
        className="eg-focus appearance-none bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md px-3 py-1.5 pr-9 text-[13px] text-[var(--text-primary)]"
      >
        <option value="">{placeholder}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="h-4 w-4 text-[var(--text-secondary)] absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
    </div>
  );
}

export default function AnomalyTable() {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [department, setDepartment] = useState("");
  const [riskLevel, setRiskLevel] = useState("");
  const [anomalyType, setAnomalyType] = useState("");
  const [sorting, setSorting] = useState([{ id: "ensemble_score", desc: true }]);

  const pageSize = 20;

  useEffect(() => {
    setLoading(true);
    getAnomalies({
      page,
      per_page: pageSize,
      department: department || undefined,
      risk_level: riskLevel || undefined,
      anomaly_type: anomalyType || undefined,
    })
      .then((r) => {
        setRows(r.data || []);
        setTotal(r.total || 0);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, department, riskLevel, anomalyType]);

  const columns = useMemo(
    () => [
      columnHelper.accessor("transaction_id", {
        header: "İşlem",
        cell: (info) => <span className="eg-mono text-[12px] text-[var(--text-secondary)]">{info.getValue()}</span>,
      }),
      columnHelper.accessor("expense_date", {
        header: "Tarih",
        cell: (info) => (
          <span className="eg-mono text-[12px] text-[var(--text-secondary)]">
            {(info.getValue() || "").toString().slice(0, 10)}
          </span>
        ),
      }),
      columnHelper.accessor("employee_name", { header: "Çalışan" }),
      columnHelper.accessor("department", { header: "Departman" }),
      columnHelper.accessor("vendor", { header: "Tedarikçi" }),
      columnHelper.accessor("expense_category", { header: "Kategori" }),
      columnHelper.accessor("amount", {
        header: "Tutar",
        cell: (info) => (
          <span className="eg-mono font-medium tabular-nums text-right block">
            ${(Number(info.getValue()) || 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}
          </span>
        ),
      }),
      columnHelper.accessor("ensemble_score", {
        header: "Risk Skoru",
        cell: (info) => (
          <span className="eg-mono font-medium tabular-nums">
            {(Number(info.getValue()) || 0).toFixed(3)}
          </span>
        ),
      }),
      columnHelper.accessor("risk_level", {
        header: "Risk",
        cell: (info) => <RiskBadge level={info.getValue()} />,
      }),
      columnHelper.accessor("anomaly_type", {
        header: "Anomali Tipi",
        cell: (info) => <TypeBadge value={(info.getValue() || "").toString()} />,
      }),
    ],
    [],
  );

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    state: { sorting },
    onSortingChange: setSorting,
  });

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const deptOptions = useMemo(() => {
    const set = new Set((rows || []).map((r) => r.department).filter(Boolean));
    return Array.from(set)
      .sort((a, b) => a.localeCompare(b))
      .map((d) => ({ value: d, label: d }));
  }, [rows]);

  const typeOptions = useMemo(() => {
    const set = new Set(
      (rows || [])
        .map((r) => r.anomaly_type || r.anomaly_types)
        .filter(Boolean)
        .map((v) => v.toString()),
    );
    return Array.from(set)
      .sort((a, b) => a.localeCompare(b))
      .map((t) => ({ value: t, label: t.replaceAll("_", " ") }));
  }, [rows]);

  return (
    <div className="rounded-[12px] overflow-hidden">
      <div className="flex items-center justify-between gap-4 px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="text-[16px] font-semibold text-[var(--text-primary)]">Anomali Detayları</div>
          <span className="inline-flex items-center rounded-full bg-[var(--bg-elevated)] border border-[var(--border-subtle)] px-2.5 py-0.5 text-[12px] text-[var(--text-secondary)]">
            {total.toLocaleString("tr-TR")} kayıt
          </span>
        </div>

        <div className="eg-mono text-[13px] text-[var(--text-muted)]">
          Sayfa {page}/{totalPages}
        </div>
      </div>

      <div className="px-5 pb-4">
        <div className="flex flex-wrap items-center gap-3">
          <Select
            value={department}
            onChange={(v) => {
              setPage(1);
              setDepartment(v);
            }}
            placeholder="Departman"
            options={deptOptions}
          />
          <Select
            value={riskLevel}
            onChange={(v) => {
              setPage(1);
              setRiskLevel(v);
            }}
            placeholder="Risk Seviyesi"
            options={[
              { value: "low", label: "Low" },
              { value: "medium", label: "Medium" },
              { value: "high", label: "High" },
            ]}
          />
          <Select
            value={anomalyType}
            onChange={(v) => {
              setPage(1);
              setAnomalyType(v);
            }}
            placeholder="Anomali Tipi"
            options={typeOptions}
          />
          <button
            type="button"
            className="text-[13px] font-medium text-[var(--accent-blue)] hover:underline"
            onClick={() => {
              setDepartment("");
              setRiskLevel("");
              setAnomalyType("");
              setPage(1);
            }}
          >
            Filtreleri Temizle
          </button>
        </div>
      </div>

      <div className="h-px bg-[var(--border-subtle)]" />

      {loading ? (
        <div className="loading-overlay">
          <div className="spinner" />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead className="bg-[var(--bg-elevated)]">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--text-secondary)] uppercase tracking-[0.05em] border-b border-[var(--border-default)]"
                    >
                      {header.isPlaceholder ? null : (
                        <button
                          type="button"
                          className="inline-flex items-center gap-2 hover:text-[var(--text-primary)] transition-colors"
                          onClick={header.column.getToggleSortingHandler()}
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          <span className="eg-mono text-[11px] text-[var(--text-muted)]">
                            {header.column.getIsSorted() === "asc"
                              ? "↑"
                              : header.column.getIsSorted() === "desc"
                                ? "↓"
                                : ""}
                          </span>
                        </button>
                      )}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className="bg-transparent hover:bg-[var(--bg-elevated)] transition-colors"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="px-4 py-3 text-[13px] text-[var(--text-primary)] border-b border-[var(--border-subtle)]"
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-end gap-3 px-5 py-4">
        <div className="eg-mono text-[13px] text-[var(--text-muted)]">
          Sayfa {page}/{totalPages}
        </div>
        <button
          type="button"
          className="eg-focus rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-default)] px-3 py-2 text-[13px] text-[var(--text-primary)] disabled:opacity-50 hover:border-[rgba(76,158,235,0.6)] transition-colors"
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
        >
          Önceki
        </button>
        <button
          type="button"
          className="eg-focus rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-default)] px-3 py-2 text-[13px] text-[var(--text-primary)] disabled:opacity-50 hover:border-[rgba(76,158,235,0.6)] transition-colors"
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          disabled={page === totalPages}
        >
          Sonraki
        </button>
      </div>
    </div>
  );
}
