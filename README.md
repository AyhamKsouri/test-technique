# Terrasses parisiennes et signalements citoyens

Étude de la relation entre les terrasses commerciales autorisées à Paris et les
signalements d'anomalies sur l'espace public (application Dans Ma Rue), à partir des
données ouvertes de la Ville de Paris.

## Question posée

Existe-t-il une relation mesurable entre la présence, la nature ou la densité des
terrasses et les signalements d'anomalies sur l'espace public environnant ? Quatre
hypothèses en découlent, testées une à une dans l'analyse.

## Résultats en un coup d'œil

| Hypothèse | Résultat |
|---|---|
| H1 — Présence d'une terrasse / type de signalement | Soutenue — association statistiquement significative, mais faible (V = 0,157) |
| H2 — Typologie de terrasse / type de signalement | Non soutenue — association négligeable (V = 0,075) |
| H1-bis — Densité de terrasses / signalements commerciaux (par arrondissement) | Signal positif modéré, robustesse variable selon le modèle |
| H3 — Saisonnalité / moment des signalements | Non concluante — puissance statistique insuffisante (n = 20) |

Le détail de la méthode, des résultats et des limites est dans l'analyse (voir
ci-dessous) et dans la présentation.

## Structure du dépôt

```
extraction/
  extract.py                        script d'extraction des donnees via l'API
                                     Open Data Paris (schema / export / agregation)

data-understanding/
  01_exploration_terrasses.ipynb    exploration du jeu "terrasses-autorisations"
  02_exploration_dans_ma_rue.ipynb  exploration du jeu "dans-ma-rue"
  03_analyse_hypotheses.ipynb       analyse complete des 4 hypotheses (notebook principal)

presentation/
  presentation.pptx                 support de restitution orale

data/                                (non versionne, voir plus bas)
```

## Sources de données

Toutes les données proviennent de l'API [Open Data Paris](https://opendata.paris.fr) :

- `terrasses-autorisations` — 24 207 autorisations de terrasses et étalages commerciaux
- `dans-ma-rue` — 1 474 285 signalements citoyens d'anomalies sur l'espace public
- `quartier_paris` — référentiel géographique (surface par quartier)

## Reproduire l'analyse

```bash
pip install requests pandas numpy scipy statsmodels geopandas matplotlib

cd extraction
python extract.py schema     # inspecter les champs disponibles
python extract.py export     # telecharge terrasses-autorisations et quartier_paris

# dans-ma-rue (1.47M lignes) : export complet via l'API, utilise par le notebook d'analyse
```

Les notebooks se trouvent dans `data-understanding/` et attendent les fichiers dans un
dossier `data/` au même niveau que `extraction/` et `data-understanding/`. Le dossier
`data/` n'est pas versionné (fichiers volumineux, jusqu'à 500 Mo) — il se régénère
entièrement via le script d'extraction.

## Présentation

`presentation/presentation.pptx` résume la démarche et les conclusions : contexte et
hypothèse de départ, méthode (données, traitements, outils), résultats et
visualisations clés, conclusions avec leurs limites.
