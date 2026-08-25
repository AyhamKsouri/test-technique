#!/usr/bin/env python3
"""
Extraction Paris Open Data - API Explore v2.1

Ordre d'execution recommande :
    python extract.py schema                  # 1. inspecter les champs (A FAIRE EN PREMIER)
    python extract.py export                  # 2. terrasses + quartiers (fichiers complets)
    python extract.py export-signalements      # 3. dans-ma-rue en entier (~500 Mo, requis
                                                #    par le notebook d'analyse principal)
    python extract.py anomalies <champ> [an]  # 4. agregation dans-ma-rue cote serveur,
                                                #    alternative legere a export-signalements
                                                #    quand on n'a besoin que d'un comptage

Dependances : pip install requests
"""

import sys
import json
import time
import pathlib

import requests

BASE = "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets"

# "dans-ma-rue-historique-anomalies-signalees" n'a PAS de records interrogeables
# (has_records=false, fields=[]) : c'est un simple conteneur de 14 pieces jointes ZIP
# (un CSV par annee, 2012->2025, ~107 Mo compresse rien que pour 2025). Impossible
# d'y faire un group_by. Le jeu reellement exploitable est "dans-ma-rue" : donnees
# live (annee precedente + annee en cours a J-3 mois), 1.47M enregistrements, avec
# un champ "conseilquartier" deja present (pas de jointure spatiale necessaire).
# Existe en miroir identique sur ce meme portail (BASE) et sur
# parisdata.opendatasoft.com -- teste sur les deux le 2026-08-22, resultats identiques.
TERRASSES = "terrasses-autorisations"
ANOMALIES_HIST = "dans-ma-rue-historique-anomalies-signalees"  # info seulement, non interrogeable
ANOMALIES = "dans-ma-rue"  # jeu live, interrogeable, meme portail (BASE)
QUARTIERS = "quartier_paris"

OUT = pathlib.Path("data")
OUT.mkdir(exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "projet-etudiant-datascience"})


# ---------------------------------------------------------------- helpers

def _get(url, **params):
    r = SESSION.get(url, params=params, timeout=120)
    if not r.ok:
        # l'API renvoie un JSON d'erreur explicite : on l'affiche avant de lever
        print(f"[HTTP {r.status_code}] {url}", file=sys.stderr)
        print(r.text[:500], file=sys.stderr)
        r.raise_for_status()
    return r


# ---------------------------------------------------------------- 1. schema

def schema(dataset_id, base=BASE):
    """Affiche le nombre d'enregistrements et la liste des champs."""
    meta = _get(f"{base}/{dataset_id}").json()

    metas = meta.get("metas", {}).get("default", {})
    print(f"\n=== {dataset_id} ===")
    print(f"  titre      : {metas.get('title')}")
    print(f"  records    : {metas.get('records_count')}")
    print(f"  modifie le : {metas.get('modified')}")
    print(f"  {'-' * 70}")

    for f in meta.get("fields", []):
        print(f"  {f.get('name', ''):<32} {f.get('type', ''):<10} {f.get('label', '')}")

    return meta


def cmd_schema():
    for ds in (TERRASSES, QUARTIERS, ANOMALIES):
        try:
            schema(ds)
        except Exception as e:
            print(f"\n!! echec sur {ds} : {e}", file=sys.stderr)

    # jeu historique : affiche pour memoire mais n'a pas de champs interrogeables
    try:
        meta = _get(f"{BASE}/{ANOMALIES_HIST}").json()
        print(f"\n=== {ANOMALIES_HIST} (non interrogeable, pieces jointes seulement) ===")
        print(f"  has_records : {meta.get('has_records')}")
        print(f"  fields      : {meta.get('fields')}")
        atts = meta.get("attachments", [])
        print(f"  {len(atts)} pieces jointes (1 zip par annee) :")
        for a in atts:
            print(f"    - {a.get('title')}")
    except Exception as e:
        print(f"\n!! echec sur {ANOMALIES_HIST} : {e}", file=sys.stderr)

    print(
        "\n>> Note les noms EXACTS des champs ci-dessus : "
        "arrondissement / conseilquartier / anneedecl / type / geo_point_2d.\n"
        ">> Ils conditionnent les commandes suivantes."
    )


# ---------------------------------------------------------------- 2. export

