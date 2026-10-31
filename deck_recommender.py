"""Analiza el metajuego de varios formatos y recomienda mazos para comprar."""

from __future__ import annotations

import argparse
import math
import re
from io import StringIO
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup


FORMAT_URLS = {
    "standard": "https://mtgdecks.net/Standard/metagame:last-30-days",
    "pioneer": "https://mtgdecks.net/Pioneer/metagame:last-30-days",
    "modern": "https://mtgdecks.net/Modern/metagame:last-30-days",
    "pauper": "https://mtgdecks.net/Pauper/metagame:last-30-days",
    "premodern": "https://mtgdecks.net/Premodern/metagame:last-30-days",
}
BEST_WEIGHTS = {
    "price_score": 0.30,
    "conversion_score": 0.35,
    "winrate_score": 0.30,
    "trend_score": 0.05,
}
CHEAP_WEIGHTS = {
        "price_score": 0.80,
        "conversion_score": 0.10,
        "winrate_score": 0.05,
        "trend_score": 0.05,
}
WEIGHTS = BEST_WEIGHTS
FORMAT_WEIGHTS = {"standard": CHEAP_WEIGHTS}


def parse_number(value: str | None) -> float | None:
    """Convierte un porcentaje, multiplicador o precio en un número."""
    if not value:
        return None
    normalized = value.strip().replace(",", ".")
    if normalized in {"", "-", "—", "NA"}:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", normalized)
    return float(match.group()) if match else None


def parse_price(cell: Any, price_class: str) -> float | None:
    """Extrae el precio de una modalidad concreta del HTML."""
    price = cell.select_one(f"span.{price_class}")
    return parse_number(price.get_text(" ", strip=True) if price else None)


