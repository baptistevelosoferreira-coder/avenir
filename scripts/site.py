"""Construit index.html à partir des données datées du dossier data/ et des textes de contenu.json.

Chaque chiffre affiché porte sa source : canal, requête, date et limites.
Relancer : python scripts/site.py  (aucune dépendance hors bibliothèque standard)
"""
import csv
import datetime as dt
import glob
import html
import json
import math
import os
import re
import statistics
import unicodedata
from collections import Counter, defaultdict

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(RACINE, "data")
DEPOT = "https://github.com/baptistevelosoferreira-coder/avenir"
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


# ------------------------------------------------------------------ utilitaires

def e(x):
    return html.escape(str(x if x is not None else ""))


def norm(t):
    t = unicodedata.normalize("NFD", str(t or ""))
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def fr_date(iso, an=True):
    try:
        d = dt.date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso)
    return f"{d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]}" + (f" {d.year}" if an else "")


def nombre(n):
    if n is None:
        return "–"
    if isinstance(n, float):
        n = round(n)
    return f"{n:,}".replace(",", " ")


def pct(a, b):
    return f"{round(100 * a / b)} %" if b else "–"


def lire_csv(chemin):
    if not os.path.exists(chemin):
        return []
    with open(chemin, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def lire_json(chemin, defaut=None):
    if not os.path.exists(chemin):
        return defaut
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def lien_data(rel, texte=None):
    return f'<a href="{DEPOT}/blob/main/{e(rel)}">{e(texte or rel)}</a>'


def source(canal, requete, date, limites, fichier=None):
    """Bloc « d'où vient ce chiffre » placé sous chaque graphique."""
    if isinstance(requete, dict):
        requete = " · ".join(f"{k} = {v}" for k, v in requete.items())
    f = f" · données : {lien_data(fichier)}" if fichier else ""
    return (f'<details class="src"><summary>Source : {e(canal)}, {e(fr_date(date))}</summary>'
            f'<dl><dt>Canal</dt><dd>{e(canal)}{f}</dd><dt>Requête</dt><dd><code>{e(requete)}</code></dd>'
            f'<dt>Date</dt><dd>{e(fr_date(date))}</dd><dt>Limites</dt><dd>{e(limites)}</dd></dl></details>')


def barres(lignes, maxi=None, unite="", classe=""):
    """lignes : (libellé, valeur, note facultative, classe facultative)"""
    if not lignes:
        return '<p class="vide">Pas encore de données.</p>'
    maxi = maxi or max(v for _, v, *_ in lignes) or 1
    out = []
    for l in lignes:
        lab, v = l[0], l[1]
        note = l[2] if len(l) > 2 else ""
        cl = l[3] if len(l) > 3 else ""
        out.append(f'<div class="hb {cl}"><div class="lab">{lab}</div><div class="bar"><span style="width:{max(1.5, 100 * v / maxi):.1f}%"></span></div>'
                   f'<div class="val">{nombre(v)}{unite}{f" <small>{note}</small>" if note else ""}</div></div>')
    return f'<div class="hbars {classe}">' + "".join(out) + "</div>"


# ------------------------------------------------------------------ lieux

IDF = r"paris|la defense|puteaux|boulogne|issy|neuilly|rueil|levallois|courbevoie|nanterre|saint-ouen|saint-denis|montreuil|ivry|charenton|rungis|velizy|guyancourt|versailles|massy|clichy|seine-saint-denis|hauts-de-seine|val-de-marne|yvelines|essonne|val-d'oise|seine-et-marne|ile-de-france|villejuif|saint-cloud|suresnes|clamart|meudon|montrouge|vincennes|noisy|cergy|evry|saclay|roissy|creteil|pantin|aubervilliers|gennevilliers|asnieres|colombes|saint-germain-en-laye|antony|\((75|77|78|91|92|93|94|95)\)|\b(75|77|78|91|92|93|94|95)\d{3}\b"
VILLES = [
    (r"annecy", "Annecy", 6.13, 45.9), (r"sophia|mougins|valbonne|biot", "Sophia Antipolis", 7.02, 43.6), (r"\bnice\b", "Nice", 7.26, 43.7),
    (r"marseille|aix-en-provence|aubagne|vitrolles", "Marseille", 5.4, 43.3), (r"montpellier", "Montpellier", 3.88, 43.61),
    (r"toulouse|blagnac", "Toulouse", 1.44, 43.6), (r"bordeaux|blanquefort|merignac|pessac", "Bordeaux", -0.58, 44.84),
    (r"nantes|reze|saint-herblain|carquefou", "Nantes", -1.55, 47.22), (r"rennes|cesson", "Rennes", -1.68, 48.11),
    (r"angers", "Angers", -0.55, 47.47), (r"\btours\b", "Tours", 0.69, 47.39), (r"orleans", "Orléans", 1.9, 47.9),
    (r"contres|controis", "Contres", 1.43, 47.42), (r"lyon|limonest|villeurbanne|ecully|dardilly|vaulx|bron|venissieux|saint-priest", "Lyon", 4.84, 45.76),
    (r"saint-etienne|saint-genest", "Saint-Étienne", 4.39, 45.44), (r"grenoble|meylan", "Grenoble", 5.72, 45.19),
    (r"chambery", "Chambéry", 5.92, 45.57), (r"clermont|lempdes|cournon|riom|aubiere|puy-de-dome", "Clermont-Ferrand", 3.08, 45.78),
    (r"dijon", "Dijon", 5.04, 47.32), (r"strasbourg|mundolsheim|vendenheim|illkirch|schiltigheim", "Strasbourg", 7.75, 48.58),
    (r"mulhouse", "Mulhouse", 7.34, 47.75), (r"\bmetz\b", "Metz", 6.18, 49.12), (r"nancy", "Nancy", 6.18, 48.69), (r"reims", "Reims", 4.03, 49.26),
    (r"lille|roubaix|tourcoing|villeneuve-d'ascq|marcq|lesquin|wasquehal", "Lille", 3.1, 50.66),
    (r"arras|vitry-en-artois|douai|\blens\b", "Arras", 2.9, 50.3), (r"amiens", "Amiens", 2.3, 49.9), (r"rouen", "Rouen", 1.1, 49.44),
    (r"\bcaen\b", "Caen", -0.36, 49.18), (r"limoges", "Limoges", 1.26, 45.83), (r"poitiers", "Poitiers", 0.34, 46.58),
    (r"la rochelle", "La Rochelle", -1.15, 46.16), (r"\bpau\b", "Pau", -0.37, 43.3), (r"avignon", "Avignon", 4.8, 43.95),
    (r"valence", "Valence", 4.89, 44.93), (r"troyes", "Troyes", 4.07, 48.3), (r"besancon", "Besançon", 6.02, 47.24),
]


def lieu(texte):
    s = norm(texte)
    meilleur, pos = None, 10 ** 9
    m = re.search(IDF, s)
    if m:
        meilleur, pos = ("Île-de-France", 2.35, 48.86, True), m.start()
    for motif, nom, lon, lat in VILLES:
        r = re.search(motif, s)
        if r and r.start() < pos:
            meilleur, pos = (nom, lon, lat, False), r.start()
    return meilleur


FRANCE = [[2.37, 51.05], [3.0, 50.8], [4.2, 50.35], [4.85, 50.15], [5.8, 49.55], [6.4, 49.47], [7.6, 49.05], [8.2, 48.97], [7.75, 48.3], [7.6, 47.6], [7.0, 47.5], [6.9, 47.35], [6.1, 46.6], [6.1, 46.15], [6.8, 46.4], [7.0, 45.9], [6.8, 45.6], [7.15, 45.25], [6.6, 45.0], [7.0, 44.2], [7.5, 43.78], [7.0, 43.55], [6.2, 43.1], [5.4, 43.2], [4.6, 43.4], [3.9, 43.5], [3.1, 43.1], [3.05, 42.45], [2.5, 42.35], [1.7, 42.5], [0.7, 42.8], [-0.3, 42.85], [-1.4, 43.2], [-1.8, 43.4], [-1.25, 44.6], [-1.2, 45.7], [-1.15, 46.2], [-2.1, 46.8], [-2.5, 47.3], [-3.3, 47.7], [-4.4, 47.9], [-4.8, 48.4], [-4.5, 48.65], [-3.5, 48.85], [-2.3, 48.65], [-1.6, 48.65], [-1.6, 49.65], [-1.25, 49.7], [-1.1, 49.35], [0.1, 49.45], [0.2, 49.7], [1.4, 50.1], [1.6, 50.4], [1.6, 50.9]]
CORSE = [[9.4, 43.0], [9.55, 42.6], [9.4, 41.4], [9.1, 41.4], [8.6, 41.9], [8.6, 42.4], [9.3, 42.7]]


def proj(lon, lat):
    return (lon + 5.2) * 0.69 * 36 + 8, (51.4 - lat) * 36 + 8


def carte(groupes, titre):
    """groupes : liste (nom, lon, lat, n, idf)"""
    chemin = lambda pts: "M" + "L".join(f"{proj(*p)[0]:.1f},{proj(*p)[1]:.1f}" for p in pts) + "Z"
    s = [f'<svg viewBox="0 0 420 410" role="img" aria-label="{e(titre)}"><path class="land" d="{chemin(FRANCE)}"/><path class="land" d="{chemin(CORSE)}"/>']
    hx, hy = proj(3.08, 45.78)
    s.append(f'<circle class="home" cx="{hx:.1f}" cy="{hy:.1f}" r="7"/>')
    places = [(hx - 82, hy - 8, hx + 8, hy + 8)]
    bulles = {g[0]: (*proj(g[1], g[2]), 4 + math.sqrt(g[3]) * 4.2) for g in groupes}
    for nom, lon, lat, n, idf in sorted(groupes, key=lambda g: -g[3]):
        x, y = proj(lon, lat)
        r = bulles[nom][2]
        s.append(f'<circle class="bub{" idf" if idf else ""}" cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}"><title>{e(nom)} : {n}</title></circle>')
        if n > 1:
            s.append(f'<text class="num{" idf" if idf else ""}" x="{x:.1f}" y="{y:.1f}">{n}</text>')
        w = 6.2 * len(nom)
        cands = [(x, y + r + 13, "middle"), (x, y - r - 5, "middle")] if idf else []
        cands += [(x - r - 4, y + 4, "end"), (x + r + 4, y + 4, "start")] if lon > 6.3 else [(x + r + 4, y + 4, "start"), (x - r - 4, y + 4, "end")]
        cands += [(x, y + r + 12, "middle"), (x, y - r - 4, "middle")]
        autres = [(bx - br, by - br, bx + br, by + br) for k, (bx, by, br) in bulles.items() if k != nom]
        for lx, ly, an in cands:
            x0 = lx - (w if an == "end" else w / 2 if an == "middle" else 0)
            boite = (x0, ly - 10, x0 + w, ly + 2)
            if not any(boite[0] < b[2] and b[0] < boite[2] and boite[1] < b[3] and b[1] < boite[3] for b in places + autres):
                places.append(boite)
                s.append(f'<text class="city" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{an}">{e(nom)}</text>')
                break
    s.append(f'<text class="city muted" x="{hx - 10:.1f}" y="{hy + 4:.1f}" text-anchor="end">Clermont-Fd</text></svg>')
    return "".join(s)


def courbe(points, hauteur=170, largeur=640, unite="", libelles=None):
    """points : liste (date_iso, valeur) ; ligne simple avec points et étiquettes."""
    if not points:
        return '<p class="vide">Pas encore de données.</p>'
    vals = [v for _, v in points]
    vmax = max(vals) * 1.15 or 1
    g, d, h, b = 40, 12, 14, 26
    W, H = largeur - g - d, hauteur - h - b
    x = lambda i: g + (W * i / max(1, len(points) - 1))
    y = lambda v: h + H - H * v / vmax
    s = [f'<svg class="line" viewBox="0 0 {largeur} {hauteur}" role="img">']
    for k in range(0, 5):
        vv = vmax * k / 4
        s.append(f'<line class="grid" x1="{g}" x2="{largeur - d}" y1="{y(vv):.1f}" y2="{y(vv):.1f}"/><text class="ax" x="{g - 6}" y="{y(vv) + 4:.1f}" text-anchor="end">{nombre(round(vv))}</text>')
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(points))
    s.append(f'<polygon class="area" points="{g},{y(0):.1f} {pts} {x(len(points) - 1):.1f},{y(0):.1f}"/><polyline class="ln" points="{pts}"/>')
    pas = max(1, math.ceil(len(points) / 7))
    for i, (dte, v) in enumerate(points):
        s.append(f'<circle class="pt" cx="{x(i):.1f}" cy="{y(v):.1f}" r="3.2"><title>{fr_date(dte)} : {nombre(v)}{unite}</title></circle>')
        dernier_i = len(points) - 1
        if i == dernier_i or (i % pas == 0 and dernier_i - i >= pas):
            s.append(f'<text class="ax" x="{x(i):.1f}" y="{hauteur - 8}" text-anchor="{"end" if i == len(points) - 1 and i else "middle"}">{e(fr_date(dte, False))}</text>')
    i = len(points) - 1
    s.append(f'<text class="last" x="{x(i) - 6:.1f}" y="{y(points[-1][1]) - 9:.1f}" text-anchor="end">{nombre(points[-1][1])}{unite}</text></svg>')
    return "".join(s)


