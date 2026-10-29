# Contexto del Agente

## Propósito

Este proyecto recomienda mazos de Magic: The Gathering usando datos actuales de MTGDecks. El punto de entrada es `deck_recommender.py`.

## Fuente de datos

El script descarga en vivo el metajuego de los últimos 30 días para estos formatos:

- Standard
- Pioneer
- Modern
- Pauper
- Premodern

El precio utilizado para el cálculo es siempre `Paper`. El precio `MTGO` se conserva únicamente como dato informativo. La tabla esperada es `table#allArchetypes`.

## Argumentos y alcance

- Sin argumentos se analiza `Standard`, con tier A y los 10 primeros puestos en la salida de terminal.
- `--format` selecciona un único formato.
- `--all` analiza todos los formatos disponibles.
- `--url` sustituye la URL del análisis individual y no se puede combinar con `--all`.
- `--top` limita únicamente el ranking mostrado en terminal; el informe Markdown conserva el ranking completo.
- `--output`, `--raw-output` y `--report-output` personalizan las salidas de un único formato.
- Las salidas personalizadas y `--url` no se pueden combinar con `--all`.

## Reglas de filtrado

- Por defecto se incluye únicamente el tier A.
- `--tiers 1` incluye A, `--tiers 2` incluye A+B y `--tiers 3` incluye A+B+C.
- `--tiers all` no aplica filtro de tier e incluye todos los valores publicados.
- Se excluye el arquetipo `Rogue`.
- Se excluyen filas sin winrate, conversión Top 25% o precio `Paper` válido y positivo.
- Los mazos con pocas listas pueden aparecer, pero el informe advierte cuando la recomendación tiene menos de 10 listas.

## Cálculo del IVC

```text
IVC = puntuación de precio * 0.30
    + puntuación de conversión Top 25% * 0.35
    + puntuación de winrate * 0.25
    + puntuación de trend * 0.10
```

Todas las métricas se normalizan entre 1 y 10. La puntuación del precio usa la mediana de los precios `Paper` válidos, no la media aritmética. La mediana recibe 5 puntos, los precios más bajos obtienen mejor puntuación y el resultado queda limitado entre 1 y 10.

Las ponderaciones del IVC son: precio 30%, conversión Top 25% 35%, winrate 25% y trend 10%.

La primera recomendación siempre es el mazo con el IVC más alto. Los empates se resuelven con el precio `Paper` más bajo. La segunda recomendación es el siguiente mazo distinto del ranking y se muestra con sus métricas principales.

## Archivos generados

- `deck_data_<format>.csv`: todas las filas extraídas, con una columna `format` añadida.
- `deck_analysis_<format>.csv`: filas válidas con puntuaciones e IVC.
- `deck_recommendations_<format>.md`: informe del formato, con recomendaciones y ranking completo.
- `deck_recommendations.md`: informe combinado cuando se usa `--all`.

Los archivos generados están excluidos mediante `.gitignore`. Las dependencias están en `requirements.txt` y son `pandas`, `requests`, `beautifulsoup4` y `tabulate`.
