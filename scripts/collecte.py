"""Collecte datée des offres de STAGE et d'ALTERNANCE de chef de produit (code ROME M1703).

Canaux, tous officiels et utilisés selon leurs conditions :
  - France Travail, API « Offres d'emploi v2 »  (FT_CLIENT_ID, FT_CLIENT_SECRET)
  - Adzuna, API publique                         (ADZUNA_APP_ID, ADZUNA_APP_KEY)
  - La bonne alternance, API apprentissage      (LBA_TOKEN)
Un canal sans identifiants est simplement ignoré (et noté dans le journal).
Aucun site n'est aspiré : pas de LinkedIn, d'APEC ni d'Indeed.

Sorties, dans data/AAAA-MM-JJ/ :
  offres_adzuna.csv, offres_france_travail.csv, offres_lba.csv, recruteurs_lba.csv
  comptages.json : chaque nombre avec sa requête exacte, sa date, son canal et ses limites.
Relancer : python scripts/collecte.py  (les identifiants sont lus dans .env ou dans l'environnement)
"""
import csv
import datetime as dt
import json
import os
import re
import sys
import time

import requests

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUJ = dt.date.today().isoformat()
SORTIE = os.path.join(RACINE, "data", AUJ)
UA = {"User-Agent": "avenir-veille-metier/1.0 (projet etudiant)"}
TIMEOUT = 40
ROME = "M1703"
INTITULE = "chef de produit"
STAGE_ALT = "stage stagiaire internship alternance alternant apprentissage apprenti"
VARIANTES = ["chef de produit", "assistant chef de produit", "chef de marque", "chef de gamme",
             "product manager", "brand manager", "chef de marche"]

comptages = []   # chaque entrée : canal, mesure, valeur, requete, date, limites
journal = []


def log(msg):
    # le journal est publié : on retire toute clé d'API des URL d'erreur
    msg = re.sub(r"(app_id|app_key|token|client_secret|client_id)=[^&\s]+", r"\1=***", str(msg))
    print(msg)
    journal.append(msg)


def compte(canal, mesure, valeur, requete, limites=""):
    comptages.append({"canal": canal, "mesure": mesure, "valeur": valeur, "requete": requete,
                      "date": AUJ, "limites": limites})


def lire_env():
    p = os.path.join(RACINE, ".env")
    if os.path.exists(p):
        for ligne in open(p, encoding="utf-8"):
            if "=" in ligne and not ligne.strip().startswith("#"):
                k, v = ligne.strip().split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def ecrire_csv(nom, lignes, champs):
    if not lignes:
        return
    os.makedirs(SORTIE, exist_ok=True)
    with open(os.path.join(SORTIE, nom), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=champs, extrasaction="ignore")
        w.writeheader()
        for l in lignes:
            w.writerow({k: ("" if l.get(k) is None else l.get(k)) for k in champs})
    log(f"  -> {nom} : {len(lignes)} lignes")


