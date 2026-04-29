# -*- coding: utf-8 -*-
"""Debug 3: Hedefli kurallarin FP/TP dagilimi."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
from detectors.rule_based import RuleBasedDetector

df = pd.read_csv("../data/processed/features_engineered.csv")
df["expense_date"] = pd.to_datetime(df["expense_date"])
df["is_anomaly"] = df["is_anomaly"].astype(str).str.lower().isin(["true","1"])

rbd = RuleBasedDetector()
rdf = rbd.predict(df)

targeted = ["rule_duplicate", "rule_ghost_vendor", "rule_excessive", "rule_split_txn"]
print("=== HEDEFLI KURAL FP/TP ANALIZI ===\n")
for rc in targeted:
    fired = rdf[rdf[rc] == 1]
    tp = fired[fired["is_anomaly"]].shape[0]
    fp = fired[~fired["is_anomaly"]].shape[0]
    total = len(fired)
    prec = tp / total if total else 0
    print(f"  {rc:<25}: tetiklenen={total:>5}  TP={tp:>4}  FP={fp:>5}  Prec={prec:.3f}")
    if rc == "rule_excessive":
        # Hangi anomali tipleri yakalaniyor?
        at = fired[fired["is_anomaly"]]["anomaly_type"].value_counts()
        print(f"    Anomali tipleri: {at.to_dict()}")
    if rc == "rule_split_txn":
        at = fired[fired["is_anomaly"]]["anomaly_type"].value_counts()
        print(f"    Anomali tipleri: {at.to_dict()}")

print(f"\n=== TOPLAM KURAL BAZINDA ANALIZ ===\n")
all_rules = rbd.RULE_COLS
for rc in all_rules:
    fired = rdf[rdf[rc] == 1]
    tp = fired[fired["is_anomaly"]].shape[0]
    fp = fired[~fired["is_anomaly"]].shape[0]
    total = len(fired)
    prec = tp / total * 100 if total else 0
    print(f"  {rc:<25}: toplam={total:>5}  TP={tp:>4}  FP={fp:>5}  Prec={prec:.1f}%")

# IF/LOF precision
from pipeline.feature_eng import FEATURE_COLUMNS
from detectors.isolation_forest import IsolationForestDetector
from detectors.lof_detector import LOFDetector

avail = [c for c in FEATURE_COLUMNS if c in rdf.columns]
rule_cols_feat = [c for c in all_rules if c in rdf.columns]
X = rdf[avail + rule_cols_feat].fillna(0).to_numpy()
ifd = IsolationForestDetector()
if_l, if_s = ifd.fit_predict(X)
lof = LOFDetector()
lof_l, lof_s = lof.fit_predict(X)

gt = rdf["is_anomaly"].values
print(f"\n  IF  label=1: {if_l.sum():>5}  TP={int((if_l & gt).sum()):>4}  FP={int((if_l & ~gt).sum()):>5}  Prec={int((if_l & gt).sum())/max(if_l.sum(),1)*100:.1f}%")
print(f"  LOF label=1: {lof_l.sum():>5}  TP={int((lof_l & gt).sum()):>4}  FP={int((lof_l & ~gt).sum()):>5}  Prec={int((lof_l & gt).sum())/max(lof_l.sum(),1)*100:.1f}%")
print(f"  ML consensus=2: {int(((if_l+lof_l)>=2).sum()):>4}  TP={int(((if_l+lof_l>=2)&gt).sum()):>3}  FP={int(((if_l+lof_l>=2)&~gt).sum()):>4}")
