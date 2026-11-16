// The rail on the far left of every page of a project (#rail) and what goes with it (Asterism.rail):
// - outside chat, the chat button (#rail-chat) shows how many messages in channels are important for the reader (an
//   inverted pill), and outside private messages the private-messages button (#rail-dm) the same for private
//   conversations, from the places frame.js reads on the pages' rhythm;
// - each mode remembers its place: the chat button goes to the place the reader was last in (messages.js keeps it),
//   the files page reopens its own tabs (viewer.js), the agent button returns to the tab and scope last shown
//   (agentpage.js keeps it);
// - on a wide screen, pressing the button of the mode one is in (chat, private messages, files, agent: [data-fold])
//   folds that mode's left cells (the top-left cell and the second column) away or brings them back, remembered per
//   mode in localStorage and applied before the first paint by the head script (data-folded on <html>);
// - below 900 px the rail and the left cells live in the drawer (#nav) that #side-open opens: the top-left cell
//   (#corner) moves to the head of the second column there, and back into the top bar on a wide screen.
"use strict";
(function () {
  var A = window.Asterism, rail = document.getElementById("rail");
  if (!A || !rail) return;
  var t = A.t;
  var SLUG = rail.dataset.slug, HERE = rail.dataset.here;
  var R = A.rail = {};
  R.chatPlaceKey = "asterism-chat-place:" + SLUG;
  R.mentionKey = "asterism-mention:" + SLUG;

  // ------------------------------------------------------------------ the chat button

  var chat = document.getElementById("rail-chat");
  var counts = {chat: document.getElementById("rail-chat-count"), dm: document.getElementById("rail-dm-count")};

  // Where the chat button goes: the place last open in chat, else the project's address (#general).
  R.chatHref = function () {
    var place = A.store.get(R.chatPlaceKey, null);
    var base = "/" + encodeURIComponent(SLUG);
    return typeof place === "string" && place ? base + "#" + encodeURIComponent(place) : base;
  };
  if (chat && HERE !== "messages") chat.href = R.chatHref();

  // The agent button: the address of the agent page last shown (its tab and scope).
  R.agentKey = "asterism-agent-place:" + SLUG;
  var agentButton = document.getElementById("rail-my");
  if (agentButton && HERE !== "agent") {
    var lastAgent = A.store.get(R.agentKey, null), agentBase = "/" + encodeURIComponent(SLUG) + "/agent";
    if (typeof lastAgent === "string" && (lastAgent === agentBase || lastAgent.indexOf(agentBase + "/") === 0 ||
                                          lastAgent.indexOf(agentBase + "?") === 0)) {
      agentButton.href = lastAgent;
    }
  }

  function showOne(count, k) {
    if (!count) return;
    count.hidden = !k;
    count.firstChild.textContent = String(k);
    count.lastChild.textContent = t("rail.important", {k: k});
  }
  function showCount(places) {
    var inChannels = 0, inPrivate = 0;
    (places.channels || []).forEach(function (c) { inChannels += c.important || 0; });
    (places["private"] || []).forEach(function (p) { inPrivate += p.important || 0; });
    if (HERE !== "messages") showOne(counts.chat, inChannels);
    if (HERE !== "dm") showOne(counts.dm, inPrivate);
  }
  if (A.side) A.side.onChange(showCount);

  // ------------------------------------------------------------------ folding the second column

  var html = document.documentElement, FOLD_KEY = "asterism-folded";
  function folded() {
    return (html.getAttribute("data-folded") || "").split(/\s+/).filter(Boolean);
  }
  function setFolded(mode, fold) {
    var list = folded().filter(function (m) { return m !== mode; });
    if (fold) list.push(mode);
    if (list.length) html.setAttribute("data-folded", list.join(" ")); else html.removeAttribute("data-folded");
    try { localStorage.setItem(FOLD_KEY, list.join(" ")); } catch (err) { /* this page only */ }
    label();
  }
  function label() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-fold]"), function (b) {
      b.setAttribute("aria-expanded", String(folded().indexOf(b.dataset.fold) < 0));
    });
  }
  var narrowNow = window.matchMedia("(max-width: 899.98px)");
  Array.prototype.forEach.call(document.querySelectorAll("[data-fold]"), function (b) {
    b.addEventListener("click", function (ev) {
      if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;   // a new tab still opens
      ev.preventDefault();
      if (narrowNow.matches) { closeDrawer(true); return; }          // in the drawer the column is always there
      setFolded(b.dataset.fold, folded().indexOf(b.dataset.fold) < 0);
    });
  });
  label();
  window.addEventListener("storage", function (ev) {
    if (ev.key !== FOLD_KEY) return;
    if (ev.newValue) html.setAttribute("data-folded", ev.newValue); else html.removeAttribute("data-folded");
    label();
  });

  // ------------------------------------------------------------------ the drawer (below 900 px)
  //
  // The rail and the mode's second column slide over the page; the page behind is inert. It closes on Escape, on a
  // click outside, and when a place or a page is chosen; focus goes into it when it opens and back to the opener
  // when it closes.

  var nav = document.getElementById("nav"), opener = document.getElementById("side-open");
  var closer = document.getElementById("side-close"), scrim = document.getElementById("side-scrim");
  var page = document.getElementById("page");
  var narrow = window.matchMedia("(max-width: 899.98px)");
  var shown = false;

  // The top-left cell belongs over the second column: in the top bar's grid on a wide screen, at the head of the
  // column in the drawer below 900 px (the stylesheet hides it in the bar there until it has moved).
  var corner = document.getElementById("corner"), column = nav.querySelector(".column");
  var bar = corner && corner.parentNode;
  function placeCorner() {
    if (!corner || !column) return;
    if (narrow.matches) { if (corner.parentNode !== column) column.insertBefore(corner, column.firstChild); }
    else if (corner.parentNode !== bar) bar.insertBefore(corner, bar.firstChild);
  }
  placeCorner();

  function openDrawer() {
    if (!narrow.matches) return;
    shown = true;
    document.body.classList.add("side-shown");
    scrim.hidden = false;
    page.inert = true;
    if (opener) opener.setAttribute("aria-expanded", "true");
    nav.setAttribute("role", "dialog");
    nav.setAttribute("aria-modal", "true");
    (closer || nav).focus();
  }
  function closeDrawer(refocus) {
    if (!shown) return;
    shown = false;
    document.body.classList.remove("side-shown");
    scrim.hidden = true;
    page.inert = false;
    nav.removeAttribute("role");
    nav.removeAttribute("aria-modal");
    if (opener) {
      opener.setAttribute("aria-expanded", "false");
      if (refocus) opener.focus();
    }
  }
  R.closeDrawer = closeDrawer;

  if (opener) opener.addEventListener("click", openDrawer);
  if (closer) closer.addEventListener("click", function () { closeDrawer(true); });
  scrim.addEventListener("click", function () { closeDrawer(true); });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && shown && !ev.defaultPrevented) {
      ev.preventDefault();               // the Escape is spent: it does not also close what is under the drawer
      closeDrawer(true);
    }
  });
  // Choosing a place, a page or a file closes it.
  nav.addEventListener("click", function (ev) {
    var hit = ev.target.closest && ev.target.closest("a[href], [data-closes-drawer]");
    if (hit && !hit.closest("#me-menu")) closeDrawer(false);
  });
  R.isDrawer = function () { return shown; };
  var onWidth = function () { placeCorner(); if (!narrow.matches) closeDrawer(false); };
  if (narrow.addEventListener) narrow.addEventListener("change", onWidth);
})();