# ------------------------------------------------------------------ lexiques

QUALITES = [("Rigueur", r"rigueur|rigoureu"), ("Analyse et synthèse", r"analys|synthes"),
            ("Relationnel, communication", r"relationnel|communication|sens du contact|ecoute"), ("Autonomie", r"autonom"),
            ("Organisation", r"organis"), ("Esprit d'équipe", r"equipe|collabor"), ("Curiosité", r"curio|curieu"),
            ("Créativité", r"creati"), ("Initiative, force de proposition", r"initiative|proacti|force de proposition"),
            ("Adaptabilité, polyvalence", r"adaptab|polyvalen")]
OUTILS = [("Excel", r"excel", "cv"), ("PowerPoint", r"powerpoint", "cv"), ("Pack Office (sans détail)", r"pack office|suite office", "cv"),
          ("Réseaux sociaux", r"reseaux sociaux|social media", "cv"), ("Canva", r"canva", "cv"),
          ("IA générative, Copilot", r"copilot|\bia\b|intelligence artificielle|chatgpt", "cv"), ("Word", r"\bword\b", "non"),
          ("Panels Nielsen, IRI, Kantar, Circana", r"nielsen|\biri\b|kantar|circana", "non"), ("Suite Adobe", r"adobe|photoshop|illustrator|indesign", "non"),
          ("Power BI", r"power ?bi", "non"), ("SAP", r"\bsap\b", "non"), ("Google Analytics, GA4", r"google analytics|\bga4\b", "non"),
          ("CRM, Salesforce, HubSpot", r"\bcrm\b|salesforce|hubspot", "non")]
