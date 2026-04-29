# -*- coding: utf-8 -*-
"""
ExpenseGuard - Kural Tabanli Anomali Dedektoru

10 is kuraliyla anomali isaretler.
Kurallar:
  1. duplicate    — Cift fatura (tutar toleransli)
  2. unauthorized — Yetki disi kategori
  3. threshold    — Onay esigi atlama
  4. off_hours    — Gece islemi
  5. daily_limit  — Gunluk limit
  6. ghost_vendor — Hayalet tedarikci
  7. weekend      — Hafta sonu harcamasi
  8. split_txn    — Bolunmus islem (ayni gun/vendor/employee cok kucuk islem)
  9. excessive    — Asiri tutar (z-score > 2.5 veya dept_cat_ratio > 3)
  10. round_amount — Yuvarlak tutar + dusuk frekansi vendor
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd

from config import rules as cfg


def _date_col(df):
    for c in ["expense_date", "transaction_date"]:
        if c in df.columns:
            return c
    raise KeyError("Tarih sutunu bulunamadi")


def _cat_col(df):
    for c in ["expense_category", "category"]:
        if c in df.columns:
            return c
    raise KeyError("Kategori sutunu bulunamadi")


class RuleBasedDetector:
    """10 deterministik kural ile anomali tespiti."""

    RULE_COLS = [
        "rule_duplicate", "rule_unauthorized", "rule_threshold",
        "rule_off_hours", "rule_daily_limit", "rule_ghost_vendor",
        "rule_weekend", "rule_split_txn", "rule_excessive", "rule_round_amount",
    ]

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        dcol = _date_col(out)
        out[dcol] = pd.to_datetime(out[dcol])

        out = self._flag_duplicates(out, dcol)
        out = self._flag_unauthorized_category(out)
        out = self._flag_threshold_bypass(out)
        out = self._flag_off_hours(out, dcol)
        out = self._flag_daily_limit(out, dcol)
        out = self._flag_ghost_vendor(out)
        out = self._flag_weekend(out, dcol)
        out = self._flag_split_txn(out, dcol)
        out = self._flag_excessive(out)
        out = self._flag_round_amount(out)

        out["rule_flag"]  = out[self.RULE_COLS].any(axis=1).astype(int)

        # Agirlikli rule_score: yuksek sinyal kurallarina daha fazla agirlik
        RULE_WEIGHTS = {
            "rule_duplicate":     2.0,
            "rule_unauthorized":  1.5,
            "rule_threshold":     1.5,
            "rule_off_hours":     1.0,
            "rule_daily_limit":   1.5,
            "rule_ghost_vendor":  2.5,
            "rule_weekend":       0.5,
            "rule_split_txn":     2.0,
            "rule_excessive":     2.5,
            "rule_round_amount":  0.5,
        }
        max_weighted = sum(RULE_WEIGHTS.values())
        weighted_sum = sum(
            out[col] * RULE_WEIGHTS.get(col, 1.0) for col in self.RULE_COLS
        )
        out["rule_score"] = (weighted_sum / max_weighted).round(4)
        return out

    # ── 1. Cift Fatura ───────────────────────────────────────────────────
    def _flag_duplicates(self, df, dcol):
        tol = cfg.DUPLICATE_AMOUNT_TOLERANCE
        window_h = cfg.DUPLICATE_WINDOW_HOURS
        df_sorted = df.sort_values(dcol).copy()
        flags = pd.Series(0, index=df.index)

        for (emp, vendor), group in df_sorted.groupby(["employee_id", "vendor"]):
            if len(group) < 2:
                continue
            amounts = group["amount"].values
            times   = group[dcol].values
            idxs    = group.index.values
            for i in range(1, len(group)):
                for j in range(max(0, i-5), i):
                    dt_h = (times[i] - times[j]) / np.timedelta64(1, "h")
                    if 0 < dt_h <= window_h:
                        ratio = abs(amounts[i] - amounts[j]) / max(amounts[j], 0.01)
                        if ratio <= tol:
                            flags.loc[idxs[i]] = 1
        df["rule_duplicate"] = flags
        return df

    # ── 2. Yetki Disi Kategori ───────────────────────────────────────────
    def _flag_unauthorized_category(self, df):
        ccol = _cat_col(df)
        def check(row):
            allowed = cfg.DEPT_CATEGORY_WHITELIST.get(row["department"], None)
            return 0 if (allowed is None or row[ccol] in allowed) else 1
        df["rule_unauthorized"] = df.apply(check, axis=1)
        return df

    # ── 3. Esik Atlama ───────────────────────────────────────────────────
    def _flag_threshold_bypass(self, df):
        df["rule_threshold"] = (
            (df["amount"] >= cfg.APPROVAL_BYPASS_WINDOW - 200) &
            (df["amount"] < cfg.SINGLE_TXN_LIMIT)
        ).astype(int)
        return df

    # ── 4. Gece Islemi ───────────────────────────────────────────────────
    def _flag_off_hours(self, df, dcol):
        hour = df[dcol].dt.hour
        night = (hour >= cfg.NIGHT_HOURS_START) | (hour < cfg.NIGHT_HOURS_END)
        df["rule_off_hours"] = (night & (df["amount"] > 100)).astype(int)
        return df

    # ── 5. Gunluk Limit ──────────────────────────────────────────────────
    def _flag_daily_limit(self, df, dcol):
        df["_date"] = df[dcol].dt.date
        daily = df.groupby(["employee_id", "_date"])["amount"].transform("sum")
        df["rule_daily_limit"] = (daily > cfg.DAILY_EMPLOYEE_LIMIT).astype(int)
        df.drop(columns=["_date"], inplace=True)
        return df

    # ── 6. Hayalet Tedarikci ─────────────────────────────────────────────
    def _flag_ghost_vendor(self, df):
        if "vendor" in df.columns:
            is_unknown = df["vendor"].str.contains("UNKNOWN_VENDOR", case=False, na=False)
            # + vendor_frequency <= 2 (dusuk frekansli vendor)
            if "vendor_frequency" in df.columns:
                low_freq = df["vendor_frequency"] <= 2
                df["rule_ghost_vendor"] = (is_unknown | low_freq).astype(int)
            else:
                df["rule_ghost_vendor"] = is_unknown.astype(int)
        else:
            df["rule_ghost_vendor"] = 0
        return df

    # ── 7. Hafta Sonu ────────────────────────────────────────────────────
    def _flag_weekend(self, df, dcol):
        if "is_weekend" in df.columns:
            wk = df["is_weekend"].astype(int)
        else:
            wk = (df[dcol].dt.dayofweek >= 5).astype(int)
        # Hafta sonu + tutar > medyan * 1.5 (rastgele degil, anlamli harcama)
        median_amt = df["amount"].median()
        df["rule_weekend"] = (wk & (df["amount"] > median_amt * 1.5)).astype(int)
        return df

    # ── 8. Bolunmus Islem (Split Transaction) ────────────────────────────
    def _flag_split_txn(self, df, dcol):
        """
        Ayni gun + ayni vendor + ayni employee'de 3+ islem varsa
        VE grubun toplam tutari > 80 VE ortalama tutar < 100
        --> split_txn suphesi.
        """
        df["_date"] = df[dcol].dt.date
        grp = df.groupby(["employee_id", "vendor", "_date"])

        txn_count = grp["amount"].transform("count")
        txn_mean  = grp["amount"].transform("mean")
        txn_sum   = grp["amount"].transform("sum")

        df["rule_split_txn"] = (
            (txn_count >= 3) &
            (txn_mean < 100) &
            (txn_sum > 80)
        ).astype(int)
        df.drop(columns=["_date"], inplace=True)
        return df

    # ── 9. Asiri Tutar ───────────────────────────────────────────────────
    def _flag_excessive(self, df):
        """
        amount_zscore > 3.5 VEYA dept_category_mean_ratio > 6 ise bayrak.
        """
        flags = pd.Series(0, index=df.index)
        if "amount_zscore" in df.columns and "dept_category_mean_ratio" in df.columns:
            flags = (
                (df["amount_zscore"] > 3.5) | (df["dept_category_mean_ratio"] > 6)
            ).astype(int)
        elif "amount_zscore" in df.columns:
            flags = (df["amount_zscore"] > 3.5).astype(int)
        elif "dept_category_mean_ratio" in df.columns:
            flags = (df["dept_category_mean_ratio"] > 6).astype(int)
        else:
            flags = (df["amount"] > 2000).astype(int)
        df["rule_excessive"] = flags.astype(int)
        return df

    # ── 10. Yuvarlak Tutar + Dusuk Vendor Frekans ────────────────────────
    def _flag_round_amount(self, df):
        """
        Yuvarlak tutar (amount % 50 == 0) VE vendor_frequency dusuk ise bayrak.
        Sahte faturalar genelde yuvarlak olur.
        """
        is_round = (df["amount"] % 50 == 0) & (df["amount"] > 0)
        if "vendor_frequency" in df.columns:
            low_freq = df["vendor_frequency"] <= 5
            df["rule_round_amount"] = (is_round & low_freq).astype(int)
        else:
            df["rule_round_amount"] = is_round.astype(int)
        return df
