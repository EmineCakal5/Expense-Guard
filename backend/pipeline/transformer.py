"""
ExpenseGuard — Sparkov → Kurumsal Masraf Dönüştürücüsü
=======================================================

Kaggle `kartik2112/fraud-detection` veri setini (fraudTrain.csv) okuyup
kurumsal bir masraf veri tabanı formatına dönüştürür.

Akış:
  1. CSV oku
  2. Stratified sampling (15 000 satır, %5 fraud)
  3. Kolon dönüşümleri + yeni kolonlar
  4. Gereksiz kolonları sil
  5. Final sıralama ile kaydet
  6. 500 satırlık örnek kaydet
  7. İstatistikleri yazdır

Kullanım:
  python transformer.py                          # varsayılan yollar
  python transformer.py --input path/to/file.csv  # özel yol
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
#  Sabit Eşleme Tabloları
# ─────────────────────────────────────────────────────────────────────────────

# Sparkov kategorisi → Kurumsal harcama kategorisi
CATEGORY_MAP: dict[str, str] = {
    "shopping_net":  "Yazılım & Lisans",
    "shopping_pos":  "Ofis Malzemesi",
    "travel":        "Seyahat",
    "food_dining":   "Temsil & Ağırlama",
    "gas_transport": "Ulaşım",
    "home":          "Ekipman & Donanım",
    "entertainment": "Etkinlik & Organizasyon",
    "health_fitness":"Sağlık & Spor",
    "kids_pets":     "Diğer",
    "grocery_net":   "Ofis Malzemesi",
    "grocery_pos":   "Ofis Malzemesi",
    "misc_net":      "Diğer",
    "misc_pos":      "Diğer",
    "personal_care": "Diğer",
    "lodging":       "Konaklama",
}

# job alanındaki anahtar kelime → Departman
# Önce listede eşleşen ilk kural uygulanır (sıra önemli!)
DEPT_KEYWORD_MAP: list[tuple[list[str], str]] = [
    (["software", "developer", "engineer", "data", "analyst", "it", "tech",
      "programmer", "system", "network", "database", "cyber", "devops"],  "Bilgi Teknolojileri"),
    (["sales", "account", "business development", "commercial",
      "marketing", "brand", "advertis"],                                   "Satış & Pazarlama"),
    (["accountant", "accounting", "finance", "financial", "auditor",
      "tax", "payroll", "budget", "treasurer"],                            "Finans & Muhasebe"),
    (["hr", "human resource", "recruiter", "recruiting", "talent",
      "training", "learning", "organizational"],                           "İnsan Kaynakları"),
    (["operation", "supply chain", "logistics", "procurement",
      "warehouse", "inventory", "production", "manufactur"],               "Operasyon & Lojistik"),
    (["legal", "lawyer", "attorney", "compliance", "paralegal"],           "Hukuk & Uyum"),
    (["doctor", "nurse", "physician", "health", "medical", "clinical",
      "therapist", "pharmacist"],                                          "Sağlık"),
    (["teacher", "professor", "instructor", "education", "academic",
      "librarian", "school"],                                              "Eğitim"),
    (["manager", "director", "executive", "ceo", "cfo", "cto",
      "president", "officer", "head of", "vp ", "vice president"],        "Yönetim"),
    (["design", "graphic", "ux", "ui", "creative", "artist",
      "architect", "content"],                                             "Tasarım & Kreatif"),
    (["scientist", "research", "biolog", "chemist", "physicist",
      "lab"],                                                              "Ar-Ge"),
    (["consultant", "advisor", "strateg"],                                 "Danışmanlık"),
]
DEPT_DEFAULT = "Genel"

# Nihai kolon sırası
FINAL_COLUMNS: list[str] = [
    "transaction_id",
    "expense_date",
    "employee_id",
    "employee_name",
    "department",
    "vendor",
    "expense_category",
    "amount",
    "branch_location",
    "original_fraud",
    "is_anomaly",
    "anomaly_type",
    "risk_score",
]

# Kaynak veri setinde atılacak sütunlar
DROP_COLS: list[str] = [
    "cc_num", "first", "last", "gender", "street",
    "city", "state", "zip", "lat", "long",
    "city_pop", "dob", "trans_num", "unix_time",
    "merch_lat", "merch_long",
]


# ─────────────────────────────────────────────────────────────────────────────
#  Yardımcı Fonksiyonlar
# ─────────────────────────────────────────────────────────────────────────────

def _map_department(job: str) -> str:
    """job string'ini keyword eşleşmesiyle departmana çevirir."""
    if not isinstance(job, str):
        return DEPT_DEFAULT
    job_lower = job.lower()
    for keywords, dept in DEPT_KEYWORD_MAP:
        if any(kw in job_lower for kw in keywords):
            return dept
    return DEPT_DEFAULT


