// The right column of the messages pages (Asterism.right): one thing at a time, or nothing: the member list
// (#member-panel, with each member's status) or search (#search-results: the field and its results). #members-toggle
// and #search-open in the top bar show or hide their panel. Whether the member list is open is remembered per project
// on a wide screen; below 900 px the column is a sheet over the messages that starts closed, closes on Escape and
// gives the focus back to its control. Search takes the column while it is open and then gives back what was there.
"use strict";
(function () {
  var A = window.Asterism, root = document.getElementById("chat");
  if (!A || !root) return;
  var SLUG = root.dataset.slug, KEY = "asterism-right:" + SLUG;
  function byId(id) { return document.getElementById(id); }
  var panels = {members: byId("member-panel"), search: byId("search-results")};
  var toggles = {members: byId("members-toggle"), search: byId("search-open")};
  var narrow = window.matchMedia("(max-width: 899.98px)");
  var R = A.right = {current: null, before: null, listeners: []};

  // What a wide screen showed last: the member list (also for the task table of earlier versions) or nothing.
  function stored() { return A.store.get(KEY, "members") === "none" ? "none" : "members"; }

  // Show one panel (or none, for null). `how.remember`: a choice of the reader, kept on a wide screen;
  // `how.focus`: the focus goes into the panel (always for search, on a narrow screen for the member list).
  R.show = function (name, how) {
    how = how || {};
    var was = R.current;
    if (name === "search" && was !== "search") R.before = was;
    Object.keys(panels).forEach(function (k) { if (panels[k]) panels[k].hidden = k !== name; });
    R.current = name || null;
    Object.keys(toggles).forEach(function (k) {
      if (toggles[k]) toggles[k].setAttribute("aria-expanded", String(k === name));
    });
    if (how.remember && !narrow.matches && name !== "search" && was !== "search") A.store.set(KEY, name || "none");
    if (name && how.focus) {
      var into = name === "search" ? byId("search-input") : narrow.matches ? panels[name].querySelector(".right-close") : null;
      if (into) into.focus();
    }
    R.listeners.forEach(function (fn) { fn(R.current, was); });
  };
  R.toggle = function (name) {
    if (R.current === name) {
      if (name === "search") R.giveBack(); else R.show(null, {remember: true});
      return;
    }
    R.show(name, {remember: true, focus: true});
  };
  // After a search: what was there before (nothing on a narrow screen).
  R.giveBack = function () {
    R.show(narrow.matches ? null : (R.before === "search" ? null : R.before));
  };
  R.onShow = function (fn) { R.listeners.push(fn); fn(R.current, null); };
  // Whether the column is a sheet over the messages (below 900 px).
  R.isSheet = function () { return narrow.matches; };

  Object.keys(toggles).forEach(function (k) {
    if (toggles[k]) toggles[k].addEventListener("click", function () { R.toggle(k); });
  });
  Array.prototype.forEach.call(document.querySelectorAll(".right-panel .right-close"), function (b) {
    b.addEventListener("click", function () {
      var name = R.current;
      R.show(null, {remember: true});
      if (toggles[name]) toggles[name].focus();
    });
  });
  if (panels.members) {
    panels.members.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && narrow.matches && !ev.defaultPrevented) {
        R.show(null);
        if (toggles.members) toggles.members.focus();
      }
    });
  }

  function fit() {
    if (R.current === "search") return;
    R.show(narrow.matches || stored() === "none" ? null : "members");
  }
  if (narrow.addEventListener) narrow.addEventListener("change", fit);
  fit();
})();
