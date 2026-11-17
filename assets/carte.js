/* Carte cliquable des offres : filtre stage / alternance, clic sur une ville = liste des offres */
(function () {
  var el = document.getElementById("donnees-carte");
  if (!el) return;
  var D = JSON.parse(el.textContent), svg = document.getElementById("carte"), g = document.getElementById("bulles"),
      panneau = document.getElementById("panneau"), NS = "http://www.w3.org/2000/svg", filtre = "Tous", choisie = null;
  var MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
  function date(d) { var p = d.split("-"); return p.length === 3 ? (+p[2]) + " " + MOIS[+p[1] - 1] : d; }
  function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function offres() { return D.offres.filter(function (o) { return filtre === "Tous" || o.c === filtre; }); }
  function parVille() {
    var m = {};
    offres().forEach(function (o) { (m[o.v] = m[o.v] || []).push(o); });
    return Object.keys(m).map(function (v) { return { v: v, l: m[v], x: D.villes[v][0], y: D.villes[v][1], idf: D.villes[v][2] }; })
      .sort(function (a, b) { return b.l.length - a.l.length; });
  }
  function el_(n, a, t) { var e = document.createElementNS(NS, n); for (var k in a) e.setAttribute(k, a[k]); if (t != null) e.textContent = t; return e; }
  function dessiner() {
    while (g.firstChild) g.removeChild(g.firstChild);
    var vs = parVille(), boites = [[D.home[0] - 82, D.home[1] - 8, D.home[0] + 8, D.home[1] + 8]];
    vs.forEach(function (c) { c.r = 5 + Math.sqrt(c.l.length) * 4.2; });
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
    return '<li><div class="o-haut"><span class="tag ' + (o.c === "Alternance" ? "alt" : "st") + '">' + o.c + '</span><span class="o-date">' + date(o.d) + '</span></div>' +
      '<b>' + esc(o.t) + '</b><span class="o-ent">' + esc(o.e) + '</span>' +
      (o.u ? '<a href="' + esc(o.u) + '" target="_blank" rel="noopener">Voir l\'annonce ↗</a>' : "") + "</li>";
  }
  function liste() {
    var vs = parVille(), tot = offres().length;
    if (choisie) {
      var c = vs.filter(function (x) { return x.v === choisie; })[0];
      if (!c) { choisie = null; return liste(); }
      panneau.innerHTML = '<div class="p-tete"><button type="button" class="retour">← Toutes les villes</button><h4>' + esc(c.v) + '</h4><p>' + c.l.length + " offre" + (c.l.length > 1 ? "s" : "") + (filtre !== "Tous" ? " (" + filtre.toLowerCase() + "s)" : "") + "</p></div><ul class=\"offres\">" + c.l.map(carteOffre).join("") + "</ul>";
      panneau.querySelector(".retour").addEventListener("click", function () { choisie = null; dessiner(); liste(); });
    } else {
      var max = vs.length ? vs[0].l.length : 1;
      panneau.innerHTML = '<div class="p-tete"><h4>' + tot + " offre" + (tot > 1 ? "s" : "") + (filtre !== "Tous" ? " (" + filtre.toLowerCase() + "s)" : "") + '</h4><p>Choisis une ville sur la carte ou dans la liste.</p></div><ul class="villes">' +
        vs.map(function (c) { return '<li><button type="button" data-v="' + esc(c.v) + '"><span>' + esc(c.v) + '</span><i style="width:' + (100 * c.l.length / max).toFixed(0) + '%"></i><b>' + c.l.length + "</b></button></li>"; }).join("") + "</ul>";
      Array.prototype.forEach.call(panneau.querySelectorAll("[data-v]"), function (b) {
        b.addEventListener("click", function () { choisie = b.getAttribute("data-v"); dessiner(); liste(); });
      });
    }
  }
  Array.prototype.forEach.call(document.querySelectorAll(".filtres button"), function (b) {
    b.addEventListener("click", function () {
      filtre = b.getAttribute("data-f");
      Array.prototype.forEach.call(document.querySelectorAll(".filtres button"), function (x) { x.classList.toggle("on", x === b); });
      dessiner(); liste();
    });
  });
  dessiner(); liste();
})();