SAVOIRS = [("Lancement de produit", r"lancement|lancer", "formation"), ("Étude de marché, veille", r"etude(s)? de marche|veille|benchmark", "formation"),
           ("Gestion de gamme, assortiment", r"gamme|assortiment", "formation"), ("Packaging, chaîne graphique", r"packaging|emballage|chaine graphique|bat\b", "non"),
           ("Analyse des ventes, performance", r"performance|ventes|sell[- ]?(in|out)|kpi|reporting|tableau de bord", "formation"),
           ("Marketing digital, contenus", r"digital|contenu|site web|e-?commerce", "formation"),
           ("Trade marketing, force de vente", r"trade|force de vente|commerciaux|argumentaire|merchandising", "formation"),
           ("Gestion de projet, agences", r"projet|agence|prestataire", "formation"), ("Budget, P&L, prix", r"budget|p&l|rentabilit|prix|marge", "non"),
           ("Réglementation produit", r"reglement|affaires reglementaires|conformit|normes", "non"),
           ("Anglais", r"anglais|english", "cv"), ("RSE, éco-conception", r"\brse\b|eco-?conception|durable|developpement durable", "non")]
TENDANCES = [("IA, intelligence artificielle", r"\bia\b|intelligence artificielle|\bai\b|chatgpt|copilot"), ("RSE, durable, éco-conception", r"\brse\b|durable|eco-?conception|impact"),
             ("Data, analyse de données", r"\bdata\b|donnees|analytics|power ?bi"), ("Digital, social media", r"digital|social|reseaux sociaux|influence"),
             ("E-commerce, omnicanal", r"e-?commerce|omnicanal|marketplace|amazon"), ("Innovation", r"innovation|innover"),
             ("International, export", r"international|export|europe|global"), ("Santé, bien-être", r"sante|bien-etre|nutrition|well")]


def compter(textes, lexique):
    return [(nom, sum(1 for t in textes if re.search(motif, t)), *rest) for nom, motif, *rest in lexique]


def gratif(remu):
    s = norm(remu)
    h = re.search(r"(\d+[,.]\d+)\s*€[^0-9]{0,14}heure", s)
    if h:
        return round(float(h.group(1).replace(",", ".")) * 151.67), None
    nums = [int(re.sub(r"[\s  .]", "", m.group(1))) for m in re.finditer(r"(\d{1,2}[\s  .]\d{3}|\d{3,5})(?:[,.]\d{1,2})?\s*€", s)]
    if re.search(r"par an|/\s*an\b|annuel", s):
        nums = [n / 12 if n > 5000 else n for n in nums]
    nums = [round(n) for n in nums if 400 <= n <= 3500]
    if not nums or re.search(r"estimation|grille", s):
        return None, None
    return (min(nums), max(nums)) if len(nums) > 1 else (nums[0], None)


def famille_intitule(t):
    s = norm(t)
    if re.search(r"chef(fe)? de marque|brand", s):
        return "Chef de marque, brand manager"
    if re.search(r"chef(fe)? de gamme|category", s):
        return "Chef de gamme, category manager"
    if re.search(r"product (marketing )?manager|product marketing", s):
        return "Product (marketing) manager"
    if re.search(r"assistant", s) and re.search(r"chef(fe|\.fe|\.e)? de produit", s):
        return "Assistant(e) chef de produit"
    if re.search(r"junior", s) and re.search(r"chef(fe|\.fe|\.e)? de produit", s):
        return "Chef de produit junior"
    if re.search(r"chef(fe|\.fe|\.e|\(fe\))? de produit", s):
        return "Chef de produit (stage ou alternance)"
    if re.search(r"marketing produit|chef de projet marketing|assistant marketing", s):
        return "Marketing produit, chef de projet marketing"
    return "Autre intitulé"


# ------------------------------------------------------------------ construction

