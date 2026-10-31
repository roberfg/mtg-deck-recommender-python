# Recomendador de mazos

Script de terminal que descarga de MTGDecks el metajuego de los últimos 30 días y recomienda mazos según su precio `Paper` y su rendimiento competitivo.

## Requisitos e instalación

Se necesita Python y las dependencias definidas en `requirements.txt`:

```bash
python -m pip install -r requirements.txt
```

El script necesita conexión a Internet para consultar MTGDecks.

## Uso

El comando analiza los cinco formatos (`Standard`, `Pioneer`, `Modern`, `Pauper` y `Premodern`), considera solo los mazos de tier A y muestra los 10 primeros puestos de cada ranking:

```bash
python deck_recommender.py
```

El periodo de análisis está fijado en los últimos 30 días y no requiere opciones adicionales.

## Archivos generados

En cada ejecución se generan:

- `deck_data_<format>.csv`: todas las filas extraídas de MTGDecks, incluidos los precios `Paper` y `MTGO`.
- `deck_analysis_<format>.csv`: filas válidas con las puntuaciones y el IVC.
- `deck_recommendations.md`: informe Markdown con las recomendaciones y el ranking completo de todos los formatos.

Estos archivos están excluidos de Git mediante `.gitignore`.

La salida de terminal muestra la recomendación principal, una segunda recomendación y los 10 primeros puestos. Los informes Markdown conservan el ranking completo de mazos válidos.

## Filtrado y cálculo

Solo se incluyen mazos de tier A. Se excluyen el arquetipo `Rogue`, las filas sin winrate o conversión Top 25% y las filas sin un precio `Paper` válido.

El IVC utiliza estas ponderaciones para Pioneer, Modern, Pauper y Premodern:

- Precio relativo: 30%
- Conversión Top 25%: 35%
- Winrate: 30%
- Trend: 5%

Standard utiliza una ponderación especial por el riesgo de rotación:

- Precio relativo: 80%
- Conversión Top 25%: 10%
- Winrate: 5%
- Trend: 5%

Todas las métricas se normalizan entre 1 y 10. La puntuación del precio se calcula respecto a la mediana de los precios `Paper` válidos: la mediana recibe 5 puntos, los precios más bajos obtienen mejor puntuación y el resultado queda limitado entre 1 y 10. Esto evita que un precio excepcional distorsione la referencia.

La recomendación principal es el mazo con el IVC más alto. El precio se usa dentro del IVC y como desempate, favoreciendo el precio más bajo. Si la recomendación tiene menos de 10 listas, el informe muestra una advertencia porque el resultado es menos confiable.
