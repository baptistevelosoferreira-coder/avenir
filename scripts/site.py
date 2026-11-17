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
    return (f'<details class="src"><summary>D’où vient ce chiffre ? {e(canal)}, {e(fr_date(date))}</summary>'
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
    comptes = (lire_json(os.path.join(DATA, dernier, "comptages.json"), {}) or {}).get("comptages", []) if dernier else []
    trouve = lambda canal, debut: next((c for c in comptes if c["canal"] == canal and c["mesure"].startswith(debut)), None)

    veille = lire_json(os.path.join(DATA, "veille-stage-alternance", "serie.json"), {"serie": []})
    dates_v = [s["date"] for s in veille["serie"]]
    v_debut, v_fin = (dates_v[0], dates_v[-1]) if dates_v else ("", "")
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
    recr = lire_csv(os.path.join(DATA, dernier, "recruteurs_lba.csv")) if dernier else []
    ent = lire_csv(os.path.join(DATA, "entreprises_63.csv"))
    ent_jours = sorted(glob.glob(os.path.join(DATA, "*", "entreprises_63.json")))
    ent_meta = lire_json(ent_jours[-1], {}) if ent_jours else {}
    suivi = lire_json(os.path.join(DATA, "suivi-candidatures.json"), {})
    n_annonces = len(annonces)
    stage_annonces = sum(1 for a in annonces if a["contrat"] != "alternance")
    flag = lambda bloc: '<span class="draft">brouillon à valider</span>' if bloc.get("a_valider") else ""
    retenir = lambda txt: f'<p class="retenir"><b>À retenir</b>{txt}</p>'
    periode = f"du {fr_date(v_debut, False)} au {fr_date(v_fin)}" if dates_v else ""

    # ---------------- offres pour la carte
    est_alt = lambda r: bool(re.search(r"altern|apprenti|professionnalisation", norm(r["intitule"] + " " + r["contrat"] + " " + r.get("description_extrait", ""))))
    offres_carte, villes = [], {}
    for r in sorted(uniques.values(), key=lambda r: r.get("date_publication") or r["_jour"], reverse=True):
        l = lieu(r["lieu"])
        if not l:
            continue
        nom, lon, lat, idf = l
        x, y = proj(lon, lat)
        villes[nom] = (round(x, 1), round(y, 1), idf)
        offres_carte.append({"v": nom, "t": r["intitule"].strip(), "e": r["entreprise"].strip() or "Entreprise non précisée",
                             "c": "Alternance" if est_alt(r) else "Stage", "d": (r.get("date_publication") or r["_jour"])[:10],
                             "u": r.get("url", "")})
    n_loc = len(offres_carte)
    n_idf = sum(1 for o in offres_carte if villes[o["v"]][2])
    n_alt_v = sum(1 for o in offres_carte if o["c"] == "Alternance")
    n_clermont = sum(1 for o in offres_carte if o["v"] == "Clermont-Ferrand")
    lyon = sum(1 for o in offres_carte if o["v"] == "Lyon")
    chemin = lambda pts: "M" + "L".join(f"{proj(*p)[0]:.1f},{proj(*p)[1]:.1f}" for p in pts) + "Z"
    hx, hy = proj(3.08, 45.78)
    donnees_carte = json.dumps({"offres": offres_carte, "villes": villes, "home": [round(hx, 1), round(hy, 1)]}, ensure_ascii=False).replace("</", "<\\/")
    carte_html = f'''<div class="card carte">
<div class="carte-tete"><h3>La carte des offres</h3><div class="filtres" role="group" aria-label="Filtrer par contrat">
<button type="button" data-f="Tous" class="on">Tout</button><button type="button" data-f="Stage">Stages</button><button type="button" data-f="Alternance">Alternances</button></div></div>
<div class="outils-carte"><label class="recherche"><span class="sr">Chercher</span><input type="search" id="q" placeholder="Chercher une entreprise ou un mot (ex. Danone, santé, junior)"></label>
<label class="recent"><input type="checkbox" id="recent"> Moins de 14 jours seulement</label></div>
<p class="hint">Les {n_loc} offres de stage et d'alternance de chef de produit repérées {periode}. <b>Clique sur une ville</b> pour voir ses offres et ouvrir les annonces ; le badge <span class="tag new">Nouveau</span> marque les offres de moins de 3 jours.</p>
<div class="carte-corps"><div class="carte-svg"><svg id="carte" viewBox="0 0 420 410" role="img" aria-label="Carte de France des offres">
<path class="land" d="{chemin(FRANCE)}"/><path class="land" d="{chemin(CORSE)}"/><g id="bulles"></g>
<circle class="home" cx="{hx:.1f}" cy="{hy:.1f}" r="7"/><text class="city muted" x="{hx - 10:.1f}" y="{hy + 4:.1f}" text-anchor="end">Clermont-Fd</text></svg>
<p class="legende"><span class="pt-idf"></span>Île-de-France <span class="pt-autre"></span>autres villes <span class="pt-home"></span>Clermont-Ferrand, chez moi</p></div>
<div class="panneau" id="panneau" aria-live="polite"></div></div>
{source("Veille quotidienne (Adzuna, La bonne alternance)", "; ".join(veille.get("requetes_adzuna", [])), v_fin, "Lieu donné par l'annonce et rattaché à une ville par le script ; les lieux flous (« France ») ne sont pas placés. Certaines offres anciennes sont peut-être déjà pourvues.", "data/veille-stage-alternance/")}
<script type="application/json" id="donnees-carte">{donnees_carte}</script></div>'''

    # ---------------- 1. métier
    variantes = [c for c in comptes if c["canal"] == "Adzuna" and "titre contenant" in c["mesure"]]
    s1 = [retenir("Dans les annonces, mon métier s'appelle surtout <b>assistant(e) chef de produit</b>. C'est le mot-clé à taper sur les sites d'emploi, avec « product manager » et « brand manager » en complément.")]
    s1.append('<p class="lead">Mon diplôme dit « marketing opérationnel et digital » ; le marché dit <b>chef de produit</b>. Code ROME <b>M1703</b> (Métierscope, France Travail). '
              'Variantes : chef de marque, chef de gamme, chef de marché, product manager.</p>')
    if variantes:
        joli = lambda v: (v[0].upper() + v[1:]).replace("marche", "marché")
        lignes = [(e(joli(re.search(r"« (.+?) »", c["mesure"]).group(1))), c["valeur"]) for c in variantes]
        c0 = variantes[0]
        s1.append(f'<div class="card"><h3>Quels mots-clés taper dans les moteurs de recherche</h3>'
                  f'<p class="hint">Nombre de stages et d\'alternances en ligne ces 30 derniers jours en France, quand le titre contient ce mot.</p>'
                  f'{barres(sorted(lignes, key=lambda l: -l[1]))}'
                  f'{source("Adzuna (API)", "title_only = <intitulé> · what_or = stage, stagiaire, internship, alternance, alternant, apprentissage, apprenti · max_days_old = 30", c0["date"], c0["limites"] + " « Product manager » mélange marketing et produit numérique.", f"data/{dernier}/comptages.json")}</div>')
    s1.append('<div class="card"><h3>Mes quatre questions</h3><ol class="qs">'
              '<li>Quels secteurs recrutent le plus de stagiaires et d\'alternants ? <a href="#acteurs">Réponse</a></li>'
              '<li>Quelles compétences et quels outils sont demandés ? <a href="#competences">Réponse</a></li>'
              '<li>Où sont les offres, et quand commencent-elles ? <a href="#offres">Réponse</a></li>'
              '<li>Quelle gratification est proposée ? <a href="#offres">Réponse</a></li></ol></div>')

    # ---------------- 2. offres
    c_stage, c_alt = trouve("Adzuna", "chef de produit : stage"), trouve("Adzuna", "chef de produit : alternance")
    grat = []
    for a in annonces:
        mn, mx = gratif(a["remuneration_affichee"])
        if mn and a["contrat"] != "alternance":
            grat.append((a["entreprise"], mn, mx))
    vals = [mx or mn for _, mn, mx in grat]
    med = statistics.median(vals) if vals else None
    debuts = Counter()
    for a in annonces:
        d = norm(a["debut"])
        k = ("Décembre" if "decembre" in d else "Janvier" if "janv" in d else "Février" if "fevr" in d else "Mars" if "mars" in d
             else "Avril" if "avril" in d else "Dès que possible" if "possible" in d else "Non précisé")
        debuts[k] += 1
    dates_ok = sum(v for k, v in debuts.items() if k not in ("Non précisé", "Dès que possible"))
    duree6 = sum(1 for a in annonces if "6 mois" in norm(a["duree"]))
    bref = [(pct(n_idf, n_loc), "des offres sont en Île-de-France", f"contre {lyon} à Lyon et {n_clermont} à Clermont"),
            (pct(debuts["Janvier"], dates_ok), "des stages datés commencent en janvier", f"{duree6} annonces sur {n_annonces} durent 6 mois"),
            (f"{nombre(med)} €" if med else "–", "de gratification médiane par mois", "montant brut affiché dans l'annonce"),
            ("« Assistant chef de produit »", "le mot-clé qui ramène le plus d'offres", "puis « product manager », « brand manager »")]
    s2 = ['<div class="bref">' + "".join(f'<div><b>{v}</b><span>{l}</span><small>{n}</small></div>' for v, l, n in bref) + "</div>"]
    s2.append(carte_html)
    pay = ""
    if grat:
        lo, hi = 600, 2200
        X = lambda v: (min(hi, max(lo, v)) - lo) / (hi - lo) * 100
        rows = "".join(f'<div class="payrow"><div>{e(n)}</div><div class="track"><span class="med" style="left:{X(med):.1f}%"></span>'
                       + (f'<span class="rg" style="left:{X(mn):.1f}%;width:{X(mx) - X(mn):.1f}%"></span><span class="pt" style="left:{X(mx):.1f}%"></span>' if mx else f'<span class="pt" style="left:{X(mn):.1f}%"></span>')
                       + f'</div><div class="val">{nombre(mx or mn)} €</div></div>' for n, mn, mx in sorted(grat, key=lambda g: -(g[2] or g[1])))
        pay = (f'<div class="card"><h3>Combien c\'est payé</h3><div class="gros"><b>{nombre(med)} €</b><span>gratification médiane par mois (brut), sur {len(grat)} annonces de stage qui affichent un montant</span></div>'
               f'<p class="hint">De {nombre(min(vals))} € à {nombre(max(vals))} €. Le minimum légal est d\'environ 680 € par mois. À titre de repère, un diplômé de l\'IAE gagne 2 433 € brut médian un an après.</p>'
               f'<details class="plus"><summary>Voir le détail par entreprise</summary><div class="pay">{rows}<div class="payrow"><div></div><div class="axis"><span>600 €</span><span>1 400 €</span><span>2 200 €</span></div><div></div></div></div></details>'
               f'<p class="warn">C\'est le montant écrit dans l\'annonce, pas un salaire constaté. Beaucoup d\'annonces ne l\'indiquent pas.</p>'
               f'{source("Annonces lues en entier", "Champ « rémunération » des annonces retenues, converti en brut mensuel (horaire × 151,67 ; annuel ÷ 12)", annonces[-1]["date_veille"] if annonces else "", "Petit échantillon, choisi pour mon profil ; les annonces sans montant sont exclues.", "data/annonces-lues.csv")}</div>')
    ordre = ["Décembre", "Janvier", "Février", "Mars", "Avril", "Dès que possible", "Non précisé"]
    quand = (f'<div class="card"><h3>Quand ça commence</h3>'
             f'<div class="months">' + "".join(f'<div class="m{" hl" if k == "Janvier" else ""}"><b>{debuts[k]}</b><span>{k}</span></div>' for k in ordre if debuts[k]) + "</div>"
             f'<p class="hint">Sur {n_annonces} annonces lues en entier. {duree6} précisent une durée de 6 mois. Je suis disponible à partir de janvier 2027.</p>'
             f'{source("Annonces lues en entier", "Champ « début » de chaque annonce", annonces[-1]["date_veille"] if annonces else "", "Beaucoup d annonces ne donnent pas de date de début.", "data/annonces-lues.csv")}</div>')
    s2.append(f'<div class="grid2">{pay}{quand}</div>')

    # ---------------- 3. compétences
    formation = set(contenu.get("formation_donne", []))
    nq = sorted(compter(profils, QUALITES), key=lambda l: -l[1])[:6]
    no = sorted([x for x in compter(textes_annonces, OUTILS) if x[1]], key=lambda l: -l[1])[:7]
    ns = sorted([x for x in compter(textes_annonces, SAVOIRS) if x[1]], key=lambda l: -l[1])[:7]
    badge = lambda k: {"cv": '<i class="b ok">sur mon CV</i>', "formation": '<i class="b ok">vu en M2</i>', "non": '<i class="b gap">à travailler</i>'}.get(k, "")
    manque = [n for n, v, k in compter(textes_annonces, OUTILS) + compter(textes_annonces, SAVOIRS) if k == "non" and v >= 3]
    CONSEILS = {
        "Panels Nielsen, IRI, Kantar, Circana": "Revoir les bases (part de marché, distribution numérique et valeur) pour en parler en entretien : l'outil s'apprend sur le poste.",
        "Packaging, chaîne graphique": "Connaître les étapes d'un packaging (brief agence, BAT, impression) et en analyser un de la marque visée.",
        "Budget, P&L, prix": "Savoir lire le compte de résultat d'un produit : prix de vente, coûts, marge.",
        "Réglementation produit": "En santé et en agroalimentaire, connaître les mentions obligatoires de l'étiquetage.",
        "Suite Adobe": "Une prise en main de Photoshop ou Illustrator ; Canva est déjà sur mon CV.",
        "Power BI": "Rarement demandé : à apprendre sur le poste si besoin.",
        "SAP": "Rarement demandé : à apprendre sur le poste si besoin.",
        "RSE, éco-conception": "Avoir un avis sur l'éco-conception d'un produit de la marque visée.",
        "Google Analytics, GA4": "Rarement demandé : la certification gratuite de Google suffit.",
        "CRM, Salesforce, HubSpot": "Rarement demandé : à apprendre sur le poste si besoin.",
        "Word": "Pack Office est sur mon CV : le préciser.",
    }
    tout = [x for x in compter(textes_annonces, OUTILS) + compter(textes_annonces, SAVOIRS) if x[1]]
    atouts = sorted([x for x in tout if x[2] in ("cv", "formation")], key=lambda l: -l[1])[:7]
    manques = sorted([x for x in tout if x[2] == "non" and x[0] != "Word"], key=lambda l: -l[1])[:6]
    demandes = [x for x in tout if x[1] >= 5]
    couv = sum(1 for x in demandes if x[2] != "non")
    s3 = [retenir(f"Sur les <b>{len(demandes)}</b> compétences citées dans au moins 5 annonces, j'en ai déjà <b>{couv}</b> grâce à mon CV ou à mon M2. "
                  f"Les recruteurs insistent surtout sur la <b>{e(nq[0][0].lower())}</b> et l'<b>{e(nq[1][0].lower())}</b> : à prouver avec un exemple concret dans chaque lettre." if len(nq) > 1 else ""),
          f'<div class="grid2"><div class="card atouts"><h3>Mes atouts à mettre en avant</h3><p class="hint">Ce que les annonces demandent et que j\'ai déjà (sur {n_annonces} annonces lues).</p>'
          f'{barres([(e(n) + " " + badge(k), v) for n, v, k in atouts], maxi=n_annonces)}</div>'
          f'<div class="card manques"><h3>Ce qui me manque, et comment m\'y préparer</h3><ul class="conseils">'
          + "".join(f'<li><div><b>{e(n)}</b><span class="n-ann">{v} annonce{"s" if v > 1 else ""}</span></div><p>{e(CONSEILS.get(n, "À préparer avant l entretien."))}</p></li>' for n, v, k in manques)
          + '</ul></div></div>'
          f'<div class="card"><h3>Les qualités qu\'on me demandera de prouver</h3><div class="qualites">'
          + "".join(f'<div><b>{pct(v, len(profils))}</b><span>{e(n)}</span></div>' for n, v in nq)
          + f'</div><p class="hint">Part des {len(profils)} annonces au profil détaillé qui citent chaque qualité.</p>'
          + source("Annonces lues en entier", "Mots-clés cherchés dans les missions et le profil (liste dans scripts/site.py)", annonces[-1]["date_veille"] if annonces else "", "Comptage par mots-clés : une annonce qui cite une qualité une fois compte autant qu une annonce qui insiste.", "data/annonces-lues.csv") + "</div>"]

    # ---------------- 4. évolution
    moitie = dates_v[len(dates_v) // 2] if dates_v else ""
    debut_t = [norm(r["intitule"] + " " + r["description_extrait"]) for r in retenues_toutes if r["_jour"] < moitie]
    fin_t = [norm(r["intitule"] + " " + r["description_extrait"]) for r in retenues_toutes if r["_jour"] >= moitie]
    tend = []
    for nom, motif in TENDANCES:
        a = 100 * sum(1 for t in debut_t if re.search(motif, t)) / max(1, len(debut_t))
        b = 100 * sum(1 for t in fin_t if re.search(motif, t)) / max(1, len(fin_t))
        tend.append((nom, a, b))
    tend.sort(key=lambda t: -(t[2] - t[1]))
    trows = "".join(f'<tr><td>{e(n)}</td><td class="num">{a:.0f} %</td><td class="num">{b:.0f} %</td></tr>' for n, a, b in tend[:4])
    inter = contenu.get("intervenants", {})
    items = "".join(f'<li><b>{e(p["nom"])}</b> ({e(p["structure"])}) : ' + (e(p["ce_qu_il_a_dit"]) if p.get("ce_qu_il_a_dit") else '<span class="todo">à compléter</span>') + "</li>" for p in inter.get("liste", []))
    qs = "".join(f"<li>{e(q)}</li>" for q in contenu.get("questions_intervenants", []))
    s4 = [retenir("Le métier se tourne vers l'<b>IA</b> et la <b>donnée</b> : l'APEC classe le chef de produit parmi les métiers marketing où l'IA est le plus citée. "
                  "Dans mes annonces, la <b>santé</b> et la <b>RSE</b> progressent, mais deux semaines de veille, c'est encore court pour parler de tendance."),
          '<div class="grid2"><div class="card"><h3>Ce que disent les études</h3><ul class="facts">'
          '<li><b>APEC, mars 2026</b> : le chef de produit est l\'un des trois métiers commercial-marketing où l\'IA est le plus souvent citée dans les offres cadres. <a href="https://www.apec.fr/tendances-emploi-cadre/evolution-des-metiers-et-competences/quel-impact-de-l-ia-sur-les-competences-des-metiers-du-commercial-et-du-marketing-.html">Source</a></li>'
          '<li><b>WEF, Future of Jobs 2025</b> : « IA et big data » est la compétence qui progresse le plus d\'ici 2030 ; 39 % des compétences clés vont changer. <a href="https://reports.weforum.org/docs/WEF_Future_of_Jobs_Report_2025.pdf">Source</a></li></ul></div>'
          f'<div class="card"><h3>Les thèmes qui montent dans mes annonces</h3><p class="hint">Part des offres qui citent le thème, {fr_date(v_debut, False)} – {fr_date(moitie, False)} puis {fr_date(moitie, False)} – {fr_date(v_fin, False)}.</p>'
          f'<div class="tablebox"><table><thead><tr><th>Thème</th><th class="num">Avant</th><th class="num">Après</th></tr></thead><tbody>{trows}</tbody></table></div>'
          f'{source("Veille quotidienne", "Mots-clés dans le titre et l extrait de chaque offre retenue", v_fin, "Deux semaines et des extraits courts : un écart de quelques points n est pas une tendance.", "data/veille-stage-alternance/")}</div></div>'
          f'<div class="card"><h3>Ce qu\'en disent les professionnels</h3><ul class="facts">{items}</ul><h4>Mes questions pour eux</h4><ol class="qs">{qs}</ol></div>']

    # ---------------- 5. acteurs
    secteurs = suivi.get("par_secteur", {})
    lig = []
    for k, v in sorted(secteurs.items(), key=lambda kv: -sum(kv[1].values())):
        envs = sum(n for x, n in v.items() if x != "a_envoyer")
        reps = v.get("refusee", 0) + v.get("entretien", 0)
        lig.append((e(k) + (f' <small>{envs} envoyée{"s" if envs > 1 else ""} · {reps} réponse{"s" if reps > 1 else ""}</small>' if envs else ""), sum(v.values())))
    pas_employeur = r"^(stage|alternance|confidentiel|entreprise)$|studi|iscod|openclassrooms|ecole|school|institut|formation|interim|recrutement|cabinet|hays|michael page|robert walters|adecco|randstad|manpower"
    graphies = defaultdict(Counter)
    for r in uniques.values():
        n = r["entreprise"].strip()
        if n and not re.search(pas_employeur, norm(n)):
            graphies[norm(n)][n] += 1
    rec_ent = Counter({max(g, key=lambda x: (g[x], not x.isupper())): sum(g.values()) for g in graphies.values()})
    top = rec_ent.most_common(10)
    s5 = [retenir(f"L'<b>agroalimentaire</b> et la <b>santé</b> recrutent le plus de stagiaires dans mes offres ; la distribution (Cdiscount, Monoprix) publie beaucoup. "
                  f"Autour de Clermont, des dizaines d'entreprises fabriquent des produits de marque <b>sans publier d'offre</b> : c'est là que je peux candidater spontanément.")]
    s5.append(f'<div class="grid2"><div class="card"><h3>Les secteurs de mes offres</h3><p class="hint">Secteur des {suivi.get("briefs", 0)} offres que j\'ai retenues pour candidater.</p>{barres(lig)}'
              f'{source("Veille quotidienne et mon tableau de suivi", "Secteur attribué à chaque offre retenue", suivi.get("date_export", ""), "Échantillon choisi pour mon profil : il dit où je candidate autant que qui recrute.", "data/suivi-candidatures.json")}</div>'
              f'<div class="card"><h3>Les entreprises qui publient le plus</h3><p class="hint">Nombre d\'offres repérées {periode}. Clique sur un nom pour voir ses offres sur la carte.</p>{barres([(f'<button type="button" class="lien-q" data-q="{e(k)}">{e(k)}</button>', v) for k, v in top])}'
              f'{source("Veille quotidienne", "Champ entreprise des offres retenues", v_fin, "Écoles, cabinets et annonces sans employeur retirés ; noms écrits différemment regroupés.", "data/veille-stage-alternance/")}</div></div>')
    if ent:
        pub = {norm(k) for k in rec_ent}
        cache = [r for r in ent if not any(norm(r["nom"]).split(" ")[0] in p for p in pub if p)]
        taille = lambda r: int(re.sub(r"\D", "", r["effectif"].split(" à ")[0].split(" et ")[0]) or 0)
        fab = sorted([r for r in cache if r["famille"] != "Commerce de gros"], key=lambda r: -taille(r))[:10]
        joli_nom = lambda n: re.sub(r"\s*\(.*?\)", "", n).title().replace("Sas", "SAS").replace(" Sa", " SA")
        cartes = "".join(f'<div class="ent"><b>{e(joli_nom(r["nom"]))}</b><span>{e(r["activite"])}</span><small>{e(r["commune"].title())} · {e(r["effectif"])} salariés</small>'
                         f'<p class="ent-liens"><a href="https://www.google.com/search?q={e(joli_nom(r["nom"]).replace(" ", "+"))}+recrutement+stage" target="_blank" rel="noopener">Page carrière ↗</a>'
                         f'<a href="{e(r["fiche"])}" target="_blank" rel="noopener">Fiche entreprise ↗</a></p></div>' for r in fab)
        s5.append(f'<div class="card"><h3>Candidatures spontanées près de Clermont</h3>'
                  f'<p class="hint">Dans le Puy-de-Dôme, <b>{len(ent)}</b> entreprises de plus de 20 salariés travaillent dans un secteur qui gère des gammes de produits. '
                  f'<b>{len(cache)}</b> n\'apparaissent dans aucune de mes offres. Voici les plus grands fabricants : des cibles pour une candidature spontanée.</p>'
                  f'<div class="ents">{cartes}</div>'
                  f'{source("API Recherche d entreprises (data.gouv)", ent_meta.get("requete", {}), ent_meta.get("date", ""), ent_meta.get("limites", ""), "data/entreprises_63.csv")}</div>')
    pro = contenu.get("professionnels", {})
    pl = "".join(f'<li><b>{e(p.get("nom"))}</b>, {e(p.get("poste"))}, {e(p.get("entreprise"))}</li>' for p in pro.get("liste", []))
    s5.append(f'<div class="card"><h3>Des chefs de produit à contacter</h3>'
              + (f'<ul class="facts">{pl}</ul>' if pl else '<p class="todo">À compléter : trois chefs de produit repérés sur LinkedIn, dans les entreprises qui recrutent le plus.</p>')
              + '<p class="hint">Repérés à la main, seulement nom, poste et entreprise, pour ma candidature ; chacun peut demander à être retiré.</p></div>')

    # ---------------- 6. actions
    def entonnoir(suivi, env, rep, st):
        nb = suivi.get("briefs", 0) or 1
        etapes = [("Préparées", suivi.get("briefs", 0), "offres retenues, CV et lettre adaptés"), ("Envoyées", env, "candidatures parties"),
                  ("Réponses", rep, f"{st.get('refusee', 0)} refus, {st.get('entretien', 0)} entretien"), ("Entretiens", st.get("entretien", 0), "décrochés")]
        h = "".join(f'<div class="et"><div class="et-lab"><b>{v}</b><span>{l}</span></div><div class="et-bar"><span style="width:{max(2, 100 * v / nb):.0f}%"></span></div><small>{n}</small></div>' for l, v, n in etapes)
        a_env = st.get("a_envoyer", 0)
        return (f'<div class="grid2"><div class="card"><h3>Mon entonnoir</h3><div class="entonnoir">{h}</div></div>'
                f'<div class="card"><h3>À faire maintenant</h3><ul class="todo-liste">'
                f'<li><b>{a_env}</b><span>candidatures prêtes à envoyer</span></li>'
                f'<li><b>{suivi.get("sans_reponse", 0)}</b><span>relances à faire (sans réponse depuis 7 jours)</span></li>'
                f'<li><b>{pct(rep, env)}</b><span>de taux de réponse pour l\'instant</span></li></ul></div></div>')

    st = suivi.get("statuts", {})
    env = sum(v for k, v in st.items() if k != "a_envoyer")
    rep = st.get("entretien", 0) + st.get("refusee", 0)
    act = contenu.get("actions", {})
    s6 = [retenir(f"J'ai préparé <b>{suivi.get('briefs', 0)}</b> candidatures et envoyé <b>{env}</b>. La priorité : envoyer les <b>{st.get('a_envoyer', 0)}</b> prêtes avant fin novembre, car les stages de janvier se pourvoient maintenant."),
          entonnoir(suivi, env, rep, st)
          + source("Mon tableau de suivi (privé)", "Statut saisi à la main à chaque envoi, relance ou réponse", suivi.get("date_export", ""), "Le détail par entreprise reste privé ; seuls les totaux sont publiés.", "data/suivi-candidatures.json"),
          '<h3 class="sous">Mes prochaines étapes</h3><ol class="actions">' + "".join(f'<li><time>{e(a["date"])}</time><div><b>{e(a["action"])}</b><p>Preuve : {e(a["preuve"])}</p></div></li>' for a in act.get("liste", [])) + "</ol>"]

    # ---------------- 7. fabrication
    nb_csv = sum(1 for f in glob.glob(os.path.join(DATA, "**", "*.csv"), recursive=True))
    s7 = f'''<div class="card"><h3>La méthode : d'où viennent les chiffres</h3>
<p>Chaque matin vers 6 h 40, un robot GitHub (<a href="{DEPOT}/blob/main/.github/workflows/veille.yml">veille.yml</a>) interroge des sources officielles et gratuites, enregistre des fichiers datés, puis réécrit cette page. À ce jour : {len(jours) + len(dates_v)} extractions et {nb_csv} fichiers dans <a href="{DEPOT}/tree/main/data">data/</a>.</p>
<ul class="canaux"><li><b>France Travail</b> offres du code ROME M1703</li><li><b>Adzuna</b> comptages et offres</li><li><b>La bonne alternance</b> alternances et entreprises qui recrutent</li><li><b>Recherche d'entreprises</b> base du Puy-de-Dôme</li></ul>
<details class="plus"><summary>Le détail technique et ma règle RGPD</summary>
<ol class="steps"><li><a href="{DEPOT}/blob/main/scripts/collecte.py">collecte.py</a> interroge les API et écrit <code>data/AAAA-MM-JJ/</code>, avec un <code>comptages.json</code> qui garde la requête de chaque chiffre.</li>
<li><a href="{DEPOT}/blob/main/scripts/entreprises.py">entreprises.py</a> met à jour la base des entreprises du 63.</li>
<li><a href="{DEPOT}/blob/main/scripts/site.py">site.py</a> relit les données et réécrit cette page ; l'historique Git sert d'archive.</li></ol>
<p class="hint">Pas d'aspiration de LinkedIn, de l'APEC ni d'Indeed (leurs conditions l'interdisent). Les clés d'API sont dans les secrets du dépôt, jamais dans le code.</p>
<p class="hint"><b>RGPD :</b> le dépôt est public, donc la base d'entreprises ne contient aucun nom de personne. Les professionnels sont notés pour une seule finalité, ma candidature, avec leur seul nom, poste et entreprise, et peuvent demander à être retirés. Le détail de mes candidatures reste privé.</p></details></div>'''

    # ---------------- page
    pos = contenu.get("position", {})
    maj = dt.date.today().isoformat()
    hero_tiles = [(nombre(c_stage["valeur"]) if c_stage else "–", "stages « chef de produit » en ligne en France"),
                  (nombre(c_alt["valeur"]) if c_alt else "–", "alternances « chef de produit » en ligne"),
                  (pct(n_idf, n_loc), "des offres en Île-de-France"),
                  (f"{env} / {suivi.get('briefs', 0)}", "candidatures envoyées sur celles préparées")]
    s3[0] = s3[0].replace("<b>À retenir</b>", "<b>Ce qu'ils cherchent</b>", 1)
    sections = [
        ("offres", "1", "Les offres", "".join(s2) + "".join(s1[2:3])),
        ("competences", "2", "Ce que les recruteurs demandent", "".join(s3)),
        ("acteurs", "3", "Où candidater", "".join(s5)),
        ("actions", "4", f"Où j'en suis {flag(act)}", "".join(s6)),
    ]
    nav = "".join(f'<a href="#{i}">{t.split(" <span")[0]}</a>' for i, n, t, _ in sections)
    corps = "".join(f'<section id="{i}"><header class="sh"><span class="n">{n}</span><h2>{t}</h2></header>{c}</section>' for i, n, t, c in sections)
    page = f'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ma recherche de stage et d'alternance · Baptiste Veloso Ferreira</title>
<meta name="description" content="Ma recherche de stage et d'alternance d'assistant chef de produit : les offres sur une carte, ce que demandent les recruteurs, les entreprises à cibler et où j'en suis.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700;12..96,800&family=Instrument+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="assets/style.css"></head><body>
<header class="hero"><div class="in hero-grid"><div class="hero-txt">
<p class="eyebrow">{e(contenu.get("auteur", ""))} · M2 Marketing opérationnel et digital</p>
<h1>Ma recherche<br><em>de stage et</em><br><em>d'alternance</em></h1>
<div class="sep"><span></span><i></i><span></span></div>
<p class="lead">Assistant chef de produit, à partir de janvier 2027. Ici, toutes les offres que je repère chaque matin, ce que les recruteurs demandent, les entreprises à cibler et où j'en suis.</p>
<p class="cta"><a class="btn" href="#offres">Voir la carte des offres <span aria-hidden="true">→</span></a><a class="btn ghost" href="#position">Ma stratégie</a></p>
<p class="by">Mis à jour le {fr_date(maj)}</p>
</div><ul class="chips"><li><b>Janvier 2027</b><span>début</span></li><li><b>Stage</b><span>ou alternance</span></li><li><b>2 sem. / 2 sem.</b><span>jusqu'à fin mars</span></li></ul></div>
<div class="in"><div class="tiles big">{"".join(f'<div class="tile"><b>{v}</b><span>{l}</span></div>' for v, l in hero_tiles)}</div></div>
</header>
<nav class="toc"><div class="in">{nav}<a href="#position">Ma stratégie</a></div></nav>
<main class="in">{corps}
<section id="position" class="position"><header class="sh"><span class="n">→</span><h2>Ma stratégie {flag(pos)}</h2></header><p>{e(pos.get("intro", ""))}</p>
<div class="prios">{"".join(f'<div class="prio"><i>Priorité {i}</i><b>{e(x["titre"])}</b><p>{e(x["texte"])}</p></div>' for i, x in enumerate(pos.get("priorites", []), 1))}</div></section>
</main>
<footer><div class="in"><p>Les offres sont collectées automatiquement chaque matin (France Travail, Adzuna, La bonne alternance, annuaire des entreprises). Données et méthode : <a href="{DEPOT}">{DEPOT.replace("https://", "")}</a>.</p></div></footer>
<script src="assets/carte.js"></script>
</body></html>'''
    with open(os.path.join(RACINE, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print(f"index.html écrit ({len(page) // 1024} Ko), dernière collecte : {dernier}")


if __name__ == "__main__":
    construire()