def construire():
    contenu = lire_json(os.path.join(RACINE, "contenu.json"), {})
    jours = sorted(d for d in os.listdir(DATA) if re.match(r"\d{4}-\d{2}-\d{2}$", d) and os.path.isdir(os.path.join(DATA, d)))
    dernier = jours[-1] if jours else None
    comptages_par_jour = {j: lire_json(os.path.join(DATA, j, "comptages.json"), {}) for j in jours}
    comptes = (comptages_par_jour.get(dernier) or {}).get("comptages", []) if dernier else []
    trouve = lambda canal, debut: next((c for c in comptes if c["canal"] == canal and c["mesure"].startswith(debut)), None)

    # Veille stage et alternance (série du 5 au 17 novembre, puis la collecte « avenir »)
    veille = lire_json(os.path.join(DATA, "veille-stage-alternance", "serie.json"), {"serie": []})
    serie = [(s["date"], s["retenues"]) for s in veille["serie"]]
    annonces = lire_csv(os.path.join(DATA, "annonces-lues.csv"))
    textes_annonces = [norm(a["profil"] + " " + a["missions"]) for a in annonces]
    profils = [norm(a["profil"]) for a in annonces if a["profil"] and "non detaille" not in norm(a["profil"])]
    retenues_toutes = []
    for f in sorted(glob.glob(os.path.join(DATA, "veille-stage-alternance", "*.csv"))):
        for r in lire_csv(f):
            r["_jour"] = os.path.basename(f)[:10]
            retenues_toutes.append(r)
    uniques = {}
    for r in retenues_toutes:
        uniques.setdefault(r["id"], r)

    adz = lire_csv(os.path.join(DATA, dernier, "offres_adzuna.csv")) if dernier else []
    ftv = lire_csv(os.path.join(DATA, dernier, "offres_france_travail.csv")) if dernier else []
    lba = lire_csv(os.path.join(DATA, dernier, "offres_lba.csv")) if dernier else []
    recr = lire_csv(os.path.join(DATA, dernier, "recruteurs_lba.csv")) if dernier else []
    stats = lire_json(os.path.join(DATA, dernier, "stats_adzuna.json"), {}) if dernier else {}
    ent = lire_csv(os.path.join(DATA, "entreprises_63.csv"))
    ent_jours = sorted(glob.glob(os.path.join(DATA, "*", "entreprises_63.json")))
    ent_meta = lire_json(ent_jours[-1], {}) if ent_jours else {}
    suivi = lire_json(os.path.join(DATA, "suivi-candidatures.json"), {})

    n_annonces = len(annonces)
    stage_annonces = sum(1 for a in annonces if a["contrat"] != "alternance")

    # -------- Section 1 : intitulés
    variantes = [c for c in comptes if c["canal"] == "Adzuna" and "titre contenant" in c["mesure"]]
    familles = Counter(famille_intitule(r["intitule"]) for r in uniques.values())
    s1 = []
    if variantes:
        joli = lambda v: (v[0].upper() + v[1:]).replace("marche", "marché")
        lignes = [(e(joli(re.search(r"« (.+?) »", c["mesure"]).group(1))), c["valeur"]) for c in variantes]
        c0 = variantes[0]
        s1.append(f'<div class="card"><h3>Combien d\'offres de stage ou d\'alternance pour chaque intitulé</h3>'
                  f'<p class="hint">Offres actives des 30 derniers jours dont le titre contient l\'intitulé, et qui parlent de stage ou d\'alternance.</p>'
                  f'{barres(sorted(lignes, key=lambda l: -l[1]))}'
                  f'{source("Adzuna (API)", "title_only = <intitulé> · what_or = stage, stagiaire, internship, alternance, alternant, apprentissage, apprenti · max_days_old = 30", c0["date"], c0["limites"] + " « Product manager » mélange marketing et produit numérique.", f"data/{dernier}/comptages.json")}</div>')
    s1.append(f'<div class="card"><h3>Les intitulés réellement employés dans les offres retenues</h3>'
              f'<p class="hint">{len(uniques)} offres différentes retenues par la veille quotidienne entre le {fr_date(veille["serie"][0]["date"]) if veille["serie"] else "–"} et le {fr_date(veille["serie"][-1]["date"]) if veille["serie"] else "–"}, classées par famille d\'intitulé.</p>'
              f'{barres([(e(k), v) for k, v in familles.most_common()])}'
              f'{source("Veille quotidienne (Adzuna, La bonne alternance, Jooble)", "; ".join(veille.get("requetes_adzuna", [])), veille["serie"][-1]["date"] if veille["serie"] else "", veille.get("limites", ""), "data/veille-stage-alternance/")}</div>')

    # -------- Section 2 : volume, contrats, géographie, gratifications, débuts
    pts_brutes = [(s["date"], s["brutes"]) for s in veille["serie"]]
    s2 = []
    s2.append(f'<div class="card"><h3>Offres de stage et d\'alternance retenues chaque matin</h3>'
              f'<p class="hint">{len(serie)} extractions datées. Chaque point compte les offres de moins de 14 jours qui passent le filtre « chef de produit, stage ou alternance, en France ».</p>'
              f'{courbe(serie)}'
              f'<p class="hint">Avant filtre, les requêtes renvoient de {nombre(min(v for _, v in pts_brutes)) if pts_brutes else "–"} à {nombre(max(v for _, v in pts_brutes)) if pts_brutes else "–"} résultats bruts par jour.</p>'
              f'{source("Veille quotidienne (GitHub Actions)", veille.get("filtre", ""), veille["serie"][-1]["date"] if veille["serie"] else "", veille.get("limites", ""), "data/veille-stage-alternance/serie.json")}</div>')
    # séries de la nouvelle collecte (stage / alternance)
    ser_stage = [(j, next((c["valeur"] for c in comptages_par_jour[j].get("comptages", []) if c["mesure"].startswith("chef de produit : stage")), None)) for j in jours]
    ser_alt = [(j, next((c["valeur"] for c in comptages_par_jour[j].get("comptages", []) if c["mesure"].startswith("chef de produit : alternance")), None)) for j in jours]
    ser_stage = [(j, v) for j, v in ser_stage if v is not None]
    ser_alt = [(j, v) for j, v in ser_alt if v is not None]
    c_stage, c_alt = trouve("Adzuna", "chef de produit : stage"), trouve("Adzuna", "chef de produit : alternance")
    c_tous = trouve("Adzuna", "chef de produit, tous contrats")
    ft_tot, ft_alt = trouve("France Travail", "offres ROME M1703, France"), trouve("France Travail", "offres ROME M1703, alternance (")
    tiles = []
    if c_stage:
        tiles.append((nombre(c_stage["valeur"]), "offres de stage « chef de produit » actives (Adzuna, 30 jours)"))
    if c_alt:
        tiles.append((nombre(c_alt["valeur"]), "offres d'alternance « chef de produit » actives (Adzuna, 30 jours)"))
    if c_tous:
        tiles.append((nombre(c_tous["valeur"]), "offres « chef de produit » tous contrats, pour comparaison"))
    if ft_tot:
        tiles.append((nombre(ft_tot["valeur"]), "offres France Travail sur le code ROME M1703"))
    if ft_alt:
        tiles.append((nombre(ft_alt["valeur"]), "dont alternances (France Travail)"))
    if tiles:
        s2.append('<div class="tiles">' + "".join(f'<div class="tile"><b>{v}</b><span>{l}</span></div>' for v, l in tiles) + "</div>"
                  + source("Adzuna et France Travail (API)", "title_only = chef de produit · what_or = stage… / alternance… · max_days_old = 30 ; France Travail : codeROME = M1703", dernier,
                           "Adzuna repère « stage » ou « alternance » n'importe où dans l'annonce : une offre de CDI qui cite « stagiaire » peut être comptée. France Travail publie peu de stages.",
                           f"data/{dernier}/comptages.json"))
    if len(ser_stage) > 1:
        s2.append(f'<div class="card"><h3>Stages « chef de produit » actifs, jour après jour</h3>{courbe(ser_stage)}'
                  f'{source("Adzuna (API)", "title_only = chef de produit · what_or = stage stagiaire internship · max_days_old = 30", ser_stage[-1][0], "Une offre reste comptée 30 jours ; le nombre bouge avec les publications et les retraits.", "data/")}</div>')

    # contrats dans les offres retenues
    contrats = Counter("Alternance" if re.search(r"altern|apprenti|professionnalisation", norm(r["contrat"] + " " + r["intitule"])) else "Stage" for r in uniques.values())
    lieux_ret = [lieu(r["lieu"]) for r in uniques.values()]
    n_loc = sum(1 for l in lieux_ret if l)
    n_idf = sum(1 for l in lieux_ret if l and l[3])
    n_clermont = sum(1 for l in lieux_ret if l and l[0] == "Clermont-Ferrand")
    groupes = defaultdict(lambda: [None, None, 0, False])
    for l in lieux_ret:
        if l:
            g = groupes[l[0]]
            g[0], g[1], g[3] = l[1], l[2], l[3]
            g[2] += 1
    gl = [(k, v[0], v[1], v[2], v[3]) for k, v in groupes.items()]
    liste_villes = "".join(f"<li><span>{e(k)}</span><b>{n}</b></li>" for k, _, _, n, _ in sorted(gl, key=lambda g: -g[3])[:12])
    s2.append(f'<div class="card"><h3>Où sont les offres</h3>'
              f'<p class="hint">{len(uniques)} offres retenues entre le 5 novembre et aujourd\'hui. Île-de-France : <b>{n_idf}</b> ({pct(n_idf, n_loc)} des offres localisées). '
              f'Autour de Clermont-Ferrand : <b>{n_clermont}</b>. Le cercle pointillé marque Clermont-Ferrand.</p>'
              f'<div class="mapwrap">{carte(gl, "Carte des offres de stage et d alternance retenues")}<ul class="cities">{liste_villes}</ul></div>'
              f'{source("Veille quotidienne", "Lieu indiqué par l annonce, rattaché à une ville par le script", veille["serie"][-1]["date"] if veille["serie"] else "", "Les lieux flous (« France », siège non précisé) ne sont pas placés. Une offre ancienne de 14 jours au plus est comptée une fois.", "data/veille-stage-alternance/")}</div>')
    geo = (stats.get("geodata") or {}).get("donnees", {}).get("locations", [])
    if geo:
        lignes = sorted([(e(g["location"]["display_name"].replace(", France", "")), g["count"]) for g in geo if g.get("count")], key=lambda l: -l[1])[:10]
        s2.append(f'<div class="card"><h3>Répartition par région (Adzuna)</h3>{barres(lignes)}'
                  f'{source("Adzuna (API geodata)", stats["geodata"]["requete"], stats["geodata"]["date"], "Recherche du mot-clé dans toute l annonce, pas seulement le titre.", f"data/{dernier}/stats_adzuna.json")}</div>')
    zones = [c for c in comptes if c["canal"] == "Adzuna" and re.search(r"stage ou alternance : (Clermont|Puy|Auvergne|Île|Lyon)", c["mesure"])]
    if zones:
        s2.append(f'<div class="card"><h3>Près de chez moi</h3>{barres([(e(c["mesure"].split(" : ")[1].replace(" (30 jours)", "")), c["valeur"]) for c in zones])}'
                  f'{source("Adzuna (API)", "title_only = chef de produit · what_or = stage… alternance… · where = <lieu> · max_days_old = 30", zones[0]["date"], zones[0]["limites"], f"data/{dernier}/comptages.json")}</div>')

    # gratifications affichées
    grat = []
    for a in annonces:
        mn, mx = gratif(a["remuneration_affichee"])
        if mn and a["contrat"] != "alternance":
            grat.append((a["entreprise"], mn, mx))
    vals = [mx or mn for _, mn, mx in grat]
    med = statistics.median(vals) if vals else None
    if grat:
        lo, hi = 600, 2200
        X = lambda v: (min(hi, max(lo, v)) - lo) / (hi - lo) * 100
        rows = "".join(f'<div class="payrow"><div>{e(n)}</div><div class="track"><span class="med" style="left:{X(med):.1f}%"></span>'
                       + (f'<span class="rg" style="left:{X(mn):.1f}%;width:{X(mx) - X(mn):.1f}%"></span><span class="pt" style="left:{X(mx):.1f}%"></span>' if mx else f'<span class="pt" style="left:{X(mn):.1f}%"></span>')
                       + f'</div><div class="val">{nombre(mn)}{"–" + nombre(mx) if mx else ""} €</div></div>' for n, mn, mx in sorted(grat, key=lambda g: -(g[2] or g[1])))
        s2.append(f'<div class="card"><h3>Gratifications affichées (stage, brut mensuel)</h3>'
                  f'<p class="hint"><b>{len(grat)}</b> des {stage_annonces} annonces de stage lues affichent un montant ; médiane <b>{nombre(med)} €</b> par mois (haut de fourchette quand le montant dépend du niveau d\'études, ce qui correspond à un Bac+5). '
                  f'Pour comparer : l\'insertion à un an des diplômés de l\'IAE est de 2 433 € brut médian (chiffre de la rentrée 2026).</p>'
                  f'<div class="pay">{rows}<div class="payrow"><div></div><div class="axis"><span>600 €</span><span>1 000 €</span><span>1 400 €</span><span>1 800 €</span><span>2 200 €</span></div><div></div></div></div>'
                  f'<p class="warn">Montant affiché dans l\'annonce, pas un salaire constaté : une gratification de stage n\'est pas un salaire, et beaucoup d\'annonces ne l\'indiquent pas.</p>'
                  f'{source("Annonces lues en entier", "Champ « rémunération » des annonces retenues pour un brief, montant converti en brut mensuel (horaire × 151,67 ; annuel ÷ 12)", annonces[-1]["date_veille"] if annonces else "", "Petit échantillon, biaisé vers les offres qui m intéressent ; les annonces sans montant sont exclues.", "data/annonces-lues.csv")}</div>')

    # dates de début
    debuts = Counter()
    for a in annonces:
        d = norm(a["debut"])
        k = ("Décembre 2026" if "decembre" in d else "Janvier 2027" if "janv" in d else "Février 2027" if "fevr" in d else "Mars 2027" if "mars" in d
             else "Avril 2027" if "avril" in d else "Dès que possible" if "possible" in d else "Non précisé")
        debuts[k] += 1
    duree6 = sum(1 for a in annonces if "6 mois" in norm(a["duree"]))
    ordre = ["Décembre 2026", "Janvier 2027", "Février 2027", "Mars 2027", "Avril 2027", "Dès que possible", "Non précisé"]
    s2.append(f'<div class="card"><h3>Quand commencent les stages</h3>'
              f'<div class="months">' + "".join(f'<div class="m{" hl" if k == "Janvier 2027" else ""}"><b>{debuts[k]}</b><span>{k}</span></div>' for k in ordre if debuts[k]) + "</div>"
              f'<p class="hint">{duree6} annonces sur {n_annonces} précisent une durée de 6 mois. Je suis disponible à partir de janvier 2027.</p>'
              f'{source("Annonces lues en entier", "Champ « début » de chaque annonce", annonces[-1]["date_veille"] if annonces else "", "Une annonce sur trois ne donne pas de date de début.", "data/annonces-lues.csv")}</div>')

    # -------- Section 3 : compétences et outils
    formation = set(contenu.get("formation_donne", []))
    nq = compter(profils, QUALITES)
    no = compter(textes_annonces, OUTILS)
    ns = compter(textes_annonces, SAVOIRS)
    adz_txt = [norm(r["intitule"] + " " + r["description_extrait"]) for r in adz]
    ft_comp = Counter(c.strip() for r in ftv for c in (r.get("competences") or "").split("|") if c.strip())
    badge = lambda k: {"cv": '<i class="b ok">sur mon CV</i>', "formation": '<i class="b ok">dans ma formation</i>', "non": '<i class="b gap">la formation ne le donne pas</i>'}.get(k, "")
    s3 = [f'<div class="grid2"><div class="card"><h3>Qualités demandées</h3><p class="hint">Nombre d\'annonces qui citent la qualité, sur {len(profils)} profils détaillés.</p>'
          f'{barres(sorted([(e(n), v) for n, v in nq], key=lambda l: -l[1]), maxi=len(profils))}</div>'
          f'<div class="card"><h3>Logiciels et outils</h3><p class="hint">Nombre d\'annonces qui les citent (missions et profil), sur {n_annonces}.</p>'
          f'{barres(sorted([(e(n) + " " + badge(k), v) for n, v, k in no if v], key=lambda l: -l[1]), maxi=n_annonces)}</div></div>',
          f'<div class="card"><h3>Savoir-faire attendus</h3><p class="hint">Missions et profil des {n_annonces} annonces lues, confrontés à ma maquette de M2 (mix marketing, gestion de gamme, diagnostic stratégique, marketing digital) et à mon CV.</p>'
          f'{barres(sorted([(e(n) + " " + badge(k), v) for n, v, k in ns if v], key=lambda l: -l[1]), maxi=n_annonces)}'
          f'{source("Annonces lues en entier", "Mots-clés cherchés dans les champs missions et profil (liste dans scripts/site.py)", annonces[-1]["date_veille"] if annonces else "", "Comptage par mots-clés : une annonce qui dit « rigueur » une fois compte autant qu une annonce qui insiste ; 4 annonces sans profil détaillé.", "data/annonces-lues.csv")}</div>']
    if adz_txt:
        na = compter(adz_txt, OUTILS + [(n, m, k) for n, m, k in SAVOIRS])
        s3.append(f'<div class="card"><h3>Le même comptage sur {len(adz_txt)} offres Adzuna du jour</h3>'
                  f'{barres(sorted([(e(n), v) for n, v, *_ in na if v], key=lambda l: -l[1])[:12])}'
                  f'{source("Adzuna (API)", "title_only = chef de produit · what_or = stage… alternance… · max_days_old = 30 · 50 offres par page", dernier, "Adzuna ne fournit qu un extrait de 500 caractères par annonce : les outils cités plus bas dans l annonce sont manqués.", f"data/{dernier}/offres_adzuna.csv")}</div>')
    if ft_comp:
        s3.append(f'<div class="card"><h3>Compétences déclarées dans les offres France Travail (ROME M1703)</h3>'
                  f'{barres([(e(k), v) for k, v in ft_comp.most_common(12)])}'
                  f'{source("France Travail (API Offres d emploi v2)", "codeROME = M1703", dernier, "Compétences choisies par le recruteur dans la liste du ROME ; tous contrats confondus.", f"data/{dernier}/offres_france_travail.csv")}</div>')
    manque = [n for n, v, k in no + ns if k == "non" and v]

    # -------- Section 4 : évolution
    dates_v = [s["date"] for s in veille["serie"]]
    moitie = dates_v[len(dates_v) // 2] if dates_v else ""
    debut_t = [norm(r["intitule"] + " " + r["description_extrait"]) for r in retenues_toutes if r["_jour"] < moitie]
    fin_t = [norm(r["intitule"] + " " + r["description_extrait"]) for r in retenues_toutes if r["_jour"] >= moitie]
    tend = []
    for nom, motif in TENDANCES:
        a = 100 * sum(1 for t in debut_t if re.search(motif, t)) / max(1, len(debut_t))
        b = 100 * sum(1 for t in fin_t if re.search(motif, t)) / max(1, len(fin_t))
        tend.append((nom, a, b))
    tend.sort(key=lambda t: -(t[2] - t[1]))
    trows = "".join(f'<tr><td>{e(n)}</td><td class="num">{a:.0f}</td><td class="num">{b:.0f}</td><td class="num {"up" if b - a >= 2 else "down" if a - b >= 2 else ""}">{"+" if b - a > 0 else ""}{b - a:.0f}</td></tr>' for n, a, b in tend)
    s4 = [f'<div class="card"><h3>Les mots qui montent dans les annonces</h3>'
          f'<p class="hint">Part des offres retenues qui citent chaque thème, pour 100 offres : du {fr_date(dates_v[0]) if dates_v else ""} au {fr_date(moitie)} ({len(debut_t)} lignes) contre du {fr_date(moitie)} au {fr_date(dates_v[-1]) if dates_v else ""} ({len(fin_t)} lignes).</p>'
          f'<div class="tablebox"><table><thead><tr><th>Thème</th><th class="num">1re moitié</th><th class="num">2de moitié</th><th class="num">Écart</th></tr></thead><tbody>{trows}</tbody></table></div>'
          f'{source("Veille quotidienne", "Mots-clés dans le titre et l extrait de description (liste dans scripts/site.py)", dates_v[-1] if dates_v else "", "Deux semaines seulement et des extraits courts : un écart de quelques points n est pas une tendance. La série s allonge chaque jour grâce à l Action.", "data/veille-stage-alternance/")}</div>']
    hist = (stats.get("historique_salaires") or {}).get("donnees", {}).get("month", {})
    s4.append('<div class="grid2"><div class="card"><h3>Ce que disent l\'APEC et le WEF</h3><ul class="facts">'
              '<li><b>APEC, mars 2026</b> (« L\'intelligence artificielle en commercial-marketing ») : le <b>chef de produit</b> est l\'un des trois métiers commercial-marketing où l\'IA est le plus souvent citée dans les offres cadres, avec le business developer et le business analyst. 13 % des offres cadres qui citent l\'IA en 2025 relèvent du commercial-marketing, mais seulement 2 % des offres de cette fonction la mentionnent. <a href="https://www.apec.fr/tendances-emploi-cadre/evolution-des-metiers-et-competences/quel-impact-de-l-ia-sur-les-competences-des-metiers-du-commercial-et-du-marketing-.html">Source</a></li>'
              '<li><b>WEF, Future of Jobs 2025</b> : « IA et big data » est la compétence qui progresse le plus d\'ici 2030, devant la pensée créative (4e) et la pensée analytique (9e). Les employeurs s\'attendent à ce que 39 % des compétences clés changent d\'ici 2030. Les product managers figurent parmi les métiers en croissance. <a href="https://reports.weforum.org/docs/WEF_Future_of_Jobs_Report_2025.pdf">Source</a></li>'
              '</ul></div>')
    inter = contenu.get("intervenants", {})
    items = []
    for p in inter.get("liste", []):
        txt = p.get("ce_qu_il_a_dit") or ""
        items.append(f'<li><b>{e(p["nom"])}</b>, {e(p["structure"])}, {e(p["date"])} : ' + (e(txt) if txt else '<span class="todo">son avis sur l\'évolution du métier reste à noter</span>') + "</li>")
    qs = "".join(f"<li>{e(q)}</li>" for q in contenu.get("questions_intervenants", []))
    s4.append(f'<div class="card"><h3>Ce que les professionnels en ont dit</h3><ul class="facts">{"".join(items)}</ul>'
              f'<h4>Mes trois questions, tirées de mes chiffres</h4><ol class="qs">{qs}</ol></div></div>')

    # -------- Section 5 : acteurs
    secteurs = suivi.get("par_secteur", {})
    carte_secteurs = ""
    if secteurs:
        lig = []
        for k, v in sorted(secteurs.items(), key=lambda kv: -sum(kv[1].values())):
            envoyees = sum(n for st_, n in v.items() if st_ != "a_envoyer")
            rep_ = v.get("refusee", 0) + v.get("entretien", 0)
            note = f" <small>{envoyees} envoyée{'s' if envoyees > 1 else ''}, {rep_} réponse{'s' if rep_ > 1 else ''}</small>" if envoyees else ""
            lig.append((e(k) + note, sum(v.values())))
        carte_secteurs = (f'<div class="card"><h3>Les secteurs qui recrutent des stagiaires et alternants chefs de produit</h3>'
                          f'<p class="hint">Secteur des {suivi.get("briefs", 0)} offres que j\'ai retenues et préparées depuis le 5 novembre (les meilleures de la veille, trois par jour au plus), avec les candidatures envoyées et les réponses reçues.</p>'
                          f'{barres(lig)}'
                          f'{source("Veille quotidienne et mon tableau de suivi", "Secteur attribué à chaque offre retenue, à partir du nom et de l activité de l entreprise", suivi.get("date_export", ""), "Échantillon choisi pour correspondre à mon profil (grande consommation et santé surreprésentées) : il dit où je candidate autant que qui recrute.", "data/suivi-candidatures.json")}</div>')
    pas_employeur = r"^(stage|alternance|confidentiel|entreprise)$|studi|iscod|openclassrooms|ecole|school|business school|institut|formation|interim|recrutement|cabinet|hays|michael page|robert walters|adecco|randstad|manpower"
    graphies = defaultdict(Counter)
    for r in uniques.values():
        n = r["entreprise"].strip()
        if n and not re.search(pas_employeur, norm(n)):
            graphies[norm(n)][n] += 1
    rec_ent = Counter({max(g, key=lambda x: (g[x], not x.isupper())): sum(g.values()) for g in graphies.values()})
    top = rec_ent.most_common(15)
    top_adz = (stats.get("top_entreprises") or {}).get("donnees", {}).get("leaderboard", [])
    s5 = [carte_secteurs, f'<div class="grid2"><div class="card"><h3>Les entreprises qui publient le plus</h3><p class="hint">Offres retenues par la veille depuis le 5 novembre ({len(rec_ent)} entreprises différentes).</p>'
          f'{barres([(e(k), v) for k, v in top])}'
          f'{source("Veille quotidienne", "Champ entreprise des offres retenues", dates_v[-1] if dates_v else "", "Adzuna affiche parfois le groupe plutôt que la marque (ex. Air Liquide pour Seppic). Les écoles, cabinets et annonces sans nom d employeur sont retirés ; les noms écrits différemment sont regroupés.", "data/veille-stage-alternance/")}</div>']
    if top_adz:
        s5.append(f'<div class="card"><h3>Classement Adzuna</h3><p class="hint">Entreprises qui publient le plus d\'offres contenant « chef produit stage ».</p>{barres([(e(t.get("canonical_name")), t.get("count", 0)) for t in top_adz[:12]])}'
                  f'{source("Adzuna (API top_companies)", stats["top_entreprises"]["requete"], stats["top_entreprises"]["date"], "Mot-clé cherché dans toute l annonce ; tous contrats.", f"data/{dernier}/stats_adzuna.json")}</div></div>')
    else:
        s5[1] = s5[1].replace('<div class="grid2">', "", 1)
    if ent:
        fam = Counter(r["famille"] for r in ent)
        pub = {norm(k) for k in rec_ent} | {norm(r["entreprise"]) for r in adz + ftv + lba}
        cache = [r for r in ent if not any(norm(r["nom"]).split(" ")[0] in p for p in pub if p)]
        taille = lambda r: int(re.sub(r"\D", "", r["effectif"].split(" à ")[0].split(" et ")[0]) or 0)
        gros = sorted([r for r in cache if r["famille"] != "Commerce de gros"], key=lambda r: -taille(r))[:12]
        lignes_ent = "".join(f'<tr><td><a href="{e(r["fiche"])}">{e(r["nom"])}</a></td><td>{e(r["commune"])}</td><td>{e(r["activite"])}</td><td class="nw">{e(r["effectif"])}</td></tr>' for r in gros)
        s5.append(f'<div class="card"><h3>Le marché caché du Puy-de-Dôme</h3>'
                  f'<p class="hint"><b>{len(ent)}</b> entreprises d\'au moins 20 salariés ont un établissement dans le 63 et travaillent dans un secteur qui gère des gammes de produits. '
                  f'<b>{len(cache)}</b> n\'apparaissent dans aucune offre de ma veille : c\'est le marché qu\'on ne voit pas sur les sites d\'emploi.</p>'
                  f'{barres([(e(k), v) for k, v in fam.most_common()])}'
                  f'<h4>Les plus grands fabricants, sans offre repérée (hors commerce de gros)</h4><div class="tablebox"><table><thead><tr><th>Entreprise</th><th>Commune</th><th>Activité</th><th>Effectif</th></tr></thead><tbody>{lignes_ent}</tbody></table></div>'
                  f'{source("API Recherche d entreprises (data.gouv)", ent_meta.get("requete", {}), ent_meta.get("date", ""), ent_meta.get("limites", ""), "data/entreprises_63.csv")}</div>')
    if recr:
        tous = [r for r in recr if r["ville_requete"] == "Clermont-Ferrand"]
        hors = r"informatique|logiciel|programmation|systemes|presse|traduction|telecom|ingenierie|edition"
        vus, rc = set(), []
        for r in tous:
            if not re.search(hors, norm(r["naf"])) and norm(r["entreprise"]) not in vus:
                vus.add(norm(r["entreprise"]))
                rc.append(r)
        s5.append(f'<div class="card"><h3>Entreprises qui recrutent en alternance sans publier (autour de Clermont)</h3>'
                  f'<p class="hint">La bonne alternance signale {len(tous)} établissements à 60 km de Clermont-Ferrand pour le code M1703. Le code mélange produits physiques et logiciels : j\'écarte les {len(tous) - len(rc)} entreprises d\'informatique et d\'édition, il reste <b>{len(rc)}</b> entreprises.</p>'
                  f'<ul class="cols">' + "".join(f"<li>{e(r['entreprise'])} <small>{e(re.sub(r" ?\(commerce interentreprises\)", "", r['naf'] or ""))}</small></li>" for r in rc[:30]) + "</ul>"
                  f'{source("La bonne alternance (API)", "romes = M1703 · latitude = 45.7772 · longitude = 3.087 · radius = 60", dernier, "Prédiction fondée sur les embauches passées, pas une offre.", f"data/{dernier}/recruteurs_lba.csv")}</div>')
    pro = contenu.get("professionnels", {})
    pl = "".join(f'<li><b>{e(p.get("nom"))}</b>, {e(p.get("poste"))}, {e(p.get("entreprise"))}</li>' for p in pro.get("liste", []))
    s5.append(f'<div class="card"><h3>Des professionnels qui exercent le métier</h3>'
              + (f'<ul class="facts">{pl}</ul>' if pl else '<p class="todo">Trois professionnels repérés à la main sur LinkedIn, dans les entreprises qui publient le plus : à ajouter dans contenu.json.</p>')
              + f'<p class="hint">{e(pro.get("regle", ""))}</p></div>')
    # suivi
    st = suivi.get("statuts", {})
    env = sum(v for k, v in st.items() if k != "a_envoyer")
    rep = st.get("entretien", 0) + st.get("refusee", 0)
    s6_suivi = (f'<div class="card"><h3>Où j\'en suis : mes candidatures</h3><div class="tiles">'
                f'<div class="tile"><b>{suivi.get("briefs", 0)}</b><span>offres retenues et préparées (CV et lettre adaptés)</span></div>'
                f'<div class="tile"><b>{env}</b><span>candidatures envoyées</span></div>'
                f'<div class="tile"><b>{rep}</b><span>réponses ({st.get("entretien", 0)} entretien, {st.get("refusee", 0)} refus)</span></div>'
                f'<div class="tile"><b>{pct(rep, env)}</b><span>taux de réponse</span></div></div>'
                f'{source("Mon tableau de suivi (privé)", "Statut saisi à la main à chaque envoi, relance ou réponse", suivi.get("date_export", ""), "Le détail par entreprise reste privé ; seuls les totaux sont publiés.", "data/suivi-candidatures.json")}</div>') if suivi else ""

    # -------- Section 6 : actions
    act = contenu.get("actions", {})
    s6 = [s6_suivi, '<ol class="actions">' + "".join(f'<li><time>{e(a["date"])}</time><div><b>{e(a["action"])}</b><p>Preuve : {e(a["preuve"])}</p></div></li>' for a in act.get("liste", [])) + "</ol>"]

    # -------- Section 7 : fabrication
    fichiers = sorted(glob.glob(os.path.join(DATA, "**", "*.*"), recursive=True))
    nb_csv = sum(1 for f in fichiers if f.endswith(".csv"))
    s7 = f'''<div class="grid2"><div class="card"><h3>Les canaux branchés</h3><div class="tablebox"><table><thead><tr><th>Canal</th><th>Accès</th><th>Ce que j'en tire</th></tr></thead><tbody>
<tr><td>France Travail, Offres d'emploi v2</td><td>API officielle, clé gratuite</td><td>Offres du code ROME M1703, compétences déclarées, alternances</td></tr>
<tr><td>Adzuna</td><td>API, clé gratuite</td><td>Comptages par intitulé et par lieu, offres du jour, régions, entreprises</td></tr>
<tr><td>La bonne alternance</td><td>API de l'État, jeton gratuit</td><td>Offres d'alternance et entreprises qui recrutent sans publier</td></tr>
<tr><td>Jooble</td><td>API, clé sur demande</td><td>Offres complémentaires (veille du 5 au 17 novembre)</td></tr>
<tr><td>Recherche d'entreprises</td><td>API data.gouv, sans clé</td><td>Base des entreprises du 63 (Sirene et registre)</td></tr>
</tbody></table></div><p class="hint">Pas d'aspiration de LinkedIn, de l'APEC ni d'Indeed : leurs conditions l'interdisent.</p></div>
<div class="card"><h3>La chaîne automatique</h3><ol class="steps">
<li><b>Chaque matin vers 6 h 40</b>, une GitHub Action (<a href="{DEPOT}/blob/main/.github/workflows/veille.yml">veille.yml</a>) se lance, ordinateur éteint.</li>
<li><a href="{DEPOT}/blob/main/scripts/collecte.py">collecte.py</a> interroge France Travail, Adzuna et La bonne alternance et écrit des CSV datés dans <code>data/AAAA-MM-JJ/</code>, avec un <code>comptages.json</code> qui garde la requête de chaque chiffre.</li>
<li><a href="{DEPOT}/blob/main/scripts/entreprises.py">entreprises.py</a> met à jour la base des entreprises du 63.</li>
<li><a href="{DEPOT}/blob/main/scripts/site.py">site.py</a> relit toutes les données et réécrit cette page.</li>
<li>L'Action enregistre le tout par un commit : l'historique Git devient l'archive du marché. GitHub Pages publie la page.</li>
</ol><p class="hint">À ce jour : {len(jours) + len(dates_v)} extractions datées et {nb_csv} fichiers CSV dans <a href="{DEPOT}/tree/main/data">data/</a>. Les clés d'API sont rangées dans les secrets du dépôt, jamais dans le code.</p></div></div>
<div class="card"><h3>Ma règle RGPD pour les contacts</h3><p>Le dépôt est public : la base d'entreprises ne contient aucun nom de personne, seulement l'entreprise, son activité, sa taille et sa commune. Les professionnels notés à la main le sont pour une finalité unique, ma candidature, et seulement avec leur nom, leur poste et leur entreprise. Aucun fichier n'est revendu ni partagé, aucun contact n'est collecté hors de sa fonction, et toute personne peut demander à être retirée. Le suivi détaillé de mes candidatures reste privé.</p>
<p class="hint">Référence : CNIL, la prospection commerciale B2B (finalité claire, lien avec la fonction, droit d'opposition).</p></div>'''

    # -------- en-tête et conclusion
    pos = contenu.get("position", {})
    maj = dt.date.today().isoformat()
    hero_tiles = [(nombre(len(uniques)), "offres de stage et d'alternance retenues depuis le 5 novembre"),
                  (nombre(len(dates_v) + len(jours)), "extractions datées"),
                  (nombre(n_annonces), "annonces lues en entier"),
                  (pct(n_idf, n_loc), "des offres en Île-de-France")]
    if ent:
        hero_tiles.append((nombre(len(ent)), "entreprises du 63 dans ma base"))
    hero_tiles.append((nombre(env), "candidatures envoyées"))
    flag = lambda bloc: '<span class="draft">brouillon à valider</span>' if bloc.get("a_valider") else ""
    sections = [
        ("metier", "1", "Le métier tel que le marché le nomme",
         f'<p class="lead">Le diplôme dit « marketing opérationnel et digital » ; les offres disent <b>chef de produit</b>, et pour un étudiant <b>assistant(e) chef de produit</b>. '
         f'Code ROME <b>M1703</b> (Management et gestion de produit, Métierscope France Travail), variantes : chef de marque, chef de gamme, product manager, chef de marché.</p>'
         + "".join(s1) +
         '<div class="card"><h3>Les questions que je pose au marché</h3><ol class="qs">'
         '<li>Quels secteurs recrutent le plus de stagiaires et d\'alternants chefs de produit ? <a href="#acteurs">→ Acteurs</a></li>'
         '<li>Quelles compétences et quels outils reviennent le plus ? <a href="#competences">→ Compétences</a></li>'
         '<li>Où se concentrent les offres, et quand recrutent les entreprises ? <a href="#offres">→ Les offres</a></li>'
         '<li>Quelle gratification et quel rythme sont proposés ? <a href="#offres">→ Les offres</a></li></ol></div>'),
        ("offres", "2", "Ce que disent les offres", "".join(s2)),
        ("competences", "3", "Compétences et outils demandés",
         "".join(s3) + (f'<p class="callout">Ce que ma formation ne me donnera pas : <b>{e(", ".join(manque))}</b>. Je les cite seulement si je les ai vraiment pratiqués.</p>' if manque else "")),
        ("evolution", "4", "Évolution du métier", "".join(s4)),
        ("acteurs", "5", "Les acteurs", "".join(s5)),
        ("actions", "6", f"Mes actions pour l'année {flag(act)}", "".join(s6)),
        ("fabrication", "7", "Comment ce site est fabriqué", s7),
    ]
    nav = "".join(f'<a href="#{i}">{n}. {t.split(" <span")[0]}</a>' for i, n, t, _ in sections)
    corps = "".join(f'<section id="{i}"><header class="sh"><span class="n">{n}</span><h2>{t}</h2></header>{c}</section>' for i, n, t, c in sections)
    page = f'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chef de produit, le marché compté · Baptiste Veloso Ferreira</title>
<meta name="description" content="Le marché des stages et alternances de chef de produit, compté à partir des offres : volume, lieux, gratifications, compétences, acteurs. Veille automatique, données datées.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700;12..96,800&family=Instrument+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="assets/style.css"></head><body>
<header class="hero"><div class="in hero-grid"><div class="hero-txt">
<p class="eyebrow">Séminaires métiers · {e(contenu.get("formation", ""))}</p>
<h1>Chef de produit<br><em>le marché</em><br><em>compté</em></h1>
<div class="sep"><span></span><i></i><span></span></div>
<p class="lead">Je cherche un {e(contenu.get("recherche", ""))[0].lower() + e(contenu.get("recherche", ""))[1:]} Ce site compte ce marché à partir des offres, chaque matin.</p>
<p class="cta"><a class="btn" href="#offres">Voir les chiffres <span aria-hidden="true">→</span></a><a class="btn ghost" href="#position">Ma position</a></p>
<p class="by">{e(contenu.get("auteur", ""))} · mis à jour le {fr_date(maj)}</p>
</div><ul class="chips"><li><b>Données</b><span>datées</span></li><li><b>Sources</b><span>citées</span></li><li><b>Mise à jour</b><span>chaque matin</span></li></ul></div>
<div class="in"><div class="tiles big">{"".join(f'<div class="tile"><b>{v}</b><span>{l}</span></div>' for v, l in hero_tiles)}</div></div>
</header>
<nav class="toc"><div class="in">{nav}<a href="#position">Ma position</a></div></nav>
<main class="in">{corps}
<section id="position" class="position"><header class="sh"><span class="n">→</span><h2>Ma position {flag(pos)}</h2></header><p>{e(pos.get("texte", ""))}</p></section>
</main>
<footer><div class="in"><p>Données et scripts : <a href="{DEPOT}">{DEPOT.replace("https://", "")}</a>. Chaque chiffre indique sa source ; cliquer sur « Source » pour voir la requête, la date et les limites.</p></div></footer>
</body></html>'''
    with open(os.path.join(RACINE, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print(f"index.html écrit ({len(page) // 1024} Ko), dernière collecte : {dernier}")


if __name__ == "__main__":
    construire()
