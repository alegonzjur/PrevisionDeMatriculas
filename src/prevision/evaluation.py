"""Líneas base y evaluación de origen móvil (fase 3).

Un modelo es una función `historia -> previsión`: recibe la matrícula de una serie hasta el
origen (indexada por `year_start`, sin NaN) y devuelve la previsión del curso siguiente al
último. Así los modelos de la fase 4 se evalúan con el mismo marco.
"""

from collections.abc import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from prevision.config import (
    GBM_PARAMS,
    MA_WINDOW,
    MIN_TRAIN,
    MIN_TRAIN_EXAMPLES,
    RIDGE_ALPHA,
)
from prevision.features import FEATURE_SETS, build_examples, build_prediction_rows


def _require_history(history: pd.Series) -> None:
    if len(history) == 0:
        raise ValueError("La historia está vacía: no se puede prever.")


def naive(history: pd.Series) -> float:
    """Ingenuo: el último valor."""
    _require_history(history)
    return float(history.iloc[-1])


def drift(history: pd.Series) -> float:
    """Ingenuo con deriva: último valor más la pendiente media por curso.

    La pendiente es `(último - primero) / (año último - año primero)`, de modo que un
    curso sin dato en medio no distorsiona el cálculo. Con un solo valor devuelve ese valor.
    """
    _require_history(history)
    last = float(history.iloc[-1])
    span = history.index[-1] - history.index[0]
    if span == 0:
        return last
    return last + (last - float(history.iloc[0])) / span


def moving_average(history: pd.Series, window: int = MA_WINDOW) -> float:
    """Media de los últimos `window` cursos (todos los que haya si son menos)."""
    _require_history(history)
    return float(history.iloc[-window:].mean())


BASELINES: dict[str, Callable[[pd.Series], float]] = {
    "naive": naive,
    "drift": drift,
    "moving_average": moving_average,
}


FORECAST_COLUMNS = [
    "series_id",
    "origin_year",
    "target_year",
    "model",
    "y_true",
    "y_pred",
    "is_provisional_target",
]


def rolling_origin_forecasts(
    series: pd.DataFrame,
    models: dict[str, Callable[[pd.Series], float]] = BASELINES,
    min_train: int = MIN_TRAIN,
) -> pd.DataFrame:
    """Previsiones de origen móvil: cada origen `t` prevé el curso `t+1`.

    Un par (serie, origen) existe si `t` es un curso con matrícula informada, la historia
    hasta `t` (solo cursos con dato) tiene al menos `min_train` valores y el curso `t+1`
    tiene dato. La historia se corta por posición antes de llamar al modelo, de modo que
    ningún dato posterior a `t` puede influir en la previsión.

    Devuelve una fila por par y modelo con las columnas de `FORECAST_COLUMNS`.
    """
    rows = []
    for series_id, group in series.groupby("series_id", sort=True):
        data = group.dropna(subset=["enrolled"]).sort_values("year_start")
        years = data["year_start"].to_numpy()
        values = data["enrolled"].to_numpy(dtype=float)
        provisional = data["is_provisional"].to_numpy(dtype=bool)
        for position in range(min_train - 1, len(data) - 1):
            origin, target = years[position], years[position + 1]
            if target != origin + 1:
                continue  # el curso siguiente no tiene dato
            history = pd.Series(values[: position + 1], index=years[: position + 1])
            for name, model in models.items():
                rows.append(
                    {
                        "series_id": series_id,
                        "origin_year": int(origin),
                        "target_year": int(target),
                        "model": name,
                        "y_true": values[position + 1],
                        "y_pred": float(model(history)),
                        "is_provisional_target": bool(provisional[position + 1]),
                    }
                )
    return pd.DataFrame(rows, columns=FORECAST_COLUMNS)


# --- Modelos globales (fase 4) ---------------------------------------------------------------
# Un modelo global no recibe una serie sino todas: en cada origen `t` se ajusta con los ejemplos
# cuyo curso objetivo es `<= t` y prevé `t+1`. Predice el crecimiento logarítmico del curso
# siguiente; la previsión es `último valor * exp(predicción)`.


def make_ridge() -> Pipeline:
    """Ridge con imputación por la mediana y estandarización (ajustadas en cada entrenamiento)."""
    return Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("ridge", Ridge(alpha=RIDGE_ALPHA)),
        ]
    )


