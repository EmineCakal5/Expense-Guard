"""
ExpenseGuard — Transformer Tests
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import pytest
from pipeline.transformer import SparkovTransformer


MOCK_SPARKOV = pd.DataFrame({
    "trans_date_trans_time": ["2020-06-01 12:00:00", "2020-06-02 08:30:00"],
    "cc_num":    [1234567890123456, 9876543210987654],
    "merchant":  ["fraud_Coffee Shop", "Grocery Mart"],
    "category":  ["food_dining", "grocery_pos"],
    "amt":       [45.50, 120.00],
    "first":     ["Ahmet", "Zeynep"],
    "last":      ["Yılmaz", "Demir"],
    "gender":    ["M", "F"],
    "city":      ["ankara", "istanbul"],
    "state":     ["AN", "IS"],
    "lat":       [39.9, 41.0],
    "long":      [32.8, 28.9],
    "is_fraud":  [0, 1],
})


def test_transform_returns_dataframe():
    t = SparkovTransformer()
    result = t.transform(MOCK_SPARKOV)
    assert isinstance(result, pd.DataFrame)


def test_transform_has_required_columns():
    t = SparkovTransformer()
    result = t.transform(MOCK_SPARKOV)
    required = [
        "expense_id", "employee_id", "employee_name", "department",
        "category", "vendor", "amount", "currency",
        "transaction_date", "submission_date",
        "city", "country", "is_fraud_original",
    ]
    for col in required:
        assert col in result.columns, f"Eksik sütun: {col}"


def test_transform_row_count():
    t = SparkovTransformer()
    result = t.transform(MOCK_SPARKOV)
    assert len(result) == len(MOCK_SPARKOV)


def test_transform_category_mapping():
    t = SparkovTransformer()
    result = t.transform(MOCK_SPARKOV)
    assert result["category"].iloc[0] == "Temsil"    # food_dining → Temsil
    assert result["category"].iloc[1] == "Ofis Malzemesi"  # grocery_pos


def test_transform_vendor_cleanup():
    t = SparkovTransformer()
    result = t.transform(MOCK_SPARKOV)
    assert "fraud_" not in result["vendor"].iloc[0]


def test_transform_currency_usd():
    t = SparkovTransformer()
    result = t.transform(MOCK_SPARKOV)
    assert (result["currency"] == "USD").all()
