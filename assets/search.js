// Search over the recipes. Our own script, the only one the site runs (the content-security policy
// in netlify.toml allows no other, and no inline one). It reads index.json and puts text on the page
// with textContent only: nothing that came from a recipe is ever interpreted as markup.
(function () {
  "use strict";
  var me = document.currentScript;
  var root = (me && me.getAttribute("data-root")) || "";
  var form = document.querySelector("form.search");
  if (!form) return;
  var input = form.querySelector("input");
  var box = form.querySelector(".results");
  form.hidden = false; // without this script the box stays hidden: it would do nothing
  var data = null, loading = null, shown = [], chosen = -1;

  function load() {
    if (data || loading) return loading;
    loading = fetch(root + "index.json", { credentials: "omit" })
      .then(function (r) { return r.json(); })
      .then(function (d) { data = d; })
      .catch(function () { data = { recipes: [], categories: [] }; });
    return loading;
  }

  function names() {
    var by = {};
    (data.categories || []).forEach(function (c) { by[c.id] = c.name; });
    return by;
  }

  function words(text) {
    return String(text || "").toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
  }

  function search(query) {
    var q = words(query);
    if (!q.length) return [];
    var by = names();
    var out = [];
    (data.recipes || []).forEach(function (r) {
      if (!/^[a-z0-9][a-z0-9-]*$/.test(r.id)) return;
      var hay = (r.title + " " + r.summary + " " + (by[r.category] || "") + " " + r.id).toLowerCase();
      var score = 0;
      for (var i = 0; i < q.length; i++) {
        if (hay.indexOf(q[i]) < 0) return;          // every word has to be there
        score += String(r.title).toLowerCase().indexOf(q[i]) >= 0 ? 3 : 1;
      }
      out.push({ r: r, score: score, cat: by[r.category] || "" });
    });
    out.sort(function (a, b) { return b.score - a.score; });
    return out.slice(0, 8);
  }

  function render(found, query) {
    box.textContent = "";
    shown = [];
    chosen = -1;
    if (!query.trim()) { box.hidden = true; return; }
    if (!found.length) {
      var none = document.createElement("div");
      none.className = "none";
      none.textContent = "No recipe matches. Try fewer or other words.";
      box.appendChild(none);
    }
    found.forEach(function (f) {
      var a = document.createElement("a");
      a.href = root + "r/" + f.r.id + "/index.html";
      var t = document.createElement("strong");
      t.textContent = f.r.title;
      var s = document.createElement("span");
      s.textContent = (f.cat ? f.cat + " · " : "") + f.r.summary;
      a.appendChild(t);
      a.appendChild(s);
      box.appendChild(a);
      shown.push(a);
    });
    box.hidden = false;
  }

  function choose(step) {
    if (!shown.length) return;
    chosen = (chosen + step + shown.length) % shown.length;
    shown.forEach(function (a, i) { a.classList.toggle("on", i === chosen); });
  }

  input.addEventListener("focus", load);
  input.addEventListener("input", function () {
    var q = input.value;
    load().then(function () { if (input.value === q) render(search(q), q); });
  });
  input.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown") { e.preventDefault(); choose(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); choose(-1); }
    else if (e.key === "Enter") {
      var a = shown[chosen >= 0 ? chosen : 0];
      if (a) { e.preventDefault(); window.location.href = a.href; }
    } else if (e.key === "Escape") { input.value = ""; render([], ""); input.blur(); }
  });
  document.addEventListener("keydown", function (e) {
    var tag = (document.activeElement && document.activeElement.tagName) || "";
    if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA") { e.preventDefault(); input.focus(); }
  });
  document.addEventListener("click", function (e) { if (!form.contains(e.target)) box.hidden = true; });
  form.addEventListener("submit", function (e) { e.preventDefault(); });
})();

// The sort in the bar at the top, on pages that list recipes. The search box at the top also narrows
// the cards on the page as you type. Works on the cards already on the page.
(function () {
  "use strict";
  var bar = document.getElementById("toolbar");
  if (!bar) return;
  bar.hidden = false; // without this script the bar would do nothing, so it stays hidden
  var filter = document.querySelector("form.search input");
  var sort = document.getElementById("sort");
  var shown = document.getElementById("shown");

  function cards() { return Array.prototype.slice.call(document.querySelectorAll("article.card")); }

  function apply() {
    var words = (filter ? filter.value : "").toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
    var visible = 0;
    cards().forEach(function (c) {
      var text = c.getAttribute("data-text") || "";
      var ok = words.every(function (w) { return text.indexOf(w) >= 0; });
      c.hidden = !ok;
      if (ok) visible++;
    });
    if (shown) shown.textContent = "Showing " + visible + (visible === 1 ? " recipe" : " recipes");
  }

  function order() {
    var by = sort.value;
    Array.prototype.forEach.call(document.querySelectorAll(".grid"), function (grid) {
      var list = Array.prototype.slice.call(grid.children).filter(function (n) { return n.matches && n.matches("article.card"); });
      list.sort(function (a, b) {
        if (by === "title") return (a.getAttribute("data-title") || "").localeCompare(b.getAttribute("data-title") || "");
        if (by === "time") return (b.getAttribute("data-time") || "").localeCompare(a.getAttribute("data-time") || "");
        var d = Number(b.getAttribute("data-score")) - Number(a.getAttribute("data-score"));
        return d || (b.getAttribute("data-time") || "").localeCompare(a.getAttribute("data-time") || "");
      });
      list.forEach(function (c) { grid.appendChild(c); });
    });
  }

  if (filter) filter.addEventListener("input", apply);
  sort.addEventListener("change", order);
  order();
  apply();
})();
