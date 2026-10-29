# Recomendador de mazos

Script de terminal que descarga de MTGDecks el metajuego de los últimos 30 días y recomienda mazos según su precio `Paper` y su rendimiento competitivo.

## Requisitos e instalación

Se necesita Python y las dependencias definidas en `requirements.txt`:

```bash
python -m pip install -r requirements.txt
```

El script necesita conexión a Internet para consultar MTGDecks.

## Uso

Sin argumentos analiza `Standard`, considera solo los mazos de tier A y muestra los 10 primeros puestos:

```bash
python deck_recommender.py
```

Los formatos disponibles son `standard`, `pioneer`, `modern`, `pauper` y `premodern`:

```bash
python deck_recommender.py --format pioneer
python deck_recommender.py --format modern
python deck_recommender.py --format pauper
python deck_recommender.py --format premodern
```

El periodo de análisis está fijado en los últimos 30 días. Para procesar todos los formatos:

```bash
python deck_recommender.py --all
```

`--all` no se puede combinar con `--url`, `--output`, `--raw-output` ni `--report-output`.

## Opciones

```text
--format FORMAT          Formato individual. Por defecto: standard.
--all                    Analiza todos los formatos disponibles.
--tiers {1,2,3,all}      Tiers incluidos. Por defecto: 1.
--top N                  Filas del ranking que se muestran en terminal. Por defecto: 10.
--url URL                URL alternativa para el análisis de un único formato.
--output FILE             CSV del análisis calculado.
--raw-output FILE         CSV con todas las filas extraídas.
--report-output FILE      Informe Markdown del formato.
```

El nivel de tiers es acumulativo:

```bash
python deck_recommender.py --format modern --tiers 1  # Solo tier A
python deck_recommender.py --format modern --tiers 2  # Tiers A y B
python deck_recommender.py --format modern --tiers 3  # Tiers A, B y C
python deck_recommender.py --format modern --tiers all  # Todos los tiers publicados
```

Ejemplo con opciones de salida personalizadas:

```bash
python deck_recommender.py --format standard --top 15 --output standard_analysis.csv --raw-output standard_data.csv --report-output standard_report.md
```

## Archivos generados

En un análisis individual se generan, por defecto:

- `deck_data_<format>.csv`: todas las filas extraídas de MTGDecks, incluidos los precios `Paper` y `MTGO`.
- `deck_analysis_<format>.csv`: filas válidas con las puntuaciones y el IVC.
- `deck_recommendations_<format>.md`: informe Markdown con las recomendaciones y el ranking completo.

Con `--all` se genera además `deck_recommendations.md`, que reúne los informes de todos los formatos. Estos archivos están excluidos de Git mediante `.gitignore`.

La salida de terminal muestra la recomendación principal, una segunda recomendación y el ranking limitado por `--top`. Los informes Markdown conservan el ranking completo de mazos válidos, independientemente de `--top`.

## Filtrado y cálculo

Por defecto solo se incluyen mazos de tier A. `--tiers 2` incluye A+B, `--tiers 3` incluye A+B+C y `--tiers all` elimina el filtro de tier. Se excluyen el arquetipo `Rogue`, las filas sin winrate o conversión Top 25% y las filas sin un precio `Paper` válido.

El IVC utiliza estas ponderaciones:

- Precio relativo: 30%
- Conversión Top 25%: 35%
- Winrate: 25%
- Trend: 10%

Todas las métricas se normalizan entre 1 y 10. La puntuación del precio se calcula respecto a la mediana de los precios `Paper` válidos: la mediana recibe 5 puntos, los precios más bajos obtienen mejor puntuación y el resultado queda limitado entre 1 y 10. Esto evita que un precio excepcional distorsione la referencia.

La recomendación principal es el mazo con el IVC más alto. El precio se usa dentro del IVC y como desempate, favoreciendo el precio más bajo. Si la recomendación tiene menos de 10 listas, el informe muestra una advertencia porque el resultado es menos confiable.
