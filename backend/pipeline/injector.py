# -*- coding: utf-8 -*-
"""
ExpenseGuard — Anomali Enjektörü
=================================

corporate_expenses.csv üzerine 6 tip sentetik anomali enjekte eder.
Her anomali satırına is_anomaly=True ve anomaly_type="tip_adı" yazılır.

Anomali Tipleri:
  1. duplicate_expense    — Aynı harcamanın tekrar edilmesi (çift fatura)
  2. excessive_amount     — Grup ortalamasının 4–8x üstünde tutar
  3. weekend_expense      — Hafta sonu yapılmış anormal harcama
  4. split_transaction    — Büyük tutarın eşik altı parçalara bölünmesi
  5. ghost_vendor         — Kayıt dışı / bilinmeyen tedarikçiye ödeme
  6. off_season           — Mevsimle uyumsuz kategori harcaması

Kullanım:
  python injector.py                        # varsayılan yollar
  python injector.py --input x.csv --output y.csv
"""

import argparse
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
#  Sabitler
# ─────────────────────────────────────────────────────────────────────────────

# Duplicate enjeksiyonu için başlangıç ID numarası
DUPLICATE_TXN_START = 90_001

# split_transaction için kullanılan başlangıç ID numarası
SPLIT_TXN_START = 91_001


# ─────────────────────────────────────────────────────────────────────────────
#  AnomalyInjector
# ─────────────────────────────────────────────────────────────────────────────