def make_gbm() -> HistGradientBoostingRegressor:
    """Gradient boosting con los hiperparámetros fijos de `config.GBM_PARAMS` (admite NaN)."""
    return HistGradientBoostingRegressor(**GBM_PARAMS)


# nombre del modelo -> (fábrica del estimador, conjunto de variables de `FEATURE_SETS`)
GLOBAL_MODELS: dict[str, tuple[Callable[[], object], str]] = {
    "ridge": (make_ridge, "base"),
    "gbm": (make_gbm, "base"),
    "ridge_region": (make_ridge, "with_region"),
    "gbm_region": (make_gbm, "with_region"),
    "ridge_no_system": (make_ridge, "without_system"),
    "gbm_no_system": (make_gbm, "without_system"),
}


def rolling_origin_global(
    series: pd.DataFrame,
    models: dict[str, tuple[Callable[[], object], str]] = GLOBAL_MODELS,
    min_train: int = MIN_TRAIN,
) -> pd.DataFrame:
    """Previsiones de origen móvil de modelos globales, sobre los mismos pares que las líneas base.

    Los pares (serie, origen) son exactamente los de `rolling_origin_forecasts`. Para cada origen
    `t` con pares, cada modelo se ajusta con `build_examples(series, up_to=t)` (solo objetivos
    `<= t`) y prevé `t+1`. Si hay menos de `MIN_TRAIN_EXAMPLES` ejemplos, o un par no tiene fila de
    variables, lanza `ValueError`: nunca se ajusta con casi nada ni se rellena con otro modelo.

    Devuelve las columnas de `FORECAST_COLUMNS`, ordenado por serie, origen y modelo.
    """
    pairs = rolling_origin_forecasts(series, models={"naive": naive}, min_train=min_train)
    rows = []
    for origin, origin_pairs in pairs.groupby("origin_year", sort=True):
        origin = int(origin)
        examples = build_examples(series, up_to=origin)
        if len(examples) < MIN_TRAIN_EXAMPLES:
            raise ValueError(
                f"Origen {origin}: {len(examples)} ejemplos de entrenamiento, "
                f"el mínimo es {MIN_TRAIN_EXAMPLES}."
            )
        prediction = build_prediction_rows(series, origin=origin).set_index("series_id")
        missing = sorted(set(origin_pairs["series_id"]) - set(prediction.index))
        if missing:
            raise ValueError(
                f"Origen {origin}: sin variables para prever las series {missing} "
                f"(¿`min_train` menor que MIN_FEATURE_HISTORY?)."
            )
        features = prediction.loc[origin_pairs["series_id"].to_numpy()]
        for name, (factory, feature_set) in models.items():
            columns = FEATURE_SETS[feature_set]
            estimator = factory()
            estimator.fit(examples[columns], examples["target"])
            growth = estimator.predict(features[columns])
            y_pred = features["last_value"].to_numpy() * np.exp(growth)
            rows.append(
                pd.DataFrame(
                    {
                        "series_id": origin_pairs["series_id"].to_numpy(),
                        "origin_year": origin,
                        "target_year": origin_pairs["target_year"].to_numpy(),
                        "model": name,
                        "y_true": origin_pairs["y_true"].to_numpy(),
                        "y_pred": y_pred,
                        "is_provisional_target": origin_pairs["is_provisional_target"].to_numpy(),
                    }
                )
            )
    if not rows:
        return pd.DataFrame(columns=FORECAST_COLUMNS)
    result = pd.concat(rows, ignore_index=True)
    result = result.sort_values(["series_id", "origin_year"], kind="stable")
    return result[FORECAST_COLUMNS].reset_index(drop=True)


METRIC_COLUMNS = ["n_pairs", "mae", "wape", "mape", "bias", "n_excluded_mape"]
VS_NAIVE_COLUMNS = ["mae_vs_naive", "wape_vs_naive", "mape_vs_naive"]
SIZE_TIER_LABELS = ["pequeño", "mediano", "grande"]


def _group_metrics(group: pd.DataFrame) -> pd.Series:
    """MAE, WAPE y MAPE de un grupo de pares (y_true, y_pred)."""
    error = (group["y_pred"] - group["y_true"]).abs()
    total = group["y_true"].sum()
    nonzero = group["y_true"] != 0
    return pd.Series(
        {
            "n_pairs": len(group),
            "mae": error.mean(),
            # WAPE: error relativo del conjunto (domina el tamaño de los centros grandes).
            "wape": error.sum() / total if total != 0 else float("nan"),
            # MAPE: error relativo medio por par (todos pesan igual); sin y_true == 0.
            "mape": (error[nonzero] / group.loc[nonzero, "y_true"]).mean()
            if nonzero.any()
            else float("nan"),
            # Sesgo: error medio con signo (positivo = sobreestima, negativo = infravalora).
            "bias": (group["y_pred"] - group["y_true"]).mean(),
            "n_excluded_mape": int((~nonzero).sum()),
        }
    )


