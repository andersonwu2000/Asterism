// The right column of the messages page (Asterism.right): one thing at a time, or nothing: the task table
// (#task-panel), the member list (#member-panel) or search results (#search-results). #task-toggle and
// #members-toggle in the channel bar show or hide their panel. Which one is open is remembered per project on a wide
// screen; below 900 px the column is a sheet over the messages that starts closed, closes on Escape and gives the
// focus back to its control. Search results take the column while a search is shown and then give back what was
// there before.
"use strict";
(function () {
  var A = window.Asterism, root = document.getElementById("chat");
  if (!A || !root) return;
  var SLUG = root.dataset.slug, KEY = "asterism-right:" + SLUG, OLD_KEY = "asterism-tasks-folded:" + SLUG;
  function byId(id) { return document.getElementById(id); }
  var panels = {tasks: byId("task-panel"), members: byId("member-panel"), search: byId("search-results")};
  var toggles = {tasks: byId("task-toggle"), members: byId("members-toggle")};
  var narrow = window.matchMedia("(max-width: 899.98px)");
  var R = A.right = {current: null, before: null, listeners: []};

  // What a wide screen showed last: "tasks", "members" or "none" (the task table's old folded flag counts).
  function stored() {
    var v = A.store.get(KEY, null);
    if (v === "tasks" || v === "members" || v === "none") return v;
    return A.store.get(OLD_KEY, 0) === 1 ? "none" : "tasks";
  }

  // Show one panel (or none, for null). `how.remember`: a choice of the reader, kept on a wide screen;
  // `how.focus`: on a narrow screen the focus goes into the sheet.
  R.show = function (name, how) {
    how = how || {};
    var was = R.current;
    if (name === "search" && was !== "search") R.before = was;
    Object.keys(panels).forEach(function (k) { if (panels[k]) panels[k].hidden = k !== name; });
    R.current = name || null;
    Object.keys(toggles).forEach(function (k) {
      if (toggles[k]) toggles[k].setAttribute("aria-expanded", String(k === name));
    });
    if (how.remember && !narrow.matches && name !== "search") A.store.set(KEY, name || "none");
    if (name && narrow.matches && how.focus) {
      var close = panels[name].querySelector(".right-close, .search-close");
      (close || panels[name]).focus();
    }
    R.listeners.forEach(function (fn) { fn(R.current, was); });
  };
  R.toggle = function (name) {
    R.show(R.current === name ? null : name, {remember: true, focus: true});
  };
  // After a search: what was there before (nothing on a narrow screen).
  R.giveBack = function () {
    R.show(narrow.matches ? null : (R.before === "search" ? null : R.before));
  };
  R.onShow = function (fn) { R.listeners.push(fn); fn(R.current, null); };

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
  Object.keys(panels).forEach(function (k) {
    if (!panels[k] || k === "search") return;
    panels[k].addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && narrow.matches && !ev.defaultPrevented) {
        R.show(null);
        if (toggles[k]) toggles[k].focus();
      }
    });
  });

  function fit() {
    if (R.current === "search") return;
    var v = stored();
    R.show(narrow.matches ? null : (v === "none" ? null : v));
  }
  if (narrow.addEventListener) narrow.addEventListener("change", fit);
  fit();
})();