class AnomalyInjector:
    """
    corporate_expenses.csv verisine 6 tip sentetik anomali enjekte eder.

    Parameters
    ----------
    df           : pd.DataFrame  — corporate_expenses.csv'den okunan veri
    random_state : int           — Tekrar üretilebilirlik için seed (varsayılan 42)
    """

    def __init__(self, df: pd.DataFrame, random_state: int = 42):
        self.df  = df.copy()
        self.rng = np.random.RandomState(random_state)

        # expense_date'i datetime'a çevir (güvenli)
        self.df["expense_date"] = pd.to_datetime(self.df["expense_date"])

        # Dahili sayaçlar — yeni transaction_id üretimi için
        self._dup_counter   = DUPLICATE_TXN_START
        self._split_counter = SPLIT_TXN_START

    # ─────────────────────────────────────────────────────────────────── #
    #  Herkese Açık: Tüm Anomalileri Enjekte Et                           #
    # ─────────────────────────────────────────────────────────────────── #

    def inject_all(self) -> pd.DataFrame:
        """
        6 anomali tipini sırayla enjekte eder.

        Returns
        -------
        pd.DataFrame  — Anomaliler eklenmiş/değiştirilmiş DataFrame
        """
        print("\n[AnomalyInjector] Anomali enjeksiyonu başlıyor...")

        self._inject_duplicates(count=80)
        print("  [OK] duplicate_expense    enjekte edildi (80 kopya)")

        self._inject_excessive(count=100)
        print("  [OK] excessive_amount     enjekte edildi (100 satir)")

        self._inject_weekend(count=60)
        print("  [OK] weekend_expense      enjekte edildi (60 satir)")

        self._inject_splits(count=50)
        print("  [OK] split_transaction    enjekte edildi (50 orijinal -> parcalar)")

        self._inject_ghost_vendor(count=40)
        print("  [OK] ghost_vendor         enjekte edildi (40 satir)")

        self._inject_off_season(count=30)
        print("  [OK] off_season           enjekte edildi (30 satir)")

        self.df = self.df.reset_index(drop=True)
        print(f"\n  Toplam satir (enjeksiyon sonrasi): {len(self.df):,}")
        return self.df

    # ─────────────────────────────────────────────────────────────────── #
    #  1. Çift Fatura (Duplicate Expense)                                  #
    # ─────────────────────────────────────────────────────────────────── #

    def _inject_duplicates(self, count: int = 80) -> None:
        """
        Normal satırlardan count adet seç, kopyala ve anomali olarak ekle.

        - Tarih: orijinalden ±1–3 gün kaydırılır
        - Tutar: ±%2 gürültü eklenir
        - Yeni transaction_id: TXN90001, TXN90002…
        - is_anomaly=True, anomaly_type="duplicate_expense"
        """
        pool = self.df[self.df["is_anomaly"] == False]
        if len(pool) < count:
            count = len(pool)

        chosen = pool.sample(n=count, random_state=self.rng.randint(0, 99_999))
        copies = chosen.copy()

        # Tarih kaydırma: -3 ile +3 gün arası (0 hariç)
        day_offsets = self.rng.choice(
            [-3, -2, -1, 1, 2, 3], size=count, replace=True
        )
        copies["expense_date"] = copies["expense_date"] + pd.to_timedelta(day_offsets, unit="D")

        # Tutar gürültüsü: ±%2
        noise = self.rng.uniform(-0.02, 0.02, size=count)
        copies["amount"] = (copies["amount"] * (1 + noise)).round(2)

        # Yeni transaction_id
        new_ids = [f"TXN{self._dup_counter + i:05d}" for i in range(count)]
        self._dup_counter += count
        copies["transaction_id"] = new_ids

        # Anomali etiketleri
        copies["is_anomaly"]   = True
        copies["anomaly_type"] = "duplicate_expense"
        copies["risk_score"]   = 0.0  # detector dolduracak

        self.df = pd.concat([self.df, copies], ignore_index=True)

    # ─────────────────────────────────────────────────────────────────── #
    #  2. Aşırı Tutar (Excessive Amount)                                   #
    # ─────────────────────────────────────────────────────────────────── #

    def _inject_excessive(self, count: int = 100) -> None:
        """
        Grup (department + expense_category) ortalamasının 4–8x katı tutar atar.

        - Grup ortalaması hesaplanır
        - Normal satırlardan count adet seçilir
        - Tutar → grup_ortalama × U(4, 8) olarak güncellenir
        - is_anomaly=True, anomaly_type="excessive_amount"
        """
        # Grup ortalamaları
        grp_mean = (
            self.df[self.df["is_anomaly"] == False]
            .groupby(["department", "expense_category"])["amount"]
            .mean()
            .rename("grp_mean")
        )

        pool = self.df[self.df["is_anomaly"] == False].copy()
        pool = pool.join(grp_mean, on=["department", "expense_category"])

        if len(pool) < count:
            count = len(pool)

        chosen_idx = pool.sample(n=count, random_state=self.rng.randint(0, 99_999)).index

        # Çarpanlar
        multipliers = self.rng.uniform(4, 8, size=count)
        grp_means   = pool.loc[chosen_idx, "grp_mean"].fillna(
            self.df["amount"].mean()
        ).values

        self.df.loc[chosen_idx, "amount"]       = (grp_means * multipliers).round(2)
        self.df.loc[chosen_idx, "is_anomaly"]   = True
        self.df.loc[chosen_idx, "anomaly_type"] = "excessive_amount"

    # ─────────────────────────────────────────────────────────────────── #
    #  3. Hafta Sonu Harcaması (Weekend Expense)                           #
    # ─────────────────────────────────────────────────────────────────── #

    def _inject_weekend(self, count: int = 60) -> None:
        """
        Hafta içi normal satırları seçip tarihlerini en yakın hafta sonuna kaydırır.

        - Pazartesi (0)–Cuma (4) olan satırlar seçilir
        - Pazartesi/Salı/Çarşamba → önceki Pazar (−1/−2/−3 gün)
        - Perşembe/Cuma            → sonraki Cumartesi (+2/+1 gün)
        - is_anomaly=True, anomaly_type="weekend_expense"
        """
        pool = self.df[
            (self.df["is_anomaly"] == False) &
            (self.df["expense_date"].dt.dayofweek <= 4)   # Hafta içi
        ]
        if len(pool) < count:
            count = len(pool)

        chosen_idx = pool.sample(n=count, random_state=self.rng.randint(0, 99_999)).index
        dow        = self.df.loc[chosen_idx, "expense_date"].dt.dayofweek   # 0=Mon…4=Fri

        # Gün kaydırma: Pzt(-1→Paz), Sal(-2→Paz), Çar(-3→Paz), Per(+2→Cmt), Cum(+1→Cmt)
        shift_map  = {0: -1, 1: -2, 2: -3, 3: 2, 4: 1}
        day_deltas = dow.map(shift_map).fillna(1).astype(int)

        self.df.loc[chosen_idx, "expense_date"] = (
            self.df.loc[chosen_idx, "expense_date"] +
            pd.to_timedelta(day_deltas.values, unit="D")
        )
        self.df.loc[chosen_idx, "is_anomaly"]   = True
        self.df.loc[chosen_idx, "anomaly_type"] = "weekend_expense"

    # ─────────────────────────────────────────────────────────────────── #
    #  4. İşlem Bölme (Split Transaction)                                  #
    # ─────────────────────────────────────────────────────────────────── #

    def _inject_splits(self, count: int = 50) -> None:
        """
        Büyük tutarlı satırları siler ve aynı toplama bölünen 3–5 parçayla değiştirir.

        - amount > 100 olan normal satırlardan count adet seçilir
        - Orijinal satır silinir
        - Yerine 3–5 parça eklenir (rastgele bölüm, toplam = orijinal tutar)
        - Aynı gün, vendor, employee_id, employee_name, department
        - Her parçaya is_anomaly=True, anomaly_type="split_transaction"
        """
        pool = self.df[
            (self.df["is_anomaly"] == False) &
            (self.df["amount"] > 100)
        ]
        if len(pool) < count:
            count = len(pool)

        chosen = pool.sample(n=count, random_state=self.rng.randint(0, 99_999))
        drop_idx   = chosen.index.tolist()
        new_rows   = []

        for _, row in chosen.iterrows():
            n_parts = int(self.rng.randint(3, 6))           # 3–5 parça
            total   = float(row["amount"])

            # Rastgele bölüm: Dirichlet dağılımı ile toplamı koru
            weights = self.rng.dirichlet(np.ones(n_parts))
            parts   = (weights * total).round(2)
            # Yuvarlama farkını son parçaya ekle
            parts[-1] = round(total - parts[:-1].sum(), 2)

            for part_amount in parts:
                new_row = row.copy()
                new_row["transaction_id"] = f"TXN{self._split_counter:05d}"
                self._split_counter      += 1
                new_row["amount"]         = max(0.01, part_amount)  # negatif olmasın
                new_row["is_anomaly"]     = True
                new_row["anomaly_type"]   = "split_transaction"
                new_row["risk_score"]     = 0.0
                new_rows.append(new_row)

        # Orijinal satırları sil
        self.df = self.df.drop(index=drop_idx)

        # Parçaları ekle
        if new_rows:
            parts_df  = pd.DataFrame(new_rows)
            self.df   = pd.concat([self.df, parts_df], ignore_index=True)

    # ─────────────────────────────────────────────────────────────────── #
    #  5. Hayalet Tedarikçi (Ghost Vendor)                                 #
    # ─────────────────────────────────────────────────────────────────── #

    def _inject_ghost_vendor(self, count: int = 40) -> None:
        """
        Normal satırların vendor değerini UNKNOWN_VENDOR_XXXX ile değiştirir.

        - is_anomaly=True, anomaly_type="ghost_vendor"
        """
        pool = self.df[self.df["is_anomaly"] == False]
        if len(pool) < count:
            count = len(pool)

        chosen_idx = pool.sample(n=count, random_state=self.rng.randint(0, 99_999)).index

        fake_ids   = self.rng.randint(1_000, 9_999, size=count)
        fake_names = [f"UNKNOWN_VENDOR_{fid}" for fid in fake_ids]

        self.df.loc[chosen_idx, "vendor"]       = fake_names
        self.df.loc[chosen_idx, "is_anomaly"]   = True
        self.df.loc[chosen_idx, "anomaly_type"] = "ghost_vendor"

    # ─────────────────────────────────────────────────────────────────── #
    #  6. Mevsim Dışı Harcama (Off-Season Expense)                         #
    # ─────────────────────────────────────────────────────────────────── #

    def _inject_off_season(self, count: int = 30) -> None:
        """
        Ayına göre uyumsuz (mevsim dışı) kategori atar.

        Kural:
          Kış  (Aralık 12, Ocak 1, Şubat 2)   → "Seyahat"
          Yaz  (Haziran 6, Temmuz 7, Ağustos 8) → "Ofis Malzemesi"
          Diğer aylar                            → "Ekipman & Donanım"

        - is_anomaly=True, anomaly_type="off_season"
        """
        pool = self.df[self.df["is_anomaly"] == False]
        if len(pool) < count:
            count = len(pool)

        chosen_idx = pool.sample(n=count, random_state=self.rng.randint(0, 99_999)).index
        months     = self.df.loc[chosen_idx, "expense_date"].dt.month

        WINTER  = {12, 1, 2}
        SUMMER  = {6, 7, 8}

        new_cats = months.map(
            lambda m: "Seyahat"          if m in WINTER else
                      "Ofis Malzemesi"   if m in SUMMER else
                      "Ekipman & Donanım"
        )

        self.df.loc[chosen_idx, "expense_category"] = new_cats.values
        self.df.loc[chosen_idx, "is_anomaly"]       = True
        self.df.loc[chosen_idx, "anomaly_type"]     = "off_season"

    # ─────────────────────────────────────────────────────────────────── #
    #  Özet                                                                #
    # ─────────────────────────────────────────────────────────────────── #

    def get_summary(self) -> dict:
        """
        Enjeksiyon özetini döndürür.

        Returns
        -------
        dict
            total_rows, total_anomalies, anomaly_rate,
            by_type (her tip için count + oran),
            normal_count, fraud_original_count
        """
        total      = len(self.df)
        anomalies  = self.df[self.df["is_anomaly"] == True]
        anom_total = len(anomalies)

        by_type: dict[str, dict] = {}
        for atype, grp in anomalies.groupby("anomaly_type"):
            by_type[atype] = {
                "count": int(len(grp)),
                "rate":  round(len(grp) / total, 4),
                "avg_amount": round(float(grp["amount"].mean()), 2),
            }

        return {
            "total_rows":           total,
            "total_anomalies":      anom_total,
            "anomaly_rate":         round(anom_total / total, 4),
            "normal_count":         total - anom_total,
            "fraud_original_count": int(self.df["original_fraud"].sum()),
            "by_type":              by_type,
        }

    def print_summary(self) -> None:
        """Özeti konsola biçimli şekilde yazar."""
        s = self.get_summary()
        print(f"\n{'='*62}")
        print("  AnomalyInjector - Enjeksiyon Ozeti")
        print(f"{'='*62}")
        print(f"\n  Toplam satir          : {s['total_rows']:,}")
        print(f"  Normal satir          : {s['normal_count']:,}")
        print(f"  Anomali satir (topla) : {s['total_anomalies']:,}")
        print(f"  Anomali orani         : %{s['anomaly_rate']*100:.2f}")
        print(f"  Original fraud (ref)  : {s['fraud_original_count']:,}")

        print(f"\n  {'Anomali Tipi':<28} {'Sayi':>6}  {'Oran':>7}  {'Ort.Tutar':>12}")
        print(f"  {'-'*28} {'-'*6}  {'-'*7}  {'-'*12}")
        for atype, info in sorted(s["by_type"].items(), key=lambda x: -x[1]["count"]):
            print(
                f"  {atype:<28} {info['count']:>6,}  "
                f"%{info['rate']*100:>5.2f}  ${info['avg_amount']:>10,.2f}"
            )
        print(f"\n{'='*62}\n")


