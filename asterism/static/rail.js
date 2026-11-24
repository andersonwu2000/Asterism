// The rail on the far left of every page of a project (#rail) and what goes with it (Asterism.rail):
// - outside chat, the chat button (#rail-chat) shows how many messages in channels are important for the reader (an
//   inverted pill), and outside private messages the private-messages button (#rail-dm) the same for private
//   conversations, from the places frame.js reads on the pages' rhythm;
// - each mode remembers its place: the chat button goes to the place the reader was last in (messages.js keeps it),
//   the files page reopens its own tabs (viewer.js), the agent button returns to the agent last chosen (agentpage.js
//   keeps it), the work button to the tab and scope last shown (workpage.js keeps it);
// - on a wide screen, pressing the button of the mode one is in (chat, private messages, files, agent, work:
//   [data-fold])
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
  var counts = {chat: document.getElementById("rail-chat-count"), dm: document.getElementById("rail-dm-count"),
                my: document.getElementById("rail-my-count")};

  // Where the chat button goes: the place last open in chat, else the project's address (its first channel).
  R.chatHref = function () {
    var place = A.store.get(R.chatPlaceKey, null);
    var base = "/" + encodeURIComponent(SLUG);
    return typeof place === "string" && place ? base + "#" + encodeURIComponent(place) : base;
  };
  if (chat && HERE !== "messages") chat.href = R.chatHref();

  // The agent button returns to the agent last chosen on the agent page, the work button to the tab and scope last
  // shown on the work page (each page keeps its address under its key). Only an address of that page is taken.
  R.agentKey = "asterism-agent-chosen:" + SLUG;
  R.workKey = "asterism-work-place:" + SLUG;
  function returnTo(id, here, key, path) {
    var button = document.getElementById(id);
    if (!button || HERE === here) return;
    var last = A.store.get(key, null), base = "/" + encodeURIComponent(SLUG) + path;
    if (typeof last === "string" && (last === base || last.indexOf(base + "/") === 0 || last.indexOf(base + "?") === 0)) {
      button.href = last;
    }
    button.dataset.back = button.href;          // where it goes when no count sends it elsewhere
  }
  returnTo("rail-my", "agent", R.agentKey, "/agent");
  returnTo("rail-work", "work", R.workKey, "/work");

  // A count (2a): `n` unread for the reader (not muted), `k` of them important. The inverted pill with k when there
  // is any; else, when anything is unread, the mark without a number; else nothing.
  function showOne(count, n, k) {
    shownTotal.n += n;
    shownTotal.k += k;
    if (!count) return;
    count.dataset.unread = String(n);
    count.dataset.important = String(k);
    count.hidden = !n && !k;
    count.classList.toggle("quiet", !k);
    var pill = count.querySelector(".pill"), dot = count.querySelector(".rail-dot"), said = count.querySelector(".vh");
    pill.hidden = !k;
    pill.textContent = String(k);
    if (dot) dot.hidden = !!k || !n;
    said.textContent = k ? t("rail.important", {k: k}) : n ? t("rail.unread") : "";
  }
  // The private button counts the conversations with people, the agent button those with agents (1g); while the
  // agent button carries a mark (the pill, or the unread bar: 2a) it leads to 對話 of the newest such conversation.
  // Below 900 px the rail is in the drawer: its opener (#side-open) carries the same mark while the drawer is closed
  // (2a): the inverted pill with what the rail's buttons count as important, else the bar when something is unread.
  var shownTotal = {n: 0, k: 0}, opener = document.getElementById("side-open"), openerCount = null;
  if (opener) {
    openerCount = A.make("span", "rail-count side-count");
    openerCount.hidden = true;
    var pill = A.make("span", "pill"), dot = A.make("span", "rail-dot");
    pill.setAttribute("aria-hidden", "true");
    dot.setAttribute("aria-hidden", "true");
    openerCount.append(pill, dot);
    opener.appendChild(openerCount);
    opener.dataset.label = opener.getAttribute("aria-label") || "";
  }
  function showOpener() {
    if (!openerCount) return;
    var n = shownTotal.n, k = shownTotal.k;
    openerCount.dataset.unread = String(n);
    openerCount.dataset.important = String(k);
    openerCount.hidden = !n && !k;
    openerCount.classList.toggle("quiet", !k);
    openerCount.firstChild.hidden = !k;
    openerCount.firstChild.textContent = String(k);
    openerCount.lastChild.hidden = !!k || !n;
    var said = k ? t("rail.important", {k: k}) : n ? t("rail.unread") : "";
    opener.setAttribute("aria-label", opener.dataset.label + (said ? " · " + said : ""));
  }
  function showCount(places) {
    var k = {chat: 0, dm: 0, my: 0}, n = {chat: 0, dm: 0, my: 0}, wrote = null;
    shownTotal = {n: 0, k: 0};
    (places.channels || []).forEach(function (c) {
      k.chat += c.important || 0;
      n.chat += c.muted ? c.important || 0 : c.unread || 0;   // a muted channel counts only what is important
    });
    (places["private"] || []).forEach(function (p) {
      var which = p.kind === "agent" ? "my" : "dm";
      k[which] += p.important || 0;
      n[which] += p.unread || 0;
      if (which === "my" && !wrote && (p.important || p.unread)) wrote = p["with"];   // newest first: what the mark is about
    });
    if (HERE !== "messages") showOne(counts.chat, n.chat, k.chat);
    if (HERE !== "dm") showOne(counts.dm, n.dm, k.dm);
    if (HERE !== "agent") {
      showOne(counts.my, n.my, k.my);
      var my = document.getElementById("rail-my");
      if (my && wrote) my.href = "/" + encodeURIComponent(SLUG) + "/agent?name=" + encodeURIComponent(wrote);
      else if (my && my.dataset.back) my.href = my.dataset.back;
    }
    showOpener();
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