def parse_decks(html: str) -> pd.DataFrame:
    """Extrae todas las filas del dataframe publicado por MTGDecks."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table#allArchetypes")
    if table is None:
        raise ValueError("No se encontró la tabla de arquetipos de MTGDecks.")

    rows: list[dict[str, Any]] = []
    for row in table.select("tbody tr"):
        cells = row.select("td")
        if len(cells) < 9:
            continue

        name_node = row.select_one("strong[name]")
        meta_node = row.select_one("td.meta .meta-share.hidden-xs")
        if meta_node is None:
            meta_node = row.select_one("td.meta .meta-share")
        metric_text = [cell.get_text(" ", strip=True) for cell in cells]
        tier = metric_text[4] or None

        rows.append(
            {
                "name": name_node.get("name") if name_node else metric_text[1],
                "meta_share_pct": parse_number(meta_node.get_text(strip=True) if meta_node else None),
                "trend_pct": parse_number(metric_text[3]),
                "tier": tier,
                "winrate_pct": parse_number(metric_text[5]),
                "top25_conversion": parse_number(metric_text[6]),
                "decks": parse_number(metric_text[7]),
                "paper_price_usd": parse_price(cells[8], "paper"),
                "mtgo_price_usd": parse_price(cells[8], "mtgo"),
            }
        )

    if not rows:
        raise ValueError("La tabla no contiene filas de mazos.")
    return pd.DataFrame(rows).convert_dtypes()


def normalize_series(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """Normaliza una métrica entre 1 y 10 mediante interpolación lineal."""
    minimum = series.min()
    maximum = series.max()
    if minimum == maximum:
        return pd.Series(5.0, index=series.index)
    ratio = (series - minimum) / (maximum - minimum)
    if not higher_is_better:
        ratio = 1 - ratio
    return 1 + ratio * 9


def relative_price_score(prices: pd.Series) -> tuple[pd.Series, float]:
    """Puntúa el precio respecto a la mediana: mediana=5, con límites 1..10."""
    median = float(prices.median())
    scores = 5 - 4 * prices.map(lambda price: math.log2(price / median))
    return scores.clip(lower=1, upper=10), median


def calculate_ivc(
    dataframe: pd.DataFrame,
    tiers: set[str] | None = None,
    format_name: str | None = None,
    weights: dict[str, float] | None = None,
) -> tuple[pd.DataFrame, float]:
    """Filtra los datos válidos y calcula las puntuaciones y el IVC."""
    required = ["winrate_pct", "top25_conversion", "paper_price_usd"]
    valid_mask = (
        (dataframe["name"].str.lower() != "rogue")
        & dataframe[required].notna().all(axis=1)
        & (dataframe["paper_price_usd"] > 0)
    )
    if tiers is not None:
        valid_mask &= dataframe["tier"].isin(tiers)
    valid = dataframe[valid_mask].copy()
    if valid.empty:
        raise ValueError("No hay mazos con precio Paper, winrate y conversión válidos.")

    valid["price_score"], median_price = relative_price_score(valid["paper_price_usd"])
    valid["conversion_score"] = normalize_series(valid["top25_conversion"])
    valid["winrate_score"] = normalize_series(valid["winrate_pct"])
    valid["trend_score"] = normalize_series(valid["trend_pct"].fillna(0))
    selected_weights = weights or FORMAT_WEIGHTS.get(format_name, WEIGHTS)
    valid["ivc"] = sum(valid[column] * weight for column, weight in selected_weights.items())
    valid = valid.sort_values(["ivc", "paper_price_usd"], ascending=[False, True]).reset_index(drop=True)
    return valid, median_price


def select_recommendation(dataframe: pd.DataFrame) -> pd.Series:
    """Elige siempre el mazo con el IVC más alto."""
    return dataframe.sort_values(["ivc", "paper_price_usd"], ascending=[False, True]).iloc[0]


def select_second_recommendation(dataframe: pd.DataFrame, first: pd.Series) -> pd.Series | None:
    """Elige la siguiente alternativa del ranking, excluyendo la primera."""
    alternatives = dataframe[dataframe["name"] != first["name"]]
    if alternatives.empty:
        return None
    return alternatives.sort_values(["ivc", "paper_price_usd"], ascending=[False, True]).iloc[0]


def dataframe_markdown(dataframe: pd.DataFrame, columns: list[str]) -> str:
    """Convierte columnas del dataframe a una tabla Markdown legible."""
    display = dataframe[columns].astype(object).copy()
    display = display.where(display.notna(), "—")
    return display.to_markdown(index=False, floatfmt=".2f")


def build_markdown_report(
    format_name: str,
    raw: pd.DataFrame,
    scored: pd.DataFrame,
    median_price: float,
    weights: dict[str, float] | None = None,
) -> str:
    """Genera el informe Markdown de un formato."""
    recommendation = select_recommendation(scored)
    second_recommendation = select_second_recommendation(scored, recommendation)
    selected_weights = weights or FORMAT_WEIGHTS.get(format_name, WEIGHTS)
    weight_summary = (
        f"precio {selected_weights['price_score']:.0%}, "
        f"conversión Top 25% {selected_weights['conversion_score']:.0%}, "
        f"winrate {selected_weights['winrate_score']:.0%}, "
        f"trend {selected_weights['trend_score']:.0%}"
    )
    second_name = second_recommendation["name"] if second_recommendation is not None else "No disponible"
    second_details = ""
    if second_recommendation is not None:
        second_details = f"""- IVC: **{second_recommendation['ivc']:.2f}**
- Precio Paper: **${second_recommendation['paper_price_usd']:.2f}**
- Winrate: **{second_recommendation['winrate_pct']:.0f}%**
- Conversión Top 25%: **{second_recommendation['top25_conversion']:.2f}x**
- Trend: **{second_recommendation['trend_pct']:+.2f}%**
"""
    raw_columns = [
        "name", "meta_share_pct", "trend_pct", "tier", "winrate_pct",
        "top25_conversion", "decks", "paper_price_usd", "mtgo_price_usd",
    ]
    scored_columns = [
        "name", "tier", "decks", "paper_price_usd", "winrate_pct",
        "top25_conversion", "trend_pct", "price_score", "conversion_score",
        "winrate_score", "trend_score", "ivc",
    ]
    warning = ""
    if recommendation["decks"] < 10:
        warning = (
            f"\n> Advertencia: este arquetipo solo tiene {int(recommendation['decks'])} listas "
            "registradas; su IVC es menos confiable.\n"
        )

    return f"""## {format_name.title()}

### Resumen

- Mazos extraídos: {len(raw)}
- Mazos válidos incluidos: {len(scored)}
- Precio Paper mediano: ${median_price:.2f}
- Ponderación: {weight_summary}

### Recomendación

**{recommendation['name']}**

- IVC: **{recommendation['ivc']:.2f}**
- Precio Paper: **${recommendation['paper_price_usd']:.2f}**
- Winrate: **{recommendation['winrate_pct']:.0f}%**
- Conversión Top 25%: **{recommendation['top25_conversion']:.2f}x**
- Trend: **{recommendation['trend_pct']:+.2f}%**
{warning}
### Segunda recomendación

