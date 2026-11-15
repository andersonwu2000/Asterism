// The rail on the far left of every page of a project (#rail) and what goes with it (Asterism.rail):
// - outside chat, the chat button (#rail-chat) shows how many messages are important for the reader (an inverted
//   pill), from the places frame.js reads on the pages' rhythm; in chat it shows nothing extra;
// - each mode remembers its place: the chat button goes to the place the reader was last in (messages.js keeps it),
//   the files page reopens its own tabs (viewer.js);
// - the mode's second column folds away on a wide screen ([data-fold] buttons in the page's header), remembered per
//   mode in localStorage and applied before the first paint by the head script (data-folded on <html>);
// - below 900 px the rail and the second column live in the drawer (#nav) that #side-open opens.
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

  var chat = document.getElementById("rail-chat"), count = document.getElementById("rail-count");

  // Where the chat button goes: the place last open in chat, else the project's address (#general).
  R.chatHref = function () {
    var place = A.store.get(R.chatPlaceKey, null);
    var base = "/" + encodeURIComponent(SLUG);
    return typeof place === "string" && place ? base + "#" + encodeURIComponent(place) : base;
  };
  if (chat && HERE !== "messages") chat.href = R.chatHref();

  function showCount(places) {
    if (!count || HERE === "messages") return;
    var k = 0;
    (places.channels || []).forEach(function (c) { k += c.important || 0; });
    (places["private"] || []).forEach(function (p) { k += p.important || 0; });
    count.hidden = !k;
    count.firstChild.textContent = String(k);
    count.lastChild.textContent = t("rail.important", {k: k});
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
  Array.prototype.forEach.call(document.querySelectorAll("[data-fold]"), function (b) {
    b.addEventListener("click", function () { setFolded(b.dataset.fold, folded().indexOf(b.dataset.fold) < 0); });
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
  var onWidth = function () { if (!narrow.matches) closeDrawer(false); };
  if (narrow.addEventListener) narrow.addEventListener("change", onWidth);
})();
