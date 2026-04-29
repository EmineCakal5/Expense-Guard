# -*- coding: utf-8 -*-
"""
ExpenseGuard - FastAPI Entry Point
===================================
Startup: corporate_expenses_with_anomalies.csv yuklenir -> pipeline calisir -> app.state.df
CORS   : localhost:5173 (React dev server)
Port   : 8000
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# backend/ klasorunu Python path'e ekle (detectors/pipeline importlari icin)
sys.path.insert(0, str(Path(__file__).parent))

from api.routes import router, run_pipeline_on_df

# --------------------------------------------------------------------------- #
#  Varsayilan veri yolu                                                         #
# --------------------------------------------------------------------------- #
_BASE = Path(__file__).resolve().parent.parent          # ExpenseGuard/
_STARTUP_INPUT = _BASE / "data" / "processed" / "corporate_expenses_with_anomalies.csv"
_STARTUP_FALLBACK = _BASE / "data" / "processed" / "corporate_expenses.csv"
_STARTUP_RESULTS = _BASE / "data" / "processed" / "ensemble_results.csv"


# --------------------------------------------------------------------------- #
#  Lifespan: startup + shutdown                                                #
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama baslarken CSV'yi yukle, kapanirken temizle."""
    csv_path = _STARTUP_INPUT if _STARTUP_INPUT.exists() else _STARTUP_FALLBACK

    if csv_path.exists():
        print(f"\n[Startup] Yukleniyor: {csv_path.name}")
        input_df = pd.read_csv(csv_path, low_memory=False)

        try:
            print("[Startup] Pipeline calisiyor (transform -> feature_eng -> detect)...")
            result_df, _summary = run_pipeline_on_df(input_df)
            app.state.df = result_df

            _STARTUP_RESULTS.parent.mkdir(parents=True, exist_ok=True)
            result_df.to_csv(_STARTUP_RESULTS, index=False)
            print(f"[Startup] Kaydedildi: {_STARTUP_RESULTS.name}")
            print(f"[Startup] {len(result_df):,} satir, {result_df.shape[1]} sutun hazir.")
        except Exception as exc:
            print(f"[Startup] UYARI: Pipeline calismadi ({exc}) -> ham veri ile devam.")
            app.state.df = input_df
    else:
        print(f"[Startup] UYARI: CSV bulunamadi -> bos DataFrame ile baslatildi.")
        app.state.df = pd.DataFrame()

    yield  # uygulama calisirken burada bekler

    # Shutdown
    print("[Shutdown] Uygulama kapaniyor.")


# --------------------------------------------------------------------------- #
#  FastAPI uygulamasi                                                          #
# --------------------------------------------------------------------------- #
app = FastAPI(
    title="ExpenseGuard API",
    description="Kurumsal Masraf Anomali Tespit Sistemi",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "*",                        # gelistirme ortami icin tam acik
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router
app.include_router(router, prefix="/api")


# --------------------------------------------------------------------------- #
#  Dev server                                                                  #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        # Windows'ta reload modunda reloader + child process acilir ve
        # bazen (port zaten kullanimda kalmisken) WinError 10013 gorulebilir.
        # Reload istenirse CLI ile calistirin:
        #   python -m uvicorn backend.main:app --reload --port 8000
        reload=False,
    )