def download(dataset_id, fmt="csv", dest=None, **params):
    """Telecharge un export COMPLET (pas de limite de pagination) en streaming."""
    params.setdefault("lang", "fr")
    params.setdefault("timezone", "Europe/Paris")
    if fmt == "csv":
        params.setdefault("delimiter", ";")
        params.setdefault("use_labels", "false")  # noms techniques, plus stables

    dest = dest or OUT / f"{dataset_id}.{fmt}"
    url = f"{BASE}/{dataset_id}/exports/{fmt}"

    with SESSION.get(url, params=params, stream=True, timeout=900) as r:
        if not r.ok:
            print(f"[HTTP {r.status_code}] {r.url}", file=sys.stderr)
            print(r.text[:500], file=sys.stderr)
            r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                fh.write(chunk)

    mb = dest.stat().st_size / 1e6
    print(f"  -> {dest}  ({mb:.1f} Mo)")
    return dest


def cmd_export():
    print("Terrasses (CSV + GeoJSON) :")
    download(TERRASSES, "csv")
    download(TERRASSES, "geojson")

    print("Quartiers administratifs (GeoJSON, pour la jointure spatiale) :")
    download(QUARTIERS, "geojson")

    print(
        "\n>> dans-ma-rue n'est PAS exporte par cette commande (1,47M lignes, ~500 Mo) : "
        "utilise `python extract.py export-signalements` pour le telecharger en entier "
        "(necessaire pour le notebook d'analyse), ou `python extract.py anomalies <champ>` "
        "pour n'en recuperer qu'une agregation cote serveur."
    )


def cmd_export_signalements():
    """Telecharge dans-ma-rue en entier : requis par 03_analyse_hypotheses.ipynb, qui a
    besoin des lignes individuelles (jointure par adresse) et pas seulement d'un comptage
    agrege. Fichier volumineux (~500 Mo) -- separe de `export` intentionnellement."""
    print("Dans Ma Rue (CSV complet, ~500 Mo -- peut prendre plusieurs minutes) :")
    download(ANOMALIES, "csv")


# ---------------------------------------------------------------- 3. agregation

def aggregate(dataset_id, group_fields, where=None, extra_select=None, base=BASE):
    """
    Agregation cote serveur via group_by : on ne rapatrie que le resultat.
    group_fields : ex. "arrondissement" ou "arrondissement, type"
    """
    select = f"{group_fields}, count(*) as nb"
    if extra_select:
        select += f", {extra_select}"

    rows, offset, page = [], 0, 100
    while True:
        params = {
            "select": select,
            "group_by": group_fields,
            "order_by": "nb DESC",
            "limit": page,
            "offset": offset,
        }
        if where:
            params["where"] = where

        data = _get(f"{base}/{dataset_id}/records", **params).json()
        batch = data.get("results", [])
        rows.extend(batch)

        if len(batch) < page:
            break
        offset += page
        if offset >= 10_000:  # plafond offset de l'API
            print("!! plafond d'offset atteint, resultat tronque", file=sys.stderr)
            break
        time.sleep(0.2)

    return rows


def cmd_anomalies(champ_group, annee=None, champ_date=None):
    """
    champ_group : nom EXACT du champ geographique (vu via `schema`)
    annee       : ex. 2025 -> filtre sur une annee
    champ_date  : nom EXACT du champ date, requis si annee est fourni
    """
    where = None
    if annee:
        if not champ_date:
            sys.exit("!! precise aussi le champ date : anomalies <champ> <annee> <champ_date>")
        where = f"{champ_date} >= date'{annee}-01-01' AND {champ_date} < date'{int(annee) + 1}-01-01'"
        print(f"filtre : {where}")

    rows = aggregate(ANOMALIES, champ_group, where=where)

    dest = OUT / f"anomalies_par_{champ_group}{'_' + str(annee) if annee else ''}.json"
    dest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(r.get("nb", 0) for r in rows)
    print(f"  {len(rows)} groupes, {total:,} signalements au total")
    print(f"  -> {dest}")

    for r in rows[:10]:
        print(f"     {r.get(champ_group)!s:<30} {r.get('nb'):>10,}")


# ---------------------------------------------------------------- main

USAGE = __doc__

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(USAGE)

    cmd = sys.argv[1]
    if cmd == "schema":
        cmd_schema()
    elif cmd == "export":
        cmd_export()
    elif cmd == "export-signalements":
        cmd_export_signalements()
    elif cmd == "anomalies":
        cmd_anomalies(*sys.argv[2:])
    else:
        sys.exit(USAGE)
