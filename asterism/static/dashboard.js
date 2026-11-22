// The work page's dashboard tab (#dashboard; m1s_contract.md section 5): what each agent is working on, from
// /api/statuses (statuses.js) and the members (frame.js).
// - Scopes: 所有群組 (every agent, the first), then each group that has agents, in the groups' order (custom groups,
//   each person's agent group, then the default ones), with its number of agents.
// - One card per agent of the chosen scope, in the agents' order: its picture, presence and name, its model, what it
//   is doing (working or idle while online, as the member list says it), its person, its quotas (an agent of the
//   reader's own, from /api/my); then its status: the title, the body (Markdown with mathematics, folded after a few
//   lines, opened in place), "更新於 3 小時前" and the overdue mark; an agent without one says so quietly. For the
//   agent's own person, "要求每 __ 小時更新" (set or clear, in place); for others, how often its person asks, as a fact.
// - The name opens the agent page at that agent.
"use strict";
(function () {
  var A = window.Asterism, G = A && A.workPage, view = document.getElementById("dashboard");
  var St = A && A.statuses, S = A && A.side;
  if (!G || !view || !St || !S) return;
  var t = A.t, make = A.make, ME = G.me;
  var mine = null, mineRaw = "";

  function agents() { return (S.members && S.members.agents) || []; }
  function statusOf(name) { return St.agent(name); }
  function groups() { return (S.members && S.members.groups) || []; }
  function label(g) { return A.people && S.members ? A.people.rules(S.members).label(g) : g.name; }
  // The groups that hold agents, in the groups' order but the default ones last.
  function scopeGroups() {
    var list = agents(), gs = groups().filter(function (g) {
      return list.some(function (a) { return (a.groups || []).indexOf(g.name) >= 0; });
    });
    return gs.filter(function (g) { return g.kind !== "default"; }).concat(gs.filter(function (g) { return g.kind === "default"; }));
  }
  function scope() {
    var g = G.params().get("group") || "";
    return scopeGroups().some(function (x) { return x.name === g; }) ? g : "";
  }
  function query(g) { return g ? "group=" + encodeURIComponent(g) : ""; }
  function shown(g) {
    return agents().filter(function (a) { return !g || (a.groups || []).indexOf(g) >= 0; });
  }

  // ------------------------------------------------------------------ a card

  function quotaLine(a) {
    if (a.owner !== ME || !mine) return null;
    var me = (mine.agents || []).filter(function (x) { return x.name === a.name; })[0];
    var cred = me && (mine.credentials || []).filter(function (c) { return c.id === me.credential; })[0];
    var q = cred && (cred.quotas || []).filter(function (x) { return x.product === a.kind; })[0];
    if (!q || !(q.windows || []).length) return null;
    var span = make("span", "db-quota", A.quotaText(q, false));
    span.title = A.quotaText(q, true);
    span.setAttribute("aria-label", t("quota.label", {text: A.quotaText(q, true)}));
    return span;
  }

  function card(a) {
    var st = statusOf(a.name) || {agent: a.name, title: (a.status && a.status.title) || "", body: "",
                                   at: a.status && a.status.at, overdue: !!(a.status && a.status.overdue),
                                   update_every_h: null};
    var li = make("li", "db-card" + (st.overdue ? " overdue" : ""));
    li.dataset.agent = a.name;
    var head = make("div", "db-head");
    head.append(S.avatar(a.name, 24, {kind: "agent", avatar: a.avatar}), S.presence({kind: "agent", online: !!a.online}));
    var name = make("a", "db-name mono", a.name);
    name.href = "/" + encodeURIComponent(G.slug) + "/agent?name=" + encodeURIComponent(a.name);
    name.dataset.key = "db-name:" + a.name;
    head.appendChild(name);
    var model = A.modelTag(a.model);
    if (model) head.appendChild(model);
    var state = S.workMark(a, "db-state");
    if (state) head.appendChild(state);
    li.appendChild(head);
    var facts = [a.owner === ME ? t("nav.my_agent") : t("mem.agent_of", {owner: a.owner || "?"})];
    if (!a.online) facts.push(t("presence.offline"));
    var quota = quotaLine(a);
    if (quota) facts.push(quota);
    li.appendChild(G.facts("db-facts", facts));
    if (st.title) {
      li.appendChild(make("h3", "db-title", st.title));
      li.appendChild(St.body(st.body, "db:" + a.name));
    } else {
      li.appendChild(make("p", "db-none", t("db.no_status")));
    }
    var upd = St.updated(st, "db-updated");
    var every = st.update_every_h && a.owner !== ME ? t("st.every", {n: st.update_every_h}) : "";
    if (upd || every) li.appendChild(G.facts("db-track", [upd, every]));
    if (a.owner === ME && statusOf(a.name)) {
      li.appendChild(St.everyControl(st, function () { St.load(true); }));
    }
    return li;
  }

  // ------------------------------------------------------------------ drawing

  function draw() {
    var g = scope(), list = shown(g);
    view.textContent = "";
    if (!S.members) return;
    if (!list.length) { view.appendChild(make("p", "tt-empty", t("db.none"))); return; }
    var ul = make("ul", "db-list");
    list.forEach(function (a) { ul.appendChild(card(a)); });
    view.appendChild(ul);
  }

  G.register({
    scopes: function () {
      var out = [{heading: t("db.agents")}, {query: "", label: t("db.all"), count: agents().length}];
      var gs = scopeGroups();
      if (gs.length) out.push({heading: t("db.groups")});
      gs.forEach(function (g) {
        out.push({query: query(g.name), label: label(g), mono: g.kind === "custom", count: shown(g.name).length});
      });
      return out;
    },
    current: function () { return query(scope()); },
    title: function () {
      var g = scope(), x = groups().filter(function (y) { return y.name === g; })[0];
      return t("ag.count", {name: x ? label(x) : t("db.all"), n: shown(g).length});
    },
    draw: draw,
    // A number being written in "要求每 __ 小時更新" is not thrown away by a redraw.
    busy: function () {
      var a = document.activeElement;
      return !!(a && view.contains(a) && a.tagName === "INPUT");
    }
  });
  St.onChange(function () { G.redraw(false); });
  S.onMembers(function () { G.redraw(false); });
  S.loadMembers();
  St.follow();
  async function loadMine() {
    var r = await A.request(G.api + "my");
    if (!r.ok) return;
    var raw = JSON.stringify(r.data);
    if (raw === mineRaw) return;
    mineRaw = raw;
    mine = r.data;
    G.redraw(false);
  }
  loadMine();
  setInterval(loadMine, 30000);
})();
