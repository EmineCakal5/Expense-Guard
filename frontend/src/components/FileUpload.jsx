import React, { useMemo, useState } from "react";
import { useDropzone } from "react-dropzone";
import { UploadCloud, FileSpreadsheet } from "lucide-react";
import { uploadCSV } from "../api/client";

export default function FileUpload({ onSuccess }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);

  const handleFile = async (file) => {
    if (!file) return;
    setLoading(true);
    setStatus(null);
    setProgress(0);
    try {
      const res = await uploadCSV(file, {
        onUploadProgress: (evt) => {
          const total = evt.total || 0;
          if (!total) return;
          setProgress(Math.max(0, Math.min(100, Math.round((evt.loaded / total) * 100))));
        },
      });
      setStatus({ ok: true, msg: `✓ ${res.message} — ${res.total_transactions} işlem, ${res.flagged_anomalies} anomali` });
      onSuccess?.();
    } catch (e) {
      setStatus({ ok: false, msg: `⚠ Yükleme başarısız: ${e.response?.data?.detail || e.message}` });
    } finally {
      setLoading(false);
    }
  };

  const accept = useMemo(
    () => ({
      "text/csv": [".csv"],
      "application/vnd.ms-excel": [".xls"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
    }),
    [],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    multiple: false,
    accept,
    disabled: loading,
    onDrop: (files) => handleFile(files?.[0]),
  });

  return (
    <div>
      <div
        {...getRootProps()}
        className={[
          "eg-focus flex items-center justify-between gap-4",
          "max-h-12 rounded-lg px-5 py-3",
          "bg-[var(--bg-surface)] border border-dashed border-[var(--border-default)]",
          "transition-colors",
          isDragActive ? "bg-[rgba(34,211,238,0.04)] border-[var(--accent-cyan)]" : "",
          loading ? "opacity-60 cursor-not-allowed" : "cursor-pointer",
        ].join(" ")}
      >
        <input {...getInputProps()} />

        <div className="flex items-center gap-3 min-w-0">
          {isDragActive ? (
            <UploadCloud className="h-4 w-4 text-[var(--accent-cyan)]" />
          ) : (
            <FileSpreadsheet className="h-4 w-4 text-[var(--accent-blue)]" />
          )}
          <div className="text-[14px] font-medium text-[var(--text-primary)]">
            CSV / Excel yükle
          </div>
        </div>

        <button
          type="button"
          className="eg-focus shrink-0 rounded-lg bg-[var(--accent-blue)] px-3 py-2 text-[13px] font-semibold text-white hover:opacity-95 transition-opacity"
          disabled={loading}
        >
          {loading ? "İşleniyor…" : "Dosya Seç"}
        </button>
      </div>

      {loading ? (
        <div className="mt-2">
          <div className="flex items-center justify-between text-[12px] text-[var(--text-secondary)] mb-1">
            <span>Yükleniyor</span>
            <span className="eg-mono">{progress}%</span>
          </div>
          <div className="h-2 rounded-full bg-[var(--bg-elevated)] overflow-hidden border border-[var(--border-subtle)]">
            <div className="h-2 bg-[var(--accent-blue)]" style={{ width: `${progress}%` }} />
          </div>
        </div>
      ) : null}

      {status ? (
        <div
          className="mt-2 text-[13px]"
          style={{ color: status.ok ? "var(--risk-low)" : "var(--risk-high)" }}
        >
          {status.msg}
        </div>
      ) : null}
    </div>
  );
}
