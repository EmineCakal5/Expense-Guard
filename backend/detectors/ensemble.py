# -*- coding: utf-8 -*-
"""
ExpenseGuard - Ensemble Detektor
=================================

IF + LOF + Kural Tabanli dedektorlerin ciktilarini agirlikli ortalama ile
birlestirir. Otomatik threshold (F1 optimize) destekler.

Kullanim:
  python detectors/ensemble.py --input ../data/processed/features_engineered.csv
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from config import ml as cfg
from pipeline.feature_eng import FeatureEngineer, FEATURE_COLUMNS
from detectors.isolation_forest import IsolationForestDetector
from detectors.lof_detector import LOFDetector
from detectors.rule_based import RuleBasedDetector


class EnsembleDetector:
    """
    IF + LOF + Rule-based ensemble motoru.
    Otomatik threshold belirleyerek Recall/Precision/F1 optimize eder.
    """

    def __init__(self):
        self.ifd = IsolationForestDetector()
        self.lof = LOFDetector()
        self.rbd = RuleBasedDetector()

    def fit_predict(self, df: pd.DataFrame, ground_truth_col: str = "is_anomaly") -> pd.DataFrame:
        """
        Tum dedektorleri calistirir, skorlari birlestirir,
        ground_truth varsa optimal threshold bulur.
        """
        # -- YENI STRATEJI: Kural bayraklari -> ozellik matrisine ekle -> ML --

        # 2. Once kural tabanli dedektoru calistir (bayraklari feature olarak kullanacagiz)
        print("  [Ensemble] Kural tabanli detektor...")
        rule_df = self.rbd.predict(df)
        rule_scores = rule_df["rule_score"].to_numpy()

        # 3. Ozellik matrisi = sayisal ozellikler + kural bayraklari
        available = [c for c in FEATURE_COLUMNS if c in df.columns]
        rule_flag_cols = [c for c in self.rbd.RULE_COLS if c in rule_df.columns]
        all_feature_cols = available + rule_flag_cols
        X = rule_df[all_feature_cols].fillna(0).to_numpy(dtype=np.float64)
        print(f"  [Ensemble] Ozellik matrisi: {X.shape[0]:,} x {X.shape[1]} ({len(available)} sayi + {len(rule_flag_cols)} kural)")

        # 4. Isolation Forest (kural sinyalleri dahil)
        print("  [Ensemble] Isolation Forest...")
        if_labels, if_scores = self.ifd.fit_predict(X)

        # 5. LOF (kural sinyalleri dahil)
        print("  [Ensemble] LOF...")
        lof_labels, lof_scores = self.lof.fit_predict(X)

        # 6. Skorlari [0,1] arasina normalize et
        if_norm   = _minmax(if_scores)
        lof_norm  = _minmax(lof_scores)
        rule_norm = _minmax(rule_scores)

        # 7. Binary label boost
        label_boost = (if_labels * 0.10) + (lof_labels * 0.08)

        # 8. Agirlikli ensemble skoru
        w = cfg.ENSEMBLE_WEIGHTS
        ensemble_scores = (
            w["isolation_forest"] * if_norm +
            w["lof"]              * lof_norm +
            w["rule_based"]       * rule_norm +
            label_boost
        )
        ensemble_scores = _minmax(ensemble_scores)

        # 9. Sonuclari birlestir
        result = rule_df.copy()
        result["if_label"]       = if_labels
        result["if_score"]       = np.round(if_scores, 4)
        result["lof_label"]      = lof_labels
        result["lof_score"]      = np.round(lof_scores, 4)
        result["ensemble_score"] = np.round(ensemble_scores, 4)

        # 10. Hibrit karar: precision-katmanli voting
        #
        # KATMAN 1: Yuksek-precision kurallar (FP~0) --> dogrudan anomali
        hp_rules = ["rule_ghost_vendor", "rule_split_txn"]
        hp_cols = [c for c in hp_rules if c in result.columns]
        hp_count = result[hp_cols].sum(axis=1)

        # KATMAN 2: Orta-precision kurallar (FP ~%50)
        mp_rules = ["rule_duplicate", "rule_excessive"]
        mp_cols = [c for c in mp_rules if c in result.columns]
        mp_count = result[mp_cols].sum(axis=1)

        # KATMAN 3: Dusuk-precision kurallar (FP cok yuksek)
        lp_rules = ["rule_unauthorized", "rule_weekend", "rule_off_hours",
                     "rule_daily_limit", "rule_threshold", "rule_round_amount"]
        lp_cols = [c for c in lp_rules if c in result.columns]
        lp_count = result[lp_cols].sum(axis=1)

        # ML konsensus
        ml_consensus = (if_labels + lof_labels)

        # KARAR:
        # A) Yuksek-precision kural tetiklendi --> kesin anomali
        cond_a = hp_count >= 1

        # B1) rule_duplicate + herhangi ML (IF veya LOF)
        has_dup = result.get("rule_duplicate", pd.Series(0, index=result.index)).astype(bool)
        cond_b1 = has_dup  # duplicate tek basina %54 prec -> kabul edilebilir
        # B2) rule_excessive + ML tam konsensus (IF + LOF ikisi de)
        has_exc = result.get("rule_excessive", pd.Series(0, index=result.index)).astype(bool)
        cond_b2 = has_exc & (ml_consensus >= 2)

        # C) Herhangi orta + 2 dusuk destek
        cond_c = (mp_count >= 1) & (lp_count >= 2)
        # D) 2+ orta-precision kural birden
        cond_d = mp_count >= 2
        # E) ML tam konsensus (IF + LOF) + 2+ kural
        all_rule_count = hp_count + mp_count + lp_count
        cond_e = (ml_consensus >= 2) & (all_rule_count >= 2)
        # F) Weekend/off_hours + ML tam konsensus + 1 ek sinyal
        wk_oh = pd.Series(0, index=result.index)
        for c in ["rule_weekend", "rule_off_hours"]:
            if c in result.columns:
                wk_oh = wk_oh + result[c]
        other_signal = (mp_count >= 1) | (result.get("rule_unauthorized", pd.Series(0, index=result.index)) >= 1)
        cond_f = (wk_oh >= 1) & (ml_consensus >= 2) & other_signal

        result["predicted_anomaly"] = (
            cond_a | cond_b1 | cond_b2 | cond_c | cond_d | cond_e | cond_f
        ).astype(int)

        return result

    @staticmethod
    def summary(result):
        total   = len(result)
        flagged = int(result["predicted_anomaly"].sum())
        by_type = {}
        for col in ["anomaly_type", "anomaly_types"]:
            if col in result.columns:
                tdf = result[result[col].notna() & (result[col].astype(str) != "") & (result[col].astype(str) != "None")]
                if len(tdf):
                    by_type = tdf[col].value_counts().to_dict()
                break
        return {
            "total_transactions": total,
            "flagged_anomalies":  flagged,
            "anomaly_rate":       round(flagged / total, 4) if total else 0.0,
            "by_type":            by_type,
            "avg_ensemble_score": round(float(result["ensemble_score"].mean()), 4),
        }

    @staticmethod
    def evaluate(result, gt_col="is_anomaly"):
        """Precision, Recall, F1 hesaplar."""
        if gt_col not in result.columns:
            return {}
        gt   = result[gt_col].astype(str).str.lower().isin(["true", "1"]).values
        pred = result["predicted_anomaly"].values.astype(bool)
        tp = int((pred & gt).sum())
        fp = int((pred & ~gt).sum())
        fn = int((~pred & gt).sum())
        tn = int((~pred & ~gt).sum())
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec  = tp / (tp + fn) if (tp + fn) else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        return {
            "TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "precision": round(prec, 4),
            "recall":    round(rec, 4),
            "f1_score":  round(f1, 4),
        }

    @staticmethod
    def print_summary(result, gt_col="is_anomaly"):
        s = EnsembleDetector.summary(result)
        e = EnsembleDetector.evaluate(result, gt_col)

        print(f"\n{'='*62}")
        print("  EnsembleDetector - Tespit Ozeti")
        print(f"{'='*62}")
        print(f"\n  Toplam islem          : {s['total_transactions']:,}")
        print(f"  Tespit edilen anomali : {s['flagged_anomalies']:,}")
        print(f"  Anomali orani         : %{s['anomaly_rate']*100:.2f}")
        print(f"  Ort. ensemble skoru   : {s['avg_ensemble_score']:.4f}")

        if s["by_type"]:
            print(f"\n  {'Anomali Tipi':<30} {'Sayi':>6}")
            print(f"  {'-'*30} {'-'*6}")
            for atype, cnt in sorted(s["by_type"].items(), key=lambda x: -x[1]):
                print(f"  {atype:<30} {cnt:>6,}")

        if e:
            print(f"\n  -- Performans Metrikleri --")
            print(f"  TP={e['TP']:>5}  FP={e['FP']:>5}  FN={e['FN']:>5}  TN={e['TN']:>5}")
            print(f"  Precision : %{e['precision']*100:.2f}")
            print(f"  Recall    : %{e['recall']*100:.2f}")
            print(f"  F1 Score  : %{e['f1_score']*100:.2f}")

        print(f"\n{'='*62}\n")


# ─────────────────────────────────────────────────────────────────────────────
#  Yardimci fonksiyonlar
# ─────────────────────────────────────────────────────────────────────────────

def _minmax(arr: np.ndarray) -> np.ndarray:
    """Min-max normalizasyon [0, 1]."""
    mn, mx = arr.min(), arr.max()
    if mx - mn < 1e-9:
        return np.zeros_like(arr)
    return (arr - mn) / (mx - mn)


def _find_optimal_threshold(scores: np.ndarray, ground_truth: np.ndarray) -> float:
    """
    En iyi threshold'u bulur.
    Oncelik: Recall >= 60% VE Precision >= 50% olan en yuksek F1.
    Bulunamazsa: Recall >= 60% VE Precision >= 30% olan en yuksek F1.
    O da yoksa: En yuksek F1.
    """
    results = []
    for t in np.arange(0.01, 0.99, 0.005):
        pred = scores >= t
        tp = (pred & ground_truth).sum()
        fp = (pred & ~ground_truth).sum()
        fn = (~pred & ground_truth).sum()
        prec = tp / (tp + fp) if (tp + fp) else 0
        rec  = tp / (tp + fn) if (tp + fn) else 0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
        results.append((t, prec, rec, f1))

    # Strateji 1: Recall >= 60% ve Precision >= 50%
    tier1 = [(t, p, r, f) for t, p, r, f in results if r >= 0.60 and p >= 0.50]
    if tier1:
        best = max(tier1, key=lambda x: x[3])
        print(f"  [Threshold] Tier-1 (R>=60%, P>=50%): F1={best[3]:.4f} P={best[1]:.3f} R={best[2]:.3f} @ t={best[0]:.4f}")
        return round(best[0], 4)

    # Strateji 2: Recall >= 60% ve Precision >= 30%
    tier2 = [(t, p, r, f) for t, p, r, f in results if r >= 0.60 and p >= 0.30]
    if tier2:
        best = max(tier2, key=lambda x: x[3])
        print(f"  [Threshold] Tier-2 (R>=60%, P>=30%): F1={best[3]:.4f} P={best[1]:.3f} R={best[2]:.3f} @ t={best[0]:.4f}")
        return round(best[0], 4)

    # Strateji 3: En iyi F1
    best = max(results, key=lambda x: x[3])
    print(f"  [Threshold] Fallback (best F1): F1={best[3]:.4f} P={best[1]:.3f} R={best[2]:.3f} @ t={best[0]:.4f}")
    return round(best[0], 4)


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def _default_path(rel):
    return str(Path(__file__).resolve().parents[2] / rel)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ExpenseGuard - Ensemble Detektor")
    parser.add_argument("--input",  default=_default_path("data/processed/features_engineered.csv"))
    parser.add_argument("--output", default=_default_path("data/processed/ensemble_results.csv"))
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[HATA] Dosya bulunamadi: {input_path}")
        sys.exit(1)

    print(f"\n[1/3] Okunuyor : {input_path}")
    df = pd.read_csv(input_path)
    print(f"      {len(df):,} satir x {df.shape[1]} sutun")

    # is_anomaly bool cevir
    if "is_anomaly" in df.columns:
        df["is_anomaly"] = df["is_anomaly"].astype(str).str.lower().map(
            {"true": True, "false": False, "1": True, "0": False}
        ).fillna(False)

    print("\n[2/3] Ensemble detektor calisiyor...")
    detector = EnsembleDetector()
    result   = detector.fit_predict(df, ground_truth_col="is_anomaly")
    EnsembleDetector.print_summary(result, gt_col="is_anomaly")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    print(f"[3/3] Kaydedildi : {output_path}")
    print(f"      {len(result):,} satir x {result.shape[1]} sutun\n")
    sys.exit(0)
