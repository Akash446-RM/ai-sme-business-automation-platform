"""Feature engineering tests, with an explicit guard against data leakage."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ml.features import (
    add_calendar_features,
    add_lag_features,
    build_demand_features,
    build_sales_features,
    chronological_split,
)

pytestmark = pytest.mark.ml


@pytest.fixture()
def daily_sales() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=400, freq="D")
    rng = np.random.default_rng(7)
    revenue = 1000 + np.arange(400) * 2 + rng.normal(0, 50, 400)
    return pd.DataFrame(
        {
            "date": dates,
            "revenue": revenue,
            "transactions": rng.integers(10, 40, 400),
            "units": rng.integers(20, 90, 400),
            "discount": rng.random(400) * 10,
        }
    )


@pytest.fixture()
def product_demand() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=200, freq="D")
    rng = np.random.default_rng(11)
    rows = []
    for product_id in (1, 2, 3):
        for offset, day in enumerate(dates):
            rows.append(
                {
                    "date": day,
                    "product_id": product_id,
                    "units": int(max(0, rng.poisson(2 + product_id))),
                    "revenue": float(rng.random() * 100),
                    "avg_price": 100.0 + product_id,
                    "category": "Electronics" if product_id < 3 else "Grocery",
                    "selling_price": 120.0 + product_id,
                    "cost_price": 80.0 + product_id,
                }
            )
    return pd.DataFrame(rows)


def test_calendar_features_are_correct() -> None:
    frame = pd.DataFrame({"date": [pd.Timestamp("2024-03-16")]})  # a Saturday
    result = add_calendar_features(frame)
    assert result.loc[0, "day_of_week"] == 5
    assert result.loc[0, "is_weekend"] == 1
    assert result.loc[0, "month"] == 3
    assert result.loc[0, "quarter"] == 1


def test_lag_features_use_only_past_values() -> None:
    frame = pd.DataFrame(
        {"date": pd.date_range("2024-01-01", periods=5), "value": [10, 20, 30, 40, 50]}
    )
    result = add_lag_features(frame, "value", lags=(1, 2), windows=(2,))
    assert pd.isna(result.loc[0, "value_lag_1"])
    assert result.loc[1, "value_lag_1"] == 10
    assert result.loc[4, "value_lag_2"] == 30


def test_rolling_mean_excludes_the_current_row() -> None:
    """The critical leakage guard: a rolling window must not see today."""
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=6),
            "value": [10.0, 20.0, 30.0, 40.0, 50.0, 1000.0],
        }
    )
    result = add_lag_features(frame, "value", lags=(1,), windows=(3,))
    # Row 5 has an extreme value; its own rolling mean must be unaffected by it.
    expected = np.mean([30.0, 40.0, 50.0])
    assert result.loc[5, "value_roll_mean_3"] == pytest.approx(expected)
    assert result.loc[5, "value_roll_mean_3"] < 100


def test_no_feature_correlates_perfectly_with_target(daily_sales) -> None:
    """A perfect correlation would indicate the target leaked into a feature."""
    frame, features = build_sales_features(daily_sales)
    target = frame["revenue"]
    for column in features:
        series = frame[column]
        if series.nunique() <= 1:
            continue
        correlation = abs(np.corrcoef(series.astype(float), target)[0, 1])
        assert correlation < 0.999, f"feature '{column}' appears to leak the target"


def test_target_column_is_not_a_feature(daily_sales) -> None:
    _, features = build_sales_features(daily_sales)
    assert "revenue" not in features
    assert "units" not in features
    assert "transactions" not in features


def test_demand_features_are_grouped_per_product(product_demand) -> None:
    frame, features = build_demand_features(product_demand)
    assert "units" not in features
    # The raw product id is intentionally excluded: an arbitrary integer carries
    # no order, the product's own lags already encode its demand level, and
    # leaving it out lets the model generalise to newly added products.
    assert "product_id" not in features

    # Lags must be computed within a product, never across products.
    ordered = product_demand[product_demand["product_id"] == 2].sort_values("date")
    subset = frame[frame["product_id"] == 2].sort_values("date")
    sample = subset.iloc[10]
    previous_day = sample["date"] - pd.Timedelta(days=1)
    expected = ordered.loc[ordered["date"] == previous_day, "units"].iloc[0]
    assert sample["units_lag_1"] == expected


def test_chronological_split_is_ordered_in_time(daily_sales) -> None:
    frame, _ = build_sales_features(daily_sales)
    train, validation, test = chronological_split(
        frame, test_days=30, validation_days=30
    )
    assert train["date"].max() < validation["date"].min()
    assert validation["date"].max() < test["date"].min()
    assert len(train) > len(test)


def test_split_never_mixes_future_into_training(daily_sales) -> None:
    frame, _ = build_sales_features(daily_sales)
    train, _, test = chronological_split(frame, test_days=30, validation_days=30)
    assert set(train["date"]).isdisjoint(set(test["date"]))
    assert train["date"].max() < test["date"].min()
