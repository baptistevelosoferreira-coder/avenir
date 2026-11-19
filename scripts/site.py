"""Construit index.html à partir des données datées du dossier data/ et des textes de contenu.json.

Chaque chiffre affiché porte sa source : canal, requête, date et limites.
Relancer : python scripts/site.py  (aucune dépendance hors bibliothèque standard)

Version publique par défaut : aucune donnée personnelle (ni nom, ni école, ni suivi de candidatures).
Version privée : AVENIR_PRIVE=<dossier> python scripts/site.py lit identite.json et
suivi-candidatures.json dans ce dossier (hors dépôt) et écrit la page dans <dossier>/site/.
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
PRIVE = os.environ.get("AVENIR_PRIVE", "")
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


SOURCES = []


def source(canal, requete, date, limites, fichier=None):
    """Note de source : gardée pour la note unique en bas de page (rien sous le graphique)."""
    SOURCES.append((canal, requete, date, limites, fichier))
    return ""


def note_sources():
    vus, lignes = set(), []
    for canal, requete, date, limites, fichier in SOURCES:
        if isinstance(requete, dict):
            requete = " · ".join(f"{k} = {v}" for k, v in requete.items())
        cle = (canal, requete)
        if cle in vus:
            continue
        vus.add(cle)
        f = f" · {lien_data(fichier)}" if fichier else ""
        lignes.append(f'<li><b>{e(canal)}</b>, {e(fr_date(date))}{f}<br><span>{e(limites)}</span></li>')
    return f'<details class="sources"><summary>D’où viennent les chiffres</summary><ul>{"".join(lignes)}</ul></details>'


def source_inline(canal, requete, date, limites, fichier=None):
    """Ancien bloc sous chaque graphique (plus utilisé)."""
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


def courbe(points, hauteur=170, largeur=640, unite="", libelles=None, zero=True):
    """points : liste (date_iso, valeur) ; ligne simple avec points et étiquettes."""
    if not points:
        return '<p class="vide">Pas encore de données.</p>'
    vals = [v for _, v in points]
    vmax = max(vals) * 1.15 or 1
    vmin = 0 if zero else math.floor(min(vals) * 0.9 / 1000) * 1000
    if not zero:
        vmax = math.ceil(max(vals) * 1.05 / 1000) * 1000
    g, d, h, b = 40, 12, 14, 26
    W, H = largeur - g - d, hauteur - h - b
    x = lambda i: g + (W * i / max(1, len(points) - 1))
    y = lambda v: h + H - H * (v - vmin) / ((vmax - vmin) or 1)
    s = [f'<svg class="line" viewBox="0 0 {largeur} {hauteur}" role="img">']
    for k in range(0, 5):
        vv = vmin + (vmax - vmin) * k / 4
        s.append(f'<line class="grid" x1="{g}" x2="{largeur - d}" y1="{y(vv):.1f}" y2="{y(vv):.1f}"/><text class="ax" x="{g - 6}" y="{y(vv) + 4:.1f}" text-anchor="end">{nombre(round(vv))}</text>')
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(points))
    s.append(f'<polygon class="area" points="{g},{y(vmin):.1f} {pts} {x(len(points) - 1):.1f},{y(vmin):.1f}"/><polyline class="ln" points="{pts}"/>')
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

# ------------------------------------------------------------------ « Et après » : marché CDI / CDD

PERTINENT = r"chef(fe|\.fe|\(fe\)|\.e|·fe)?s? (de )?(projet marketing|projets? marketing|produits?|gamme|marque)|product (marketing )?manager|brand manager|category manager|marketing produit|trade marketing|chef de marche"
CABINETS = r"michael page|page personnel|hays|robert (walters|half)|adecco|randstad|manpower|marvesting|sintel|jd consultants|ropsi|talents commerciaux|experiences|enalees|reisel|france travail|hellowork|recrutement|interim|cabinet|consult|direct emploi|search|school|ecole|emploi|talent|rh\\b|^$"
EN_MOIS = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"])}


def salaire_annuel(mn, mx):
    try:
        mn, mx = float(mn or 0), float(mx or 0)
    except ValueError:
        return None
    v = (mn + mx) / 2 if mn and mx else (mn or mx)
    if not v:
        return None
    if v < 200:          # horaire
        v *= 151.67 * 12
    elif v < 10000:      # mensuel
        v *= 12
    return v if 18000 <= v <= 150000 else None


def k_euros(v):
    return f"{nombre(round(v / 1000))} k€"


def barres_empilees(lignes, cles, noms):
    """lignes : (libellé, {clé: valeur}) ; une barre par ligne, segments par clé."""
    maxi = max(sum(d.values()) for _, d in lignes) or 1
    out = []
    for lab, d in lignes:
        tot = sum(d.values())
        seg = "".join(f'<span class="sg {k}" style="width:{100 * d.get(k, 0) / maxi:.2f}%" title="{e(noms[k])} : {d.get(k, 0)}"></span>' for k in cles if d.get(k))
        out.append(f'<div class="hb"><div class="lab">{lab}</div><div class="bar pile">{seg}</div><div class="val">{nombre(tot)}</div></div>')
    leg = "".join(f'<span><i class="sg {k}"></i>{e(noms[k])}</span>' for k in cles)
    return f'<div class="hbars">{"".join(out)}</div><p class="legende-pile">{leg}</p>'


def retenir(txt):
    return f'<p class="retenir"><b>À retenir</b>{txt}</p>'


def section_marche():
    fichiers = sorted(f for f in glob.glob(os.path.join(DATA, "marche", "*.json")) if re.match(r"\d{4}-\d{2}-\d{2}\.json$", os.path.basename(f)))
    if not fichiers:
        return ""
    M = lire_json(fichiers[-1], {})
    jour = M.get("date", "")
    csvp = fichiers[-1].replace(".json", "_offres.csv")
    brutes = lire_csv(csvp) if os.path.exists(csvp) else []
    comptes = M.get("comptages", [])
    cpt = lambda metier, contrat="tous", filtre=None: next((c for c in comptes if c["metier"] == metier and c["contrat"] == contrat and c.get("filtre") == filtre), {})
    exclu = r"stage|stagiaire|altern|apprenti|internship|v\.?i\.?e\b"

    # offres détaillées, nettoyées
    offres = []
    for r in brutes:
        t = norm(r["intitule"])
        if not re.search(PERTINENT, t) or re.search(exclu, t):
            continue
        sal = salaire_annuel(r["salaire_min"], r["salaire_max"]) if str(r.get("salaire_estime")) not in ("1", "True") else None
        c = r["contrat"] or ("CDI" if re.search(r"\bcdi\b", t + " " + norm(r["extrait"])) else "CDD" if re.search(r"\bcdd\b", t) else "")
        offres.append({"t": r["intitule"], "e": r["entreprise"], "l": r["lieu"], "reg": r["region"], "c": c, "d": r["date_publication"],
                       "sal": sal, "x": norm(r["extrait"]), "u": r["url"], "src": "Adzuna", "dep": r.get("departement", ""), "m": r.get("metier") or "chef de produit"})
    n_adz = len(offres)
    # Indeed (recherches faites avec le connecteur Indeed, autorisé par l'enseignant car l'API France Travail ne répond pas)
    n_ind = 0
    if True:
        vus = {(norm(o["t"]), norm(o["e"])) for o in offres}
        for f in sorted(glob.glob(os.path.join(DATA, "marche", "indeed_*.json"))):
            for r in lire_json(f, []):
                t = norm(r["intitule"])
                if re.search(exclu, t) or re.search(r"stage|appren|internship", norm(r["type"])) or not re.search(PERTINENT, t):
                    continue
                if (t, norm(r["entreprise"])) in vus:
                    continue
                vus.add((t, norm(r["entreprise"])))
                m = re.match(r"(\w+) (\d+), (\d{4})", r.get("publie", ""))
                d = f"{m.group(3)}-{EN_MOIS.get(m.group(1).lower(), 1):02d}-{int(m.group(2)):02d}" if m else ""
                ty = norm(r["type"])
                c = "CDI" if "permanent" in ty or re.search(r"\bcdi\b", t) else "CDD" if re.search(r"cdd|courte duree|temporary|interim", ty + " " + t) else ""
                offres.append({"t": r["intitule"], "e": r["entreprise"], "l": r["lieu"], "reg": "", "c": c, "d": d, "sal": None, "x": "",
                               "u": r["url"], "src": "Indeed", "m": ""})
                n_ind += 1

    # chiffres clés
    tot = cpt("chef de produit")
    n_cdi, n_cdd = cpt("chef de produit", "CDI").get("valeur"), cpt("chef de produit", "CDD").get("valeur")
    stal = M.get("stage_alternance_chef_de_produit")
    sals = sorted(o["sal"] for o in offres if o["sal"])
    med = statistics.median(sals) if sals else None
    q1, q3 = (statistics.quantiles(sals, n=4)[0], statistics.quantiles(sals, n=4)[2]) if len(sals) >= 8 else (None, None)
    loc = [o for o in offres if o["src"] == "Adzuna"]
    n_idf = sum(1 for o in loc if o["reg"] == "Ile-de-France")
    n_63 = sum(1 for o in offres if re.search(r"puy-de-dome|clermont|\(63\)", norm(o["l"] + " " + o.get("dep", ""))))
    n_aura = sum(1 for o in loc if o["reg"] == "Auvergne-Rhône-Alpes")
    n_tt = sum(1 for o in loc if re.search(r"teletravail|remote|hybride", o["x"] + " " + norm(o["t"])))
    sans_sal = sum(1 for o in loc if not o["sal"])
    med_c = {c: statistics.median([o["sal"] for o in offres if o["sal"] and o["c"] == c]) for c in ("CDI", "CDD") if sum(1 for o in offres if o["sal"] and o["c"] == c) >= 3}
    ans = []
    for o in loc:
        m = re.search(r"(\d+)\s*(?:a|à)?\s*(\d+)?\s*ans? (?:d'|d’|minimum d'|minimum d’|au moins d')?experience", o["x"])
        if m:
            ans.append(int(m.group(1)))
    tranches = Counter("0 à 2 ans" if a <= 2 else "3 à 5 ans" if a <= 5 else "6 ans et plus" for a in ans)

    bref = [(nombre(tot.get("valeur", 0)), f"offres d'emploi « chef de produit » en {M.get('jours', 60)} jours", f"contre {nombre(stal)} stages et alternances" if stal else ""),
            (f"{pct(n_cdi or 0, (n_cdi or 0) + (n_cdd or 0))}" if n_cdi is not None and n_cdd is not None else "–", "sont des CDI (quand le contrat est précisé)", f"{nombre(n_cdi or 0)} CDI, {nombre(n_cdd or 0)} CDD"),
            (k_euros(med) if med else "–", "salaire annuel brut médian affiché dans les annonces", f"de {k_euros(q1)} à {k_euros(q3)} pour la moitié d'entre elles ; {pct(sans_sal, len(loc))} n'affichent rien" if q1 else ""),
            (pct(n_idf, len(loc)), "des offres sont en Île-de-France", f"{n_aura} en Auvergne-Rhône-Alpes ; " + (f"{n_63} dans le Puy-de-Dôme" if n_63 else "aucune dans le Puy-de-Dôme"))]
    h = ['<h3 class="sous gros-titre" id="et-apres">Et après ? Le marché de l\'emploi en CDI et CDD</h3>',
         retenir(f"Le métier recrute : <b>{nombre(tot.get('valeur', 0))}</b> offres d'emploi de chef de produit en {M.get('jours', 60)} jours, surtout en CDI. "
                 f"Les annonces affichent surtout entre <b>{k_euros(q1) if q1 else '–'}</b> et <b>{k_euros(q3) if q3 else '–'}</b> brut par an, au-dessus du repère d'insertion de l'IAE (2 433 € brut par mois à un an, environ 29 k€ par an) car beaucoup demandent de l'expérience. "
                 f"Attention, ce niveau de salaire est sans doute gonflé par le poids de Paris et de l'Île-de-France, où se trouvent {pct(n_idf, len(loc))} des offres et où les salaires sont plus élevés. "
                 f"Ces postes de chef de produit sont aussi généralement accessibles après quelques années d'expérience. "
                 f"Mon but : décrocher d'abord un poste d'<b>assistant chef de produit</b> ou de <b>chef de produit junior</b>, puis évoluer vers un poste de chef de produit. "
                 f"Mon stage de fin d'études, dans une entreprise qui recrute aussi en CDI, doit m'y préparer."),
         '<div class="bref bref4">' + "".join(f'<div><b>{v}</b><span>{l}</span><small>{n}</small></div>' for v, l, n in bref) + "</div>"]

    # carte + tableau
    villes, donnees = {}, []
    for o in offres:
        l = lieu(o["l"])
        v = None
        if l:
            v, lon, lat, idf = l
            x, y = proj(lon, lat)
            villes[v] = [round(x, 1), round(y, 1), idf]
        donnees.append({"t": o["t"], "e": o["e"] or "Entreprise non précisée", "l": o["l"], "v": v, "c": o["c"], "d": o["d"],
                        "s": k_euros(o["sal"]) if o["sal"] else "", "n": round(o["sal"]) if o["sal"] else 0, "u": o["u"], "src": o["src"]})
    n_places = sum(1 for d in donnees if d["v"])
    chemin = lambda pts: "M" + "L".join(f"{proj(*p)[0]:.1f},{proj(*p)[1]:.1f}" for p in pts) + "Z"
    hx, hy = proj(3.08, 45.78)
    js = json.dumps({"offres": sorted(donnees, key=lambda d: d["d"], reverse=True), "villes": villes, "home": [round(hx, 1), round(hy, 1)]}, ensure_ascii=False).replace("</", "<\\/")
    filtres = ('<div class="filtres m-filtres" role="group" aria-label="Filtrer par contrat">'
               '<button type="button" data-f="Tous" class="on">Tout</button><button type="button" data-f="CDI">CDI</button><button type="button" data-f="CDD">CDD</button></div>')
    src_txt = f"{n_adz} offres Adzuna" + (f" et {n_ind} offres Indeed" if n_ind else "")
    h.append(f'''<div class="card carte"><div class="carte-tete"><h3>Où sont les emplois</h3>{filtres}</div>
<p class="hint">{src_txt} de chef de produit et métiers proches publiées ces {M.get("jours", 60)} derniers jours, hors stages et alternances ; {n_places} sont placées sur la carte. {n_tt} offres Adzuna mentionnent le télétravail. <b>Cliquer sur une ville</b> pour voir ses offres.</p>
<div class="carte-corps"><div class="carte-svg"><svg viewBox="0 0 420 410" role="img" aria-label="Carte de France des offres d'emploi">
<path class="land" d="{chemin(FRANCE)}"/><path class="land" d="{chemin(CORSE)}"/><g id="m-bulles"></g>
<circle class="home" cx="{hx:.1f}" cy="{hy:.1f}" r="7"/><text class="city muted" x="{hx - 10:.1f}" y="{hy + 4:.1f}" text-anchor="end">Clermont-Fd</text></svg>
<p class="legende"><span class="pt-idf"></span>Île-de-France <span class="pt-autre"></span>autres villes <span class="pt-home"></span>Clermont-Ferrand</p></div>
<div class="panneau" id="m-panneau" aria-live="polite"></div></div>
<script type="application/json" id="donnees-marche">{js}</script></div>''')
    source("Adzuna (API), marché de l'emploi", "title_only = <métier> · what_exclude = stage, stagiaire, internship, alternance, alternant, apprentissage, apprenti · max_days_old = 60 · permanent = 1 (CDI) ou contract = 1 (CDD)", jour, M.get("limites", ""), f"data/marche/{os.path.basename(fichiers[-1])}")
    if n_ind:
        source("Indeed (recherche d'offres)", "chef de produit, chef de gamme, chef de marque, product marketing manager · plusieurs villes · temps plein ou CDD", "2026-11-19", "Recherches faites avec le connecteur officiel Indeed (pas d'aspiration du site), avec l'accord de l'enseignant car l'API France Travail ne répondait pas. Échantillon : 10 résultats par recherche, sans total ni salaire ; les doublons avec Adzuna sont retirés.", "data/marche/indeed_2026-11-19.json")

    # métiers : CDI / CDD / non précisé
    noms_m = {"chef de produit": "Chef de produit", "assistant chef de produit": "Assistant chef de produit", "chef de gamme": "Chef de gamme", "chef de marque": "Chef de marque", "brand manager": "Brand manager",
              "product marketing": "Product marketing", "marketing produit": "Marketing produit", "category manager": "Category manager",
              "chef de projet marketing": "Chef de projet marketing", "trade marketing": "Trade marketing"}
    lig, lig_pct = [], []
    for m, nom in noms_m.items():
        t_ = cpt(m).get("valeur") or 0
        a, b = cpt(m, "CDI").get("valeur") or 0, cpt(m, "CDD").get("valeur") or 0
        if not t_:
            continue
        lig.append((e(nom), {"cdi": a, "cdd": b, "np": max(0, t_ - a - b)}))
        lig_pct.append((e(nom), round(100 * a / (a + b)) if a + b else 0, f"{a + b} précisés"))
    lig.sort(key=lambda l: -sum(l[1].values()))
    lig_pct.sort(key=lambda l: -l[1])
    sal_m = sorted([(e(noms_m[c["metier"]]), round(c["salaire_moyen"] / 1000), "") for c in comptes if c["contrat"] == "tous" and not c.get("filtre") and c.get("salaire_moyen") and c["metier"] in noms_m], key=lambda l: -l[1])
    h.append(f'''<div class="card"><div class="carte-tete"><h3>Quels intitulés recrutent, et en quel contrat</h3><div class="filtres" role="group" aria-label="Affichage">
<button type="button" class="on" data-vue-metiers="n">Nombre d'offres</button><button type="button" data-vue-metiers="p">Part de CDI</button></div></div>
<p class="hint">Offres d'emploi des {M.get("jours", 60)} derniers jours en France dont le titre contient ce mot, stages et alternances exclus.</p>
<div class="metiers-vue" data-vue="n">{barres_empilees(lig, ["cdi", "cdd", "np"], {"cdi": "CDI", "cdd": "CDD", "np": "contrat non précisé"})}</div>
<div class="metiers-vue" data-vue="p" hidden>{barres(lig_pct, maxi=100, unite=" %")}<p class="hint">Part de CDI parmi les offres dont le contrat est précisé.</p></div></div>''')

    # zoom : assistant chef de produit (le poste d'entrée)
    asst = [o for o in offres if re.search(r"\bassistant\S{0,6} (de )?chef (de )?produit", norm(o["t"])) and not re.search(r"intership|interpret", norm(o["t"]))]
    a_tot, a_cdi, a_cdd = (cpt("assistant chef de produit", c).get("valeur") for c in ("tous", "CDI", "CDD"))
    if asst or a_tot:
        a_sals = sorted(o["sal"] for o in asst if o["sal"])
        a_med = statistics.median(a_sals) if len(a_sals) >= 3 else None
        a_moy = cpt("assistant chef de produit").get("salaire_moyen")
        a_villes = Counter("Lieu non précisé" if norm(o["l"]).strip() in ("", "france") else re.sub(r"\s*\(\d+\)", "", o["l"].split(",")[0]).strip() for o in asst)
        a_bref = [(nombre(a_tot) if a_tot is not None else "–", f"offres d'emploi « assistant chef de produit » en {M.get('jours', 60)} jours",
                   f"soit {pct(a_tot, tot.get('valeur'))} des offres « chef de produit »" if a_tot and tot.get("valeur") else ""),
                  (f"{nombre(a_cdi or 0)} CDI · {nombre(a_cdd or 0)} CDD" if a_cdi is not None else "–", "quand le contrat est précisé",
                   f"{pct(a_cdi or 0, (a_cdi or 0) + (a_cdd or 0))} de CDI" if (a_cdi or 0) + (a_cdd or 0) else ""),
                  (k_euros(a_med) if a_med else (k_euros(a_moy) if a_moy else "–"), "salaire annuel brut " + ("médian affiché" if a_med else "moyen affiché (Adzuna)"),
                   f"contre {k_euros(med)} pour l'ensemble des offres" if med else ""),
                  (str(len(asst)), "offres détaillées ci-dessous", f"{sum(1 for o in asst if o['src'] == 'Indeed')} via Indeed, {sum(1 for o in asst if o['src'] == 'Adzuna')} via Adzuna")]
        comp = [("Assistant chef de produit (emploi)", a_tot or 0), ("Chef de produit (emploi)", tot.get("valeur") or 0)] + ([("Chef de produit (stage, alternance)", stal)] if stal else [])
        lignes_a = "".join(f'<tr><td>{"<a href=" + chr(34) + e(o["u"]) + chr(34) + " target=_blank rel=noopener>" + e(o["t"]) + "</a>" if o["u"] else e(o["t"])}</td><td>{e(o["e"] or "Non précisée")}</td><td>{e(o["l"])}</td>'
                           f'<td class="nw">{e(o["c"] or "–")}</td><td class="num">{k_euros(o["sal"]) if o["sal"] else "–"}</td><td class="nw">{e(fr_date(o["d"]) if o["d"] else "–")}</td><td class="nw">{o["src"]}</td></tr>'
                           for o in sorted(asst, key=lambda o: o["d"], reverse=True))
        h.append(f'''<div class="card zoom" id="assistant"><h3>Zoom : assistant chef de produit, hors stage et alternance</h3>
<p class="hint">Le poste d'entrée le plus proche de mon stage : un premier emploi en CDI ou en CDD, souvent ouvert aux jeunes diplômés. Offres des {M.get("jours", 60)} derniers jours dont l'intitulé contient « assistant chef de produit ».</p>
<div class="bref bref4">{"".join(f'<div><b>{v}</b><span>{l}</span><small>{n}</small></div>' for v, l, n in a_bref)}</div>
<div class="grid2"><div><p class="hint">Volume comparé (offres en {M.get("jours", 60)} jours) :</p>{barres(comp)}</div>
<div><p class="hint">Où sont ces offres :</p>{barres([(e(k), v) for k, v in a_villes.most_common(8)])}</div></div>
{('<div class="tablebox"><table><thead><tr><th>Intitulé</th><th>Entreprise</th><th>Lieu</th><th>Contrat</th><th class="num">Salaire</th><th>Publiée</th><th>Source</th></tr></thead><tbody>' + lignes_a + '</tbody></table></div>') if asst else ""}
<p class="warn">Peu d'offres portent ce titre exact : beaucoup d'entreprises recrutent un « chef de produit junior » pour le même rôle. Le volume est petit, les pourcentages sont donc à lire avec prudence.</p></div>''')

    # salaires
    bornes = [(0, 30000, "moins de 30 k€"), (30000, 35000, "30 à 35 k€"), (35000, 40000, "35 à 40 k€"), (40000, 45000, "40 à 45 k€"),
              (45000, 50000, "45 à 50 k€"), (50000, 60000, "50 à 60 k€"), (60000, 10 ** 9, "60 k€ et plus")]
    hist_l = [(lab, sum(1 for v in sals if a <= v < b)) for a, b, lab in bornes]
    histo = (M.get("stats", {}).get("historique", {}).get("donnees") or {}).get("month", {})
    pts = [(k + "-01", round(v)) for k, v in sorted(histo.items())]
    h.append(f'''<div class="grid2"><div class="card"><h3>Combien c'est affiché</h3><div class="gros"><b>{k_euros(med) if med else "–"}</b><span>salaire annuel brut médian affiché, sur {len(sals)} offres qui donnent un montant (annualisé)</span></div>
<div class="duo">{"".join(f'<div><b>{k_euros(v)}</b><span>médiane affichée en {c}</span></div>' for c, v in med_c.items())}<div><b>29 k€</b><span>repère IAE : 2 433 € brut par mois à un an</span></div></div>
<p class="hint">Salaire moyen affiché par intitulé (k€ brut par an) :</p>{barres(sal_m, unite=" k€")}
<p class="warn">Ce sont des salaires affichés dans les annonces, pas des salaires versés. Ils sont certainement gonflés par le fait que la plupart des offres sont à Paris et en Île-de-France ({pct(n_idf, len(loc))} des offres), où les salaires sont plus hauts. Et ces postes sont généralement accessibles après quelques années d'expérience : un premier poste d'assistant chef de produit ou de chef de produit junior se situe plutôt dans le bas de la fourchette.</p></div>
<div class="card"><h3>L'évolution du salaire moyen affiché</h3><p class="hint">Offres « chef de produit » sur Adzuna, moyenne mensuelle, en € brut par an.</p>{courbe(pts, unite=" €", zero=False)}
{('<p class="hint">Répartition des ' + str(len(sals)) + ' offres qui affichent un salaire (brut annuel) :</p>' + barres(hist_l)) if sals else ""}</div></div>''')

    # niveau d'expérience et régions
    niv = [(nom, cpt("chef de produit", "tous", {"what_and": mot}).get("valeur") or 0) for nom, mot in
           [("« Junior »", "junior"), ("« Assistant »", "assistant"), ("« Confirmé »", "confirmé"), ("« Senior »", "senior")]]
    regions = defaultdict(lambda: {"n": 0, "cdi": 0, "sal": []})
    for o in loc:
        r = {"Ile-de-France": "Île-de-France", "Hauts-De-France": "Hauts-de-France", "Grand-Est": "Grand Est", "Pays-de-la-Loire": "Pays de la Loire", "Paysde-la-Loire": "Pays de la Loire",
             "Centre": "Centre-Val de Loire", "Centre-Val-de-Loire": "Centre-Val de Loire", "": "Non précisée"}.get(o["reg"], o["reg"])
        regions[r]["n"] += 1
        regions[r]["cdi"] += o["c"] == "CDI"
        if o["sal"]:
            regions[r]["sal"].append(o["sal"])
    reg_rows = "".join(f'<tr><td>{e(r)}{" <small>(Clermont)</small>" if r == "Auvergne-Rhône-Alpes" else ""}</td><td class="num">{d["n"]}</td><td class="num">{pct(d["n"], len(loc))}</td>'
                       f'<td class="num">{pct(d["cdi"], d["n"])}</td><td class="num">{k_euros(statistics.median(d["sal"])) if len(d["sal"]) >= 3 else "–"}</td></tr>'
                       for r, d in sorted(regions.items(), key=lambda kv: (kv[0] == "Non précisée", -kv[1]["n"])))
    ents = Counter()
    for o in offres:
        if o["e"] and not re.search(CABINETS, norm(o["e"])):
            ents[o["e"].strip().title() if o["e"].isupper() else o["e"].strip()] += 1
    top = [x for x in ents.most_common(10) if x[1] > 1]
    exp_html = ('<p class="hint">Expérience demandée, quand l\'extrait de l\'annonce la précise (' + str(len(ans)) + ' offres) :</p>' + barres([(k, tranches.get(k, 0)) for k in ["0 à 2 ans", "3 à 5 ans", "6 ans et plus"]])) if len(ans) >= 5 else ""
    h.append(f'''<div class="grid2"><div class="card"><h3>Le niveau demandé</h3><p class="hint">Offres « chef de produit » dont l'annonce contient ce mot.</p>{barres(niv)}{exp_html}
<p class="warn">La plupart des postes demandent de l'expérience : un stage ou une alternance de chef de produit compte comme première expérience.</p></div>
<div class="card"><h3>Les employeurs qui recrutent</h3><p class="hint">Offres d'emploi dans l'échantillon (cabinets de recrutement et intérim retirés).</p>{barres(top)}</div></div>
<div class="card"><h3>Par région</h3><div class="tablebox"><table><thead><tr><th>Région</th><th class="num">Offres</th><th class="num">Part</th><th class="num">Part de CDI</th><th class="num">Salaire médian</th></tr></thead><tbody>{reg_rows}</tbody></table></div>
<p class="hint">Sur les {len(loc)} offres Adzuna détaillées. Salaire médian affiché quand au moins 3 offres le donnent ; la part de CDI compte les offres où le contrat est indiqué ou écrit dans l'annonce.</p></div>''')

    # tableau des offres
    h.append(f'''<div class="card"><div class="carte-tete"><h3>Toutes les offres d'emploi</h3>{filtres}</div>
<div class="outils-carte"><label class="recherche"><span class="sr">Chercher</span><input type="search" id="m-q" placeholder="Chercher un mot, une entreprise, une ville (ex. assistant, Lyon, junior)"></label><span class="hint" id="m-compte"></span></div>
<div class="tablebox"><table id="m-table"><thead><tr><th data-k="t">Intitulé</th><th data-k="e">Entreprise</th><th data-k="l">Lieu</th><th data-k="c">Contrat</th><th data-k="n" class="num">Salaire</th><th data-k="d" aria-sort="descending">Publiée</th><th data-k="src">Source</th></tr></thead><tbody id="m-corps"></tbody></table></div>
<p class="suivant gauche"><button type="button" class="btn ghost" id="m-plus" hidden></button></p>
<p class="hint">Cliquer sur un en-tête pour trier. Le salaire n'apparaît que s'il est écrit dans l'annonce.</p></div>''')
    return "".join(h)


def section_sources(prive=False):
    """Onglet « Sources » : les trois sources citées."""
    srcs = [
        ("Adzuna", "https://www.adzuna.fr/", "Agrégateur d'offres d'emploi, interrogé par son API publique : offres de stage, d'alternance, de CDI et de CDD, comptages par intitulé, salaires affichés."),
        ("Indeed", "https://fr.indeed.com/", "Site d'offres d'emploi, consulté avec le connecteur officiel Indeed : offres de CDI et de CDD (dont assistant chef de produit)."),
        ("Jooble", "https://fr.jooble.org/", "Agrégateur d'offres d'emploi, interrogé par son API : offres complémentaires de stage et d'alternance."),
        ("Fiche ROME M1703 « Management et gestion de produit », France Travail", "https://candidat.francetravail.fr/metierscope/fiche-metier/M1703",
         "Fiche métier du chef de produit : missions, compétences et accès au métier."),
    ]
    return ('<div class="card"><h3>Sources</h3><ul class="refs">'
            + "".join(f'<li><a href="{e(u)}" target="_blank" rel="noopener"><b>{e(n)}</b></a><br><span class="hint">{e(d)}</span></li>' for n, u, d in srcs)
            + "</ul></div>")

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
    suivi = lire_json(os.path.join(PRIVE, "suivi-candidatures.json"), {}) if PRIVE else {}
    ident = lire_json(os.path.join(PRIVE, "identite.json"), {}) if PRIVE else {}
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
<p class="hint">Les {n_loc} offres de stage et d'alternance de chef de produit repérées {periode}. <b>Cliquer sur une ville</b> pour voir ses offres et ouvrir les annonces ; le badge <span class="tag new">Nouveau</span> marque les offres de moins de 3 jours.</p>
<div class="carte-corps"><div class="carte-svg"><svg id="carte" viewBox="0 0 420 410" role="img" aria-label="Carte de France des offres">
<path class="land" d="{chemin(FRANCE)}"/><path class="land" d="{chemin(CORSE)}"/><g id="bulles"></g>
<circle class="home" cx="{hx:.1f}" cy="{hy:.1f}" r="7"/><text class="city muted" x="{hx - 10:.1f}" y="{hy + 4:.1f}" text-anchor="end">Clermont-Fd</text></svg>
<p class="legende"><span class="pt-idf"></span>Île-de-France <span class="pt-autre"></span>autres villes <span class="pt-home"></span>Clermont-Ferrand{", chez moi" if PRIVE else ""}</p></div>
<div class="panneau" id="panneau" aria-live="polite"></div></div>
{source("Veille quotidienne (Adzuna, La bonne alternance)", "; ".join(veille.get("requetes_adzuna", [])), v_fin, "Lieu donné par l'annonce et rattaché à une ville par le script ; les lieux flous (« France ») ne sont pas placés. Certaines offres anciennes sont peut-être déjà pourvues.", "data/veille-stage-alternance/")}
<script type="application/json" id="donnees-carte">{donnees_carte}</script></div>'''

    # ---------------- 1. métier
    variantes = [c for c in comptes if c["canal"] == "Adzuna" and "titre contenant" in c["mesure"]]
    s1 = [retenir("Dans les annonces, mon métier s'appelle surtout <b>assistant(e) chef de produit</b>. C'est le mot-clé à taper sur les sites d'emploi, avec « product manager » et « brand manager » en complément.")]
    if variantes:
        joli = lambda v: (v[0].upper() + v[1:]).replace("marche", "marché")
        lignes = [(e(joli(re.search(r"« (.+?) »", c["mesure"]).group(1))), c["valeur"]) for c in variantes]
        c0 = variantes[0]
        s1.append(f'<div class="card"><h3>Quels mots-clés taper dans les moteurs de recherche</h3>'
                  f'<p class="hint">Nombre de stages et d\'alternances en ligne ces 30 derniers jours en France, quand le titre contient ce mot.</p>'
                  f'{barres(sorted(lignes, key=lambda l: -l[1]))}'
                  f'{source("Adzuna (API)", "title_only = <intitulé> · what_or = stage, stagiaire, internship, alternance, alternant, apprentissage, apprenti · max_days_old = 30", c0["date"], c0["limites"] + " « Product manager » mélange marketing et produit numérique.", f"data/{dernier}/comptages.json")}</div>')

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
               f'<p class="hint">De {nombre(min(vals))} € à {nombre(max(vals))} €. Le minimum légal est d\'environ 680 € par mois.</p>'
               f'<details class="plus"><summary>Voir le détail par entreprise</summary><div class="pay">{rows}<div class="payrow"><div></div><div class="axis"><span>600 €</span><span>1 400 €</span><span>2 200 €</span></div><div></div></div></div></details>'
               f'<p class="warn">C\'est le montant écrit dans l\'annonce, pas un salaire constaté. Beaucoup d\'annonces ne l\'indiquent pas.</p>'
               f'{source("Annonces lues en entier", "Champ « rémunération » des annonces retenues, converti en brut mensuel (horaire × 151,67 ; annuel ÷ 12)", annonces[-1]["date_veille"] if annonces else "", "Petit échantillon, choisi pour mon profil ; les annonces sans montant sont exclues.", "data/annonces-lues.csv")}</div>')
    ordre = ["Décembre", "Janvier", "Février", "Mars", "Avril", "Dès que possible", "Non précisé"]
    quand = (f'<div class="card"><h3>Quand ça commence</h3>'
             f'<div class="months">' + "".join(f'<div class="m{" hl" if k == "Janvier" else ""}"><b>{debuts[k]}</b><span>{k}</span></div>' for k in ordre if debuts[k]) + "</div>"
             f'<p class="hint">Sur {n_annonces} annonces lues en entier. {duree6} précisent une durée de 6 mois. Je suis disponible à partir de janvier 2027.</p>'
             f'{source("Annonces lues en entier", "Champ « début » de chaque annonce", annonces[-1]["date_veille"] if annonces else "", "Beaucoup d annonces ne donnent pas de date de début.", "data/annonces-lues.csv")}</div>')
    s2.append(quand)

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
    rec_ent = Counter({(k.title().replace('Bnp', 'BNP') if k.isupper() else k): v for k, v in rec_ent.items()})
    top = rec_ent.most_common(10)
    s5 = [retenir(f"L'<b>agroalimentaire</b> et la <b>santé</b> recrutent le plus de stagiaires dans mes offres ; la distribution (Cdiscount, Monoprix) publie beaucoup.")]
    carte_ent = (f'<div class="card"><h3>Les entreprises qui publient le plus</h3><p class="hint">Nombre d\'offres repérées {periode}. Cliquer sur un nom pour voir ses offres sur la carte.</p>{barres([(f'<button type="button" class="lien-q" data-q="{e(k)}">{e(k)}</button>', v) for k, v in top])}'
                 f'{source("Veille quotidienne", "Champ entreprise des offres retenues", v_fin, "Écoles, cabinets et annonces sans employeur retirés ; noms écrits différemment regroupés.", "data/veille-stage-alternance/")}</div>')
    if not suivi:
        s5.append(carte_ent)
    else:
      s5.append(f'<div class="grid2"><div class="card"><h3>Les secteurs de mes offres</h3><p class="hint">Secteur des {suivi.get("briefs", 0)} offres que j\'ai retenues pour candidater.</p>{barres(lig)}'
              f'{source("Veille quotidienne et mon tableau de suivi", "Secteur attribué à chaque offre retenue", suivi.get("date_export", ""), "Échantillon choisi pour mon profil : il dit où je candidate autant que qui recrute.", "")}</div>'
              f'<div class="card"><h3>Les entreprises qui publient le plus</h3><p class="hint">Nombre d\'offres repérées {periode}. Cliquer sur un nom pour voir ses offres sur la carte.</p>{barres([(f'<button type="button" class="lien-q" data-q="{e(k)}">{e(k)}</button>', v) for k, v in top])}'
              f'{source("Veille quotidienne", "Champ entreprise des offres retenues", v_fin, "Écoles, cabinets et annonces sans employeur retirés ; noms écrits différemment regroupés.", "data/veille-stage-alternance/")}</div></div>')

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
          + source("Mon tableau de suivi (privé)", "Statut saisi à la main à chaque envoi, relance ou réponse", suivi.get("date_export", ""), "Le détail par entreprise reste privé.", ""),
          '<h3 class="sous">Mes prochaines étapes</h3><ol class="actions">' + "".join(f'<li><time>{e(a["date"])}</time><div><b>{e(a["action"])}</b></div></li>' for a in act.get("liste", [])) + "</ol>"]

    # ---------------- page
    pos = contenu.get("position", {})
    maj = dt.date.today().isoformat()
    hero_tiles = [(nombre(c_stage["valeur"]) if c_stage else "–", "stages « chef de produit » en ligne en France"),
                  (nombre(c_alt["valeur"]) if c_alt else "–", "alternances « chef de produit » en ligne"),
                  (f"{env} / {suivi.get('briefs', 0)}", "candidatures envoyées sur celles préparées")]
    if not suivi:
        hero_tiles = hero_tiles[:2]
    s3[0] = s3[0].replace("<b>À retenir</b>", "<b>Ce qu'ils cherchent</b>", 1)
    sections = [
        ("offres", "1", "Les offres", "".join(s2) + "".join(s1[1:])),
        ("competences", "2", "Ce que les recruteurs demandent, et après", '<h3 class="sous gros-titre">Pour le stage et l\'alternance</h3>' + "".join(s3) + section_marche()),
        ("acteurs", "3", "Où candidater", "".join(s5)),
        ("actions", "4", f"Où j'en suis {flag(act)}", "".join(s6)),
    ]
    if not suivi:
        sections = sections[:3]
        SOURCES[:] = [x for x in SOURCES if "suivi" not in x[0]]
    sections.append(("sources", str(len(sections) + 1), "Sources", section_sources(bool(suivi))))
    courts = {"offres": "Les offres", "competences": "Les attentes des recruteurs", "acteurs": "Où candidater", "actions": "Où j'en suis", "sources": "Sources"}
    onglets = [("accueil", "Accueil")] + [(i, courts[i]) for i, *_ in sections]
    nav = "".join(f'<a href="#{i}" data-onglet="{i}">{t}</a>' for i, t in onglets)
    def suivant(i):
        k = [x for x, _ in onglets].index(i)
        if k + 1 < len(onglets):
            return f'<p class="suivant"><a class="btn" href="#{onglets[k + 1][0]}">{onglets[k + 1][1]} <span aria-hidden="true">→</span></a></p>'
        return ""
    corps = "".join(f'<section id="{i}" class="onglet"><div class="in"><header class="sh"><span class="n">{n}</span><h2>{t}</h2></header>{c}{suivant(i)}</div></section>' for i, n, t, c in sections)
    page = f'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ma recherche de stage et d'alternance{" · " + e(ident["auteur"]) if ident.get("auteur") else ""}</title>
<meta name="description" content="Ma recherche de stage et d'alternance d'assistant chef de produit : les offres sur une carte, ce que demandent les recruteurs, les entreprises à cibler et où j'en suis.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700;12..96,800&family=Playfair+Display:wght@600;700;800&family=Instrument+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="assets/style.css"></head><body><div class="lave" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></div>
<nav class="toc" aria-label="Onglets"><div class="in"><span class="marque">{e(ident["auteur"].split(" ")[0]) + " · " if ident.get("auteur") else ""}{"stage" if ident.get("auteur") else "Stage"} &amp; alternance</span>{nav}</div></nav>
<main>
<section id="accueil" class="onglet">
<header class="hero"><div class="in hero-grid"><div class="hero-txt">
<p class="eyebrow">{e(ident["auteur"]) + " · " if ident.get("auteur") else ""}M2 Marketing opérationnel et digital</p>
<h1>Ma recherche<br><em>de stage et</em><br><em>d'alternance</em></h1>
<div class="sep"><span></span><i></i><span></span></div>
<p class="lead">Assistant chef de produit, à partir de janvier 2027. Ici, toutes les offres que je repère chaque matin, ce que les recruteurs demandent, les entreprises à cibler{" et où j'en suis" if suivi else ''}.</p>
<p class="cta"><a class="btn" href="#offres">Voir la carte des offres <span aria-hidden="true">→</span></a>{'<a class="btn ghost" href="#actions">Où j' + "'" + 'en suis</a>' if suivi else '<a class="btn ghost" href="#competences">Ce que demandent les recruteurs</a>'}</p>
<p class="by">Mis à jour le {fr_date(maj)}</p>
</div><ul class="chips"><li><b>Janvier 2027</b><span>début</span></li><li><b>Stage</b><span>ou alternance</span></li><li><b>2 sem. / 2 sem.</b><span>jusqu'à fin mars</span></li></ul></div>
<div class="in"><div class="tiles big">{"".join(f'<div class="tile"><b>{v}</b><span>{l}</span></div>' for v, l in hero_tiles)}</div></div>
</header>
<div class="in">{suivant("accueil")}</div>
</section>
{corps}
</main>
<footer><div class="in"><p>Sources : <a href="#sources">onglet Sources</a>.</p></div></footer>
<script src="assets/onglets.js"></script>
<script src="assets/carte.js"></script>
<script src="assets/marche.js"></script>
</body></html>'''
    sortie = os.path.join(PRIVE, "site") if PRIVE else RACINE
    if PRIVE:
        import shutil
        os.makedirs(sortie, exist_ok=True)
        shutil.copytree(os.path.join(RACINE, "assets"), os.path.join(sortie, "assets"), dirs_exist_ok=True)
    with open(os.path.join(sortie, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print(f"index.html écrit ({len(page) // 1024} Ko), dernière collecte : {dernier}")


if __name__ == "__main__":
    construire()