# ─────────────────────────────────────────────────────────────────────────────
#  CLI — Doğrudan Çalıştırma
# ─────────────────────────────────────────────────────────────────────────────

def _default_path(relative: str) -> str:
    """Bu script'e göre proje kökünü bul ve yolu oluştur."""
    root = Path(__file__).resolve().parents[2]
    return str(root / relative)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ExpenseGuard - Anomali Enjektoru"
    )
    parser.add_argument(
        "--input",
        default=_default_path("data/processed/corporate_expenses.csv"),
        help="corporate_expenses.csv yolu (girdi)",
    )
    parser.add_argument(
        "--output",
        default=_default_path("data/processed/corporate_expenses_with_anomalies.csv"),
        help="Çıktı CSV yolu",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed (varsayılan: 42)",
    )
    args = parser.parse_args()

    # ── Oku ──────────────────────────────────────────────────────────────
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[HATA] Girdi dosyasi bulunamadi: {input_path}")
        print("       Once transformer.py'yi calistirin.")
        sys.exit(1)

    print(f"\n[1/3] Okunuyor : {input_path}")
    df = pd.read_csv(input_path)
    print(f"      {len(df):,} satir x {df.shape[1]} sutun yuklendi")

    # is_anomaly sütununu bool'a çevir (CSV'den string gelebilir)
    df["is_anomaly"] = df["is_anomaly"].astype(str).str.lower().map(
        {"true": True, "false": False, "1": True, "0": False}
    ).fillna(False)

    # ── Enjeksiyon ───────────────────────────────────────────────────────
    print("\n[2/3] Anomaliler enjekte ediliyor...")

    injector = AnomalyInjector(df, random_state=args.random_state)
    result   = injector.inject_all()
    injector.print_summary()

    # ── Kaydet ───────────────────────────────────────────────────────────
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    print(f"[3/3] Kaydedildi : {output_path}")
    print(f"      {len(result):,} satir x {result.shape[1]} sutun\n")

    sys.exit(0)
