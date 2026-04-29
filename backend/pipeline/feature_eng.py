# -*- coding: utf-8 -*-
"""
ExpenseGuard - Ozellik Muhendisligi (Feature Engineering)
==========================================================

corporate_expenses_with_anomalies.csv uzerine anomali tespiti icin
gerekli 10 sayisal ozellik kolonu ekler.

Eklenen ozellikler:
  1.  dept_category_mean_ratio   - Tutar / grup ortalamasi
  2.  amount_zscore              - Kategori ici z-skoru
  3.  vendor_frequency           - Tedarikci tekrar sayisi
  4.  is_weekend                 - Hafta sonu mu? (1/0)
  5.  day_of_week                - Haftanin gunu (0-6)
  6.  month                      - Ay (1-12)
  7.  rolling_7d_employee_count  - Son 7 gunde calisan islem sayisi
  8.  is_round_amount            - Yuvarlak tutar mi? (1/0)
  9.  amount_log                 - log1p(amount)
  10. dept_monthly_total_ratio   - Tutar / departman aylik toplam

Kullanim:
  python feature_eng.py
  python feature_eng.py --input x.csv --output y.csv
"""

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd


# Eklenen ozellik kolon isimleri (sabit referans)
FEATURE_COLUMNS: List[str] = [
    "dept_category_mean_ratio",
    "amount_zscore",
    "vendor_frequency",
    "is_weekend",
    "day_of_week",
    "month",
    "rolling_7d_employee_count",
    "is_round_amount",
    "amount_log",
    "dept_monthly_total_ratio",
]


