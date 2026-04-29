"""
ExpenseGuard — Detector Tests
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
import pytest
from detectors.rule_based import RuleBasedDetector
from detectors.isolation_forest import IsolationForestDetector
from detectors.lof_detector import LOFDetector


# ---------------------------------------- #
#  Basit test verisi                        #
# ---------------------------------------- #
def make_sample_df(n=100):
    rng = np.random.default_rng(0)
    depts = ["IT", "Satış", "Muhasebe", "İnsan Kaynakları", "Operasyon", "Yönetim"]
    cats  = ["Yazılım", "Seyahat", "Ofis Malzemesi", "Eğitim", "Temsil"]
    dates = pd.date_range("2020-01-01", periods=n, freq="h")
    return pd.DataFrame({
        "expense_id":       [f"EXP-{i:06d}" for i in range(n)],
        "employee_id":      [f"EMP-{i % 10:04d}" for i in range(n)],
        "employee_name":    ["Test User"] * n,
        "department":       rng.choice(depts, n),
        "category":         rng.choice(cats, n),
        "vendor":           [f"Vendor {i % 20}" for i in range(n)],
        "amount":           rng.uniform(50, 6000, n).round(2),
        "currency":         ["USD"] * n,
        "transaction_date": dates,
        "submission_date":  dates + pd.Timedelta(days=2),
        "cost_center":      ["CC-IT-01"] * n,
        "project_code":     ["PRJ-0001"] * n,
        "city":             ["Ankara"] * n,
        "country":          ["USA"] * n,
        "is_fraud_original": rng.integers(0, 2, n),
        "is_anomaly":       [0] * n,
        "anomaly_types":    [""] * n,
        "anomaly_score":    [0.0] * n,
    })


# ---------------------------------------- #
#  Kural Tabanlı Testler                   #
# ---------------------------------------- #
class TestRuleBasedDetector:
    def test_returns_dataframe(self):
        df = make_sample_df()
        det = RuleBasedDetector()
        result = det.predict(df)
        assert isinstance(result, pd.DataFrame)

    def test_has_rule_columns(self):
        df = make_sample_df()
        det = RuleBasedDetector()
        result = det.predict(df)
        for col in ["rule_flag", "rule_score", "rule_duplicate",
                    "rule_unauthorized", "rule_threshold",
                    "rule_off_hours", "rule_daily_limit"]:
            assert col in result.columns

    def test_rule_score_range(self):
        df = make_sample_df()
        det = RuleBasedDetector()
        result = det.predict(df)
        assert result["rule_score"].between(0, 1).all()

    def test_threshold_bypass_flag(self):
        """4799 USD tutarı threshold bypass olarak işaretlenmeli."""
        df = make_sample_df(10)
        df["amount"] = 4850.0
        det = RuleBasedDetector()
        result = det.predict(df)
        assert result["rule_threshold"].sum() > 0


# ---------------------------------------- #
#  Isolation Forest Testler                #
# ---------------------------------------- #
class TestIsolationForestDetector:
    def _get_X(self, n=200):
        rng = np.random.default_rng(42)
        return rng.standard_normal((n, 10))

    def test_fit_predict_returns_binary(self):
        X = self._get_X()
        det = IsolationForestDetector()
        labels, scores = det.fit_predict(X)
        assert set(np.unique(labels)).issubset({0, 1})

    def test_scores_in_range(self):
        X = self._get_X()
        det = IsolationForestDetector()
        _, scores = det.fit_predict(X)
        assert np.all(scores >= 0) and np.all(scores <= 1)

    def test_unfitted_raises(self):
        det = IsolationForestDetector()
        with pytest.raises(RuntimeError):
            det.predict(np.zeros((5, 5)))


# ---------------------------------------- #
#  LOF Testler                             #
# ---------------------------------------- #
class TestLOFDetector:
    def _get_X(self, n=200):
        rng = np.random.default_rng(42)
        return rng.standard_normal((n, 10))

    def test_fit_predict_shape(self):
        X = self._get_X()
        det = LOFDetector()
        labels, scores = det.fit_predict(X)
        assert len(labels) == len(X)
        assert len(scores) == len(X)

    def test_labels_binary(self):
        X = self._get_X()
        det = LOFDetector()
        labels, _ = det.fit_predict(X)
        assert set(np.unique(labels)).issubset({0, 1})

    def test_scores_normalized(self):
        X = self._get_X()
        det = LOFDetector()
        _, scores = det.fit_predict(X)
        assert scores.min() >= 0.0
        assert scores.max() <= 1.0
