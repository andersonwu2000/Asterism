// The page "members and groups". On the left (#groups) the list: all members, then the custom groups, the default
// groups and each person's agents, each with its number of members. On the right (#group-detail) the chosen entry,
// named in the address (?g=<group>; none: all members) so a reload or a shared link shows the same thing:
// - all members: every person and agent with their groups, and the acts that belong to a member (into and out of a
//   group, out of the project);
// - a custom or default group: its members (add, take out) and its permissions as rows, saved as each changes
//   (only a custom group's, by who may manage groups); a custom group can be removed;
// - a person's agents: those agents and that person's four switches, which the person changes here.
// The data is /api/members (embedded in the page at first, then read again every 15 s while nobody is mid-act).
// Only what the reader may do is offered; a refusal shows the server's sentence at the row that was used. Taking a
// member out of a group confirms in place, in two steps; removing a group or a member floats (Asterism.gone).
"use strict";
(function () {
  var A = window.Asterism, root = document.getElementById("members-root");
  if (!A || !root) return;
  var t = A.t, make = A.make;
  var SLUG = root.dataset.slug, API = "/" + encodeURIComponent(SLUG) + "/api/";
  var CATALOGUE = A.parseJSON(root.dataset.catalogue, []), MANAGEMENT = A.parseJSON(root.dataset.management, []);
  var SWITCHES = ["others_mention", "others_channel", "others_assign", "others_regroup"];
  var EVERY_MS = 15000;
  var list = document.getElementById("groups-body"), detail = document.getElementById("group-detail");
  var view = A.parseJSON(root.dataset.view, null), last = JSON.stringify(view);
  var narrow = window.matchMedia("(max-width: 759.98px)");
  if (!view) return;

  // ------------------------------------------------------------------ what the data says

  function mine(p) { return view.me.permissions.indexOf(p) >= 0; }
  function holdsAll(perms) { return perms.every(mine); }
  function chosen() { return new URLSearchParams(window.location.search).get("g") || ""; }
  function group(name) {
    for (var i = 0; i < view.groups.length; i++) if (view.groups[i].name === name) return view.groups[i];
    return null;
  }
  function ownership(person) {
    return view.groups.filter(function (g) { return g.kind === "ownership" && g.owner === person; })[0] || null;
  }
  function label(g) {
    if (!g) return "";
    if (g.kind === "default" && A.MSG["group." + g.name]) return t("group." + g.name);
    if (g.kind === "ownership" && g.owner) return t("group.ownership", {owner: g.owner});
    return g.name;
  }
  function labelOf(name) { return label(group(name)) || name; }
  function inGroup(name) {
    return {people: view.people.filter(function (x) { return x.groups.indexOf(name) >= 0; }),
            agents: view.agents.filter(function (x) { return x.groups.indexOf(name) >= 0; })};
  }
  function count(name) { var m = inGroup(name); return m.people.length + m.agents.length; }

  // May the reader put `who` (a row of people or agents) into, or take it out of, the group `g`? (The server's rules:
  // projects.change_groups; offering only what will pass.)
  function mayRegroup(who, isAgent, g) {
    if (!g || g.kind === "ownership") return false;
    if (isAgent && who.owner === view.me.name) return true;           // one's own agent: groups one is in (adding)
    if (!mine("manage_groups") || !holdsAll(g.permissions)) return false;
    if (isAgent) {
      var own = ownership(who.owner);
      return !!(own && own.switches && own.switches.others_regroup);
    }
    return true;
  }
  function mayAdd(who, isAgent, g) {
    if (!mayRegroup(who, isAgent, g)) return false;
    if (isAgent && who.owner === view.me.name) {
      var me = view.people.filter(function (x) { return x.name === view.me.name; })[0];
      return !!(me && me.groups.indexOf(g.name) >= 0);
    }
    return true;
  }
  function closedToMe(who, isAgent) {             // another person's agent whose person keeps its groups closed
    if (!isAgent || who.owner === view.me.name || !mine("manage_groups")) return false;
    var own = ownership(who.owner);
    return !(own && own.switches && own.switches.others_regroup);
  }
  function mayRemove(who, isAgent) {
    if (isAgent) return who.owner === view.me.name || mine("manage_members");
    if (who.name === view.me.name || !mine("manage_members")) return false;
    var held = [];
    who.groups.forEach(function (n) { var g = group(n); if (g) held = held.concat(g.permissions); });
    return holdsAll(held);
  }

  // ------------------------------------------------------------------ calls

  async function load(force) {
    if (!force && busy()) return;
    var r = await A.request(API + "members");
    if (!r.ok) return;
    var raw = JSON.stringify(r.data);
    if (raw === last && !force) return;
    if (!force && busy()) return;
    last = raw;
    view = r.data;
    draw();
  }

  // Someone is choosing, typing, has an act armed or the floating confirmation open: a redraw would lose it.
  function busy() {
    var a = document.activeElement;
    return A.isArmed(root) || !!document.querySelector("dialog.gone[open]") ||
           !!(a && root.contains(a) && /^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName) && a.type !== "checkbox");
  }

  async function regroup(member, add, remove, out) {
    var r = await A.request(API + "members/" + encodeURIComponent(member) + "/groups", null, {add: add, remove: remove});
    if (!r.ok) { out.textContent = A.refusal("mem.refused", r.data); return false; }
    await load(true);
    return true;
  }

  // ------------------------------------------------------------------ the list

  function go(name, focusDetail) {
    var url = window.location.pathname + (name ? "?g=" + encodeURIComponent(name) : "");
    if (url !== window.location.pathname + window.location.search) window.history.pushState(null, "", url);
    draw();
    if (focusDetail) detail.focus({preventScroll: false});
  }

  function entry(name, text, n, mono) {
    var li = make("li"), a = make("a", "place");
    a.href = window.location.pathname + (name ? "?g=" + encodeURIComponent(name) : "");
    a.dataset.key = "g:" + name;
    a.dataset.group = name;
    if (chosen() === name) a.setAttribute("aria-current", "true");
    var span = make("span", "place-name" + (mono ? " mono" : ""), text);
    var c = make("span", "count", t("mem.count", {n: n}));
    c.setAttribute("aria-hidden", "true");
    a.append(span, c, make("span", "vh", t("mem.count_label", {n: n})));
    li.appendChild(a);
    return li;
  }

  function section(title, groups) {
    if (!groups.length) return null;
    var sec = make("section", "groups-sec"), ul = make("ul", "side-list");
    if (title) sec.appendChild(make("h3", "", title));
    groups.forEach(function (g) { ul.appendChild(entry(g.name, label(g), count(g.name), g.kind === "custom")); });
    sec.appendChild(ul);
    return sec;
  }

  function drawList() {
    list.textContent = "";
    var all = make("ul", "side-list");
    all.appendChild(entry("", t("mem.all"), view.people.length + view.agents.length, false));
    list.appendChild(all);
    [["mem.custom", "custom"], ["mem.default", "default"], ["mem.ownership", "ownership"]].forEach(function (s) {
      var sec = section(t(s[0]), view.groups.filter(function (g) { return g.kind === s[1]; }));
      if (sec) list.appendChild(sec);
    });
  }

  list.addEventListener("click", function (ev) {
    var a = ev.target.closest && ev.target.closest("a.place");
    if (!a || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;
    ev.preventDefault();
    go(a.dataset.group, narrow.matches);
  });
  window.addEventListener("popstate", draw);

  // ------------------------------------------------------------------ rows of members

  function presence(who, isAgent) {
    var d = isAgent ? {kind: "agent", online: who.online} : {kind: "person"};
    return A.side ? A.side.presence(d) : make("span");
  }

  function subline(who, isAgent) {
    if (!isAgent) return "";                    // the square already says "a person"
    var bits = [t("mem.agent_of", {owner: who.owner}), t(who.online ? "presence.online" : "presence.offline")];
    if (who.busy) bits.push(t("mem.busy"));
    return bits.join(" · ");
  }

  function memberRow(who, isAgent) {
    var li = make("li", "mrow"), text = make("div", "mtext");
    text.appendChild(make("span", "mname" + (isAgent ? " mono" : ""), who.name));
    if (isAgent) text.appendChild(make("span", "msub", subline(who, isAgent)));
    li.append(presence(who, isAgent), text);
    return li;
  }

  function outOf(li) {
    var out = make("div", "out");
    out.setAttribute("aria-live", "polite");
    li.appendChild(out);
    return out;
  }

  function removeButton(who, isAgent, after) {
    var b = A.button("btn", t("mem.remove_member"));
    b.dataset.key = "rm:" + who.name;
    b.addEventListener("click", function () {
      var kind = isAgent ? "agent" : "person";
      A.gone({title: t("gone." + kind + ".title", {name: who.name}), text: t("gone." + kind + ".text", {name: who.name}),
              name: who.name, button: t("gone.member.button"), opener: b, after: after || detail,
              run: function () { return A.request(API + "members/" + encodeURIComponent(who.name) + "/remove", null, {}); },
              done: function () { load(true); }});
    });
    return b;
  }

  // ------------------------------------------------------------------ all members

  function allRow(who, isAgent) {
    var li = memberRow(who, isAgent), text = li.querySelector(".mtext"), tags = make("div", "mtags");
    var acts = make("div", "macts"), out;
    if (!who.groups.length) tags.appendChild(make("span", "dim small", t("mem.no_groups")));
    who.groups.forEach(function (n) {
      var g = group(n);
      if (mayRegroup(who, isAgent, g)) {
        var chip = A.button("chip-btn", labelOf(n)), x = make("span", "cross");
        x.setAttribute("aria-hidden", "true");
        chip.appendChild(x);
        chip.dataset.key = "out:" + who.name + ":" + n;
        chip.setAttribute("aria-label", t("mem.take_out_label", {group: labelOf(n), name: who.name}));
        chip.addEventListener("click", function () {
          if (!A.twoStep(chip, t("mem.confirm_take_out", {group: labelOf(n), name: who.name}))) return;
          regroup(who.name, [], [n], out);
        });
        tags.appendChild(chip);
      } else {
        tags.appendChild(make("span", "tag", labelOf(n)));
      }
    });
    text.appendChild(tags);
    var choices = view.groups.filter(function (g) { return who.groups.indexOf(g.name) < 0 && mayAdd(who, isAgent, g); });
    if (choices.length) {
      var sel = make("select");
      sel.dataset.key = "add:" + who.name;
      sel.setAttribute("aria-label", t("mem.add_group_label", {name: who.name}));
      choices.forEach(function (g) { var o = make("option", "", label(g)); o.value = g.name; sel.appendChild(o); });
      var add = A.button("btn", t("mem.add"), function () { regroup(who.name, [sel.value], [], out); });
      add.dataset.key = "add-go:" + who.name;
      acts.append(sel, add);
    }
    if (mayRemove(who, isAgent)) acts.appendChild(removeButton(who, isAgent, null));
    if (acts.childNodes.length) li.appendChild(acts);
    out = outOf(li);
    return li;
  }

  function drawAll() {
    var head = make("header", "gd-head");
    var h = make("h2", "gd-title", t("mem.all"));
    h.id = "gd-title";
    head.append(h, make("p", "", t("mem.all_hint")));
    detail.appendChild(head);
    [["mem.people", view.people, false], ["mem.agents", view.agents, true]].forEach(function (s) {
      if (!s[1].length) return;
      var sec = make("section", "gd-sec"), ul = make("ul", "mlist");
      sec.appendChild(make("h3", "", t(s[0]) + " · " + s[1].length));
      s[1].forEach(function (who) { ul.appendChild(allRow(who, s[2])); });
      sec.appendChild(ul);
      detail.appendChild(sec);
    });
  }

  // ------------------------------------------------------------------ one group

  function membersSection(g) {
    var sec = make("section", "gd-sec"), m = inGroup(g.name);
    sec.appendChild(make("h3", "", t("mem.members") + " · " + (m.people.length + m.agents.length)));
    if (g.kind !== "ownership") {
      var cands = view.people.filter(function (x) { return x.groups.indexOf(g.name) < 0 && mayAdd(x, false, g); })
        .map(function (x) { return [x, false]; })
        .concat(view.agents.filter(function (x) { return x.groups.indexOf(g.name) < 0 && mayAdd(x, true, g); })
          .map(function (x) { return [x, true]; }));
      if (cands.length) {
        var row = make("div", "gd-add"), sel = make("select"), out = make("span", "out");
        out.setAttribute("aria-live", "polite");
        sel.dataset.key = "gadd:" + g.name;
        sel.setAttribute("aria-label", t("mem.add_label", {group: label(g)}));
        cands.forEach(function (c) {
          var o = make("option", "", c[1] ? c[0].name + " (" + t("mem.agent_of", {owner: c[0].owner}) + ")" : c[0].name);
          o.value = c[0].name;
          sel.appendChild(o);
        });
        var add = A.button("btn", t("mem.add"), function () { regroup(sel.value, [g.name], [], out); });
        add.dataset.key = "gadd-go:" + g.name;
        row.append(sel, add, out);
        sec.appendChild(row);
      }
    }
    var ul = make("ul", "mlist");
    m.people.map(function (x) { return [x, false]; }).concat(m.agents.map(function (x) { return [x, true]; }))
      .forEach(function (c) {
        var who = c[0], isAgent = c[1], li = memberRow(who, isAgent), out;
        if (g.kind !== "ownership" && mayRegroup(who, isAgent, g)) {
          var acts = make("div", "macts");
          var b = A.button("btn", t("mem.take_out"));
          b.dataset.key = "gout:" + who.name;
          b.setAttribute("aria-label", t("mem.take_out_label", {group: label(g), name: who.name}));
          b.addEventListener("click", function () {
            if (!A.twoStep(b, t("mem.confirm_take_out", {group: label(g), name: who.name}))) return;
            regroup(who.name, [], [g.name], out);
          });
          acts.appendChild(b);
          li.appendChild(acts);
        } else if (g.kind !== "ownership" && closedToMe(who, isAgent)) {
          li.appendChild(make("p", "mnote", t("mem.closed_regroup", {owner: who.owner})));
        }
        out = outOf(li);
        ul.appendChild(li);
      });
    if (!ul.childNodes.length) {
      ul.appendChild(make("li", "mempty", g.kind === "ownership" ? t("mem.no_agents", {owner: g.owner}) : t("mem.empty")));
    }
    sec.appendChild(ul);
    return sec;
  }

  function permRow(g, p, editable) {
    var row = make("div", "perm-row"), box = make("input"), id = "perm-" + p;
    box.type = "checkbox";
    box.id = id;
    box.checked = g.permissions.indexOf(p) >= 0;
    box.disabled = !editable || !mine(p);
    box.dataset.key = "perm:" + g.name + ":" + p;
    var text = make("label", "perm-text");
    text.htmlFor = id;
    text.append(make("span", "perm-name", t("perm." + p)), make("span", "perm-hint", t("perm_hint." + p)));
    var out = make("span", "out");
    out.setAttribute("aria-live", "polite");
    if (editable && !mine(p)) {
      row.classList.add("unheld");
      text.appendChild(make("span", "perm-hint", t("mem.perm_unheld")));
    }
    text.appendChild(out);
    row.append(box, text);
    box.addEventListener("change", async function () {
      var want = CATALOGUE.filter(function (x) { return x === p ? box.checked : g.permissions.indexOf(x) >= 0; });
      out.textContent = "";
      var r = await A.request(API + "groups/" + encodeURIComponent(g.name), null, {permissions: want});
      if (!r.ok) {
        box.checked = !box.checked;
        out.textContent = A.refusal("mem.refused", r.data);
        return;
      }
      g.permissions = r.data.permissions;      // the page's copy follows; the next reading redraws the rest
      out.textContent = t("mem.saved");
    });
    return row;
  }

  function permsSection(g) {
    var sec = make("section", "gd-sec"), editable = g.kind === "custom" && mine("manage_groups") && holdsAll(g.permissions);
    sec.appendChild(make("h3", "", t("mem.perms")));
    sec.appendChild(make("p", "", t("mem.perms_hint")));
    var why = g.kind === "default" ? "mem.perms_fixed" : !mine("manage_groups") ? "mem.perms_readonly" :
              !holdsAll(g.permissions) ? "mem.perms_not_mine" : null;
    if (why) sec.appendChild(make("p", "", t(why)));
    var plain = make("div", "perm-list"), manage = make("div", "perm-list");
    CATALOGUE.forEach(function (p) {
      (MANAGEMENT.indexOf(p) >= 0 ? manage : plain).appendChild(permRow(g, p, editable));
    });
    sec.appendChild(plain);
    sec.append(make("h3", "gd-sub", t("mem.management")), make("p", "", t("mem.management_hint")), manage);
    return sec;
  }

  function removeSection(g) {
    var sec = make("section", "gd-sec");
    sec.appendChild(make("h3", "", t("mem.remove_group")));
    sec.appendChild(make("p", "", t("mem.remove_group_hint", {name: g.name})));
    var b = A.button("btn", t("mem.remove_group"));
    b.dataset.key = "grm:" + g.name;
    b.addEventListener("click", function () {
      A.gone({title: t("gone.group.title", {name: g.name}), text: t("gone.group.text", {name: g.name}), name: g.name,
              button: t("gone.group.button"), opener: b, after: list,
              run: function () { return A.request(API + "groups/" + encodeURIComponent(g.name) + "/remove", null, {}); },
              done: async function () {
                window.history.replaceState(null, "", window.location.pathname);
                await load(true);
                var all = list.querySelector('[data-key="g:"]');
                if (all) all.focus();
              }});
    });
    sec.appendChild(b);
    return sec;
  }

  function switchesSection(g) {
    var sec = make("section", "gd-sec"), self = g.owner === view.me.name;
    sec.appendChild(make("h3", "", t("mem.switches", {owner: g.owner})));
    sec.appendChild(make("p", "", self ? t("mem.switches_own") : t("mem.switches_other", {owner: g.owner})));
    var box = make("div", "perm-list");
    SWITCHES.forEach(function (k) {
      var row = make("div", "perm-row"), input = make("input"), id = "sw-" + k;
      input.type = "checkbox";
      input.id = id;
      input.checked = !!(g.switches && g.switches[k]);
      input.disabled = !self;
      input.dataset.key = "sw:" + k;
      var text = make("label", "perm-text"), out = make("span", "out");
      text.htmlFor = id;
      out.setAttribute("aria-live", "polite");
      text.append(make("span", "perm-name", self ? t("switch." + k) : t("mem.sw." + k, {owner: g.owner})), out);
      row.append(input, text);
      input.addEventListener("change", async function () {
        var body = {};
        body[k] = input.checked;
        out.textContent = "";
        var r = await A.request(API + "my/switches", null, body);
        if (!r.ok) { input.checked = !input.checked; out.textContent = A.refusal("mem.refused", r.data); return; }
        g.switches = g.switches || {};
        g.switches[k] = input.checked;
        out.textContent = t("mem.saved");
      });
      box.appendChild(row);
    });
    sec.appendChild(box);
    return sec;
  }

  function drawGroup(g) {
    var head = make("header", "gd-head"), h = make("h2", "gd-title", label(g));
    h.id = "gd-title";
    if (label(g) !== g.name) h.appendChild(make("small", "", g.name));
    head.appendChild(h);
    head.appendChild(make("p", "", g.kind === "ownership" ? t("mem.kind.ownership", {owner: g.owner})
                                                          : t("mem.kind." + g.kind, {name: g.name})));
    detail.appendChild(head);
    detail.appendChild(membersSection(g));
    if (g.kind === "ownership") {
      detail.appendChild(switchesSection(g));
      return;
    }
    detail.appendChild(permsSection(g));
    if (g.kind === "custom" && mine("manage_groups") && holdsAll(g.permissions)) detail.appendChild(removeSection(g));
  }

  function drawMissing() {
    var head = make("header", "gd-head"), h = make("h2", "gd-title", chosen());
    h.id = "gd-title";
    var back = make("a", "", t("mem.back_all"));
    back.href = window.location.pathname;
    back.dataset.key = "back-all";
    back.addEventListener("click", function (ev) { ev.preventDefault(); go("", false); });
    var p = make("p", "", t("mem.no_group") + " ");
    p.appendChild(back);
    head.append(h, p);
    detail.appendChild(head);
  }

  function draw() {
    A.keepFocus(root, function () {
      drawList();
      detail.textContent = "";
      var name = chosen(), g = name ? group(name) : null;
      if (!name) drawAll(); else if (g) drawGroup(g); else drawMissing();
      detail.setAttribute("aria-labelledby", "gd-title");
    });
  }

  // ------------------------------------------------------------------ making a group

  var form = document.getElementById("group-create"), opener = document.getElementById("group-create-open");
  function reveal(show) {
    form.hidden = !show;
    opener.setAttribute("aria-expanded", String(show));
    if (show) form.elements.name.focus(); else opener.focus();
  }
  if (form && opener) {
    opener.addEventListener("click", function () { reveal(form.hidden); });
    form.querySelector("[data-dismiss]").addEventListener("click", function () { reveal(false); });
    form.addEventListener("keydown", function (ev) { if (ev.key === "Escape") { ev.stopPropagation(); reveal(false); } });
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var out = form.querySelector("[data-out]"), name = form.elements.name.value.trim();
      var perms = Array.prototype.filter.call(form.querySelectorAll('input[name="perm"]'), function (b) { return b.checked; })
        .map(function (b) { return b.value; });
      var r = await A.request(API + "groups", null, {name: name, permissions: perms});
      if (!r.ok) { out.textContent = A.refusal("mem.refused", r.data); return; }
      out.textContent = "";
      form.reset();
      form.hidden = true;
      opener.setAttribute("aria-expanded", "false");
      window.history.pushState(null, "", window.location.pathname + "?g=" + encodeURIComponent(r.data.name));
      await load(true);
      detail.focus();
    });
  }

  draw();
  setInterval(function () { load(false); }, EVERY_MS);
})();
