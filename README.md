# Chef de produit, le marché compté

Site de Baptiste Veloso Ferreira pour le séminaire métiers du M2 Marketing opérationnel et digital (IAE Clermont Auvergne).
Il compte le marché des **stages et alternances de chef de produit** à partir des offres publiées, chaque matin, et dit ce que j'en conclus pour ma propre recherche (stage de fin d'études à partir de janvier 2027, ou alternance).

Page publiée : `index.html` à la racine (GitHub Pages).

## Le métier

- Intitulé visé : **assistant(e) chef de produit** (stage ou alternance).
- Code ROME : **M1703**, Management et gestion de produit (Métierscope, France Travail).
- Variantes suivies : chef de produit, chef de marque, chef de gamme, chef de marché, product manager, brand manager.

## Les questions posées au marché

1. Quels secteurs recrutent le plus de stagiaires et d'alternants chefs de produit ?
2. Quelles compétences et quels outils reviennent le plus dans les offres ?
3. Où se concentrent les offres, et quand les entreprises recrutent-elles ?
4. Quelle gratification et quel rythme sont proposés ?

## Ce que contient le site

| Section | Contenu |
|---|---|
| 1. Le métier | Nombre d'offres par intitulé, intitulés réellement employés |
| 2. Les offres | Volume jour après jour, carte, régions, Clermont et alentours, gratifications affichées, dates de début |
| 3. Compétences | Qualités, logiciels et savoir-faire demandés, comparés à ma formation et à mon CV |
| 4. Évolution | Thèmes qui montent dans les annonces, APEC et WEF, avis des intervenants, mes questions |
| 5. Acteurs | Secteurs, entreprises qui publient, marché caché du Puy-de-Dôme, recruteurs en alternance sans offre, professionnels |
| 6. Actions | Où en sont mes candidatures (totaux), trois actions datées avec leur preuve |
| 7. Fabrication | Canaux, chaîne automatique, règle RGPD |
| Ma position | Ce que je décide à partir des chiffres |

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
contenu.json              textes écrits à la main (intervenants, actions, position)
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
La base d'entreprises ne contient aucun nom de personne. Les professionnels notés à la main (section Acteurs) le sont pour une seule finalité, ma candidature, avec leur seul nom, poste et entreprise ; toute personne peut demander à être retirée.
