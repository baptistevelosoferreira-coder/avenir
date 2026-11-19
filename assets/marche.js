/* « Et après » : carte des offres CDI/CDD (filtre par contrat, clic sur une ville) et tableau filtrable des offres */
(function () {
  var el = document.getElementById("donnees-marche");
  if (!el) return;
  var D = JSON.parse(el.textContent), NS = "http://www.w3.org/2000/svg";
  var g = document.getElementById("m-bulles"), panneau = document.getElementById("m-panneau");
  var filtre = "Tous", choisie = null, q = "", tri = { k: "d", sens: -1 }, montres = 15;
  var MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
  function date(d) { var p = (d || "").split("-"); return p.length === 3 ? (+p[2]) + " " + MOIS[+p[1] - 1] + " " + p[0] : (d || "–"); }
  function esc(t) { return String(t == null ? "" : t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function sa(t) { return String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
  function el_(n, a, t) { var e = document.createElementNS(NS, n); for (var k in a) e.setAttribute(k, a[k]); if (t != null) e.textContent = t; return e; }
  function garde(o) { return filtre === "Tous" || o.c === filtre; }

  /* ---------- carte */
  function parVille() {
    var m = {};
    D.offres.forEach(function (o) { if (o.v && D.villes[o.v] && garde(o)) (m[o.v] = m[o.v] || []).push(o); });
    return Object.keys(m).map(function (v) { return { v: v, l: m[v], x: D.villes[v][0], y: D.villes[v][1], idf: D.villes[v][2] }; })
      .sort(function (a, b) { return b.l.length - a.l.length; });
  }
  function dessiner() {
    if (!g) return;
    while (g.firstChild) g.removeChild(g.firstChild);
    var vs = parVille(), boites = [[D.home[0] - 82, D.home[1] - 8, D.home[0] + 8, D.home[1] + 8]];
    vs.forEach(function (c) { c.r = 4 + Math.sqrt(c.l.length) * 3.6; });
    vs.forEach(function (c) {
      var grp = el_("g", { "class": "ville" + (c.idf ? " idf" : "") + (choisie === c.v ? " on" : ""), tabindex: "0", role: "button",
        "aria-label": c.v + " : " + c.l.length + " offre" + (c.l.length > 1 ? "s" : "") });
      grp.appendChild(el_("circle", { "class": "bub" + (c.idf ? " idf" : ""), cx: c.x, cy: c.y, r: c.r }));
      if (c.l.length > 1) grp.appendChild(el_("text", { "class": "num", x: c.x, y: c.y }, c.l.length));
      var w = 6.2 * c.v.length, cands = [[c.x + c.r + 4, c.y + 4, "start"], [c.x - c.r - 4, c.y + 4, "end"], [c.x, c.y + c.r + 12, "middle"], [c.x, c.y - c.r - 4, "middle"]];
      if (c.idf) cands.unshift([c.x, c.y + c.r + 13, "middle"]);
      var autres = vs.filter(function (o) { return o !== c; }).map(function (o) { return [o.x - o.r, o.y - o.r, o.x + o.r, o.y + o.r]; });
      for (var i = 0; i < cands.length; i++) {
        var lx = cands[i][0], ly = cands[i][1], an = cands[i][2], x0 = lx - (an === "end" ? w : an === "middle" ? w / 2 : 0), b = [x0, ly - 10, x0 + w, ly + 2];
        var coupe = boites.concat(autres).some(function (o) { return b[0] < o[2] && o[0] < b[2] && b[1] < o[3] && o[1] < b[3]; });
        if (!coupe) { boites.push(b); grp.appendChild(el_("text", { "class": "city", x: lx, y: ly, "text-anchor": an }, c.v)); break; }
      }
      function choisir() { choisie = choisie === c.v ? null : c.v; dessiner(); liste(); }
      grp.addEventListener("click", choisir);
      grp.addEventListener("keydown", function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); choisir(); } });
      g.appendChild(grp);
    });
  }
  function carteOffre(o) {
    return '<li><div class="o-haut"><span><span class="tag ' + (o.c === "CDD" ? "alt" : "st") + '">' + esc(o.c || "Contrat ?") + "</span> <span class=\"tag src\">" + esc(o.src) + '</span></span><span class="o-date">' + date(o.d) + "</span></div>" +
      "<b>" + esc(o.t) + '</b><span class="o-ent">' + esc(o.e) + (o.s ? " · " + esc(o.s) : "") + "</span>" +
      (o.u ? '<a href="' + esc(o.u) + '" target="_blank" rel="noopener">Voir l\'annonce ↗</a>' : "") + "</li>";
  }
  function liste() {
    if (!panneau) return;
    var vs = parVille(), tot = vs.reduce(function (s, c) { return s + c.l.length; }, 0), suf = filtre !== "Tous" ? " en " + filtre : "";
    if (choisie) {
      var c = vs.filter(function (x) { return x.v === choisie; })[0];
      if (!c) { choisie = null; return liste(); }
      panneau.innerHTML = '<div class="p-tete"><button type="button" class="retour">← Toutes les villes</button><h4>' + esc(c.v) + "</h4><p>" + c.l.length + " offre" + (c.l.length > 1 ? "s" : "") + suf + '</p></div><ul class="offres">' + c.l.map(carteOffre).join("") + "</ul>";
      panneau.querySelector(".retour").addEventListener("click", function () { choisie = null; dessiner(); liste(); });
      return;
    }
    if (!tot) { panneau.innerHTML = '<div class="p-tete"><h4>Aucune offre</h4><p>Aucune offre localisée pour ce filtre.</p></div>'; return; }
    var max = vs[0].l.length;
    panneau.innerHTML = '<div class="p-tete"><h4>' + tot + " offre" + (tot > 1 ? "s" : "") + " localisée" + (tot > 1 ? "s" : "") + suf + '</h4><p>Choisir une ville sur la carte ou dans la liste.</p></div><ul class="villes">' +
      vs.map(function (c) { return '<li><button type="button" data-v="' + esc(c.v) + '"><span>' + esc(c.v) + '</span><i style="width:' + (100 * c.l.length / max).toFixed(0) + '%"></i><b>' + c.l.length + "</b></button></li>"; }).join("") + "</ul>";
    Array.prototype.forEach.call(panneau.querySelectorAll("[data-v]"), function (b) {
      b.addEventListener("click", function () { choisie = b.getAttribute("data-v"); dessiner(); liste(); });
    });
  }

  /* ---------- tableau */
  var corps = document.getElementById("m-corps"), plus = document.getElementById("m-plus"), compte = document.getElementById("m-compte");
  function lignes() {
    var mots = sa(q).split(/\s+/).filter(Boolean);
    return D.offres.filter(function (o) {
      if (!garde(o)) return false;
      var t = sa(o.t + " " + o.e + " " + o.l + " " + o.src);
      return mots.every(function (m) { return t.indexOf(m) >= 0; });
    }).sort(function (a, b) {
      var x = a[tri.k] == null ? "" : a[tri.k], y = b[tri.k] == null ? "" : b[tri.k];
      if (tri.k === "n") { x = a.n || 0; y = b.n || 0; }
      return (x < y ? -1 : x > y ? 1 : 0) * tri.sens;
    });
  }
  function tableau() {
    if (!corps) return;
    var ls = lignes();
    compte.textContent = ls.length + " offre" + (ls.length > 1 ? "s" : "");
    corps.innerHTML = ls.slice(0, montres).map(function (o) {
      return "<tr><td>" + (o.u ? '<a href="' + esc(o.u) + '" target="_blank" rel="noopener">' + esc(o.t) + "</a>" : esc(o.t)) + "</td><td>" + esc(o.e) + "</td><td>" + esc(o.l) +
        '</td><td class="nw">' + esc(o.c || "–") + '</td><td class="num">' + (o.s ? esc(o.s) : "–") + '</td><td class="nw">' + date(o.d) + '</td><td class="nw">' + esc(o.src) + "</td></tr>";
    }).join("") || '<tr><td colspan="7">Aucune offre ne correspond.</td></tr>';
    plus.hidden = ls.length <= montres;
    plus.textContent = "Afficher " + Math.min(15, ls.length - montres) + " de plus (" + (ls.length - montres) + " restantes)";
  }
  if (plus) plus.addEventListener("click", function () { montres += 15; tableau(); });
  var champ = document.getElementById("m-q");
  if (champ) champ.addEventListener("input", function () { q = champ.value; montres = 15; tableau(); });
  Array.prototype.forEach.call(document.querySelectorAll("#m-table th[data-k]"), function (th) {
    th.addEventListener("click", function () {
      var k = th.getAttribute("data-k");
      tri = { k: k, sens: tri.k === k ? -tri.sens : (k === "d" || k === "n" ? -1 : 1) };
      Array.prototype.forEach.call(document.querySelectorAll("#m-table th[data-k]"), function (x) { x.removeAttribute("aria-sort"); });
      th.setAttribute("aria-sort", tri.sens > 0 ? "ascending" : "descending");
      tableau();
    });
  });

  /* ---------- filtres communs (carte + tableau) */
  Array.prototype.forEach.call(document.querySelectorAll(".m-filtres button"), function (b) {
    b.addEventListener("click", function () {
      filtre = b.getAttribute("data-f"); choisie = null; montres = 15;
      Array.prototype.forEach.call(document.querySelectorAll(".m-filtres button"), function (x) { x.classList.toggle("on", x.getAttribute("data-f") === filtre); });
      dessiner(); liste(); tableau();
    });
  });

  /* ---------- graphique métiers : bascule nombre / part de CDI */
  Array.prototype.forEach.call(document.querySelectorAll("[data-vue-metiers]"), function (b) {
    b.addEventListener("click", function () {
      var v = b.getAttribute("data-vue-metiers");
      Array.prototype.forEach.call(document.querySelectorAll("[data-vue-metiers]"), function (x) { x.classList.toggle("on", x === b); });
      Array.prototype.forEach.call(document.querySelectorAll(".metiers-vue"), function (x) { x.hidden = x.getAttribute("data-vue") !== v; });
    });
  });

  dessiner(); liste(); tableau();
})();
