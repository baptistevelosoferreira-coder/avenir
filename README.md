# Chef de produit, le marché compté

Ma recherche de **stage ou d'alternance d'assistant(e) chef de produit**, à partir de janvier 2027. Le site repère chaque matin les offres publiées, les place sur une carte, montre ce que les recruteurs demandent, les entreprises à cibler et où j'en suis.

Page publiée : `index.html` à la racine (GitHub Pages). Le site est découpé en onglets (`assets/onglets.js`).

Intitulés suivis : chef de produit, chef de marque, chef de gamme, chef de marché, product manager, brand manager.

## Ce que contient le site

| Onglet | Contenu |
|---|---|
| 1. Les offres | Carte cliquable des offres, dates de début, mots-clés à taper |
| 2. Ce que les recruteurs demandent | Compétences et qualités demandées, comparées à mon CV |
| 3. Où candidater | Secteurs, entreprises qui publient le plus, candidatures spontanées près de Clermont |
| 4. Où j'en suis | Entonnoir de mes candidatures (totaux), prochaines étapes |
| Accueil | Résumé de ma recherche |

Chaque graphique a un bloc « Source » qui donne le canal, la requête exacte, la date et les limites du chiffre, avec un lien vers le fichier de données.

## Les canaux

| Canal | Accès | Usage |
|---|---|---|
| France Travail, Offres d'emploi v2 | API officielle, clé gratuite (francetravail.io) | Offres du code ROME M1703, compétences déclarées |
| Adzuna | API, clé gratuite | Comptages par intitulé et par lieu, offres détaillées, régions, entreprises |
| La bonne alternance | API de l'État, jeton gratuit | Offres d'alternance et entreprises qui recrutent sans publier |
| Recherche d'entreprises | API data.gouv, sans clé | Base des entreprises du Puy-de-Dôme dans les secteurs qui gèrent des gammes |
| Jooble | API, clé sur demande | Offres complémentaires de la veille du 5 au 17 novembre |

Pas d'aspiration de LinkedIn, de l'APEC ni d'Indeed : leurs conditions d'utilisation l'interdisent.

## Les fichiers

```
scripts/collecte.py       interroge France Travail, Adzuna, La bonne alternance
scripts/entreprises.py    base des entreprises du 63 (API Recherche d'entreprises)
scripts/site.py           relit data/ et contenu.json, écrit index.html
contenu.json              textes écrits à la main (prochaines étapes, stratégie)
assets/style.css          mise en page
data/AAAA-MM-JJ/          une extraction datée : CSV des offres, comptages.json (requête de chaque chiffre)
data/veille-stage-alternance/   veille quotidienne du 5 au 17 novembre 2026 (une ligne par offre retenue)
data/annonces-lues.csv    annonces lues en entier (missions, profil, gratification, début)
data/suivi-candidatures.json    totaux de mon suivi de candidatures (le détail reste privé)
data/entreprises_63.csv   base des entreprises du Puy-de-Dôme
.github/workflows/veille.yml    automatisation quotidienne
```

## Automatisation

Chaque matin vers 6 h 40, l'Action `veille.yml` lance `collecte.py`, `entreprises.py` puis `site.py`, et enregistre le résultat par un commit. L'historique Git sert d'archive datée du marché.

Les clés d'API ne sont jamais dans le code. Elles se rangent dans **Settings → Secrets and variables → Actions** du dépôt :
`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `LBA_TOKEN`, `FT_CLIENT_ID`, `FT_CLIENT_SECRET`.
Sans clé, l'Action saute la collecte et reconstruit seulement la page.

Relancer à la main sur son ordinateur :

```bash
pip install requests
cp .env.example .env          # puis y coller ses clés
python scripts/collecte.py
python scripts/entreprises.py
python scripts/site.py        # aucune dépendance, bibliothèque standard seulement
```

Ou depuis GitHub : onglet **Actions → Veille du métier → Run workflow**.

## RGPD

Le dépôt est public. Il ne contient ni CV, ni lettre, ni coordonnées, ni le détail de mes candidatures entreprise par entreprise : seulement des totaux.
La base d'entreprises ne contient aucun nom de personne.
