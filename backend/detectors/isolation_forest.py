"""
ExpenseGuard — Isolation Forest Dedektörü

scikit-learn IsolationForest modelini sarmalar.
Hem fit() hem de predict() destekler; skor [0,1] aralığına normalize edilir.
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler

from config import ml as cfg


class IsolationForestDetector:
    """Isolation Forest tabanlı anomali dedektörü."""

    def __init__(self):
        self.model = IsolationForest(
            n_estimators=cfg.IF_N_ESTIMATORS,
            contamination=cfg.IF_CONTAMINATION,
            max_samples=cfg.IF_MAX_SAMPLES,
            random_state=cfg.IF_RANDOM_STATE,
            n_jobs=-1,
        )
        self.scaler = MinMaxScaler()
        self._fitted = False

    # ------------------------------------------------------------------ #
    #  Eğitim                                                             #
    # ------------------------------------------------------------------ #
    def fit(self, X: np.ndarray) -> "IsolationForestDetector":
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self._fitted = True
        return self

    # ------------------------------------------------------------------ #
    #  Tahmin                                                              #
    # ------------------------------------------------------------------ #
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Returns
        -------
        labels : np.ndarray of int  (1=normal, -1=anomali → 0/1 binary)
        """
        self._check_fitted()
        X_scaled = self.scaler.transform(X)
        labels = self.model.predict(X_scaled)           # 1 veya -1
        return np.where(labels == -1, 1, 0)             # 1 → anomali

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        """
        Ham anomali skorlarını [0,1] aralığına çevirir.
        Yüksek skor → daha anomalik.
        """
        self._check_fitted()
        X_scaled  = self.scaler.transform(X)
        raw       = self.model.score_samples(X_scaled)  # negatif değerler
        # Tersini alıp normalize et
        inverted  = -raw
        normalized = (inverted - inverted.min()) / (inverted.max() - inverted.min() + 1e-9)
        return normalized

    def fit_predict(self, X: np.ndarray):
        self.fit(X)
        return self.predict(X), self.score_samples(X)

    def _check_fitted(self):
        if not self._fitted:
            raise RuntimeError("Model henüz eğitilmedi. Önce fit() çağırın.")
