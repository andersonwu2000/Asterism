// People (Asterism.people), on the messages pages and in the settings layer:
// - the rules of who may put whom into or out of which group and remove whom (the server's: projects.change_groups
//   and remove_member; only what will pass is offered), and the acts themselves with their confirmations;
// - in chat and private messages, the member list in the right column (#member-panel): a switch at its top between
//   people and agents (remembered), then sections as Discord's: one per group shown separately, in the groups'
//   order, holding the online members whose highest such group it is; "online" for the other online members;
//   "offline" for every offline member. In a channel only who may read it (its permissions' readers). A row keeps the
//   name's width; what an agent is doing stays by it (frame.js, S.workMark), the owner note goes first. Under each
//   member, its status (1s, statuses.js): an agent's title on one line, cut with an ellipsis, with "更新於 3 小時前" and
//   the overdue mark; a person's title; the reader's own entry sets it in place (one line). A member's row has a "..."
//   control, right click, the context-menu key or Shift+F10 for the member's menu;
// - a profile card (a popover: name, kind, presence, its status, groups with x and +, and mention, private message
//   for a person or, for an agent, 對話 (one's own) or 動態 (anybody else's) on its agent page (1g), open in settings),
//   opened by any name marked data-member (in a message, the member list); the member's menu gives the same acts, with
//   the groups as a submenu of check boxes, for an agent "open on the dashboard", and removal at the foot. The card and
//   the menu work wherever the room is (#chat): chat, private messages and the agent page.
// Default groups (owner, human, ai) are never shown as groups here: only in the settings layer.
// The data is /api/members as the frame reads it (Asterism.side) or as the settings layer holds it.
"use strict";
(function () {
  var A = window.Asterism, rail = document.getElementById("rail");
  if (!A || !rail) return;
  var t = A.t, make = A.make;
  var SLUG = rail.dataset.slug, ME = rail.dataset.me, API = "/" + encodeURIComponent(SLUG) + "/api/";
  var P = A.people = {};

  // ------------------------------------------------------------------ the rules

  P.rules = function (view) {
    var R = {};
    function mine(p) { return view.me.permissions.indexOf(p) >= 0; }
    function holdsAll(perms) { return perms.every(mine); }
    R.mine = mine;
    R.holdsAll = holdsAll;
    R.group = function (name) {
      for (var i = 0; i < view.groups.length; i++) if (view.groups[i].name === name) return view.groups[i];
      return null;
    };
    R.isDefault = function (g) { return !!g && (g.default || g.kind === "default"); };
    function ownership(person) {
      return view.groups.filter(function (g) { return g.kind === "ownership" && g.owner === person; })[0] || null;
    }
    R.ownership = ownership;
    R.label = function (g) {
      if (!g) return "";
      if (g.kind === "default" && A.MSG["group." + g.name]) return t("group." + g.name);
      if (g.kind === "ownership" && g.owner) return t("group.ownership", {owner: g.owner});
      return g.name;
    };
    R.labelOf = function (name) { return R.label(R.group(name)) || name; };
    R.find = function (name) {
      var p = view.people.filter(function (x) { return x.name === name; })[0];
      if (p) return {who: p, isAgent: false};
      var a = view.agents.filter(function (x) { return x.name === name; })[0];
      return a ? {who: a, isAgent: true} : null;
    };
    R.inGroup = function (name) {
      return {people: view.people.filter(function (x) { return x.groups.indexOf(name) >= 0; }),
              agents: view.agents.filter(function (x) { return x.groups.indexOf(name) >= 0; })};
    };
    R.count = function (name) { var m = R.inGroup(name); return m.people.length + m.agents.length; };
    // The groups of `who` in the groups' order: the non-default ones, and the default ones apart.
    R.ordered = function (who) {
      return view.groups.filter(function (g) { return who.groups.indexOf(g.name) >= 0; });
    };
    R.plainOf = function (who) { return R.ordered(who).filter(function (g) { return !R.isDefault(g); }); };
    R.defaultsOf = function (who) { return R.ordered(who).filter(R.isDefault); };
    // May the reader put `who` into, or take it out of, the group `g`? Never a default group (who is in one follows
    // joining) nor a person's own agent group (it follows ownership).
    R.mayRegroup = function (who, isAgent, g) {
      if (!g || g.kind === "ownership" || R.isDefault(g)) return false;
      if (isAgent && who.owner === view.me.name) return true;           // one's own agent: groups one is in (adding)
      if (!mine("manage_groups") || !holdsAll(g.permissions)) return false;
      if (isAgent) {
        var own = ownership(who.owner);
        return !!(own && own.switches && own.switches.others_regroup);
      }
      return true;
    };
    R.mayAdd = function (who, isAgent, g) {
      if (!R.mayRegroup(who, isAgent, g)) return false;
      if (isAgent && who.owner === view.me.name) {
        var me = view.people.filter(function (x) { return x.name === view.me.name; })[0];
        return !!(me && me.groups.indexOf(g.name) >= 0);
      }
      return true;
    };
    R.closedToMe = function (who, isAgent) {      // another person's agent whose person keeps its groups closed
      if (!isAgent || who.owner === view.me.name || !mine("manage_groups")) return false;
      var own = ownership(who.owner);
      return !(own && own.switches && own.switches.others_regroup);
    };
    R.mayRemove = function (who, isAgent) {
      if (isAgent) return who.owner === view.me.name || mine("manage_members");
      if (who.name === view.me.name || !mine("manage_members")) return false;
      var held = [];
      who.groups.forEach(function (n) { var g = R.group(n); if (g) held = held.concat(g.permissions); });
      return holdsAll(held);
    };
    // The groups the reader may give to `who` (not in them yet); `defaults`: the default groups too.
    R.addable = function (who, isAgent, defaults) {
      return view.groups.filter(function (g) {
        return (defaults || !R.isDefault(g)) && who.groups.indexOf(g.name) < 0 && R.mayAdd(who, isAgent, g);
      });
    };
    // Every group whose membership the reader may change for `who`, with whether `who` is in it.
    R.offered = function (who, isAgent, defaults) {
      return view.groups.filter(function (g) {
        if (!defaults && R.isDefault(g)) return false;
        return who.groups.indexOf(g.name) >= 0 ? R.mayRegroup(who, isAgent, g) : R.mayAdd(who, isAgent, g);
      }).map(function (g) { return {group: g, member: who.groups.indexOf(g.name) >= 0}; });
    };
    R.mayManage = function () { return mine("manage_members") || mine("manage_groups"); };
    return R;
  };

  // An agent's state in words (frame.js, S.workText): working or idle while online; nothing while offline or for a
  // person.
  P.stateWord = function (who, isAgent) {
    return isAgent && S ? S.workText(who) : "";
  };

  // ------------------------------------------------------------------ the acts

  P.regroup = function (member, add, remove) {
    return A.request(API + "members/" + encodeURIComponent(member) + "/groups", null, {add: add, remove: remove});
  };

  // Removing a member floats (the name typed). `after`: where the focus goes once it is done.
  P.remove = function (who, isAgent, opener, after, done) {
    var kind = isAgent ? "agent" : "person";
    A.gone({title: t("gone." + kind + ".title", {name: who.name}), text: t("gone." + kind + ".text", {name: who.name}),
            name: who.name, button: t("gone.member.button"), opener: opener, after: after, act: "mem.remove",
            run: function () { return A.request(API + "members/" + encodeURIComponent(who.name) + "/remove", null, {}); },
            done: done});
  };

  // The groups of `who` as check boxes in a menu: choosing one puts `who` into it or takes it out. `defaults`: the
  // default groups too (the settings layer only).
  P.groupItems = function (rules, who, isAgent, done, defaults) {
    return rules.offered(who, isAgent, defaults).map(function (o) {
      return {label: rules.label(o.group), checked: o.member, run: async function () {
        var r = await P.regroup(who.name, o.member ? [] : [o.group.name], o.member ? [o.group.name] : []);
        done(r);
      }};
    });
  };

  // A chip of a group `who` is in: × takes it out in two steps where the reader may; otherwise a quiet tag.
  P.chip = function (rules, who, isAgent, name, done) {
    var g = rules.group(name);
    if (!rules.mayRegroup(who, isAgent, g)) return make("span", "tag", rules.labelOf(name));
    var chip = A.button("chip-btn", rules.labelOf(name)), x = make("span", "cross");
    x.setAttribute("aria-hidden", "true");
    chip.appendChild(x);
    chip.dataset.key = "out:" + who.name + ":" + name;
    chip.setAttribute("aria-label", t("mem.take_out_label", {group: rules.labelOf(name), name: who.name}));
    chip.addEventListener("click", async function () {
      if (!A.twoStep(chip, t("mem.confirm_take_out", {group: rules.labelOf(name), name: who.name}))) return;
      done(await P.regroup(who.name, [], [name]), chip);
    });
    return chip;
  };

  // The + after the chips: a menu of the groups that may be given, as the data says when it is opened (`rulesNow`
  // gives the rules of the newest data). `defaults`: the default groups too, as check boxes (the settings layer).
  P.plus = function (rulesNow, who, isAgent, done, defaults) {
    var rules = rulesNow();
    if (!(defaults ? rules.offered(who, isAgent, true) : rules.addable(who, isAgent)).length) return null;
    var b = A.button("chip-btn chip-plus"), plus = make("span", "plus");
    plus.setAttribute("aria-hidden", "true");
    b.appendChild(plus);
    b.dataset.key = "plus:" + who.name;
    b.setAttribute("aria-label", t("mem.add_to_label", {name: who.name}));
    b.title = t("mem.add_to");
    b.setAttribute("aria-haspopup", "menu");
    b.setAttribute("aria-expanded", "false");
    b.addEventListener("click", function () {
      var now = rulesNow(), found = now.find(who.name) || {who: who, isAgent: isAgent};
      var items = defaults ? P.groupItems(now, found.who, found.isAgent, function (r) { done(r, b); }, true)
        : now.addable(found.who, found.isAgent).map(function (g) {
          return {label: now.label(g), run: async function () { done(await P.regroup(who.name, [g.name], []), b); }};
        });
      A.menu({label: t("mem.add_to_label", {name: who.name}), anchor: b}, items, b);
    });
    return b;
  };

  // ------------------------------------------------------------------ in chat and private messages
  var chat = document.getElementById("chat");
  if (!chat || !A.side) return;
  var S = A.side, St = A.statuses;

  function view() { return S.members; }
  function rulesNow() { return view() ? P.rules(view()) : null; }
  function settingsHref(name) {
    return "/" + encodeURIComponent(SLUG) + "/settings/members?m=" + encodeURIComponent(name);
  }
  function dmHref(name) { return "/" + encodeURIComponent(SLUG) + "/dm/" + encodeURIComponent(name); }
  // Where one talks with a member, or reads it (1g): another person, a private conversation; an agent, its page, in
  // 對話 for one's own agent and 動態 for anybody else's. Null for oneself.
  function talk(found) {
    if (!found || found.who.name === ME) return null;
    if (!found.isAgent) return {label: t("people.message"), href: dmHref(found.who.name)};
    var page = "/" + encodeURIComponent(SLUG) + "/agent?name=" + encodeURIComponent(found.who.name);
    return found.who.owner === ME ? {label: t("people.agent_chat"), href: page}
                                  : {label: t("people.agent_activity"), href: page + "&view=activity"};
  }
  function kindText(found) {
    return found.isAgent ? t("mem.agent_of", {owner: found.who.owner}) : t("people.person");
  }
  function after(r, out) {
    if (r && !r.ok && out) out.textContent = A.refusal("mem.regroup", r.data);
    return S.loadMembers();
  }
  function dirOf(found) {
    return {kind: found.isAgent ? "agent" : "person", online: !!found.who.online};
  }

  // ------------------------------------------------------------------ the profile card

  var card = make("div", "card-pop");
  card.id = "profile-card";
  card.setAttribute("role", "dialog");
  card.tabIndex = -1;
  card.hidden = true;
  if (typeof card.showPopover === "function") card.setAttribute("popover", "manual");
  document.body.appendChild(card);
  var shown = null;                    // {name, anchor}

  function fillCard(name) {
    var rules = rulesNow(), found = rules ? rules.find(name) : null;
    card.textContent = "";
    card.setAttribute("aria-label", t("people.card", {name: name}));
    var head = make("div", "card-head");
    var who = found ? found.who : {name: name};
    var dir = found ? dirOf(found) : S.directory[name] || {kind: "person"};
    head.appendChild(S.avatar(name, 40, {kind: dir.kind, avatar: found ? who.avatar : dir.avatar}));
    head.appendChild(S.presence(dir));
    var names = make("div", "card-names");
    var title = make("div", "card-title");
    title.appendChild(make("h2", "card-name" + (found && found.isAgent ? " mono" : ""), name));
    var model = found && found.isAgent ? A.modelTag(who.model) : null;
    if (model) title.appendChild(model);
    names.appendChild(title);
    var sub = [];
    if (found) {
      sub.push(kindText(found), t(who.online ? "presence.online" : "presence.offline"));
      if (P.stateWord(who, found.isAgent)) sub.push(P.stateWord(who, found.isAgent));
    }
    names.appendChild(make("p", "card-sub", sub.join(" · ")));
    head.appendChild(names);
    card.appendChild(head);
    if (!found) return;
    var out = make("p", "out card-out");
    out.setAttribute("aria-live", "polite");

    var groups = make("section", "card-sec");
    groups.appendChild(make("h3", "", t("people.groups")));
    var chips = make("div", "mtags");
    function redo(r, from) {
      var key = from && from.dataset ? from.dataset.key : null;
      after(r, out).then(function () {
        if (!shown || shown.name !== name) return;
        if (r && !r.ok) return;
        fillCard(name);
        var again = key && card.querySelector('[data-key="' + key.replace(/["\\]/g, "\\$&") + '"]');
        (again || card.querySelector("button") || card).focus();
      });
    }
    var plain = rules.plainOf(who);
    if (!plain.length) chips.appendChild(make("span", "dim small", t("mem.no_groups")));
    plain.forEach(function (g) { chips.appendChild(P.chip(rules, who, found.isAgent, g.name, redo)); });
    var plus = P.plus(rulesNow, who, found.isAgent, redo);
    if (plus) chips.appendChild(plus);
    groups.appendChild(chips);
    card.appendChild(groups);

    // Its status: an agent's title with when it was updated and the overdue mark, a person's title.
    var st = who.status || {};
    var status = make("section", "card-sec");
    status.appendChild(make("h3", "", t("people.status")));
    status.appendChild(make("p", st.title ? "card-status" : "dim small", st.title || t("people.no_status")));
    var upd = found.isAgent && St ? St.updated(st) : null;
    if (upd) status.appendChild(upd);
    card.insertBefore(status, groups);

    var acts = make("div", "card-acts");
    if (A.chat) {
      acts.appendChild(A.button("btn", t("people.mention"), function () {
        A.popup.close(false);
        A.chat.mention(name);
      }));
    }
    var way = talk(found);
    if (way) {
      var pm = make("a", "btn", way.label);
      pm.href = way.href;
      pm.addEventListener("click", function () { A.popup.close(false); });
      acts.appendChild(pm);
    }
    if (rules.mayManage()) {
      var st = make("a", "btn quiet", t("people.open_settings"));
      st.href = settingsHref(name);
      acts.appendChild(st);
    }
    card.append(acts, out);
  }

  P.card = function (name, anchor) {
    if (A.popup.isOpen(card) && shown && shown.anchor === anchor) { A.popup.close(true); return; }
    var now = shown = {name: name, anchor: anchor};
    fillCard(name);
    if (!A.popup.open(card, anchor, {onClose: function () { if (shown === now) shown = null; }})) {
      if (shown === now) shown = null;
      return;
    }
    if (!view()) S.loadMembers().then(function () { if (shown && shown.name === name) fillCard(name); });
  };

  // ------------------------------------------------------------------ the menu of a member

  function dashboardHref(name) {
    var a = view() && view().agents.filter(function (x) { return x.name === name; })[0];
    var own = a && P.rules(view()).plainOf(a)[0];
    return "/" + encodeURIComponent(SLUG) + "/work" + (own ? "?group=" + encodeURIComponent(own.name) : "");
  }

  P.menu = function (name, where, opener) {
    var rules = rulesNow(), found = rules ? rules.find(name) : null;
    var items = [{label: t("people.profile"), run: function () { P.card(name, opener); }}];
    if (A.chat) items.push({label: t("people.mention"), run: function () { A.chat.mention(name); }});
    var way = talk(found);
    if (way) items.push(way);
    if (found) {
      if (found.isAgent) items.push({label: t("people.open_dashboard"), href: dashboardHref(name)});
      var boxes = P.groupItems(rules, found.who, found.isAgent, function (r) { after(r, null); });
      if (boxes.length) items.push({label: t("people.groups"), items: boxes});
      if (rules.mayManage()) items.push({label: t("people.open_settings"), href: settingsHref(name)});
      if (rules.mayRemove(found.who, found.isAgent)) {
        items.push({separator: true}, {label: t("people.remove"), run: function () {
          P.remove(found.who, found.isAgent, opener, null, function () { S.loadMembers(); });
        }});
      }
    }
    A.menu(Object.assign({label: t("people.acts", {name: name})}, where), items, opener);
  };

  // Any name marked data-member: a click opens the card, right click or the menu keys the menu.
  document.addEventListener("click", function (ev) {
    var el = ev.target.closest && ev.target.closest("[data-member]");
    if (!el || card.contains(el)) return;
    ev.preventDefault();
    P.card(el.dataset.member, el);
  });
  document.addEventListener("contextmenu", function (ev) {
    var el = ev.target.closest && ev.target.closest("[data-member]");
    if (!el) return;
    ev.preventDefault();
    P.menu(el.dataset.member, {x: ev.clientX, y: ev.clientY}, el);
  });
  document.addEventListener("keydown", function (ev) {
    var el = ev.target.closest && ev.target.closest("[data-member]");
    if (!el || !(ev.key === "ContextMenu" || (ev.key === "F10" && ev.shiftKey))) return;
    ev.preventDefault();
    P.menu(el.dataset.member, {anchor: el}, el);
  });

  // A name that opens the card: a button with data-member (the caller styles it).
  P.nameButton = function (name, cls, text) {
    var b = A.button(cls, text === undefined ? name : text);
    b.dataset.member = name;
    b.setAttribute("aria-haspopup", "dialog");
    return b;
  };

  // ------------------------------------------------------------------ the member list

  var panel = document.getElementById("member-panel"), body = document.getElementById("member-body");
  var sw = document.getElementById("member-switch");
  var SIDE_KEY = "asterism-member-side:" + SLUG;
  var side = A.store.get(SIDE_KEY, "people") === "agents" ? "agents" : "people";

  function memberRow(found) {
    var who = found.who, li = make("li", "prow");
    var line = make("div", "prow-line");
    var b = P.nameButton(who.name, "prow-btn", "");
    b.dataset.key = "m:" + who.name;
    b.appendChild(S.presence(dirOf(found)));
    b.appendChild(S.avatar(who.name, 20, {kind: found.isAgent ? "agent" : "person", avatar: who.avatar}));
    b.appendChild(make("span", "prow-name" + (found.isAgent ? " mono" : ""), who.name));
    var model = found.isAgent ? A.modelTag(who.model) : null;
    if (model) b.appendChild(model);
    // The name keeps its width; what it is doing stays beside it; the model tag shrinks, the owner goes first.
    var state = found.isAgent ? S.workMark(who, "prow-state") : null;
    if (state) b.appendChild(state);
    var note = found.isAgent ? (who.owner === ME ? t("nav.my_agent") : t("mem.agent_of", {owner: who.owner}))
             : who.name === ME ? t("people.you") : "";
    if (note) b.appendChild(make("span", "prow-note", note));
    var acts = A.button("row-acts");
    acts.appendChild(A.glyph("dots"));
    acts.setAttribute("aria-label", t("people.member_acts", {name: who.name}));
    acts.title = t("people.member_acts", {name: who.name});
    acts.setAttribute("aria-haspopup", "menu");
    acts.setAttribute("aria-expanded", "false");
    acts.dataset.key = "ma:" + who.name;
    acts.addEventListener("click", function () { P.menu(who.name, {anchor: acts}, acts); });
    line.append(b, acts);
    li.appendChild(line);
    li.appendChild(statusLine(found));
    return li;
  }

  // The sections: the groups shown separately (in their order) for the online members whose highest such group
  // it is, then the other online members, then every offline member.
  function sections(v, list, isAgent) {
    var rules = P.rules(v), apart = v.groups.filter(function (g) { return g.separate && !rules.isDefault(g); });
    var by = {}, online = [], offline = [];
    list.forEach(function (who) {
      if (!who.online) { offline.push(who); return; }
      var top = apart.filter(function (g) { return who.groups.indexOf(g.name) >= 0; })[0];
      if (top) (by[top.name] = by[top.name] || []).push(who); else online.push(who);
    });
    var out = apart.filter(function (g) { return by[g.name]; }).map(function (g) {
      return {key: "g:" + g.name, title: t("people.section", {name: rules.label(g), n: by[g.name].length}), list: by[g.name]};
    });
    out.push({key: "on", title: t("people.online", {n: online.length}), list: online});
    out.push({key: "off", title: t("people.offline", {n: offline.length}), list: offline});
    return out.filter(function (s) { return s.list.length; }).map(function (s) {
      s.isAgent = isAgent;
      return s;
    });
  }

  // A member's status under its row: an agent's title (one line, the whole of it in its tooltip), when it was updated
  // and the overdue mark; a person's title; the reader's own, set in place.
  function statusLine(found) {
    var who = found.who, st = who.status || {}, box = make("div", "pstatus");
    if (!found.isAgent && who.name === ME && St) {
      box.appendChild(St.mine(st.title || "", function () { S.loadMembers(); }));
      return box;
    }
    if (st.title) {
      var text = make("span", "pstatus-text", st.title);
      text.title = st.title;
      box.appendChild(text);
    }
    var upd = found.isAgent && st.title && St ? St.updated(st, "pstatus-updated") : null;
    if (found.isAgent && !st.title && st.overdue && St) upd = St.updated({overdue: true}, "pstatus-updated");
    if (upd) box.appendChild(upd);
    return box;
  }

  function drawSwitch() {
    Array.prototype.forEach.call(sw.querySelectorAll("[data-side]"), function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.side === side));
    });
  }

  function drawList() {
    var v = view();
    if (!panel || !body || !v) return;
    drawSwitch();
    A.keepFocus(body, function () {
      body.textContent = "";
      var list = side === "agents" ? v.agents : v.people;
      // In a channel, only who may read it (as Discord's member list); in a private conversation, everyone.
      var may = readers.place === S.current && readers.names ? readers.names[side] : null;
      if (may) list = list.filter(function (who) { return may.indexOf(who.name) >= 0; });
      sections(v, list, side === "agents").forEach(function (s) {
        var sec = make("section", "psec"), ul = make("ul", "plist");
        sec.appendChild(make("h3", "", s.title));
        s.list.forEach(function (who) { ul.appendChild(memberRow({who: who, isAgent: s.isAgent})); });
        sec.appendChild(ul);
        body.appendChild(sec);
      });
      if (!list.length) body.appendChild(make("p", "dim", t("people.none_here")));
    });
  }

  if (sw) {
    sw.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-side]");
      if (!b || b.dataset.side === side) return;
      side = b.dataset.side;
      A.store.set(SIDE_KEY, side);
      drawList();
    });
  }
  if (body) {
    // The member's menu from the row (right click, the context-menu key and Shift+F10 come from the name button).
    body.addEventListener("contextmenu", function (ev) {
      var row = ev.target.closest(".prow");
      if (!row || ev.target.closest("[data-member]") || ev.target.closest(".pstatus")) return;
      var b = row.querySelector("[data-member]");
      if (!b) return;
      ev.preventDefault();
      P.menu(b.dataset.member, {x: ev.clientX, y: ev.clientY}, b);
    });
  }

  function redraw() {
    if (St && St.busy()) return;
    drawList();
  }

  // Who may read the channel open (its permissions answer it): read when the place changes and with the members.
  var readers = {place: null, names: null};
  async function loadReaders() {
    var place = S.current;
    if (!place || place.charAt(0) !== "#") { readers = {place: place, names: null}; return; }
    var r = await A.request(API + "channels/" + encodeURIComponent(place.slice(1)) + "/permissions");
    if (S.current !== place) return;
    var names = r.ok && r.data.readers ? r.data.readers : null;
    var same = readers.place === place && JSON.stringify(readers.names) === JSON.stringify(names);
    readers = {place: place, names: names};
    if (!same) redraw();
  }
  S.onChange(function () { if (readers.place !== S.current) loadReaders(); });
  var setCurrent = S.setCurrent;
  S.setCurrent = function (place) { setCurrent(place); loadReaders(); };

  if (St) St.onChange(function () { drawList(); });
  S.onMembers(function () {
    loadReaders();
    redraw();
    // The card follows the data, unless an act is armed in it or a menu from it is open.
    if (shown && A.popup.isOpen(card) && !A.isArmed(card) && !document.querySelector(".menu.shown")) {
      A.keepFocus(card, function () { fillCard(shown.name); });
    }
  });
})();