def _build_employee_id_map(cc_series: pd.Series) -> dict:
    """Her unique cc_num'a sıralı EMP001, EMP002… atar."""
    unique_cards = cc_series.unique()
    return {card: f"EMP{i+1:04d}" for i, card in enumerate(sorted(unique_cards))}


def _stratified_sample(
    df: pd.DataFrame,
    total: int = 15_000,
    fraud_n: int = 750,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Stratified örnekleme:
      - is_fraud=1 → fraud_n satır
      - is_fraud=0 → (total - fraud_n) satır
    """
    normal_n = total - fraud_n

    fraud_df  = df[df["is_fraud"] == 1]
    normal_df = df[df["is_fraud"] == 0]

    # Veri seti yeterince büyük değilse tamamını al
    fraud_sample  = fraud_df.sample(
        n=min(fraud_n, len(fraud_df)),
        random_state=random_state,
    )
    normal_sample = normal_df.sample(
        n=min(normal_n, len(normal_df)),
        random_state=random_state,
    )

    sampled = pd.concat([fraud_sample, normal_sample]).sample(
        frac=1, random_state=random_state  # karıştır
    ).reset_index(drop=True)

    print(f"  [Sampling] Fraud  : {len(fraud_sample):>6,} satır")
    print(f"  [Sampling] Normal : {len(normal_sample):>6,} satır")
    print(f"  [Sampling] Toplam : {len(sampled):>6,} satır")
    return sampled


# ─────────────────────────────────────────────────────────────────────────────
#  Ana Dönüşüm Fonksiyonu
# ─────────────────────────────────────────────────────────────────────────────

def transform_sparkov_to_corporate(
    input_path: str,
    output_path: str,
    sample_size: int = 15_000,
) -> pd.DataFrame:
    """
    Sparkov ham CSV'sini kurumsal masraf formatına dönüştürür.

    Parameters
    ----------
    input_path  : str  — fraudTrain.csv'nin yolu
    output_path : str  — corporate_expenses.csv çıktı yolu
    sample_size : int  — Toplam satır sayısı (varsayılan 15 000)

    Returns
    -------
    pd.DataFrame  — Dönüştürülmüş kurumsal masraf verisi
    """
    input_path  = Path(input_path)
    output_path = Path(output_path)

    # ── 1. Veri okuma ────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  ExpenseGuard — Sparkov → Kurumsal Dönüştürücü")
    print(f"{'='*60}")
    print(f"\n[1/7] Okunuyor: {input_path}")
    if not input_path.exists():
        raise FileNotFoundError(
            f"Kaynak dosya bulunamadı: {input_path}\n"
            "Kaggle'dan fraudTrain.csv'yi data/raw/ klasörüne indirin."
        )
    raw = pd.read_csv(input_path)
    print(f"      Ham veri: {len(raw):,} satır | {raw.shape[1]} sütun")

    # ── 2. Stratified sampling ───────────────────────────────────────────
    print(f"\n[2/7] Stratified sampling ({sample_size:,} satır, %5 fraud)...")
    fraud_count  = int(sample_size * 0.05)   # 750
    df = _stratified_sample(raw, total=sample_size, fraud_n=fraud_count, random_state=42)

    # ── 3. Kolon dönüşümleri ─────────────────────────────────────────────
    print("\n[3/7] Kolon dönüşümleri uygulanıyor...")

    # transaction_id: TXN00001…
    df["transaction_id"] = [f"TXN{i+1:05d}" for i in range(len(df))]

    # expense_date
    df["expense_date"] = pd.to_datetime(df["trans_date_trans_time"])

    # employee_id: cc_num → EMP0001…
    emp_map = _build_employee_id_map(df["cc_num"])
    df["employee_id"] = df["cc_num"].map(emp_map)

    # employee_name
    df["employee_name"] = df["first"].str.strip() + " " + df["last"].str.strip()

    # department (job bazlı keyword mapping)
    df["department"] = df["job"].apply(_map_department)

    # vendor (fraud_ prefix'ini kaldır, title case)
    df["vendor"] = (
        df["merchant"]
        .str.replace(r"^fraud_", "", regex=True)
        .str.strip()
        .str.title()
    )

    # expense_category
    df["expense_category"] = df["category"].map(CATEGORY_MAP).fillna("Diğer")

    # amount (amt → amount)
    df["amount"] = df["amt"].round(2)

    # branch_location
    df["branch_location"] = df["city"].str.title() + ", " + df["state"].str.upper()

    # original_fraud (is_fraud → original_fraud)
    df["original_fraud"] = df["is_fraud"].astype(int)

    # Anomali sütunları — injector dolduracak
    df["is_anomaly"]  = False
    df["anomaly_type"] = None
    df["risk_score"]  = 0.0

    # ── 4. Gereksiz kolonları sil ─────────────────────────────────────────
    print("\n[4/7] Gereksiz kolonlar siliniyor...")
    # Kaynak sütunları da temizle
    extra_source_cols = ["trans_date_trans_time", "merchant", "category",
                         "amt", "job", "is_fraud"]
    drop_all = [c for c in DROP_COLS + extra_source_cols if c in df.columns]
    df.drop(columns=drop_all, inplace=True)

    # ── 5. Final kolon sıralaması ─────────────────────────────────────────
    print("\n[5/7] Final kolon sıralaması uygulanıyor...")
    # Beklenmedik ekstra kolonları koru (sonda)
    extra = [c for c in df.columns if c not in FINAL_COLUMNS]
    ordered = [c for c in FINAL_COLUMNS if c in df.columns] + extra
    df = df[ordered].reset_index(drop=True)

    # ── 6. Kaydet ─────────────────────────────────────────────────────────
    print(f"\n[6/7] Kaydediliyor...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"      ✓ Ana veri  → {output_path}  ({len(df):,} satır)")

    # 500 satırlık örnek
    sample_path = output_path.parent.parent / "sample" / "sample_expenses.csv"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    df.head(500).to_csv(sample_path, index=False)
    print(f"      ✓ Örnek veri → {sample_path}  (500 satır)")

    # ── 7. İstatistikler ──────────────────────────────────────────────────
    _print_stats(df)

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  İstatistik Çıktısı
# ─────────────────────────────────────────────────────────────────────────────

def _print_stats(df: pd.DataFrame) -> None:
    """Dönüşüm sonrası özet istatistikleri konsola yazar."""
    print(f"\n{'='*60}")
    print("  [7/7] Dönüşüm İstatistikleri")
    print(f"{'='*60}")

    print(f"\n  Toplam satır sayısı : {len(df):,}")
    print(f"  Toplam sütun sayısı : {df.shape[1]}")

    # Departman dağılımı
    print("\n  ── Departman Dağılımı ──────────────────────────")
    dept_dist = df["department"].value_counts()
    for dept, cnt in dept_dist.items():
        bar = "█" * int(cnt / len(df) * 30)
        print(f"  {dept:<30} {cnt:>5,}  {bar}")

    # Kategori dağılımı
    print("\n  ── Kategori Dağılımı ───────────────────────────")
    cat_dist = df["expense_category"].value_counts()
    for cat, cnt in cat_dist.items():
        bar = "█" * int(cnt / len(df) * 30)
        print(f"  {cat:<35} {cnt:>5,}  {bar}")

    # Tutar istatistikleri
    print("\n  ── Tutar İstatistikleri (USD) ──────────────────")
    amt = df["amount"]
    print(f"  Ortalama : ${amt.mean():>10,.2f}")
    print(f"  Medyan   : ${amt.median():>10,.2f}")
    print(f"  Min      : ${amt.min():>10,.2f}")
    print(f"  Max      : ${amt.max():>10,.2f}")
    print(f"  Std Dev  : ${amt.std():>10,.2f}")

    # Fraud bilgisi
    print("\n  ── Original Fraud Dağılımı ─────────────────────")
    fraud_cnt  = df["original_fraud"].sum()
    normal_cnt = len(df) - fraud_cnt
    print(f"  Fraud (1): {fraud_cnt:>6,}  (%{fraud_cnt/len(df)*100:.2f})")
    print(f"  Normal(0): {normal_cnt:>6,}  (%{normal_cnt/len(df)*100:.2f})")

    # Benzersiz çalışan ve tedarikçi
    print("\n  ── Diğer ───────────────────────────────────────")
    print(f"  Benzersiz çalışan  : {df['employee_id'].nunique():,}")
    print(f"  Benzersiz tedarikçi: {df['vendor'].nunique():,}")
    print(f"  Benzersiz lokasyon : {df['branch_location'].nunique():,}")
    print(f"\n{'='*60}\n")


# ─────────────────────────────────────────────────────────────────────────────
#  CLI — Doğrudan Çalıştırma
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ExpenseGuard — Sparkov → Kurumsal Masraf Dönüştürücüsü"
    )
    parser.add_argument(
        "--input",
        default=str(Path(__file__).resolve().parents[2] / "data" / "raw" / "fraudTrain.csv"),
        help="fraudTrain.csv yolu (varsayılan: data/raw/fraudTrain.csv)",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[2] / "data" / "processed" / "corporate_expenses.csv"),
        help="Çıktı CSV yolu (varsayılan: data/processed/corporate_expenses.csv)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=15_000,
        help="Toplam satır sayısı (varsayılan: 15000)",
    )
    args = parser.parse_args()

    result = transform_sparkov_to_corporate(
        input_path=args.input,
        output_path=args.output,
        sample_size=args.sample_size,
    )

    print(f"Tamamlandı! Döndürülen DataFrame: {result.shape[0]:,} satır × {result.shape[1]} sütun")
    sys.exit(0)
