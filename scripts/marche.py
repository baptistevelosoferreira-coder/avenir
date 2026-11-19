"""« Et après » : le marché de l'emploi (CDI et CDD) des métiers visés, hors stages et alternances.

Canal : Adzuna, API publique (ADZUNA_APP_ID, ADZUNA_APP_KEY). Aucune donnée personnelle.
Sorties, dans data/marche/ :
  AAAA-MM-JJ.json        : comptages (avec requête exacte), répartitions, salaires, entreprises
  AAAA-MM-JJ_offres.csv  : offres détaillées (intitulé, entreprise, lieu, contrat, salaire, extrait)
Relancer : python scripts/marche.py
"""
import csv
import datetime as dt
import json
import os
import re
import time

import requests

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUJ = dt.date.today().isoformat()
SORTIE = os.path.join(RACINE, "data", "marche")
UA = {"User-Agent": "avenir-veille-metier/1.0 (projet etudiant)"}
BASE = "https://api.adzuna.com/v1/api/jobs/fr"
EXCLU = "stage stagiaire internship alternance alternant apprentissage apprenti"
JOURS = 60
METIERS = ["chef de produit", "chef de gamme", "chef de marque", "brand manager", "product marketing",
           "marketing produit", "category manager", "chef de projet marketing", "trade marketing"]
CONTRATS = {"permanent": "CDI", "contract": "CDD"}
LIM = ("Adzuna agrège les offres de nombreux sites (une offre publiée plusieurs fois compte une fois), "
       "mais ne voit pas tout le marché. Comptage sur l'intitulé, offres des 60 derniers jours, "
       "stages et alternances exclus. Le type de contrat n'est pas renseigné sur toutes les offres.")
journal = []


def log(m):
    m = re.sub(r"(app_id|app_key)=[^&\s]+", r"\1=***", str(m))
    print(m)
    journal.append(m)


def get(chemin, **params):
    params.update({"app_id": os.environ["ADZUNA_APP_ID"], "app_key": os.environ["ADZUNA_APP_KEY"]})
    for essai in range(4):
        r = requests.get(f"{BASE}/{chemin}", params=params, headers=UA, timeout=40)
        if r.status_code in (429, 502, 503):
            time.sleep(12 * (essai + 1))
            continue
        r.raise_for_status()
        time.sleep(2.6)  # quota gratuit : 25 appels par minute
        return r.json()
    r.raise_for_status()


def propre(t, n=None):
    t = re.sub(r"<[^>]+>", " ", t or "")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:n] if n else t


