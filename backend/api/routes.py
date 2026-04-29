# -*- coding: utf-8 -*-
"""
ExpenseGuard - API Routes
==========================

Endpoint'ler:
  GET  /api/health                   -- Saglik kontrolu
  POST /api/upload                   -- CSV yukle & pipeline calistir
  GET  /api/dashboard                -- Ozet istatistikler
  GET  /api/anomalies                -- Anomali listesi (filtreleme + sayfalama)
  GET  /api/anomalies/{id}           -- Tek islem detayi
  GET  /api/departments              -- Departman bazli analiz
  GET  /api/timeline                 -- Zaman serisi
  GET  /api/metrics                  -- Model performans metrikleri
"""

import io
import json
import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

# backend/ dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.transformer import transform_sparkov_to_corporate
from pipeline.injector import AnomalyInjector
from pipeline.feature_eng import FeatureEngineer
from detectors.ensemble import EnsembleDetector

router = APIRouter()

# --------------------------------------------------------------------------- #
#  Yardimci: app.state.df'yi al                                               #
# --------------------------------------------------------------------------- #

def _df(request: Request) -> pd.DataFrame:
    """app.state.df'yi dondurur; bos ise 503 firlatir."""
    df: pd.DataFrame = getattr(request.app.state, "df", pd.DataFrame())
    if df.empty:
        raise HTTPException(
            status_code=503,
            detail="Veri yuklenmedi. /api/upload ile CSV gonderin.",
        )
    return df


def _safe_json(obj):
    """NaN / Inf / numpy tiplerini JSON-serializeable yap."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def _df_to_records(df: pd.DataFrame) -> list:
    """DataFrame'i JSON-safe dict listesine cevir."""
    records = json.loads(
        df.replace([np.inf, -np.inf], np.nan)
        .to_json(orient="records", date_format="iso", default_handler=str)
    )
    return records


def _add_risk_level(df: pd.DataFrame) -> pd.DataFrame:
    """risk_level kolonu yoksa ensemble_score'dan ekler."""
    if "risk_level" not in df.columns:
        if "ensemble_score" in df.columns:
            df = df.copy()
            df["risk_level"] = pd.cut(
                df["ensemble_score"],
                bins=[-0.001, 0.33, 0.66, 1.01],
                labels=["low", "medium", "high"],
            ).astype(str)
        else:
            df = df.copy()
            df["risk_level"] = "low"
    return df


def _coerce_boolish_series(s: pd.Series) -> pd.Series:
    """'true/false/1/0' benzeri degerleri bool'a cevirir."""
    return (
        s.astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False, "1": True, "0": False, "yes": True, "no": False})
        .fillna(False)
    )