class FeatureEngineer:
    """
    DataFrame'e anomali tespiti icin 10 ozellik kolonu ekler.

    Parameters
    ----------
    df : pd.DataFrame
        corporate_expenses (veya _with_anomalies) formati.
        Zorunlu kolonlar: amount, department, expense_category,
                          vendor, expense_date, employee_id

    Kullanim
    --------
    >>> fe = FeatureEngineer(df)
    >>> enriched_df, new_cols = fe.engineer_all()
    """

    def __init__(self, df: pd.DataFrame, random_state: int = 42):
        self.df = df.copy()
        self.rng = np.random.RandomState(random_state)

        # expense_date'i datetime'a cevir (guvenli)
        self.df["expense_date"] = pd.to_datetime(self.df["expense_date"])

    # ================================================================== #
    #  Ana metod                                                          #
    # ================================================================== #

    def engineer_all(self) -> Tuple[pd.DataFrame, List[str]]:
        """
        Tum ozellikleri sirayla ekler.

        Returns
        -------
        (pd.DataFrame, list[str])
            Zenginlestirilmis DataFrame ve eklenen kolon isimleri listesi.
        """
        print("\n[FeatureEngineer] Ozellik muhendisligi basliyor...")

        self._add_dept_category_mean_ratio()
        print("  [OK]  1/10  dept_category_mean_ratio")

        self._add_amount_zscore()
        print("  [OK]  2/10  amount_zscore")

        self._add_vendor_frequency()
        print("  [OK]  3/10  vendor_frequency")

        self._add_is_weekend()
        print("  [OK]  4/10  is_weekend")

        self._add_day_of_week()
        print("  [OK]  5/10  day_of_week")

        self._add_month()
        print("  [OK]  6/10  month")

        self._add_rolling_7d_employee_count()
        print("  [OK]  7/10  rolling_7d_employee_count")

        self._add_is_round_amount()
        print("  [OK]  8/10  is_round_amount")

        self._add_amount_log()
        print("  [OK]  9/10  amount_log")

        self._add_dept_monthly_total_ratio()
        print("  [OK] 10/10  dept_monthly_total_ratio")

        # Tum NaN degerleri 0 ile doldur
        self.df[FEATURE_COLUMNS] = self.df[FEATURE_COLUMNS].fillna(0)

        print(f"\n  Toplam {len(FEATURE_COLUMNS)} ozellik eklendi.")
        print(f"  DataFrame boyutu: {self.df.shape[0]:,} satir x {self.df.shape[1]} sutun")

        return self.df, list(FEATURE_COLUMNS)

    # ================================================================== #
    #  1. dept_category_mean_ratio                                        #
    # ================================================================== #

    def _add_dept_category_mean_ratio(self) -> None:
        """
        Her satirin tutarini ayni department + expense_category grubunun
        ortalamasina boler.

        Formul: amount / group_mean
        Yuksek deger = o grup icin anormal derecede pahali harcama.
        """
        group_mean = (
            self.df
            .groupby(["department", "expense_category"])["amount"]
            .transform("mean")
        )
        # Sifira bolmeyi onle
        self.df["dept_category_mean_ratio"] = (
            self.df["amount"] / group_mean.replace(0, np.nan)
        ).round(4)

    # ================================================================== #
    #  2. amount_zscore                                                   #
    # ================================================================== #

    def _add_amount_zscore(self) -> None:
        """
        Her satirin tutarinin ayni expense_category icindeki z-skorunu hesaplar.

        Formul: (amount - category_mean) / category_std
        |z| > 3 --> guclu anomali sinyali.
        """
        cat_mean = (
            self.df
            .groupby("expense_category")["amount"]
            .transform("mean")
        )
        cat_std = (
            self.df
            .groupby("expense_category")["amount"]
            .transform("std")
        )
        # std=0 olan gruplar icin NaN uret (sonra 0 olacak)
        self.df["amount_zscore"] = (
            (self.df["amount"] - cat_mean) / cat_std.replace(0, np.nan)
        ).round(4)

    # ================================================================== #
    #  3. vendor_frequency                                                #
    # ================================================================== #

    def _add_vendor_frequency(self) -> None:
        """
        Her vendor'in veri setinde kac kez gorundugunu hesaplar.

        Dusuk frekans (1-2) = potansiyel hayalet vendor.
        """
        self.df["vendor_frequency"] = (
            self.df
            .groupby("vendor")["vendor"]
            .transform("count")
        )

    # ================================================================== #
    #  4. is_weekend                                                      #
    # ================================================================== #

    def _add_is_weekend(self) -> None:
        """
        expense_date haftanin gunu 5 (Cumartesi) veya 6 (Pazar) ise 1, degilse 0.
        """
        dow = self.df["expense_date"].dt.dayofweek  # 0=Mon ... 6=Sun
        self.df["is_weekend"] = (dow >= 5).astype(int)

    # ================================================================== #
    #  5. day_of_week                                                     #
    # ================================================================== #

    def _add_day_of_week(self) -> None:
        """
        0-6 arasi, Pazartesi=0, Pazar=6.
        """
        self.df["day_of_week"] = self.df["expense_date"].dt.dayofweek

    # ================================================================== #
    #  6. month                                                           #
    # ================================================================== #

    def _add_month(self) -> None:
        """
        1-12 arasi ay degeri.
        """
        self.df["month"] = self.df["expense_date"].dt.month

    # ================================================================== #
    #  7. rolling_7d_employee_count                                       #
    # ================================================================== #

    def _add_rolling_7d_employee_count(self) -> None:
        """
        Her calisan icin son 7 gundeki islem sayisi.
        Yuksek deger = burst/toplu harcama sinyali.

        Yontem: tarihe gore sirala, employee_id grubunda 7 gunluk
                rolling count uygula.
        """
        # Orijinal index'i koru
        original_idx = self.df.index.copy()

        # Tarihe gore sirala
        df_sorted = self.df.sort_values("expense_date").copy()
        df_sorted = df_sorted.set_index("expense_date")

        # Her calisan icin 7 gunluk rolling count
        rolling_counts = (
            df_sorted
            .groupby("employee_id")["amount"]
            .rolling("7D", min_periods=1)
            .count()
        )

        # Multi-index'i duzlestir
        rolling_counts = rolling_counts.reset_index(level=0, drop=True)

        # Sonucu df_sorted'a ekle
        df_sorted["rolling_7d_employee_count"] = rolling_counts.values

        # index'i geri al
        df_sorted = df_sorted.reset_index()

        # Orijinal siralama ile birlestir
        self.df = self.df.drop(columns=["rolling_7d_employee_count"], errors="ignore")
        self.df = self.df.merge(
            df_sorted[["transaction_id", "rolling_7d_employee_count"]],
            on="transaction_id",
            how="left",
        )

        self.df["rolling_7d_employee_count"] = (
            self.df["rolling_7d_employee_count"].fillna(1).astype(int)
        )

    # ================================================================== #
    #  8. is_round_amount                                                 #
    # ================================================================== #

    def _add_is_round_amount(self) -> None:
        """
        Tutar tam yuvarlak sayi mi? (amount % 10 == 0) --> 1/0.
        Sahte faturalar genelde yuvarlak tutarli olur.
        """
        self.df["is_round_amount"] = (self.df["amount"] % 10 == 0).astype(int)

    # ================================================================== #
    #  9. amount_log                                                      #
    # ================================================================== #

    def _add_amount_log(self) -> None:
        """
        np.log1p(amount) -- skewed dagilimi normalize eder.
        ML modelleri icin onemli on-isleme adimi.
        """
        self.df["amount_log"] = np.log1p(self.df["amount"]).round(6)

    # ================================================================== #
    #  10. dept_monthly_total_ratio                                       #
    # ================================================================== #

    def _add_dept_monthly_total_ratio(self) -> None:
        """
        Bu harcamanin tutari / ayni departmanin o aydaki toplam harcamasi.
        Tek basina buyuk pay alan islemler supheli.
        """
        # Ay kolonu zaten eklenmis durumda
        monthly_total = (
            self.df
            .groupby(["department", "month"])["amount"]
            .transform("sum")
        )
        self.df["dept_monthly_total_ratio"] = (
            self.df["amount"] / monthly_total.replace(0, np.nan)
        ).round(6)

    # ================================================================== #
    #  Ozet / Istatistik                                                  #
    # ================================================================== #

    def print_feature_stats(self) -> None:
        """Eklenen ozelliklerin temel istatistiklerini yazdirir."""
        available = [c for c in FEATURE_COLUMNS if c in self.df.columns]
        if not available:
            print("  Henuz ozellik eklenmedi.")
            return

        print(f"\n{'='*72}")
        print("  FeatureEngineer - Ozellik Istatistikleri")
        print(f"{'='*72}")

        stats = self.df[available].describe().T[["mean", "std", "min", "50%", "max"]]
        stats.columns = ["Ortalama", "Std", "Min", "Medyan", "Max"]

        for col in available:
            row = stats.loc[col]
            print(
                f"\n  {col:.<40}"
                f"  Ort: {row['Ortalama']:>10.4f}"
                f"  Std: {row['Std']:>10.4f}"
                f"  Min: {row['Min']:>10.4f}"
                f"  Med: {row['Medyan']:>10.4f}"
                f"  Max: {row['Max']:>10.4f}"
            )

        # Anomali sinyali ozetleri
        if "amount_zscore" in self.df.columns:
            high_z = (self.df["amount_zscore"].abs() > 3).sum()
            print(f"\n  |z-score| > 3 olan satir sayisi : {high_z:,}")

        if "vendor_frequency" in self.df.columns:
            low_freq = (self.df["vendor_frequency"] <= 2).sum()
            print(f"  vendor_frequency <= 2 (supheli)  : {low_freq:,}")

        if "is_weekend" in self.df.columns:
            wk = self.df["is_weekend"].sum()
            print(f"  Hafta sonu islem sayisi          : {wk:,}")

        if "is_round_amount" in self.df.columns:
            rnd = self.df["is_round_amount"].sum()
            print(f"  Yuvarlak tutarli islem sayisi    : {rnd:,}")

        print(f"\n{'='*72}\n")


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def _default_path(relative: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return str(root / relative)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ExpenseGuard - Ozellik Muhendisligi"
    )
    parser.add_argument(
        "--input",
        default=_default_path("data/processed/corporate_expenses_with_anomalies.csv"),
        help="Girdi CSV yolu",
    )
    parser.add_argument(
        "--output",
        default=_default_path("data/processed/features_engineered.csv"),
        help="Cikti CSV yolu",
    )
    args = parser.parse_args()

    # -- Oku --
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[HATA] Dosya bulunamadi: {input_path}")
        print("       Once transformer.py ve injector.py calistirin.")
        sys.exit(1)

    print(f"\n[1/3] Okunuyor : {input_path}")
    df = pd.read_csv(input_path)
    print(f"      {len(df):,} satir x {df.shape[1]} sutun yuklendi")

    # -- Ozellik muhendisligi --
    print("\n[2/3] Ozellikler ekleniyor...")
    fe = FeatureEngineer(df)
    result, new_cols = fe.engineer_all()
    fe.print_feature_stats()

    # -- Kaydet --
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    print(f"[3/3] Kaydedildi : {output_path}")
    print(f"      {len(result):,} satir x {result.shape[1]} sutun")
    print(f"      Eklenen ozellikler: {new_cols}\n")

    sys.exit(0)