def main():
    if not (os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY")):
        print("Adzuna : identifiants absents, rien à faire")
        return
    os.makedirs(SORTIE, exist_ok=True)
    out = {"date": AUJ, "canal": "Adzuna", "limites": LIM, "jours": JOURS, "comptages": [], "stats": {}}

    def nb(metier, contrat=None, **extra):
        p = {"title_only": metier, "what_exclude": EXCLU, "max_days_old": JOURS, "results_per_page": 1, **extra}
        if contrat:
            p["contract_type"] = contrat
        try:
            d = get("search/1", **p)
            v = d.get("count", 0)
            moy = d.get("mean")
        except Exception as ex:
            log(f"comptage {metier} {contrat} : {ex}")
            v, moy = None, None
        p.pop("results_per_page")
        out["comptages"].append({"metier": metier, "contrat": CONTRATS.get(contrat, "tous"), "valeur": v,
                                 "salaire_moyen": moy, "requete": p, **({"filtre": extra} if extra else {})})
        return v

    # 1. Volume par métier et par contrat
    for m in METIERS:
        nb(m)
        for c in CONTRATS:
            nb(m, c)
    # 2. Comparaison avec les stages et alternances du même intitulé
    try:
        d = get("search/1", title_only="chef de produit", what_or=EXCLU, max_days_old=JOURS, results_per_page=1)
        out["stage_alternance_chef_de_produit"] = d.get("count")
    except Exception as ex:
        log(f"comparaison stage/alternance : {ex}")
    # 3. Niveau d'expérience visible dans l'intitulé
    for mot in ["junior", "senior", "confirmé", "assistant", "international", "digital"]:
        nb("chef de produit", None, what_and=mot)

    # 4. Statistiques Adzuna
    for nom, chemin, p in [
        ("regions", "geodata", {"what": "chef de produit", "what_exclude": EXCLU, "location0": "France"}),
        ("regions_cdi", "geodata", {"what": "chef de produit", "what_exclude": EXCLU, "location0": "France", "contract_type": "permanent"}),
        ("salaires", "histogram", {"what": "chef de produit", "what_exclude": EXCLU}),
        ("salaires_cdi", "histogram", {"what": "chef de produit", "what_exclude": EXCLU, "contract_type": "permanent"}),
        ("historique", "history", {"what": "chef de produit", "months": 24}),
        ("entreprises", "top_companies", {"what": "chef de produit", "what_exclude": EXCLU}),
    ]:
        try:
            out["stats"][nom] = {"requete": {"endpoint": chemin, **p}, "donnees": get(chemin, **p)}
        except Exception as ex:
            log(f"{nom} : {ex}")
    # Départements des 2 premières régions et d'Auvergne-Rhône-Alpes
    for reg in ["Ile-de-France", "Auvergne-Rhône-Alpes"]:
        try:
            out["stats"]["dep_" + reg] = {"requete": {"endpoint": "geodata", "what": "chef de produit", "location0": "France", "location1": reg},
                                          "donnees": get("geodata", what="chef de produit", what_exclude=EXCLU, location0="France", location1=reg)}
        except Exception as ex:
            log(f"départements {reg} : {ex}")

    # 5. Offres détaillées (intitulé « chef de produit », 60 jours, au plus 10 pages de 50)
    offres = []
    for page in range(1, 11):
        try:
            d = get(f"search/{page}", title_only="chef de produit", what_exclude=EXCLU, max_days_old=JOURS,
                    results_per_page=50, sort_by="date")
        except Exception as ex:
            log(f"page {page} : {ex}")
            break
        res = d.get("results", [])
        for x in res:
            loc = x.get("location") or {}
            area = loc.get("area") or []
            offres.append({
                "id": x.get("id"), "date_publication": (x.get("created") or "")[:10], "intitule": propre(x.get("title")),
                "entreprise": propre((x.get("company") or {}).get("display_name")), "lieu": loc.get("display_name", ""),
                "region": area[1] if len(area) > 1 else "", "departement": area[2] if len(area) > 2 else "",
                "contrat": CONTRATS.get(x.get("contract_type") or "", ""), "temps": x.get("contract_time", ""),
                "salaire_min": x.get("salary_min"), "salaire_max": x.get("salary_max"),
                "salaire_estime": x.get("salary_is_predicted"), "categorie": (x.get("category") or {}).get("label", ""),
                "extrait": propre(x.get("description"), 700), "latitude": x.get("latitude"), "longitude": x.get("longitude"),
                "url": (x.get("redirect_url") or "").split("?")[0],
            })
        if len(res) < 50:
            break
    champs = ["id", "date_publication", "intitule", "entreprise", "lieu", "region", "departement", "contrat", "temps",
              "salaire_min", "salaire_max", "salaire_estime", "categorie", "extrait", "latitude", "longitude", "url"]
    with open(os.path.join(SORTIE, f"{AUJ}_offres.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=champs)
        w.writeheader()
        w.writerows(offres)
    out["offres_detaillees"] = len(offres)
    out["journal"] = journal
    with open(os.path.join(SORTIE, f"{AUJ}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log(f"Marché : {len(out['comptages'])} comptages, {len(out['stats'])} statistiques, {len(offres)} offres")


if __name__ == "__main__":
    main()