def run_pipeline_on_df(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Pipeline: transform -> feature_eng -> detect

    - Sparkov ham format ise: transform calisir
    - Corporate format ise: transform atlanir
    - is_anomaly yoksa: injector ile ground truth enjekte edilir
    - feature_eng: 10 ozellik eklenir
    - detect: ensemble tahmini uretilir (predicted_anomaly + skorlar + rule_* kolonlari)
    """
    if df is None or df.empty:
        raise ValueError("Bos veri ile pipeline calistirilamaz.")

    work = df.copy()

    # 0) Bool kolonlarini normalize et
    for col in ["is_anomaly", "original_fraud"]:
        if col in work.columns:
            work[col] = _coerce_boolish_series(work[col])

    # 1) Transform (Sparkov ham verisini corporate formata cevir)
    # Sparkov'ta tipik kolonlar: amt, cc_num, trans_date_trans_time, merchant, category, is_fraud, job, first, last
    is_sparkov_like = any(c in work.columns for c in ["amt", "cc_num", "trans_date_trans_time", "is_fraud"])
    if is_sparkov_like:
        _RAW_TEMP.parent.mkdir(parents=True, exist_ok=True)
        work.to_csv(_RAW_TEMP, index=False)
        work = transform_sparkov_to_corporate(
            str(_RAW_TEMP),
            output_path=str(_PROCESSED / "corporate_expenses.csv"),
        )

    # 2) Ground truth / anomaly injection (yoksa)
    if "is_anomaly" not in work.columns:
        injector = AnomalyInjector(work)
        work = injector.inject_all()
    else:
        work["is_anomaly"] = _coerce_boolish_series(work["is_anomaly"])

    # 3) Feature engineering
    fe = FeatureEngineer(work)
    enriched_df, _new_cols = fe.engineer_all()

    # 4) Detect
    detector = EnsembleDetector()
    result_df = detector.fit_predict(enriched_df, ground_truth_col="is_anomaly")
    result_df = _add_risk_level(result_df)

    # 5) Ozet
    summary = EnsembleDetector.summary(result_df)
    return result_df, summary


# --------------------------------------------------------------------------- #
#  Dosya yollari                                                               #
# --------------------------------------------------------------------------- #
_BASE = Path(__file__).resolve().parents[2]   # ExpenseGuard/
_RAW_TEMP     = _BASE / "data" / "raw"   / "temp_upload.csv"
_PROCESSED    = _BASE / "data" / "processed"
_RESULTS_CSV  = _PROCESSED / "ensemble_results.csv"


# =========================================================================== #
#  GET /api/health                                                             #
# =========================================================================== #
@router.get("/health", tags=["System"])
def health(request: Request):
    """Saglik kontrolu."""
    return {"status": "ok"}


# =========================================================================== #
#  POST /api/upload                                                            #
# =========================================================================== #
@router.post("/upload", tags=["Data"])
async def upload_csv(request: Request, file: UploadFile = File(...)):
    """
    Yeni bir CSV dosyasi yukle, tam pipeline'dan gecir ve
    app.state.df'yi guncelle.

    Kabul edilen format:
    - Ham Sparkov (fraudTrain.csv uyumlu): transformer calisir
    - Zaten corporate format: transformer atlanir
    """
    filename = (file.filename or "").lower()
    is_csv = filename.endswith(".csv")
    is_excel = filename.endswith(".xlsx") or filename.endswith(".xls")
    if not (is_csv or is_excel):
        raise HTTPException(status_code=400, detail="Sadece CSV veya Excel (.xlsx/.xls) dosyasi kabul edilir.")

    contents = await file.read()
    try:
        if is_csv:
            raw_df = pd.read_csv(io.BytesIO(contents))
        else:
            # Not: Excel okumak icin genelde openpyxl gerekir.
            raw_df = pd.read_excel(io.BytesIO(contents))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Dosya okunamadi: {exc}")

    try:
        # Pipeline calistir
        result_df, summary = run_pipeline_on_df(raw_df)

        # Kaydet & state guncelle
        _RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_csv(_RESULTS_CSV, index=False)
        request.app.state.df = result_df

        return {
            "message": "Dosya basariyla islendi.",
            "rows_processed": len(result_df),
            **summary,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline hatasi: {exc}")


# =========================================================================== #
#  GET /api/dashboard                                                          #
# =========================================================================== #
@router.get("/dashboard", tags=["Analytics"])
def dashboard(request: Request):
    """
    Ozet istatistikler:
    - Toplam islem, anomali sayisi, anomali orani
    - Risk dagilimi (low/medium/high)
    - Departman bazli anomali oranlari (top 5)
    - Ortalama tutar karsilastirmasi
    """
    df = _df(request)
    df = _add_risk_level(df)

    total = len(df)
    anomaly_col = "predicted_anomaly" if "predicted_anomaly" in df.columns else "is_anomaly"
    anomaly_mask = (
        df[anomaly_col]
        .astype(str)
        .str.lower()
        .isin(["1", "true"])
        .fillna(False)
    )
    mask = anomaly_mask.to_numpy(dtype=bool)
    flagged = int(mask.sum())

    # Risk dagilimi
    risk_dist = {"low": 0, "medium": 0, "high": 0}
    if "risk_level" in df.columns:
        counts = df["risk_level"].value_counts().to_dict()
        risk_dist.update({k: int(v) for k, v in counts.items() if k in risk_dist})

    # Departman bazli anomali oranlari
    dept_anom = []
    if "department" in df.columns:
        grp = df.groupby("department").agg(
            total=(anomaly_col, "count"),
            anomalies=(anomaly_col, lambda x: int(x.astype(str).str.lower().isin(["1","true"]).sum())),
            avg_amount=("amount", "mean"),
        ).reset_index()
        grp["anomaly_rate"] = (grp["anomalies"] / grp["total"]).round(4)
        grp = grp.sort_values("anomaly_rate", ascending=False)
        dept_anom = _df_to_records(grp.head(10))

    # Anomali tipi dagilimi
    type_dist = {}
    for col in ["anomaly_type", "anomaly_types"]:
        if col in df.columns:
            type_series = df.loc[mask, col].dropna()
            type_series = type_series[type_series.astype(str).str.lower() != "none"]
            if len(type_series) > 0:
                type_dist = type_series.value_counts().to_dict()
            break

    # Tutar karsilastirmasi
    normal_avg = float(df.loc[~mask, "amount"].mean()) if (~mask).any() else 0.0
    anomaly_avg = float(df.loc[mask, "amount"].mean()) if mask.any() else 0.0

    return {
        "total_transactions": total,
        "flagged_anomalies": flagged,
        "anomaly_rate": round(flagged / total, 4) if total else 0.0,
        "risk_distribution": risk_dist,
        "top_departments_by_anomaly_rate": dept_anom,
        "anomaly_type_distribution": type_dist,
        "avg_amount_normal": round(normal_avg, 2),
        "avg_amount_anomaly": round(anomaly_avg, 2),
    }


# =========================================================================== #
#  GET /api/anomalies                                                          #
# =========================================================================== #
@router.get("/anomalies", tags=["Analytics"])
def get_anomalies(
    request: Request,
    department: Optional[str] = Query(None, description="Departman filtresi"),
    risk_level: Optional[str] = Query(None, description="low | medium | high"),
    anomaly_type: Optional[str] = Query(None, description="Anomali tipi filtresi"),
    only_flagged: bool = Query(True, description="Sadece tespit edilenleri goster (default: true)"),
    page: int = Query(1, ge=1, description="Sayfa numarasi"),
    per_page: int = Query(20, ge=1, le=200, description="Sayfa basi kayit"),
):
    """
    Anomali listesi — filtreleme + sayfalama.

    Donulen alanlar: transaction_id, employee_id, employee_name,
    department, expense_category, vendor, amount, expense_date,
    predicted_anomaly, anomaly_type, ensemble_score, risk_level,
    if_score, lof_score, rule_score
    """
    df = _df(request)
    df = _add_risk_level(df)

    anomaly_col = "predicted_anomaly" if "predicted_anomaly" in df.columns else "is_anomaly"
    mask = pd.Series(True, index=df.index)

    if only_flagged:
        mask &= df[anomaly_col].astype(str).str.lower().isin(["1", "true"])
    if department:
        if "department" in df.columns:
            mask &= df["department"].str.lower() == department.lower()
    if risk_level and "risk_level" in df.columns:
        mask &= df["risk_level"].str.lower() == risk_level.lower()
    if anomaly_type:
        for col in ["anomaly_type", "anomaly_types"]:
            if col in df.columns:
                mask &= df[col].astype(str).str.contains(anomaly_type, case=False, na=False)
                break

    filtered = df[mask].copy()
    total = len(filtered)
    total_pages = math.ceil(total / per_page) if total else 1
    start = (page - 1) * per_page
    end = start + per_page
    page_df = filtered.iloc[start:end]

    # Cikti kolonlari
    wanted = [
        "transaction_id", "employee_id", "employee_name", "department",
        "expense_category", "vendor", "amount", "expense_date",
        "predicted_anomaly", "anomaly_type", "anomaly_types",
        "ensemble_score", "risk_level",
        "if_score", "lof_score", "rule_score", "rule_flag",
        "is_anomaly", "original_fraud",
    ]
    available = [c for c in wanted if c in page_df.columns]

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "data": _df_to_records(page_df[available]),
    }


# =========================================================================== #
#  GET /api/anomalies/{transaction_id}                                         #
# =========================================================================== #
@router.get("/anomalies/{transaction_id}", tags=["Analytics"])
def get_anomaly_detail(transaction_id: str, request: Request):
    """Tek islem detayi. Bulunamazsa 404."""
    df = _df(request)
    df = _add_risk_level(df)

    # transaction_id'ye gore filtrele
    tid_col = "transaction_id" if "transaction_id" in df.columns else None
    if tid_col is None:
        raise HTTPException(status_code=400, detail="transaction_id kolonu bulunamadi.")

    row = df[df[tid_col].astype(str) == str(transaction_id)]
    if row.empty:
        raise HTTPException(
            status_code=404,
            detail=f"'{transaction_id}' ID'li islem bulunamadi.",
        )

    record = _df_to_records(row.head(1))[0]

    # Tetiklenen kurallar listesi
    triggered_rules = []
    rule_cols = [c for c in df.columns if c.startswith("rule_") and c not in ("rule_score", "rule_flag")]
    for rc in rule_cols:
        val = record.get(rc, 0)
        if val and str(val) not in ("0", "0.0", "False", "false", "nan", "None"):
            triggered_rules.append(rc.replace("rule_", ""))

    record["triggered_rules"] = triggered_rules
    return record


# =========================================================================== #
#  GET /api/departments                                                        #
# =========================================================================== #
@router.get("/departments", tags=["Analytics"])
def get_departments(request: Request):
    """
    Departman bazli toplam harcama, anomali sayisi ve anomali orani.
    Pandas groupby ile hesaplanir.
    """
    df = _df(request)
    anomaly_col = "predicted_anomaly" if "predicted_anomaly" in df.columns else "is_anomaly"

    if "department" not in df.columns:
        raise HTTPException(status_code=400, detail="department kolonu bulunamadi.")

    grp = df.groupby("department").agg(
        total_transactions=(anomaly_col, "count"),
        total_anomalies=(anomaly_col, lambda x: int(
            x.astype(str).str.lower().isin(["1", "true"]).sum()
        )),
        total_amount=("amount", "sum"),
        avg_amount=("amount", "mean"),
        avg_ensemble_score=("ensemble_score", "mean") if "ensemble_score" in df.columns else ("amount", "count"),
    ).reset_index()

    grp["anomaly_rate"] = (grp["total_anomalies"] / grp["total_transactions"]).round(4)
    grp = grp.sort_values("total_amount", ascending=False)
    grp = grp.round(2)

    return _df_to_records(grp)


# =========================================================================== #
#  GET /api/timeline                                                           #
# =========================================================================== #
@router.get("/timeline", tags=["Analytics"])
def get_timeline(
    request: Request,
    granularity: str = Query("month", pattern="^(day|week|month)$"),
):
    """
    Tarih bazli anomali sayisi ve toplam harcama trendi.

    granularity: day | week | month (default: month)
    """
    df = _df(request)
    date_col = "expense_date" if "expense_date" in df.columns else "transaction_date"
    anomaly_col = "predicted_anomaly" if "predicted_anomaly" in df.columns else "is_anomaly"

    if date_col not in df.columns:
        raise HTTPException(status_code=400, detail="Tarih kolonu bulunamadi.")

    work = df.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work = work.dropna(subset=[date_col])

    # Period icin aylik frekans: 'M' (Pandas 'ME' kabul etmiyor)
    freq_map = {"day": "D", "week": "W", "month": "M"}
    freq = freq_map[granularity]
    work["period"] = work[date_col].dt.to_period(freq).astype(str)

    agg = work.groupby("period").agg(
        total_transactions=(anomaly_col, "count"),
        total_anomalies=(anomaly_col, lambda x: int(
            x.astype(str).str.lower().isin(["1", "true"]).sum()
        )),
        total_amount=("amount", "sum"),
        avg_amount=("amount", "mean"),
    ).reset_index().sort_values("period")

    agg["anomaly_rate"] = (agg["total_anomalies"] / agg["total_transactions"]).round(4)
    agg = agg.round(2)

    return {
        "granularity": granularity,
        "data": _df_to_records(agg),
    }


# =========================================================================== #
#  GET /api/metrics                                                            #
# =========================================================================== #
@router.get("/metrics", tags=["Analytics"])
def get_metrics(request: Request):
    """
    Model performans metrikleri.

    Karsilastirma:
    - y_true: is_anomaly (enjekte edilen ground truth)
    - y_pred: predicted_anomaly (modelimizin ciktisi)
    - original_fraud: Sparkov'un orijinal fraud etiketi (referans)

    Scikit-learn ile precision, recall, F1 ve confusion matrix doner.
    """
    df = _df(request)

    if "is_anomaly" not in df.columns or "predicted_anomaly" not in df.columns:
        raise HTTPException(
            status_code=400,
            detail="is_anomaly veya predicted_anomaly kolonu bulunamadi.",
        )

    y_true = df["is_anomaly"].astype(str).str.lower().isin(["1", "true"]).astype(int).values
    y_pred = df["predicted_anomaly"].astype(str).str.lower().isin(["1", "true"]).astype(int).values

    prec  = float(precision_score(y_true, y_pred, zero_division=0))
    rec   = float(recall_score(y_true, y_pred, zero_division=0))
    f1    = float(f1_score(y_true, y_pred, zero_division=0))
    cm    = confusion_matrix(y_true, y_pred).tolist()

    # Per-class rapor
    report = classification_report(
        y_true, y_pred,
        target_names=["Normal", "Anomali"],
        output_dict=True,
        zero_division=0,
    )

    # Anomali tipi bazinda breakdown
    type_breakdown = {}
    for col in ["anomaly_type", "anomaly_types"]:
        if col in df.columns:
            anom_df = df[y_true.astype(bool)]
            for atype in anom_df[col].dropna().unique():
                if str(atype).lower() in ("none", "nan", ""):
                    continue
                mask_t = anom_df[col].astype(str) == str(atype)
                mask_p = df.loc[anom_df.index, "predicted_anomaly"].astype(str).str.lower().isin(["1", "true"])
                tp_count = int((mask_t & mask_p[anom_df.index]).sum())
                total_t  = int(mask_t.sum())
                type_breakdown[str(atype)] = {
                    "total": total_t,
                    "detected": tp_count,
                    "recall": round(tp_count / total_t, 4) if total_t else 0.0,
                }
            break

    # Original fraud vs predicted_anomaly
    orig_metrics = {}
    if "original_fraud" in df.columns:
        y_orig = df["original_fraud"].astype(str).str.lower().isin(["1", "true"]).astype(int).values
        orig_metrics = {
            "original_fraud_count": int(y_orig.sum()),
            "overlap_with_predicted": int((y_orig & y_pred).sum()),
        }

    return {
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "confusion_matrix": {
            "TN": cm[0][0], "FP": cm[0][1],
            "FN": cm[1][0], "TP": cm[1][1],
        },
        "classification_report": report,
        "anomaly_type_breakdown": type_breakdown,
        "original_fraud_comparison": orig_metrics,
        "total_evaluated": len(df),
    }