**{second_name}**
{second_details}

### Ranking completo

{dataframe_markdown(scored, scored_columns)}

### Datos extraídos

{dataframe_markdown(raw, raw_columns)}
"""


def fetch_html(url: str) -> str:
    """Descarga la página con una identificación básica del cliente."""
    response = requests.get(
        url,
        headers={"User-Agent": "deck-recommender/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def print_report(
    format_name: str,
    raw: pd.DataFrame,
    scored: pd.DataFrame,
    median_price: float,
    top: int,
) -> None:
    """Muestra el dataframe extraído y el ranking calculado."""
    recommendation = select_recommendation(scored)
    second_recommendation = select_second_recommendation(scored, recommendation)
    print(f"\n=== {format_name.title()} ===")
    print(f"Mazos extraídos: {len(raw)}")
    print(f"Mazos válidos incluidos para el IVC: {len(scored)}")
    print(f"Precio Paper mediano: ${median_price:.2f}")
    print("\nRecomendación principal:")
    print(
        f"  {recommendation['name']} | IVC {recommendation['ivc']:.2f} | "
        f"Paper ${recommendation['paper_price_usd']:.2f} | "
        f"Winrate {recommendation['winrate_pct']:.0f}% | "
        f"Top 25% {recommendation['top25_conversion']:.2f}x"
    )
    second_name = second_recommendation["name"] if second_recommendation is not None else "No disponible"
    print("\nSegunda recomendación:")
    print(f"  {second_name}")
    if second_recommendation is not None:
        print(
            f"  IVC {second_recommendation['ivc']:.2f} | "
            f"Paper ${second_recommendation['paper_price_usd']:.2f} | "
            f"Winrate {second_recommendation['winrate_pct']:.0f}% | "
            f"Top 25% {second_recommendation['top25_conversion']:.2f}x | "
            f"Trend {second_recommendation['trend_pct']:+.2f}%"
        )
    if recommendation["decks"] < 10:
        print(
            f"  Advertencia: este arquetipo solo tiene {int(recommendation['decks'])} listas; "
            "su IVC es menos confiable que el de mazos con más resultados."
        )
    print("\nRanking:")
    columns = [
        "name", "tier", "paper_price_usd", "winrate_pct", "top25_conversion",
        "trend_pct", "price_score", "conversion_score", "winrate_score", "trend_score", "ivc",
    ]
    display = scored[columns].head(top).copy()
    print(display.to_string(index=False, float_format=lambda value: f"{value:.2f}"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Recomienda mazos en los cinco formatos disponibles.")
    profile_group = parser.add_mutually_exclusive_group()
    profile_group.add_argument(
        "--cheap",
        action="store_true",
        help="Aplica la ponderación orientada al precio a todos los formatos.",
    )
    profile_group.add_argument(
        "--best",
        action="store_true",
        help="Aplica la ponderación orientada al rendimiento a todos los formatos.",
    )
    args = parser.parse_args()

    profile_weights = CHEAP_WEIGHTS if args.cheap else BEST_WEIGHTS if args.best else None
    selected_tiers = {"A"}
    formats = list(FORMAT_URLS)
    reports: list[str] = []
    for format_name in formats:
        url = FORMAT_URLS[format_name]
        analysis_output = f"deck_analysis_{format_name}.csv"
        raw_output = f"deck_data_{format_name}.csv"

        raw = parse_decks(fetch_html(url))
        raw.insert(0, "format", format_name)
        scored, median_price = calculate_ivc(raw, selected_tiers, format_name, profile_weights)
        raw.to_csv(raw_output, index=False)
        scored.to_csv(analysis_output, index=False)
        print_report(format_name, raw, scored, median_price, 10)
        print(f"Datos originales guardados en: {raw_output}")
        print(f"Análisis guardado en: {analysis_output}")
        reports.append(build_markdown_report(format_name, raw, scored, median_price, profile_weights))

    report_output = "deck_recommendations.md"
    report_header = "# Recomendaciones de mazos\n\nPeriodo: últimos 30 días\n\n"
    with open(report_output, "w", encoding="utf-8") as report_file:
        report_file.write(report_header + "\n".join(reports))
    print(f"Informe Markdown guardado en: {report_output}")


if __name__ == "__main__":
    main()
