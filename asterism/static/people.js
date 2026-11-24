// People (Asterism.people), on the messages pages and in the settings layer:
// - the rules of who may put whom into or out of which group and remove whom (the server's: projects.change_groups
//   and remove_member; only what will pass is offered), and the acts themselves with their confirmations;
// - in chat and private messages, the member list in the right column (#member-panel, 1l): a head with the title and
//   how many people and agents are listed, then one tree (#member-tree) of people with each person's agents under
//   them, in sections of people as Discord's: one per custom group shown separately, in the groups' order, holding the
//   present people whose highest such group it is; "online" for the other present people; "offline" for the others.
//   A person is present when they or one of their listed agents is online; an agent goes where its person goes. In a
//   channel only who may read it (its permissions' readers). A person with agents opens and closes them by a mark
//   (kept per project); a closed one shows a disc per agent. Under each member, its status (1s, statuses.js): an
//   agent's title on one line, cut with an ellipsis, with "更新於 3 小時前" and the overdue mark; a person's title; the
//   reader's own entry sets it in place (one line). A row opens the member's card; its "..." control, right click, the
//   context-menu key or Shift+F10 the member's menu; the tree is one tab stop with the explorer's keys;
// - a profile card (a popover: name, kind, presence, its status, groups with x and +, and mention, private message
//   for a person or, for an agent, 對話 (one's own) or 動態 (anybody else's) on its agent page (1g), open in settings;
//   for another person's agent, mention its person, with one line saying why), opened by any name marked data-member
//   (in a message) or a row of the member list; the member's menu gives the same acts, with the groups as a submenu of
//   check boxes, for an agent "open on the dashboard", for the reader "set the status", and removal at the foot. The
//   card and the menu work wherever the room is (#chat): chat, private messages and the agent page.
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
    // May the reader take `who` out of the group `g` (mayRegroup), or put it in (mayAdd)? The server's rule (2b: an
    // agent the same way as a person): who may manage groups, any member, for a group whose permissions they hold;
    // without that, only one's own agent, put only into the groups one is in (and taken out of any). Never a default
    // group (who is in one follows joining) nor a person's own agent group (it follows ownership).
    function managed(g) { return mine("manage_groups") && holdsAll(g.permissions); }
    function editable(g) { return !!g && g.kind !== "ownership" && !R.isDefault(g); }
    R.mayRegroup = function (who, isAgent, g) {
      if (!editable(g)) return false;
      return (isAgent && who.owner === view.me.name) || managed(g);
    };
    R.mayAdd = function (who, isAgent, g) {
      if (!editable(g)) return false;
      if (managed(g)) return true;
      if (!isAgent || who.owner !== view.me.name) return false;
      var me = view.people.filter(function (x) { return x.name === view.me.name; })[0];
      return !!(me && me.groups.indexOf(g.name) >= 0);
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
  var tree = document.getElementById("member-tree");

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
  // Another person's agent: a mention from outside its own side calls nobody (1e), so its person is mentioned instead.
  function otherSide(found) { return !!(found && found.isAgent && found.who.owner && found.who.owner !== ME); }
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
  // A mention into the composer. Below 900 px the right column (the member list or search) is a sheet over the
  // messages: it closes first, so that the composer the focus goes to is not behind it (2b).
  function mention(name) {
    if (A.right && A.right.isSheet() && A.right.current) A.right.show(null);
    A.chat.mention(name);
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

    // Another person's agent: one quiet line says why its person is the one mentioned (1l).
    var other = otherSide(found);
    if (other) card.appendChild(make("p", "card-why", t("people.other_side", {owner: who.owner, name: name})));
    var acts = make("div", "card-acts");
    if (A.chat) {
      var whom = other ? who.owner : name;
      acts.appendChild(A.button("btn", other ? t("people.mention_owner_short", {owner: whom}) : t("people.mention"),
                                function () {
                                  A.popup.close(false);
                                  mention(whom);
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
      var set = make("a", "btn quiet", t("people.open_settings"));
      set.href = settingsHref(name);
      acts.appendChild(set);
    }
    card.append(acts, out);
  }

  // The card by `anchor`; `back`: what opened it when that is not the anchor (a row of the member tree: the card is
  // placed by the row's name, and the focus goes back to the row).
  P.card = function (name, anchor, back) {
    var owner = back || anchor;
    if (A.popup.isOpen(card) && shown && shown.anchor === owner) { A.popup.close(true); return; }
    var now = shown = {name: name, anchor: owner};
    fillCard(name);
    if (!A.popup.open(card, anchor, {back: back, onClose: function () { if (shown === now) shown = null; }})) {
      if (shown === now) shown = null;
      return;
    }
    if (!view()) S.loadMembers().then(function () { if (shown && shown.name === name) fillCard(name); });
  };

  // The card from `el`: from a row of the member tree, by the row's name; else by `el`.
  function cardFrom(name, el) {
    var row = el && el.closest ? el.closest(".prow[role=treeitem]") : null;
    if (row) P.card(name, row.querySelector(".prow-name") || row, row);
    else P.card(name, el);
  }

  // ------------------------------------------------------------------ the menu of a member

  function dashboardHref(name) {
    var a = view() && view().agents.filter(function (x) { return x.name === name; })[0];
    var own = a && P.rules(view()).plainOf(a)[0];
    return "/" + encodeURIComponent(SLUG) + "/work" + (own ? "?group=" + encodeURIComponent(own.name) : "");
  }

  // Another person: profile, mention, private message, groups, settings, removal. The reader: profile, mention, set
  // the status (the field on their row in the member list), groups, settings. One's own agent: profile, mention, 對話,
  // the dashboard, groups, settings, removal. Another person's agent: profile, mention its person, 動態, the
  // dashboard, groups, settings, removal. Each only for who may.
  P.menu = function (name, where, opener) {
    var rules = rulesNow(), found = rules ? rules.find(name) : null;
    var items = [{label: t("people.profile"), run: function () { cardFrom(name, opener); }}];
    if (A.chat) {
      if (otherSide(found)) {
        items.push({label: t("people.mention_owner", {owner: found.who.owner}),
                    run: function () { mention(found.who.owner); }});
      } else {
        items.push({label: t("people.mention"), run: function () { mention(name); }});
      }
    }
    var way = talk(found);
    if (way) items.push(way);
    if (found && !found.isAgent && name === ME && St && tree) {
      items.push({label: t("st.set"), run: function () { editMine(found.who); }});
    }
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

  // Any name marked data-member: a click opens the card, right click or the menu keys the menu. The member tree has
  // its own (below).
  function outside(el) { return !!el && !(tree && tree.contains(el)); }
  document.addEventListener("click", function (ev) {
    var el = ev.target.closest && ev.target.closest("[data-member]");
    if (!outside(el) || card.contains(el)) return;
    ev.preventDefault();
    P.card(el.dataset.member, el);
  });
  document.addEventListener("contextmenu", function (ev) {
    var el = ev.target.closest && ev.target.closest("[data-member]");
    if (!outside(el)) return;
    ev.preventDefault();
    P.menu(el.dataset.member, {x: ev.clientX, y: ev.clientY}, el);
  });
  document.addEventListener("keydown", function (ev) {
    var el = ev.target.closest && ev.target.closest("[data-member]");
    if (!outside(el) || !(ev.key === "ContextMenu" || (ev.key === "F10" && ev.shiftKey))) return;
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

  // ------------------------------------------------------------------ the member list (1l)
  //
  // One tree (#member-tree): people at the first level, each person's agents under them (as the server orders them,
  // never by presence: an agent keeps its place and its mark changes). Sections of people, by the family's presence:
  // a person is present when they or one of their listed agents is online. The head says how many people and agents
  // are listed; #member-said says when the list is loading or could not be read. A person with agents has a
  // disclosure mark: open, or closed under 離線, until the reader presses it (kept per project in this browser,
  // `asterism-member-open:{slug}`, only the people pressed). Any row opens the member's card; only the mark (or the
  // arrow keys) opens and closes. One tab stop, with the explorer's keys.

  var body = document.getElementById("member-body"), said = document.getElementById("member-said");
  var countsEl = document.getElementById("member-counts");
  var OPEN_KEY = "asterism-member-open:" + SLUG, MANY = 6, LOADING_MS = 600;
  A.store.take("asterism-member-side:" + SLUG);          // the people | agents control of earlier versions
  var kept = {};                // person -> open or closed, the people the reader pressed (as stored, else this page's)
  var stop = null;              // the data-key of the row holding the tree's tab stop
  var turning = null;           // the person whose mark turns in this drawing
  var failed = false, waited = false, ids = 0;

  function keptNow() {
    var k = A.store.get(OPEN_KEY, null);
    if (k && typeof k === "object" && !Array.isArray(k)) kept = k;
    return kept;
  }
  function isOpen(name, section) {
    var k = keptNow();
    return Object.prototype.hasOwnProperty.call(k, name) ? !!k[name] : section !== "off";
  }
  function keepOpen(name, on) {
    var k = keptNow();
    k[name] = !!on;
    kept = k;
    A.store.set(OPEN_KEY, k);
  }
  // A name that is no person of the project any more is dropped (when the members are read).
  function prune(v) {
    var k = keptNow(), names = v.people.map(function (p) { return p.name; }), left = {}, gone = false;
    Object.keys(k).forEach(function (n) { if (names.indexOf(n) >= 0) left[n] = k[n]; else gone = true; });
    if (!gone) return;
    kept = left;
    A.store.set(OPEN_KEY, left);
  }

  // Who is listed: in a channel who may read it (as Discord's member list), in a private conversation everyone.
  function listed(v) {
    var may = readers.place === S.current && readers.names ? readers.names : null;
    function keep(kind) { return function (x) { return !may || (may[kind] || []).indexOf(x.name) >= 0; }; }
    return {people: v.people.filter(keep("people")), agents: v.agents.filter(keep("agents"))};
  }

  // The sections: one per custom group shown separately, in the groups' order, for the present people whose highest
  // such group it is; then 在線 for the other present people; then 離線 for the others (they and all their listed
  // agents offline). The reader first in their section, then as the server gives them. A listed agent whose person is
  // not listed (two readings a moment apart) is a row of the first level at the end of its section, never dropped.
  function sections(v, list) {
    var rules = P.rules(v), apart = v.groups.filter(function (g) { return g.kind === "custom" && g.separate; });
    var names = list.people.map(function (p) { return p.name; });
    var families = list.people.map(function (p) {
      return {who: p, agents: list.agents.filter(function (a) { return a.owner === p.name; })};
    });
    families = families.filter(function (f) { return f.who.name === ME; })
                       .concat(families.filter(function (f) { return f.who.name !== ME; }));
    list.agents.forEach(function (a) {
      if (names.indexOf(a.owner) < 0) families.push({who: a, lone: true, agents: []});
    });
    var by = {}, online = [], offline = [];
    families.forEach(function (f) {
      if (!(f.who.online || f.agents.some(function (a) { return a.online; }))) { offline.push(f); return; }
      var top = f.lone ? null : apart.filter(function (g) { return f.who.groups.indexOf(g.name) >= 0; })[0];
      if (top) (by[top.name] = by[top.name] || []).push(f); else online.push(f);
    });
    var out = apart.filter(function (g) { return by[g.name]; }).map(function (g) {
      return {key: "g:" + g.name, title: t("people.section", {name: rules.label(g), n: by[g.name].length}),
              families: by[g.name]};
    });
    out.push({key: "on", title: t("people.online", {n: online.length}), hint: t("people.online_hint"),
              families: online});
    out.push({key: "off", title: t("people.offline", {n: offline.length}), hint: t("people.offline_hint"),
              families: offline});
    return out.filter(function (s) { return s.families.length; });
  }

  function idOf(el) {
    if (!el.id) el.id = "mt" + (++ids);
    return el.id;
  }
  // A row is named by its name and state and described by the rest (aria-labelledby and aria-describedby, the parts
  // the row draws).
  function words(li, named, described) {
    li.setAttribute("aria-labelledby", named.filter(Boolean).map(idOf).join(" "));
    var d = described.filter(Boolean);
    if (d.length) li.setAttribute("aria-describedby", d.map(idOf).join(" "));
  }

  function treeRow(name, cls, level, pos, size) {
    var li = make("li", "prow " + cls);
    li.setAttribute("role", "treeitem");
    li.setAttribute("aria-level", String(level));
    li.setAttribute("aria-posinset", String(pos));
    li.setAttribute("aria-setsize", String(size));
    li.dataset.key = "m:" + name;
    li.dataset.name = name;
    li.tabIndex = -1;
    return li;
  }

  // "...": the member's menu (out of the tab order: the row has the context-menu key and Shift+F10).
  function actsButton(name) {
    var acts = A.button("row-acts");
    acts.appendChild(A.glyph("dots"));
    acts.tabIndex = -1;
    acts.setAttribute("aria-label", t("people.member_acts", {name: name}));
    acts.title = t("people.member_acts", {name: name});
    acts.setAttribute("aria-haspopup", "menu");
    return acts;
  }

  // A closed person's agents at the end of their row: one presence disc per agent in their order (more than six:
  // their number), and before them "1 工作中" when any works; for screen readers one sentence.
  function brood(agents) {
    var on = agents.filter(function (a) { return a.online; }).length;
    var k = agents.filter(function (a) { return a.online && a.work === "active"; }).length;
    var box = make("span", "prow-brood"), marks = make("span", "prow-brood-marks");
    marks.setAttribute("aria-hidden", "true");
    if (k) marks.appendChild(make("span", "prow-brood-work", t("people.brood_working", {k: k})));
    if (agents.length > MANY) {
      marks.appendChild(make("span", "prow-brood-many", t("people.brood_many", {n: agents.length})));
    } else {
      agents.forEach(function (a) { marks.appendChild(make("span", "presence agent" + (a.online ? " on" : ""))); });
    }
    var sentence = make("span", "vh", t("people.brood_label", {n: agents.length, on: on, k: k}));
    box.append(marks, sentence);
    return {box: box, sentence: sentence};
  }

  // A person's row: the disclosure mark (when they have listed agents; else its room), presence, avatar, name; at the
  // end, when closed, their agents' discs, and 你 on the reader's own; under it their status.
  function personRow(f, sec, pos, size) {
    var who = f.who, li = treeRow(who.name, "person", 1, pos, size), line = make("div", "prow-line");
    var has = f.agents.length > 0, open = has && isOpen(who.name, sec.key), mark;
    if (has) {
      li.setAttribute("aria-expanded", String(open));
      mark = A.button("prow-mark");
      mark.tabIndex = -1;
      mark.setAttribute("aria-label", t(open ? "people.hide_agents" : "people.show_agents", {name: who.name}));
      var turns = turning === who.name, tw = make("span", "twisty" + ((turns ? !open : open) ? " open" : ""));
      tw.setAttribute("aria-hidden", "true");
      mark.appendChild(tw);
      if (turns) requestAnimationFrame(function () { tw.classList.toggle("open", open); });
    } else {
      mark = make("span", "prow-mark none");
    }
    var presence = S.presence({kind: "person", online: who.online}), name = make("span", "prow-name", who.name);
    line.append(mark, presence, S.avatar(who.name, 20, {kind: "person", avatar: who.avatar}), name);
    var end = make("span", "prow-end"), sentence = null, you = null;
    if (has && !open) {
      var b = brood(f.agents);
      end.appendChild(b.box);
      sentence = b.sentence;
    }
    if (who.name === ME) end.appendChild(you = make("span", "prow-you", t("people.you")));
    end.appendChild(actsButton(who.name));
    line.appendChild(end);
    var status = statusLine({who: who, isAgent: false});
    li.append(line, status);
    words(li, [name, presence], [status.querySelector(".pstatus-text, .st-mine-btn:not(.dim)"), you, sentence]);
    return li;
  }

  // An agent's row: presence, avatar, name (mono), model tag, at the end what it is doing; under it its status, with
  // when it was updated and the overdue mark. No owner: the tree says it.
  function agentRow(a, level, pos, size, lone) {
    var li = treeRow(a.name, "agent" + (lone ? " lone" : ""), level, pos, size), line = make("div", "prow-line");
    li.dataset.owner = a.owner || "";
    var presence = S.presence({kind: "agent", online: a.online}), name = make("span", "prow-name mono", a.name);
    line.append(presence, S.avatar(a.name, 16, {kind: "agent", avatar: a.avatar}), name);
    var model = A.modelTag(a.model);
    if (model) line.appendChild(model);
    var end = make("span", "prow-end"), work = S.workMark(a, "prow-state");
    if (work) end.appendChild(work);
    end.appendChild(actsButton(a.name));
    line.appendChild(end);
    var status = statusLine({who: a, isAgent: true});
    li.append(line, status);
    words(li, [name, presence, work],
          [model, status.querySelector(".pstatus-text"), status.querySelector(".st-updated")]);
    return li;
  }

  // A member's status under its row: its title (one line, the whole of it in its tooltip), for an agent when it was
  // updated and the overdue mark; the reader's own, set in place (its control out of the tab order: the row's menu
  // has 設定狀態).
  function statusLine(found) {
    var who = found.who, st = who.status || {}, box = make("div", "pstatus");
    if (!found.isAgent && who.name === ME && St) {
      var mine = St.mine(st.title || "", function () { S.loadMembers(); });
      var b = mine.querySelector(".st-mine-btn");
      if (b) b.tabIndex = -1;
      box.appendChild(mine);
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

  function rows() { return Array.prototype.slice.call(tree.querySelectorAll("[role=treeitem]")); }
  function rowByKey(key) {
    return key ? tree.querySelector('[role=treeitem][data-key="' + key.replace(/["\\]/g, "\\$&") + '"]') : null;
  }
  function rowOf(name) { return rowByKey("m:" + name); }
  function holdStop(row) {
    rows().forEach(function (r) { r.tabIndex = r === row ? 0 : -1; });
    stop = row ? row.dataset.key : null;
  }
  function focusRow(row) {
    if (!row) return;
    holdStop(row);
    row.focus({preventScroll: true});
    row.scrollIntoView({block: "nearest"});
  }

  // The sentence under the tree: loading (after a moment), could not be read, nobody here.
  function sayState(empty) {
    if (!said) return;
    var text = failed ? t("people.failed") : !view() ? (waited ? t("people.loading") : "")
             : empty ? t("people.none_here") : "";
    if (said.textContent !== text) said.textContent = text;
  }

  function drawList() {
    var v = view();
    if (!tree) return;
    if (!v) { sayState(false); return; }
    var list = listed(v), secs = sections(v, list);
    if (countsEl) countsEl.textContent = t("people.counts", {p: list.people.length, a: list.agents.length});
    // What had the focus: a row, a control in it, or the reader's own status field.
    var a = document.activeElement, inside = !!(a && tree.contains(a));
    var row = inside ? a.closest("[role=treeitem]") : null;
    var own = inside && a.dataset && a.dataset.key && a.dataset.key.indexOf("st-mine") === 0 ? a.dataset.key : null;
    var top = body ? body.scrollTop : 0;
    tree.textContent = "";
    secs.forEach(function (s, i) {
      var sec = make("li", "psec"), headId = "mh" + (++ids) + "-" + i;
      sec.setAttribute("role", "group");
      var head = make("div", "psec-head", s.title);
      head.id = headId;
      head.setAttribute("role", "presentation");
      var named = [headId];
      if (s.hint) {
        head.title = s.hint;
        var hint = make("span", "vh", s.hint);
        named.push(idOf(hint));
        sec.appendChild(hint);
      }
      sec.setAttribute("aria-labelledby", named.join(" "));
      var ul = make("ul", "plist");
      ul.setAttribute("role", "none");
      s.families.forEach(function (f, j) {
        if (f.lone) { ul.appendChild(agentRow(f.who, 1, j + 1, s.families.length, true)); return; }
        var p = personRow(f, s, j + 1, s.families.length);
        ul.appendChild(p);
        if (p.getAttribute("aria-expanded") !== "true") return;
        f.agents.forEach(function (ag, k) { ul.appendChild(agentRow(ag, 2, k + 1, f.agents.length, false)); });
      });
      sec.prepend(head);
      sec.appendChild(ul);
      tree.appendChild(sec);
    });
    var all = rows();
    holdStop(rowByKey(stop) || all[0] || null);
    if (body) body.scrollTop = top;
    sayState(!all.length);
    if (!inside) return;
    // The focus stays where it was: the same field or row; a row gone, its person's (an agent hidden as its person
    // closed, or gone); else the tab stop.
    var again = (own && tree.querySelector('[data-key="' + own + '"]')) || (row && rowByKey(row.dataset.key)) ||
                (row && row.dataset.owner && rowOf(row.dataset.owner)) || rowByKey(stop);
    if (again && again.getAttribute("role") === "treeitem") holdStop(again);
    if (again) again.focus({preventScroll: true});
  }

  // Open or close a person's agents, in place; kept. The focus goes to the person's row.
  function fold(name, on) {
    keepOpen(name, on);
    turning = name;
    stop = "m:" + name;
    drawList();
    turning = null;
    focusRow(rowOf(name));
  }

  // The reader's own status, from their menu: the field on their row (the member list shown first).
  function editMine(me) {
    if (A.right && A.right.current !== "members") A.right.show("members");
    St.edit(me.status && me.status.title ? me.status.title : "");
  }

  function openCard(row) { P.card(row.dataset.name, row.querySelector(".prow-name") || row, row); }

  if (tree) {
    tree.addEventListener("click", function (ev) {
      var row = ev.target.closest("[role=treeitem]");
      if (!row || ev.target.closest(".st-mine")) return;             // the reader's own status: its field
      if (ev.target.closest(".prow-mark:not(.none)")) {
        fold(row.dataset.name, row.getAttribute("aria-expanded") !== "true");
        return;
      }
      var acts = ev.target.closest(".row-acts");
      focusRow(row);
      if (acts) { P.menu(row.dataset.name, {anchor: acts}, row); return; }
      var sel = window.getSelection ? window.getSelection() : null;
      if (sel && !sel.isCollapsed && row.contains(sel.anchorNode)) return;   // text chosen in the row, not a press
      openCard(row);
    });
    // Right click: the member's menu at the pointer; on a status line the browser's own.
    tree.addEventListener("contextmenu", function (ev) {
      var row = ev.target.closest("[role=treeitem]");
      if (!row || ev.target.closest(".pstatus")) return;
      ev.preventDefault();
      focusRow(row);
      P.menu(row.dataset.name, ev.clientX || ev.clientY ? {x: ev.clientX, y: ev.clientY} : {anchor: row}, row);
    });
    tree.addEventListener("keydown", function (ev) {
      if (ev.target.closest(".st-mine-form")) return;                // while the field is open, the keys are its
      var row = ev.target.closest("[role=treeitem]");
      if (!row) return;
      var all = rows(), i = all.indexOf(row), name = row.dataset.name, open = row.getAttribute("aria-expanded");
      function go(j) { if (all[j]) { ev.preventDefault(); focusRow(all[j]); } }
      if (ev.key === "ArrowDown") go(i + 1);
      else if (ev.key === "ArrowUp") go(i - 1);
      else if (ev.key === "Home") go(0);
      else if (ev.key === "End") go(all.length - 1);
      else if (ev.key === "ArrowRight") {
        ev.preventDefault();
        if (open === "false") fold(name, true);
        else if (open === "true" && all[i + 1] && all[i + 1].dataset.owner === name) go(i + 1);
      } else if (ev.key === "ArrowLeft") {
        ev.preventDefault();
        if (open === "true") fold(name, false);
        else if (row.getAttribute("aria-level") === "2") focusRow(rowOf(row.dataset.owner));
      } else if ((ev.key === "Enter" || ev.key === " ") && ev.target === row) {
        ev.preventDefault();
        openCard(row);
      } else if (ev.key === "ContextMenu" || (ev.key === "F10" && ev.shiftKey)) {
        ev.preventDefault();
        P.menu(name, {anchor: row}, row);
      } else if (ev.key.length === 1 && /\S/.test(ev.key) && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
        var k = ev.key.toLowerCase();
        for (var j = 1; j <= all.length; j++) {
          var x = all[(i + j) % all.length];
          if ((x.dataset.name || "").toLowerCase().indexOf(k) === 0) { go((i + j) % all.length); break; }
        }
      }
    });
    // A row keeps the tab stop once it had the focus.
    tree.addEventListener("focusin", function (ev) {
      var row = ev.target.closest("[role=treeitem]");
      if (row && row.tabIndex !== 0) holdStop(row);
    });
    setTimeout(function () { waited = true; if (!view()) sayState(false); }, LOADING_MS);
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
  if (S.onMembersRead) {
    S.onMembersRead(function (ok) {
      if (failed === !ok) return;
      failed = !ok;
      sayState(!!tree && !tree.querySelector("[role=treeitem]"));
    });
  }
  S.onMembers(function (v) {
    prune(v);
    loadReaders();
    redraw();
    // The card follows the data, unless an act is armed in it or a menu from it is open.
    if (shown && A.popup.isOpen(card) && !A.isArmed(card) && !document.querySelector(".menu.shown")) {
      A.keepFocus(card, function () { fillCard(shown.name); });
    }
  });
})();
