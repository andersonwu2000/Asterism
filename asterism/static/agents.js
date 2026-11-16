// The agent page's agents tab (#agents-view; m1f5_agent_page_design.md section 2), from /api/my, the members
// (frame.js) and the task table (tasks.js, for the counts).
// - Scope "my agents" (the bare address): my agents (#my-agents), one block each: presence, name, kind and its menu;
//   where it is ("在 {computer}"), its last activity and its tasks (a link to them); an offline agent says why on a
//   wash; its groups as chips (x and + where the reader may; never the default groups nor my own agent group) and the
//   default ones as a quiet line. Then my computers and connectors (#my-credentials) with the agents on each and
//   "revoke" (floating, the label typed), and what others may do with my agents (#my-switches: the four switches,
//   each saved as it changes).
// - Scope ?of={person}: that person's agents read only (chips where the reader may change them) and their switches,
//   disabled.
// The agent's menu: private message, its tasks, a new task for it, its groups (check boxes), open in settings,
// remove from the project (floating, the name typed).
"use strict";
(function () {
  var A = window.Asterism, G = A && A.agentPage, view = document.getElementById("agents-view");
  if (!G || !view || !A.people || !A.side) return;
  var t = A.t, make = A.make, P = A.people, S = A.side, T = A.tasks;
  var ME = G.me, API = G.api, SWITCHES = ["others_mention", "others_channel", "others_assign", "others_regroup"];
  var my = null, myRaw = "", said = {};

  function members() { return S.members; }
  function rules() { return members() ? P.rules(members()) : null; }
  function dmHref(name) { return "/" + encodeURIComponent(G.slug) + "/dm/" + encodeURIComponent(name); }
  function tasksHref(query) { return G.home + "/tasks?" + query; }
  function tasksOf(name) { return T && T.data ? T.of(name).length : 0; }

  // The other people with agents, in the order of their agent groups.
  function others() {
    var v = members();
    if (!v) return [];
    var seen = {}, out = [];
    v.groups.forEach(function (g) {
      if (g.kind !== "ownership" || !g.owner || g.owner === ME || seen[g.owner]) return;
      var n = v.agents.filter(function (a) { return a.owner === g.owner; }).length;
      if (!n) return;
      seen[g.owner] = true;
      var p = v.people.filter(function (x) { return x.name === g.owner; })[0];
      out.push({name: g.owner, count: n, online: !!(p && p.online)});
    });
    return out;
  }
  function of() {
    var who = G.params().get("of");
    return who && others().some(function (x) { return x.name === who; }) ? who : "";
  }

  // ------------------------------------------------------------------ an agent

  function refresh(r, out) {
    if (r && !r.ok) G.say(out, A.refusal("ag.refused", r.data));
    return Promise.all([S.loadMembers(), load(true)]).then(function () { G.redraw(true); });
  }

  function menuFor(who, out, mine) {
    var R = rules(), items = [];
    if (mine) items.push({label: t("ag.message"), href: dmHref(who.name)});
    items.push({label: t("ag.its_tasks"), href: tasksHref("agent=" + encodeURIComponent(who.name))});
    if (G.canEditTasks && (!T || T.mayGive(who.name))) {
      items.push({label: t("ag.add_task"), href: tasksHref("agent=" + encodeURIComponent(who.name) + "&new=1")});
    }
    if (R) {
      var boxes = P.groupItems(R, who, true, function (r) { refresh(r, out); });
      if (boxes.length) items.push({label: t("people.groups"), items: boxes});
      if (!mine && R.mayManage()) {
        items.push({label: t("people.open_settings"),
                    href: "/" + encodeURIComponent(G.slug) + "/settings/members?m=" + encodeURIComponent(who.name)});
      }
      if (R.mayRemove(who, true)) {
        items.push({separator: true}, {label: t("people.remove"), run: function () {
          P.remove(who, true, null, null, function () { refresh(null, out); });
        }});
      }
    }
    return items;
  }

  function block(a, cred, mine) {
    var v = members(), R = rules();
    var who = (v && v.agents.filter(function (x) { return x.name === a.name; })[0]) || a;
    var li = make("li", "ag-item"), out = make("div", "out");
    out.setAttribute("aria-live", "polite");
    var first = make("div", "ag-line");
    first.append(S.presence({kind: "agent", online: !!who.online}), make("span", "ag-name mono", who.name));
    var model = A.modelTag(who.model);
    if (model) first.appendChild(model);
    first.appendChild(make("span", "dim", A.MSG["kind." + who.kind] ? t("kind." + who.kind) : who.kind));
    li.appendChild(first);
    function open(where, opener) {
      A.menu(Object.assign({label: t("ag.acts", {name: who.name})}, where), menuFor(who, out, mine), opener);
    }
    var acts = G.acts(t("ag.acts", {name: who.name}), "acts:" + who.name, open);
    li.appendChild(acts);
    G.menuOn(li, acts, open);
    var n = tasksOf(who.name), link = null;
    if (n) {
      link = make("a", "", t("ag.tasks_n", {n: n}));
      link.href = tasksHref("agent=" + encodeURIComponent(who.name));
      link.dataset.key = "tasks:" + who.name;
    }
    var on = null;
    if (cred) {
      on = make("span");
      on.append(document.createTextNode(t("ag.on", {computer: ""})), make("span", "mono", cred.label));
    }
    li.appendChild(G.facts("ag-meta", [who.online ? null : t("ag.offline"), on,
                                       who.last_active ? t("ag.last", {time: G.time(who.last_active)}) : null, link]));
    if (!who.online && who.offline_because && A.MSG["offline." + who.offline_because]) {
      li.appendChild(make("div", "ag-why", t("offline." + who.offline_because)));
    }
    if (R && who.groups) {
      var chips = make("div", "ag-chips");
      R.plainOf(who).filter(function (g) { return g.kind !== "ownership"; }).forEach(function (g) {
        chips.appendChild(P.chip(R, who, true, g.name, function (r) { refresh(r, out); }));
      });
      var plus = P.plus(rules, who, true, function (r) { refresh(r, out); });
      if (plus) chips.appendChild(plus);
      var defaults = R.defaultsOf(who);
      if (defaults.length) chips.appendChild(make("span", "dim small", t("ag.defaults", {names: defaults.map(R.label).join(t("ag.sep"))})));
      if (chips.children.length) li.appendChild(chips);
    }
    li.appendChild(out);
    return li;
  }

  // ------------------------------------------------------------------ my agents, computers and switches

  function section(id, title) {
    var sec = make("section", "ag-sec");
    if (id) sec.id = id;
    sec.appendChild(make("h2", "ag-h", title));
    return sec;
  }

  function drawMine() {
    var agents = my.agents || [], creds = my.credentials || [];
    var byId = {};
    creds.forEach(function (c) { byId[c.id] = c; });
    var sec = section("my-agents", t("ag.agents_n", {n: agents.length}));
    if (agents.length) {
      var ul = make("ul", "ag-list");
      agents.forEach(function (a) { ul.appendChild(block(a, a.credential !== null ? byId[a.credential] : null, true)); });
      sec.appendChild(ul);
    } else {
      sec.appendChild(make("p", "ag-empty", t("ag.none")));
      if (A.can("manage_own_agents")) {
        var b = A.button("btn primary", t("ag.invite"));
        b.dataset.act = "invite-agent";
        b.dataset.key = "invite-empty";
        sec.appendChild(b);
      }
    }
    view.appendChild(sec);

    var cs = section("my-credentials", t("ag.creds_n", {n: creds.length}));
    if (creds.length) {
      var cl = make("ul", "ag-list");
      creds.forEach(function (c) { cl.appendChild(credential(c, agents)); });
      cs.appendChild(cl);
    } else {
      cs.appendChild(make("p", "ag-empty", t("my.no_credentials")));
    }
    view.appendChild(cs);

    var ss = section("my-switches", t("my.switches"));
    ss.appendChild(make("p", "dim", t("my.switches_hint")));
    var box = make("div", "ag-switches");
    SWITCHES.forEach(function (k) { box.appendChild(switchRow(k, !!(my.switches || {})[k], t("switch." + k), true)); });
    var more = make("a", "", t("ag.group_settings"));
    more.href = "/" + encodeURIComponent(G.slug) + "/settings/groups?g=" + encodeURIComponent(ME + "-agents");
    box.appendChild(make("p", "check")).appendChild(more);
    ss.appendChild(box);
    view.appendChild(ss);
  }

  function credential(c, agents) {
    var li = make("li", "ag-item"), out = make("div", "out");
    out.setAttribute("aria-live", "polite");
    var first = make("div", "ag-line");
    var via = A.MSG["my.via." + c.via] ? t("my.via." + c.via) : (c.via || "");
    first.append(make("span", "ag-name mono", c.label), make("span", "dim", t("ag.cred_kind", {kind: t("cred." + c.kind), via: via})));
    li.appendChild(first);
    var b = A.button("btn ag-side-btn", t("my.revoke"));
    b.setAttribute("aria-label", t("ag.revoke_label", {name: c.label}));
    b.dataset.key = "revoke:" + c.id;
    b.addEventListener("click", function () {
      A.gone({title: t("gone.revoke.title", {name: c.label}), text: t("gone.revoke.text", {name: c.label}), name: c.label,
              button: t("gone.revoke.button"), opener: b,
              run: function () { return A.request(API + "my/credentials/" + encodeURIComponent(c.id) + "/revoke", null, {}); },
              done: function () { refresh(null, out); }});
    });
    li.appendChild(b);
    var on = agents.filter(function (a) { return a.credential === c.id; }).map(function (a) { return a.name; });
    var names = null;
    if (on.length) {
      names = make("span");
      names.appendChild(document.createTextNode(t("ag.cred_agents", {names: ""})));
      on.forEach(function (n, i) {
        if (i) names.appendChild(document.createTextNode(t("ag.sep")));
        names.appendChild(make("span", "mono", n));
      });
    }
    li.appendChild(G.facts("ag-meta", ["connected" in c ? t(c.connected ? "my.connected.yes" : "my.connected.no") : null,
                                       c.last_used ? t("ag.last_used", {time: G.time(c.last_used)}) : null, names]));
    li.appendChild(out);
    return li;
  }

  // One switch: saved as it changes, "已儲存。" beside it for a moment, a refusal in the same place. Another person's
  // are shown disabled.
  function switchRow(k, on, label, mine) {
    var row = make("div", "check"), lab = make("label"), box = make("input"), out = make("span", "out");
    box.type = "checkbox";
    box.name = k;
    box.checked = on;
    box.disabled = !mine;
    box.dataset.key = "sw:" + k;
    out.setAttribute("aria-live", "polite");
    out.textContent = said[k] || "";
    lab.append(box, document.createTextNode(" " + label));
    row.append(lab, out);
    if (mine) {
      box.addEventListener("change", async function () {
        var body = {};
        body[k] = box.checked;
        var r = await A.request(API + "my/switches", null, body);
        if (!r.ok) { box.checked = !box.checked; out.textContent = A.refusal("ag.refused", r.data); return; }
        my.switches = r.data.switches;
        said[k] = t("ag.saved");
        out.textContent = said[k];
        setTimeout(function () { if (said[k] === t("ag.saved")) { said[k] = ""; out.textContent = ""; } }, 2500);
        S.loadMembers();
      });
    }
    return row;
  }

  // ------------------------------------------------------------------ another person's agents

  function drawOthers(person) {
    var v = members(), agents = v.agents.filter(function (a) { return a.owner === person; });
    var sec = section("", t("ag.agents_n", {n: agents.length}));
    var ul = make("ul", "ag-list");
    agents.forEach(function (a) { ul.appendChild(block(a, null, false)); });
    sec.appendChild(ul);
    view.appendChild(sec);
    var own = v.groups.filter(function (g) { return g.kind === "ownership" && g.owner === person; })[0];
    var ss = section("", t("mem.switches", {owner: person}));
    var box = make("div", "ag-switches");
    SWITCHES.forEach(function (k) {
      box.appendChild(switchRow(k, !!(own && own.switches && own.switches[k]), t("mem.sw." + k, {owner: person}), false));
    });
    box.appendChild(make("p", "dim", t("mem.switches_other", {owner: person})));
    ss.appendChild(box);
    view.appendChild(ss);
  }

  // ------------------------------------------------------------------ the tab

  async function load(force) {
    var r = await A.request(API + "my");
    if (!r.ok) return;
    var raw = JSON.stringify(r.data);
    if (raw === myRaw && !force) return;
    myRaw = raw;
    my = r.data;
    G.redraw(false);
  }

  G.register({
    scopes: function () {
      var out = [{heading: t("ag.me")}, {query: "", label: t("ag.mine"), count: my ? my.agents.length : 0}];
      var list = others();
      if (list.length) out.push({heading: t("ag.others")});
      list.forEach(function (x) {
        out.push({query: "of=" + encodeURIComponent(x.name), label: x.name, count: x.count,
                  presence: {kind: "person", online: x.online}});
      });
      return out;
    },
    current: function () { var p = of(); return p ? "of=" + encodeURIComponent(p) : ""; },
    title: function () {
      var p = of();
      if (p) return t("ag.count", {name: p, n: members().agents.filter(function (a) { return a.owner === p; }).length});
      return my ? t("ag.count", {name: t("ag.mine"), n: my.agents.length}) : "";
    },
    draw: function () {
      view.textContent = "";
      var p = of();
      if (p) drawOthers(p); else if (my) drawMine();
    },
    load: function () { load(false); }
  });
  S.onMembers(function () { G.redraw(false); });
  if (T) T.onChange(function () { G.redraw(false); });
  load(true);
})();
