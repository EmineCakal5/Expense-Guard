"""
ExpenseGuard — Local Outlier Factor Dedektörü

scikit-learn LocalOutlierFactor modelini sarmalar.
LOF büyük veri setlerinde yavaşlayabileceği için varsayılan olarak
novelty=False modunda (fit içinde tahmin) kullanılır.
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import MinMaxScaler

from config import ml as cfg


class LOFDetector:
    """Local Outlier Factor tabanlı anomali dedektörü."""

    def __init__(self):
        self.model = LocalOutlierFactor(
            n_neighbors=cfg.LOF_N_NEIGHBORS,
            contamination=cfg.LOF_CONTAMINATION,
            algorithm=cfg.LOF_ALGORITHM,
            metric=cfg.LOF_METRIC,
            n_jobs=-1,
        )
        self.scaler = MinMaxScaler()
        self._labels: np.ndarray | None = None
        self._scores: np.ndarray | None = None

    # ------------------------------------------------------------------ #
    #  LOF: fit + predict birlikte çalışır (novelty=False)                #
    # ------------------------------------------------------------------ #
    def fit_predict(self, X: np.ndarray):
        """
        Returns
        -------
        labels : np.ndarray — 0/1 (1=anomali)
        scores : np.ndarray — [0,1] normalize anomali skoru
        """
        X_scaled = self.scaler.fit_transform(X)
        raw_labels = self.model.fit_predict(X_scaled)   # 1=normal, -1=anomali
        self._labels = np.where(raw_labels == -1, 1, 0)

        # negative_outlier_factor_ : negatif, daha negatif → daha anomalik
        lof_scores = -self.model.negative_outlier_factor_
        min_s, max_s = lof_scores.min(), lof_scores.max()
        self._scores = (lof_scores - min_s) / (max_s - min_s + 1e-9)

        return self._labels, self._scores

    @property
    def labels(self) -> np.ndarray:
        if self._labels is None:
            raise RuntimeError("fit_predict() çağrılmadı.")
        return self._labels

    @property
    def scores(self) -> np.ndarray:
        if self._scores is None:
            raise RuntimeError("fit_predict() çağrılmadı.")
        return self._scores
