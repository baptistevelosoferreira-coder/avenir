/* Onglets : une seule section visible, choisie par l'adresse (#offres, #actions…). */
(function () {
  var onglets = document.querySelectorAll(".onglet"), liens = document.querySelectorAll(".toc a[data-onglet]");
  var ids = Array.prototype.map.call(onglets, function (o) { return o.id; });
  function montrer(defiler) {
    var h = location.hash.slice(1), cible = ids.indexOf(h) >= 0 ? h : null;
    if (!cible) { var el = h && document.getElementById(h); var o = el && el.closest(".onglet"); cible = o ? o.id : "accueil"; }
    Array.prototype.forEach.call(onglets, function (o) { o.hidden = o.id !== cible; });
    Array.prototype.forEach.call(liens, function (a) {
      if (a.getAttribute("data-onglet") === cible) { a.setAttribute("aria-current", "page"); a.scrollIntoView({ block: "nearest", inline: "center" }); }
      else a.removeAttribute("aria-current");
    });
    if (defiler) window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", function () { montrer(true); });
  montrer(false);
})();