def propre(t, n=None):
    t = re.sub(r"<[^>]+>", " ", str(t or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return t[:n] if n else t


# ------------------------------------------------------------------ Adzuna

def adzuna():
    aid, key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not (aid and key):
        log("Adzuna : identifiants absents, canal ignoré")
        return
    base = "https://api.adzuna.com/v1/api/jobs/fr"
    lim = ("Agrégateur : une offre peut être publiée sur plusieurs sites et comptée une fois par Adzuna, "
           "mais Adzuna ne voit pas tout le marché. Recherche dans le titre seulement.")

    def get(chemin, **params):
        params.update({"app_id": aid, "app_key": key})
        for essai in range(3):
            r = requests.get(f"{base}/{chemin}", params=params, headers=UA, timeout=TIMEOUT)
            if r.status_code in (429, 502, 503):
                time.sleep(10 * (essai + 1))
                continue
            r.raise_for_status()
            time.sleep(2.6)  # quota gratuit : 25 appels par minute
            return r.json()
        r.raise_for_status()

    def nb(desc, **p):
        try:
            d = get("search/1", results_per_page=1, **p)
            q = {k: v for k, v in p.items()}
            compte("Adzuna", desc, d.get("count", 0), q, lim)
            return d.get("count", 0)
        except Exception as ex:
            log(f"Adzuna comptage '{desc}' : {ex}")

    # 1. Volume par intitulé, stages et alternances seulement (offres des 30 derniers jours)
    for v in VARIANTES:
        nb(f"stage ou alternance, titre contenant « {v} » (30 jours)", title_only=v, what_or=STAGE_ALT, max_days_old=30)
    # 2. Contrats et lieux pour l'intitulé principal
    nb("chef de produit, tous contrats confondus (30 jours) : pour comparaison", title_only=INTITULE, max_days_old=30)
    nb("chef de produit : stage (30 jours)", title_only=INTITULE, what_or="stage stagiaire internship", max_days_old=30)
    nb("chef de produit : alternance (30 jours)", title_only=INTITULE, what_or="alternance alternant apprentissage apprenti",
       max_days_old=30)
    nb("chef de produit, stage ou alternance : télétravail mentionné (30 jours)", title_only=INTITULE,
       what_and="télétravail", what_or=STAGE_ALT, max_days_old=30)
    for lieu, dist in [("Clermont-Ferrand", 40), ("Puy-de-Dôme", None), ("Auvergne-Rhône-Alpes", None),
                       ("Île-de-France", None), ("Lyon", 30)]:
        p = {"title_only": INTITULE, "what_or": STAGE_ALT, "max_days_old": 30, "where": lieu}
        if dist:
            p["distance"] = dist
        nb(f"chef de produit, stage ou alternance : {lieu}{f' ({dist} km)' if dist else ''} (30 jours)", **p)

    # 3. Offres détaillées de l'intitulé principal (au plus 10 pages de 50)
    offres = []
    for page in range(1, 11):
        try:
            d = get(f"search/{page}", title_only=INTITULE, what_or=STAGE_ALT, max_days_old=30, results_per_page=50, sort_by="date")
        except Exception as ex:
            log(f"Adzuna page {page} : {ex}")
            break
        res = d.get("results", [])
        for x in res:
            loc = x.get("location") or {}
            area = loc.get("area") or []
            offres.append({
                "id": x.get("id"), "date_publication": (x.get("created") or "")[:10], "intitule": propre(x.get("title")),
                "entreprise": propre((x.get("company") or {}).get("display_name")),
                "lieu": loc.get("display_name", ""), "region": area[1] if len(area) > 1 else "",
                "departement": area[2] if len(area) > 2 else "", "contrat_type": x.get("contract_type", ""),
                "contrat_temps": x.get("contract_time", ""), "salaire_min": x.get("salary_min"),
                "salaire_max": x.get("salary_max"), "salaire_estime_par_adzuna": x.get("salary_is_predicted"),
                "categorie": (x.get("category") or {}).get("label", ""), "description_extrait": propre(x.get("description"), 600),
                "latitude": x.get("latitude"), "longitude": x.get("longitude"), "url": (x.get("redirect_url") or "").split("?")[0],
            })
        if len(res) < 50:
            break
    ecrire_csv("offres_adzuna.csv", offres, ["id", "date_publication", "intitule", "entreprise", "lieu", "region",
               "departement", "contrat_type", "contrat_temps", "salaire_min", "salaire_max", "salaire_estime_par_adzuna",
               "categorie", "description_extrait", "latitude", "longitude", "url"])

    # 4. Statistiques Adzuna (mot-clé, pas seulement le titre)
    os.makedirs(SORTIE, exist_ok=True)
    stats = {}
    for nom, chemin, p in [("geodata", "geodata", {"what": "chef produit stage", "location0": "France"}),
                           ("histogramme_salaires", "histogram", {"what": "chef produit stage"}),
                           ("historique_salaires", "history", {"category": "pr-advertising-marketing-jobs", "months": 12}),
                           ("top_entreprises", "top_companies", {"what": "chef produit stage"})]:
        try:
            stats[nom] = {"requete": {"endpoint": chemin, **p}, "date": AUJ, "donnees": get(chemin, **p)}
        except Exception as ex:
            log(f"Adzuna {nom} : {ex}")
    with open(os.path.join(SORTIE, "stats_adzuna.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    log(f"Adzuna : {len(offres)} offres détaillées, {len(stats)} statistiques")


# ------------------------------------------------------------------ France Travail

def france_travail():
    cid, sec = os.getenv("FT_CLIENT_ID"), os.getenv("FT_CLIENT_SECRET")
    if not (cid and sec):
        log("France Travail : identifiants absents, canal ignoré")
        return
    r = requests.post("https://entreprise.francetravail.fr/connexion/oauth2/access_token", params={"realm": "/partenaire"},
                      data={"grant_type": "client_credentials", "client_id": cid, "client_secret": sec,
                            "scope": "api_offresdemploiv2 o2dsoffre"}, timeout=TIMEOUT)
    r.raise_for_status()
    h = {"Authorization": "Bearer " + r.json()["access_token"], "Accept": "application/json", **UA}
    url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
    lim = ("API officielle : 150 offres par appel, 1 150 au plus par requête ; ne contient que les offres déposées "
           "chez France Travail ou ses partenaires.")

    def total(params):
        rr = requests.get(url, params={**params, "range": "0-0"}, headers=h, timeout=TIMEOUT)
        time.sleep(0.4)
        if rr.status_code == 204:
            return 0
        m = re.search(r"/(\d+)", rr.headers.get("Content-Range", ""))
        return int(m.group(1)) if m else None

    for desc, p in [("offres ROME M1703, France", {"codeROME": ROME}),
                    ("offres ROME M1703, Puy-de-Dôme (63)", {"codeROME": ROME, "departement": "63"}),
                    ("offres ROME M1703, Auvergne-Rhône-Alpes", {"codeROME": ROME, "region": "84"}),
                    ("offres ROME M1703, alternance (apprentissage ou professionnalisation)", {"codeROME": ROME, "natureContrat": "E2,FS"}),
                    ("offres ROME M1703, alternance, Auvergne-Rhône-Alpes", {"codeROME": ROME, "natureContrat": "E2,FS", "region": "84"}),
                    ("offres mot-clé « stage chef de produit », France", {"motsCles": "stage,chef,produit"})]:
        try:
            compte("France Travail", desc, total(p), p, lim)
        except Exception as ex:
            log(f"France Travail comptage '{desc}' : {ex}")

    offres = []
    for debut in range(0, 1150, 150):
        rr = requests.get(url, params={"codeROME": ROME, "range": f"{debut}-{debut + 149}"}, headers=h, timeout=TIMEOUT)
        time.sleep(0.4)
        if rr.status_code == 204 or rr.status_code >= 400:
            break
        res = rr.json().get("resultats", [])
        for x in res:
            lt, ent, sal = x.get("lieuTravail") or {}, x.get("entreprise") or {}, x.get("salaire") or {}
            offres.append({
                "id": x.get("id"), "date_publication": (x.get("dateCreation") or "")[:10], "intitule": x.get("intitule", ""),
                "entreprise": ent.get("nom", ""), "lieu": lt.get("libelle", ""), "departement": (lt.get("libelle") or "")[:2],
                "commune": lt.get("commune", ""), "latitude": lt.get("latitude"), "longitude": lt.get("longitude"),
                "contrat": x.get("typeContrat", ""), "contrat_libelle": x.get("typeContratLibelle", ""),
                "alternance": x.get("alternance", False), "salaire_affiche": sal.get("libelle", ""),
                "experience": x.get("experienceLibelle", ""), "secteur": x.get("secteurActiviteLibelle", ""),
                "competences": " | ".join(c.get("libelle", "") for c in x.get("competences", []) or []),
                "qualites": " | ".join(c.get("libelle", "") for c in x.get("qualitesProfessionnelles", []) or []),
                "description": propre(x.get("description"), 4000),
                "url": (x.get("origineOffre") or {}).get("urlOrigine", ""),
            })
        if len(res) < 150:
            break
    ecrire_csv("offres_france_travail.csv", offres, ["id", "date_publication", "intitule", "entreprise", "lieu",
               "departement", "commune", "latitude", "longitude", "contrat", "contrat_libelle", "alternance",
               "salaire_affiche", "experience", "secteur", "competences", "qualites", "description", "url"])
    log(f"France Travail : {len(offres)} offres détaillées")


# ------------------------------------------------------------------ La bonne alternance

def _c(d, *chemins):
    for ch in chemins:
        v = d
        for k in ch.split("."):
            v = v.get(k) if isinstance(v, dict) else None
        if v not in (None, "", []):
            return v
    return ""


def bonne_alternance():
    tok = os.getenv("LBA_TOKEN")
    if not tok:
        log("La bonne alternance : jeton absent, canal ignoré")
        return
    h = {"Authorization": "Bearer " + tok, "Accept": "application/json", **UA}
    villes = {"Clermont-Ferrand": (45.7772, 3.087, 60), "Paris": (48.8566, 2.3522, 60), "Lyon": (45.764, 4.8357, 60),
              "Lille": (50.6292, 3.0573, 60), "Bordeaux": (44.8378, -0.5792, 60), "Nantes": (47.2184, -1.5536, 60),
              "Toulouse": (43.6047, 1.4442, 60), "Marseille": (43.2965, 5.3698, 60), "Strasbourg": (48.5734, 7.7521, 60)}
    offres, recruteurs, vus = [], [], set()
    for ville, (lat, lon, rayon) in villes.items():
        p = {"romes": ROME, "latitude": lat, "longitude": lon, "radius": rayon}
        try:
            r = requests.get("https://api.apprentissage.beta.gouv.fr/api/job/v1/search", params=p, headers=h, timeout=TIMEOUT)
            r.raise_for_status()
            d = r.json()
        except Exception as ex:
            log(f"La bonne alternance {ville} : {ex}")
            continue
        jobs, recs = d.get("jobs", []) or [], d.get("recruiters", []) or []
        compte("La bonne alternance", f"offres d'alternance ROME M1703 à {rayon} km de {ville}", len(jobs), p,
               "Offres d'alternance publiées (France Travail, partenaires, formulaires LBA) ; plafond de résultats de l'API.")
        compte("La bonne alternance", f"entreprises susceptibles de recruter en alternance (sans offre publiée) à {rayon} km de {ville}",
               len(recs), p, "Prédiction de La bonne alternance à partir des embauches passées : ce n'est pas une offre.")
        for x in jobs:
            i = _c(x, "identifier.id", "id")
            if i in vus:
                continue
            vus.add(i)
            offres.append({"id": i, "ville_requete": ville, "date_publication": str(_c(x, "offer.publication.creation"))[:10],
                           "intitule": _c(x, "offer.title"), "entreprise": _c(x, "workplace.name", "workplace.brand", "workplace.legal_name"),
                           "siret": _c(x, "workplace.siret"), "lieu": _c(x, "workplace.location.address"),
                           "naf": _c(x, "workplace.domain.naf.label"), "taille": _c(x, "workplace.size"),
                           "description": propre(_c(x, "offer.description"), 3000), "url": _c(x, "apply.url")})
        for x in recs:
            recruteurs.append({"ville_requete": ville, "entreprise": _c(x, "workplace.name", "workplace.brand", "workplace.legal_name"),
                               "siret": _c(x, "workplace.siret"), "lieu": _c(x, "workplace.location.address"),
                               "naf": _c(x, "workplace.domain.naf.label"), "taille": _c(x, "workplace.size")})
        time.sleep(1)
    ecrire_csv("offres_lba.csv", offres, ["id", "ville_requete", "date_publication", "intitule", "entreprise", "siret", "lieu",
                                          "naf", "taille", "description", "url"])
    ecrire_csv("recruteurs_lba.csv", recruteurs, ["ville_requete", "entreprise", "siret", "lieu", "naf", "taille"])
    log(f"La bonne alternance : {len(offres)} offres, {len(recruteurs)} recruteurs potentiels")


def main():
    lire_env()
    os.makedirs(SORTIE, exist_ok=True)
    for f in (adzuna, france_travail, bonne_alternance):
        try:
            f()
        except Exception as ex:
            log(f"{f.__name__} : erreur {type(ex).__name__} {ex}")
    with open(os.path.join(SORTIE, "comptages.json"), "w", encoding="utf-8") as f:
        json.dump({"date": AUJ, "rome": ROME, "comptages": comptages, "journal": journal}, f, ensure_ascii=False, indent=1)
    log(f"{len(comptages)} comptages enregistrés dans data/{AUJ}/comptages.json")


if __name__ == "__main__":
    sys.exit(main())
