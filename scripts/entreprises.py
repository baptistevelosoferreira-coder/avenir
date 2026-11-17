"""Base d'entreprises du Puy-de-Dôme (63) où le métier de chef de produit existe.

Canal : API Recherche d'entreprises (https://recherche-entreprises.api.gouv.fr), gratuite, sans clé,
données publiques (Sirene + Registre national des entreprises).
Filtres : département 63, établissement actif, au moins 20 salariés, codes NAF des secteurs qui
gèrent des gammes de produits (agroalimentaire, boissons, cosmétique, pharmacie, caoutchouc et
plastique, articles de sport, dispositifs médicaux, commerce de gros de produits de marque).

Sortie : data/entreprises_63.csv (et une copie datée dans data/AAAA-MM-JJ/).
RGPD : le dépôt est public, donc aucun nom de personne n'est enregistré (ni dirigeant, ni salarié) :
seulement l'entreprise, son activité, sa taille et sa commune.
"""
import csv
import datetime as dt
import json
import os
import shutil
import time

import requests

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUJ = dt.date.today().isoformat()
UA = {"User-Agent": "avenir-veille-metier/1.0 (projet etudiant IAE Clermont)"}

NAF = {
    "10.11Z": "Transformation de la viande de boucherie", "10.13A": "Préparation industrielle de produits à base de viande",
    "10.13B": "Charcuterie", "10.20Z": "Transformation de poissons", "10.32Z": "Préparation de jus de fruits et légumes",
    "10.39A": "Autre transformation de légumes", "10.39B": "Transformation de fruits", "10.41A": "Fabrication d'huiles",
    "10.51A": "Fabrication de lait liquide et de produits frais", "10.51B": "Fabrication de beurre",
    "10.51C": "Fabrication de fromage", "10.51D": "Fabrication d'autres produits laitiers", "10.52Z": "Fabrication de glaces",
    "10.61A": "Meunerie", "10.62Z": "Fabrication de produits amylacés", "10.71A": "Fabrication industrielle de pain et pâtisserie",
    "10.72Z": "Fabrication de biscuits et biscottes", "10.73Z": "Fabrication de pâtes alimentaires",
    "10.82Z": "Fabrication de cacao, chocolat et confiserie", "10.83Z": "Transformation du thé et du café",
    "10.84Z": "Fabrication de condiments", "10.85Z": "Fabrication de plats préparés", "10.86Z": "Aliments homogénéisés et diététiques",
    "10.89Z": "Autres produits alimentaires", "10.91Z": "Aliments pour animaux de ferme", "10.92Z": "Aliments pour animaux de compagnie",
    "11.01Z": "Production de boissons alcooliques distillées", "11.02A": "Fabrication de vins effervescents",
    "11.05Z": "Fabrication de bière", "11.07A": "Industrie des eaux de table", "11.07B": "Production de boissons rafraîchissantes",
    "20.41Z": "Fabrication de savons et détergents", "20.42Z": "Fabrication de parfums et produits pour la toilette",
    "21.10Z": "Fabrication de produits pharmaceutiques de base", "21.20Z": "Fabrication de préparations pharmaceutiques",
    "22.11Z": "Fabrication et rechapage de pneumatiques", "22.19Z": "Fabrication d'autres articles en caoutchouc",
    "22.22Z": "Fabrication d'emballages en matières plastiques", "22.29A": "Pièces techniques en matières plastiques",
    "32.30Z": "Fabrication d'articles de sport", "32.40Z": "Fabrication de jeux et jouets",
    "32.50A": "Fabrication de matériel médico-chirurgical", "46.38B": "Commerce de gros alimentaire spécialisé",
    "46.39B": "Commerce de gros alimentaire non spécialisé", "46.45Z": "Commerce de gros de parfumerie et de beauté",
    "46.46Z": "Commerce de gros de produits pharmaceutiques", "46.49Z": "Commerce de gros d'autres biens domestiques",
}
FAMILLE = {"10": "Agroalimentaire", "11": "Boissons", "20": "Cosmétique et entretien", "21": "Pharmacie",
           "22": "Caoutchouc et plastique", "32": "Sport, jouets, médical", "46": "Commerce de gros"}
TRANCHES = {"12": "20 à 49", "21": "50 à 99", "22": "100 à 199", "31": "200 à 249", "32": "250 à 499",
            "41": "500 à 999", "42": "1 000 à 1 999", "51": "2 000 à 4 999", "52": "5 000 à 9 999", "53": "10 000 et plus"}


def main():
    url = "https://recherche-entreprises.api.gouv.fr/search"
    params = {"departement": "63", "activite_principale": ",".join(NAF), "tranche_effectif_salarie": ",".join(TRANCHES),
              "etat_administratif": "A", "per_page": 25}
    lignes, total = [], None
    for page in range(1, 41):
        r = None
        for essai in range(3):
            r = requests.get(url, params={**params, "page": page}, headers=UA, timeout=40)
            if r.status_code == 429:
                time.sleep(2 * (essai + 1))
                continue
            break
        r.raise_for_status()
        d = r.json()
        total = d.get("total_results", total)
        for e in d.get("results", []):
            s = e.get("siege") or {}
            m = (e.get("matching_etablissements") or [])
            loc = next((x for x in m if str(x.get("code_postal") or "").startswith("63")), s)
            naf = e.get("activite_principale") or s.get("activite_principale") or ""
            lignes.append({
                "siren": e.get("siren"), "nom": e.get("nom_complet"), "commune": loc.get("libelle_commune"),
                "code_postal": loc.get("code_postal"), "siege_hors_63": not str(s.get("code_postal") or "").startswith("63"), "naf": naf, "activite": NAF.get(naf, ""),
                "famille": FAMILLE.get(naf[:2], ""), "effectif": TRANCHES.get(str(e.get("tranche_effectif_salarie") or ""), ""),
                "categorie": e.get("categorie_entreprise"), "date_creation": e.get("date_creation"),
                "etablissements": e.get("nombre_etablissements"), "latitude": loc.get("latitude"), "longitude": loc.get("longitude"),
                "fiche": f"https://annuaire-entreprises.data.gouv.fr/entreprise/{e.get('siren')}",
            })
        if page >= (d.get("total_pages") or 1):
            break
        time.sleep(0.3)
    champs = ["siren", "nom", "commune", "code_postal", "siege_hors_63", "naf", "activite", "famille", "effectif", "categorie",
              "date_creation", "etablissements", "latitude", "longitude", "fiche"]
    os.makedirs(os.path.join(RACINE, "data", AUJ), exist_ok=True)
    dest = os.path.join(RACINE, "data", "entreprises_63.csv")
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=champs)
        w.writeheader()
        w.writerows(lignes)
    shutil.copy(dest, os.path.join(RACINE, "data", AUJ, "entreprises_63.csv"))
    meta = {"date": AUJ, "canal": "API Recherche d'entreprises (data.gouv)", "requete": params, "total_api": total,
            "lignes": len(lignes),
            "limites": "Sirene ne dit pas qui emploie un chef de produit : la liste repose sur le secteur (NAF) et la taille. "
                       "Une entreprise est retenue si au moins un de ses établissements est dans le 63 ; son siège peut être ailleurs (colonne siege_hors_63). La tranche d'effectif est celle de toute l'entreprise."}
    with open(os.path.join(RACINE, "data", AUJ, "entreprises_63.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"Entreprises 63 : {len(lignes)} lignes (total API {total})")


if __name__ == "__main__":
    main()
