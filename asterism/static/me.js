// The reader's own settings (the settings layer at /{slug}/me; settings.js switches its sections):
// - profile: the name in this project (#me-name: sent, then the page again, so every place shows it), the language
//   of the pages (#me-locale: kept with the account, then the page again in it) and the look (#me-theme: dark, light,
//   or the system's, kept in this browser as before);
// - computers and connectors (#me-computers, from /api/my): each with what it is, how it came, whether its program
//   is connected, when it was last used, the agents on it, and "revoke" (floating, its label typed);
// - what others may do with my agents (#me-switches): the four permissions of my own agent group, each saved as it
//   changes.
"use strict";
(function () {
  var A = window.Asterism, layer = document.getElementById("settings-layer");
  if (!A || !layer || layer.dataset.scope !== "me") return;
  var t = A.t, make = A.make;
  var API = "/" + encodeURIComponent(layer.dataset.slug) + "/api/", LANG = document.documentElement.lang || undefined;
  var my = A.parseJSON(layer.dataset.my, null), myRaw = JSON.stringify(my);

  function say(out, text, brief) {
    out.textContent = text;
    if (brief) setTimeout(function () { if (out.textContent === text) out.textContent = ""; }, 2500);
  }

  // ------------------------------------------------------------------ profile

  var nameForm = document.getElementById("me-name");
  if (nameForm) {
    nameForm.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var out = nameForm.querySelector(".out");
      out.textContent = "";
      var r = await A.request(API + "me/name", null, {name: nameForm.elements.name.value.trim()});
      if (!r.ok) {
        if (/^(invalid_name|conflict)$/.test(r.data.error)) A.fieldError(nameForm.elements.name, A.refusal("me.name", r.data));
        else out.textContent = A.refusal("me.name", r.data);
        return;
      }
      window.location.reload();
    });
  }

  var locales = document.getElementById("me-locale"), localeOut = document.getElementById("me-locale-out");
  if (locales) {
    locales.addEventListener("click", async function (ev) {
      var b = ev.target.closest && ev.target.closest("[data-locale]");
      if (!b || b.getAttribute("aria-pressed") === "true") return;
      localeOut.textContent = "";
      var r = await A.request("/api/me/settings", null, {locale: b.dataset.locale});
      if (!r.ok) { localeOut.textContent = A.refusal("me.locale", r.data); return; }
      window.location.reload();
    });
  }

  var themes = document.getElementById("me-theme");
  function markTheme() {
    if (!themes || !A.theme) return;
    var now = A.theme.choice();
    Array.prototype.forEach.call(themes.querySelectorAll("[data-theme-choice]"), function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.themeChoice === now));
    });
  }
  if (themes) {
    themes.addEventListener("click", function (ev) {
      var b = ev.target.closest && ev.target.closest("[data-theme-choice]");
      if (!b || !A.theme) return;
      A.theme.choose(b.dataset.themeChoice);
      markTheme();
    });
    window.addEventListener("storage", markTheme);
    markTheme();
  }

  // ------------------------------------------------------------------ what others may do with my agents

  Array.prototype.forEach.call(layer.querySelectorAll("input[data-switch]"), function (box) {
    var out = box.parentElement.querySelector(".out");
    box.addEventListener("change", async function () {
      var body = {};
      body[box.dataset.switch] = box.checked;
      out.textContent = "";
      var r = await A.request(API + "my/switches", null, body);
      if (!r.ok) { box.checked = !box.checked; out.textContent = A.refusal("grp.change", r.data); return; }
      A.saved(out);
    });
  });

  // ------------------------------------------------------------------ computers and connectors

  var box = document.getElementById("me-computers");

  function when(iso) {
    var d = new Date(iso);
    if (!iso || isNaN(d.getTime())) return "";
    return d.toLocaleString(LANG, {month: "long", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false});
  }

  function facts(parts) {
    var p = make("div", "ag-meta");
    parts.filter(function (x) { return x; }).forEach(function (x, i) {
      if (i) p.appendChild(document.createTextNode(" · "));
      p.appendChild(typeof x === "string" ? document.createTextNode(x) : x);
    });
    return p;
  }

  function credential(c) {
    var li = make("li", "ag-item"), out = make("div", "out");
    out.setAttribute("aria-live", "polite");
    var first = make("div", "ag-line");
    var via = A.MSG["my.via." + c.via] ? t("my.via." + c.via) : (c.via || "");
    first.append(make("span", "ag-name mono", c.label), make("span", "dim", t("ag.cred_kind", {kind: t("cred." + c.kind), via: via})));
    li.appendChild(first);
    var b = A.button("btn ag-side-btn", t("my.revoke"));
    b.setAttribute("aria-label", t("ag.revoke_label", {name: c.label}));
    b.dataset.key = "revoke:" + c.id;
    b.addEventListener("click", function () {
      A.gone({title: t("gone.revoke.title", {name: c.label}), text: t("gone.revoke.text", {name: c.label}), name: c.label,
              button: t("gone.revoke.button"), opener: b,
              run: function () { return A.request(API + "my/credentials/" + encodeURIComponent(c.id) + "/revoke", null, {}); },
              done: function () { load(true); }});
    });
    li.appendChild(b);
    var on = (my.agents || []).filter(function (a) { return a.credential === c.id; }).map(function (a) { return a.name; });
    var names = null;
    if (on.length) {
      names = make("span");
      names.appendChild(document.createTextNode(t("ag.cred_agents", {names: ""})));
      on.forEach(function (n, i) {
        if (i) names.appendChild(document.createTextNode(t("ag.sep")));
        names.appendChild(make("span", "mono", n));
      });
    }
    li.appendChild(facts(["connected" in c ? t(c.connected ? "my.connected.yes" : "my.connected.no") : null,
                          c.last_used ? t("ag.last_used", {time: when(c.last_used)}) : null, names]));
    li.appendChild(out);
    return li;
  }

  function draw() {
    if (!box || !my) return;
    A.keepFocus(box, function () {
      box.textContent = "";
      var creds = my.credentials || [];
      if (!creds.length) { box.appendChild(make("p", "ag-empty", t("me.no_credentials"))); return; }
      var ul = make("ul", "ag-list");
      creds.forEach(function (c) { ul.appendChild(credential(c)); });
      box.appendChild(ul);
    });
  }

  async function load(force) {
    var r = await A.request(API + "my");
    if (!r.ok) return;
    var raw = JSON.stringify(r.data);
    if (raw === myRaw && !force) return;
    myRaw = raw;
    my = r.data;
    draw();
  }

  draw();
  setInterval(function () { if (!document.querySelector("dialog.gone[open]")) load(false); }, 15000);
})();
