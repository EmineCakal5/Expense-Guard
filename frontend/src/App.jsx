import React from "react";
import { Shield, RefreshCw } from "lucide-react";
import "./styles/globals.css";
import Dashboard from "./components/Dashboard";

export default function App() {
  return (
    <div className="app-shell bg-[var(--bg-base)] text-[var(--text-primary)]">
      <div className="w-full border-b border-[var(--border-subtle)] bg-[var(--bg-surface)]">
        <div className="h-14 px-6 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-[rgba(76,158,235,0.12)] flex items-center justify-center border border-[var(--border-subtle)]">
              <Shield className="h-4 w-4 text-[var(--accent-blue)]" />
            </div>
            <div className="leading-tight">
              <div className="font-semibold text-[var(--text-primary)]">ExpenseGuard</div>
              <div className="text-[13px] text-[var(--text-secondary)]">
                Kurumsal Masraf Anomali Tespit
              </div>
            </div>
          </div>

          <button
            type="button"
            className="eg-focus inline-flex items-center gap-2 rounded-lg border border-[var(--border-default)] bg-transparent px-3 py-2 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
            onClick={() => window.dispatchEvent(new Event("expenseguard:refresh"))}
          >
            <RefreshCw className="h-4 w-4" />
            Yenile
          </button>
        </div>
      </div>

      <main className="main-content px-6 py-6">
        <Dashboard />
      </main>
    </div>
  );
}
