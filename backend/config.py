# -*- coding: utf-8 -*-
"""
ExpenseGuard - Global Konfigurasyon & Esik Degerleri
Tum detector parametreleri ve is kurallari buradan yonetilir.
"""
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class RuleConfig:
    # Tutar esikleri (USD)
    SINGLE_TXN_LIMIT: float = 5_000.0
    APPROVAL_BYPASS_WINDOW: float = 4_999.0
    DAILY_EMPLOYEE_LIMIT: float = 10_000.0

    # Cift fatura tespiti
    DUPLICATE_WINDOW_HOURS: int = 80
    DUPLICATE_AMOUNT_TOLERANCE: float = 0.025   # %2.5 tolerans

    # Zaman anomalisi
    WEEKEND_FLAG: bool = True
    NIGHT_HOURS_START: int = 22
    NIGHT_HOURS_END: int = 6

    # Departman-kategori eslesme kurallari
    # *** transformer.py'nin urettigi departman isimleriyle eslestirildi ***
    DEPT_CATEGORY_WHITELIST: Dict[str, List[str]] = field(default_factory=lambda: {
        "Bilgi Teknolojileri": [
            "Yazılım & Lisans", "Ekipman & Donanım", "Ofis Malzemesi",
            "Diğer", "Sağlık & Spor", "Etkinlik & Organizasyon",
        ],
        "Satış & Pazarlama": [
            "Seyahat", "Konaklama", "Temsil & Ağırlama", "Ulaşım",
            "Ofis Malzemesi", "Etkinlik & Organizasyon", "Diğer",
        ],
        "Finans & Muhasebe": [
            "Ofis Malzemesi", "Yazılım & Lisans", "Diğer",
        ],
        "İnsan Kaynakları": [
            "Etkinlik & Organizasyon", "Ofis Malzemesi", "Diğer",
        ],
        "Operasyon & Lojistik": [
            "Ekipman & Donanım", "Ulaşım", "Ofis Malzemesi", "Diğer",
        ],
        "Yönetim": [
            "Seyahat", "Konaklama", "Temsil & Ağırlama",
            "Yazılım & Lisans", "Ofis Malzemesi", "Diğer",
            "Etkinlik & Organizasyon", "Ulaşım",
        ],
        "Sağlık": [
            "Sağlık & Spor", "Ekipman & Donanım", "Ofis Malzemesi", "Diğer",
        ],
        "Eğitim": [
            "Ofis Malzemesi", "Yazılım & Lisans", "Diğer",
            "Ekipman & Donanım",
        ],
        "Ar-Ge": [
            "Ekipman & Donanım", "Yazılım & Lisans", "Ofis Malzemesi", "Diğer",
        ],
        "Tasarım & Kreatif": [
            "Yazılım & Lisans", "Ekipman & Donanım", "Ofis Malzemesi", "Diğer",
        ],
        "Danışmanlık": [
            "Seyahat", "Konaklama", "Temsil & Ağırlama", "Ofis Malzemesi", "Diğer",
        ],
        "Hukuk & Uyum": [
            "Ofis Malzemesi", "Yazılım & Lisans", "Diğer",
        ],
        "Genel": [
            "Ofis Malzemesi", "Diğer",
        ],
    })


@dataclass
class MLConfig:
    # Isolation Forest
    IF_N_ESTIMATORS: int = 300
    IF_CONTAMINATION: float = 0.08
    IF_MAX_SAMPLES: str = "auto"
    IF_RANDOM_STATE: int = 42

    # Local Outlier Factor
    LOF_N_NEIGHBORS: int = 10
    LOF_CONTAMINATION: float = 0.07
    LOF_ALGORITHM: str = "auto"
    LOF_METRIC: str = "euclidean"

    # Ensemble agirliklari
    ENSEMBLE_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        "isolation_forest": 0.30,
        "lof":              0.25,
        "rule_based":       0.45,
    })
    ANOMALY_SCORE_THRESHOLD: float = 0.0     # Otomatik threshold kullanilacak


@dataclass
class DataConfig:
    RAW_DATA_PATH: str = "data/raw/fraudTrain.csv"
    PROCESSED_DATA_PATH: str = "data/processed/corporate_expenses.csv"
    SAMPLE_DATA_PATH: str = "data/sample/sample_expenses.csv"
    SAMPLE_SIZE: int = 500


# Singleton
rules = RuleConfig()
ml = MLConfig()
data = DataConfig()
