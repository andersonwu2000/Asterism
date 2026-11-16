// The project menu in the top-left cell (#project-menu-button, #project-menu; the items are drawn by the server, each
// only for who may use it) and the floating panel its acts open (Asterism.project): inviting people (a link,
// optionally for one GitHub login), inviting an agent of mine (the server's #invite-panel, moved into the panel), creating
// a channel. Any control with data-act opens the same panel (the "+" of the channels, the agent page's "invite
// agent"). A link to a settings layer remembers the page it was followed from, so that closing the layer comes back
// here.
"use strict";
(function () {
  var A = window.Asterism, rail = document.getElementById("rail");
  if (!A || !rail) return;
  var t = A.t, make = A.make;
  var SLUG = rail.dataset.slug, API = "/" + encodeURIComponent(SLUG) + "/api/";
  var P = A.project = {fromKey: "asterism-settings-from:" + SLUG};

  // ------------------------------------------------------------------ the menu

  var button = document.getElementById("project-menu-button"), box = document.getElementById("project-menu");
  if (button && box) {
    button.addEventListener("click", function () {
      if (A.popup.isOpen(box)) { A.popup.close(true); return; }
      A.popup.open(box, button, {align: "start"});
    });
    button.addEventListener("keydown", function (ev) {
      if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
      ev.preventDefault();
      A.popup.open(box, button, {align: "start"});
      if (ev.key === "ArrowUp") A.menuKeys(box, {key: "End", preventDefault: function () {}});
    });
    box.addEventListener("keydown", function (ev) {
      if (ev.key === "Tab") { A.popup.close(false); return; }
      A.menuKeys(box, ev);
    });
    box.addEventListener("click", function (ev) {
      if (ev.target.closest && ev.target.closest(".menu-item")) A.popup.close(false);
    });
  }

  // ------------------------------------------------------------------ the floating panel
  //
  // A modal dialog over the dimmed page (as the floating confirmation): a title, the form of the act, its answer.
  // Escape and a click outside close it; the focus goes back to what opened it.

  var panel = null;

  function dialog() {
    if (panel) return panel;
    var d = make("dialog", "panel");
    d.setAttribute("closedby", "any");
    d.setAttribute("aria-labelledby", "panel-title");
    var head = make("div", "panel-head"), title = make("h2", "panel-title");
    title.id = "panel-title";
    var x = A.button("icon-btn", null, function () { d.close(); });
    x.appendChild(make("span", "cross")).setAttribute("aria-hidden", "true");
    x.setAttribute("aria-label", t("pm.close"));
    x.title = t("pm.close");
    head.append(title, x);
    var body = make("div", "panel-body");
    d.append(head, body);
    document.body.appendChild(d);
    if (!("closedBy" in HTMLDialogElement.prototype)) {       // a click on the backdrop is a click outside
      d.addEventListener("click", function (ev) {
        if (ev.target !== d) return;
        var r = d.getBoundingClientRect();
        if (ev.clientY < r.top || ev.clientY > r.bottom || ev.clientX < r.left || ev.clientX > r.right) d.close();
      });
    }
    d.addEventListener("close", function () {
      if (panel.opener && panel.opener.isConnected) panel.opener.focus();
      panel.opener = null;
    });
    panel = {dialog: d, title: title, body: body, opener: null};
    return panel;
  }

  // What the server drew for inviting an agent lives in the page; it goes back there when another act is shown.
  var invitePanel = document.getElementById("invite-panel");

  function show(titleKey, fill, opener) {
    var p = dialog();
    p.opener = opener && opener !== document.body ? opener : button;
    p.title.textContent = t(titleKey);
    if (invitePanel && p.body.contains(invitePanel)) { invitePanel.hidden = true; document.body.appendChild(invitePanel); }
    p.body.textContent = "";
    fill(p.body);
    p.dialog.showModal();
    var first = p.body.querySelector("input, button");
    if (first) first.focus();
  }

  function field(labelKey, name, extra) {
    var label = make("label", "field"), input = make("input");
    input.name = name;
    input.autocomplete = "off";
    input.spellcheck = false;
    input.setAttribute("autocapitalize", "off");
    Object.keys(extra || {}).forEach(function (k) { input.setAttribute(k, extra[k]); });
    label.append(make("span", "", t(labelKey)), input);
    return label;
  }

  function invitePeople(body) {
    var form = make("form", "stack"), out = make("p", "out"), result = make("div", "panel-result");
    out.setAttribute("role", "status");
    form.append(make("p", "dim", t("admin.invite_hint")), field("admin.invite_login", "github_login", {maxlength: "39"}));
    var row = make("div", "row"), go = make("button", "btn primary", t("admin.invite_button"));
    row.appendChild(go);
    form.append(row, out, result);
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var login = form.elements.github_login.value.trim(), payload = login ? {github_login: login} : {};
      go.disabled = true;
      try {
        var r = await A.request(API + "invites", null, payload);
        out.textContent = r.ok ? "" : A.errorText(r.data.error);
        result.textContent = "";
        if (r.ok) result.append(make("p", "", t("pm.people_link")), A.copyLine(r.data.url));
      } finally {
        go.disabled = false;
      }
    });
    body.appendChild(form);
  }

  // Inviting an agent: each press of #invite-make makes a new link and replaces what the previous one showed.
  function inviteAgent(body) {
    if (!invitePanel) return;
    invitePanel.hidden = false;
    body.appendChild(invitePanel);
  }
  var makeLink = invitePanel && document.getElementById("invite-make");
  if (makeLink) {
    makeLink.addEventListener("click", async function () {
      var out = makeLink.parentNode.querySelector("[data-out]"), result = document.getElementById("invite-result");
      makeLink.disabled = true;
      try {
        var r = await A.request(makeLink.dataset.api, null, {});
        out.textContent = r.ok ? "" : A.errorText(r.data.error);
        if (r.ok) { A.showInvite(result, r.data); result.hidden = false; }
      } finally {
        makeLink.disabled = false;
      }
    });
  }

  function newChannel(body) {
    var form = make("form", "stack"), out = make("p", "out");
    out.setAttribute("role", "status");
    form.appendChild(field("msg.channel_name", "name", {required: "", maxlength: "40"}));
    var row = make("div", "row");
    row.appendChild(make("button", "btn primary", t("msg.new_channel")));
    form.append(row, out);
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var r = await A.request(API + "channels", null, {name: form.elements.name.value.trim().replace(/^#/, "")});
      if (!r.ok) { out.textContent = A.errorText(r.data.error); return; }
      panel.opener = null;
      panel.dialog.close();
      if (A.rail) A.rail.closeDrawer(false);
      window.location.href = "/" + encodeURIComponent(SLUG) + "#" + encodeURIComponent("#" + r.data.name);
    });
    body.appendChild(form);
  }

  var ACTS = {"invite-people": ["pm.people_title", invitePeople], "invite-agent": ["invite.title", inviteAgent],
              "new-channel": ["pm.channel_title", newChannel]};
  P.act = function (name, opener) {
    if (ACTS[name]) show(ACTS[name][0], ACTS[name][1], opener || document.activeElement);
  };
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest("[data-act]");
    if (!b || !ACTS[b.dataset.act]) return;
    // An item of the project menu: the focus goes back to the menu's button, which stays where it is.
    P.act(b.dataset.act, b.closest("#project-menu") ? button : b);
  });

  // ------------------------------------------------------------------ where a settings layer was opened from

  var SETTINGS = new RegExp("^/" + encodeURIComponent(SLUG).replace(/[.*+?^${}()|[\]\\]/g, "\\$&") +
                            "/(settings(/|$)|channels/[^/]+/settings(/|$)|members$|admin$)");
  P.isSettings = function (path) { return SETTINGS.test(path); };
  function remember() {
    try { sessionStorage.setItem(P.fromKey, window.location.pathname + window.location.search + window.location.hash); }
    catch (err) { /* closing then goes to chat */ }
  }
  // Open a settings layer from a control that is not a link (the channel bar's name).
  P.openSettings = function (href) {
    remember();
    window.location.href = href;
  };
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest && ev.target.closest("a[href]");
    if (!a || a.origin !== window.location.origin || !P.isSettings(a.pathname) || P.isSettings(window.location.pathname)) return;
    remember();
  }, true);
})();