def compute_metrics(forecasts: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    """Métricas por modelo (y por cada combinación de las columnas de `by`).

    Añade `mae_vs_naive`, `wape_vs_naive` y `mape_vs_naive`: la métrica del modelo
    dividida entre la del ingenuo del mismo grupo, menos 1 (0 para el ingenuo; NaN si no
    hay ingenuo o su métrica es 0 o NaN).
    """
    keys = list(by or [])
    columns = keys + ["model"] + METRIC_COLUMNS + VS_NAIVE_COLUMNS
    if forecasts.empty:
        return pd.DataFrame(columns=columns)

    grouped = forecasts.groupby(keys + ["model"], sort=True)
    result = grouped[["y_true", "y_pred"]].apply(_group_metrics).reset_index()

    for metric in ("mae", "wape", "mape"):
        baseline = result.loc[result["model"] == "naive", keys + [metric]]
        baseline = baseline.rename(columns={metric: "_naive"})
        if keys:
            merged = result[keys].merge(baseline, on=keys, how="left")["_naive"]
        else:
            merged = pd.Series(baseline["_naive"].iloc[0] if len(baseline) else float("nan"), index=result.index)
        merged.index = result.index
        ratio = result[metric] / merged.where(merged > 0)
        result[f"{metric}_vs_naive"] = ratio - 1
    result["n_pairs"] = result["n_pairs"].astype(int)
    result["n_excluded_mape"] = result["n_excluded_mape"].astype(int)
    return result[columns]


def metrics_report(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Métricas en total y por curso objetivo, con todos los pares y sin el provisional."""
    scopes = {
        "todos": forecasts,
        "sin_provisional": forecasts[~forecasts["is_provisional_target"]],
    }
    frames = []
    for scope, subset in scopes.items():
        total = compute_metrics(subset)
        total.insert(0, "target_year", float("nan"))
        per_year = compute_metrics(subset, by=["target_year"])
        for frame in (total, per_year):
            frame.insert(0, "scope", scope)
            frames.append(frame)
    columns = ["scope", "target_year", "model"] + METRIC_COLUMNS + VS_NAIVE_COLUMNS
    non_empty = [f for f in frames if not f.empty]
    if not non_empty:
        return pd.DataFrame(columns=columns)
    report = pd.concat(non_empty, ignore_index=True)
    report["target_year"] = report["target_year"].astype(float)
    return report[columns]


def add_size_tier(
    forecasts: pd.DataFrame, quality: pd.DataFrame, n_tiers: int = 3
) -> pd.DataFrame:
    """Añade `size_tier` (terciles de `size_last` de la tabla de calidad)."""
    labels = SIZE_TIER_LABELS if n_tiers == 3 else [str(i + 1) for i in range(n_tiers)]
    tiers = pd.qcut(quality.set_index("series_id")["size_last"], n_tiers, labels=labels)
    result = forecasts.copy()
    result["size_tier"] = result["series_id"].map(tiers.astype(object))
    return result


def compare_to_naive(forecasts: pd.DataFrame, model: str) -> pd.Series:
    """En cuántos pares y series un modelo tiene menos error absoluto que el ingenuo.

    Devuelve `n_pairs`, `share_pairs_better` (fracción de pares con menor error),
    `share_pairs_equal`, `n_series` y `n_series_better` (series cuyo MAE es menor que el
    del ingenuo). Sirve para ver si una mejora agregada la sostienen muchos centros o
    unos pocos grandes.
    """
    errors = (forecasts["y_pred"] - forecasts["y_true"]).abs()
    table = errors.groupby(
        [forecasts["series_id"], forecasts["origin_year"], forecasts["model"]]
    ).first().unstack("model")
    by_series = table.groupby("series_id").mean()
    return pd.Series(
        {
            "n_pairs": len(table),
            "share_pairs_better": (table[model] < table["naive"]).mean(),
            "share_pairs_equal": (table[model] == table["naive"]).mean(),
            "n_series": len(by_series),
            "n_series_better": int((by_series[model] < by_series["naive"]).sum()),
        }
    )
