// The project's frame on every page of a project: the navigation (#side) with its channels (#side-channels) and
// private conversations (#side-private), kept current from /api/channels on the pages' rhythm and the presence
// marks from /api/members; the forms to create a channel and to start a private conversation; and below 900 px
// the drawer that #side-open opens. The messages page reads the places through Asterism.side.
"use strict";
(function () {
  var A = window.Asterism, side = document.getElementById("side");
  if (!A || !side) return;
  var t = A.t, make = A.make;
  var SLUG = side.dataset.slug, ME = side.dataset.me;
  var API = "/" + encodeURIComponent(SLUG) + "/api/";
  var PLACES_EVERY_MS = 4000, MEMBERS_EVERY_MS = 15000;
  var lists = {channels: document.getElementById("side-channels"), "private": document.getElementById("side-private")};

  var S = A.side = {
    places: null,                     // what /api/channels answered last
    directory: A.parseJSON(side.dataset.directory, {}),   // name -> {kind, online, owner}
    current: null,                    // the place open on the messages page
    listeners: []
  };
  S.onChange = function (fn) { S.listeners.push(fn); if (S.places) fn(S.places); };
  S.setCurrent = function (place) { S.current = place; draw(true); };

  // ------------------------------------------------------------------ the lists

  function hashOf(place) { return "#" + encodeURIComponent(place); }
  function hrefOf(place) { return "/" + encodeURIComponent(SLUG) + hashOf(place); }

  function presence(who) {
    var mark = make("span", "presence");
    mark.setAttribute("role", "img");
    if (who && who.kind === "agent") {
      mark.className += " agent" + (who.online ? " on" : "");
      mark.setAttribute("aria-label", t(who.online ? "presence.online" : "presence.offline"));
    } else {
      mark.className += " person";
      mark.setAttribute("aria-label", t("presence.person"));
    }
    return mark;
  }
  S.presence = presence;

  function counts(a, unread, important, muted) {
    if (important) {
      var pill = make("span", "pill", String(important));
      pill.setAttribute("aria-hidden", "true");
      a.append(pill, make("span", "vh", t("nav.important", {n: unread, k: important})));
    } else if (unread && !muted) {
      var c = make("span", "count", String(unread));
      c.setAttribute("aria-hidden", "true");
      a.append(c, make("span", "vh", t("nav.unread", {n: unread})));
    }
  }

  function item(place, inner, unread, important, muted) {
    var li = make("li"), a = make("a", "place" + (unread && !muted ? " unread" : "") + (muted ? " muted" : ""));
    a.href = hrefOf(place);
    a.dataset.place = place;
    a.dataset.key = "place:" + place;
    if (place === S.current) a.setAttribute("aria-current", "page");
    inner.forEach(function (n) { a.appendChild(n); });
    counts(a, unread, important, muted);
    li.appendChild(a);
    return li;
  }

  function privateItem(name, unread, important) {
    var who = S.directory[name], inner = [presence(who), make("span", "place-name", name)];
    if (who && who.kind === "agent" && who.owner === ME) inner.push(make("span", "note", t("nav.my_agent")));
    return item(name, inner, unread, important, false);
  }

  var drawn = "";
  function draw(force) {
    var p = S.places;
    if (!p) {                                         // before the first answer: only the current mark
      Array.prototype.forEach.call(side.querySelectorAll("a.place[data-place]"), function (a) {
        if (a.dataset.place === S.current) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
      });
      return;
    }
    var key = JSON.stringify([p, S.current, S.directory]);
    if (key === drawn && !force) return;
    drawn = key;
    A.keepFocus(side, function () {
      lists.channels.textContent = "";
      p.channels.forEach(function (c) {
        var inner = [make("span", "place-name", "#" + c.name)];
        if (c.muted) inner.push(make("span", "note", t("nav.muted")));
        lists.channels.appendChild(item("#" + c.name, inner, c.unread, c.important, c.muted));
      });
      lists["private"].textContent = "";
      var seen = false;
      p["private"].forEach(function (c) {
        if (c["with"] === S.current) seen = true;
        lists["private"].appendChild(privateItem(c["with"], c.unread, c.important));
      });
      if (S.current && S.current.charAt(0) !== "#" && !seen) {     // a conversation not started yet
        lists["private"].insertBefore(privateItem(S.current, 0, 0), lists["private"].firstChild);
      }
    });
  }

  // Several callers may ask at once; only the newest answer is drawn.
  var asked = 0;
  S.refresh = async function () {
    var mine = ++asked;
    var r = await A.request(API + "channels");
    if (!r.ok || mine !== asked) return S.places;
    S.places = {channels: r.data.channels || [], "private": r.data["private"] || []};
    draw(false);
    S.listeners.forEach(function (fn) { fn(S.places); });
    return S.places;
  };

  async function loadMembers() {
    var r = await A.request(API + "members");
    if (!r.ok) return;
    var d = {};
    (r.data.people || []).forEach(function (x) { d[x.name] = {kind: "person"}; });
    (r.data.agents || []).forEach(function (a) { d[a.name] = {kind: "agent", online: !!a.online, owner: a.owner, busy: !!a.busy}; });
    S.directory = d;
    draw(false);
  }

  setInterval(S.refresh, PLACES_EVERY_MS);
  setInterval(loadMembers, MEMBERS_EVERY_MS);
  S.refresh();

  // ------------------------------------------------------------------ creating a channel, starting a conversation

  function reveal(button, show) {
    var form = document.getElementById(button.getAttribute("aria-controls"));
    if (!form) return;
    form.hidden = !show;
    button.setAttribute("aria-expanded", String(show));
    if (show) {
      var field = form.querySelector("input, select");
      if (field) field.focus();
    } else {
      button.focus();
    }
  }
  Array.prototype.forEach.call(side.querySelectorAll("[data-reveal]"), function (b) {
    var form = document.getElementById(b.getAttribute("aria-controls"));
    b.addEventListener("click", function () { reveal(b, form.hidden); });
    form.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") { ev.stopPropagation(); reveal(b, false); }
    });
    var cancel = form.querySelector("[data-dismiss]");
    if (cancel) cancel.addEventListener("click", function () { reveal(b, false); });
  });

  function go(place) {
    closeDrawer(false);
    window.location.href = hrefOf(place);
  }

  var newChannel = document.getElementById("new-channel");
  if (newChannel) {
    newChannel.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var input = newChannel.elements.name, out = newChannel.querySelector("[data-out]");
      var r = await A.request(API + "channels", null, {name: input.value.trim().replace(/^#/, "")});
      if (!r.ok) { out.textContent = A.errorText(r.data.error); return; }
      out.textContent = "";
      input.value = "";
      newChannel.hidden = true;
      side.querySelector('[aria-controls="new-channel"]').setAttribute("aria-expanded", "false");
      await S.refresh();
      go("#" + r.data.name);
    });
  }
  var newPrivate = document.getElementById("new-private");
  if (newPrivate) {
    newPrivate.addEventListener("submit", function (ev) {
      ev.preventDefault();
      newPrivate.hidden = true;
      side.querySelector('[aria-controls="new-private"]').setAttribute("aria-expanded", "false");
      go(newPrivate.elements["with"].value);
    });
  }

  // ------------------------------------------------------------------ the drawer (below 900 px)
  //
  // The navigation slides over the page; the page behind is inert. It closes on Escape, on a click outside, and
  // when a place is chosen; focus goes into it when it opens and back to the opener when it closes.

  var opener = document.getElementById("side-open"), closer = document.getElementById("side-close");
  var scrim = document.getElementById("side-scrim"), page = document.getElementById("page");
  var narrow = window.matchMedia("(max-width: 899.98px)");
  var shown = false;

  function openDrawer() {
    if (!narrow.matches) return;
    shown = true;
    document.body.classList.add("side-shown");
    scrim.hidden = false;
    page.inert = true;
    if (opener) opener.setAttribute("aria-expanded", "true");
    side.setAttribute("role", "dialog");
    side.setAttribute("aria-modal", "true");
    (closer || side).focus();
  }
  function closeDrawer(refocus) {
    if (!shown) return;
    shown = false;
    document.body.classList.remove("side-shown");
    scrim.hidden = true;
    page.inert = false;
    side.removeAttribute("role");
    side.removeAttribute("aria-modal");
    if (opener) {
      opener.setAttribute("aria-expanded", "false");
      if (refocus) opener.focus();
    }
  }
  S.closeDrawer = closeDrawer;

  if (opener) opener.addEventListener("click", openDrawer);
  if (closer) closer.addEventListener("click", function () { closeDrawer(true); });
  scrim.addEventListener("click", function () { closeDrawer(true); });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && shown && !ev.defaultPrevented) closeDrawer(true);
  });
  side.addEventListener("click", function (ev) {
    var a = ev.target.closest && ev.target.closest("a.place");
    if (a) closeDrawer(false);
  });
  var onWidth = function () { if (!narrow.matches) closeDrawer(false); };
  if (narrow.addEventListener) narrow.addEventListener("change", onWidth);
})();
