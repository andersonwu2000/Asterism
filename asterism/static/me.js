// The reader's own settings (the settings layer at /{slug}/me; settings.js switches its sections):
// - profile: the name in this project (#me-name: sent, then the page again, so every place shows it), the status in
//   this project (#me-status: one line, a mood or a few words about oneself, saved in place; 1s), the avatar
//   in this project (#me-avatar: the picture or the monogram, "choose a picture" and "remove", A.side.pickAvatar), the
//   language of the pages (#me-locale: kept with the account, then the page again in it) and the look (#me-theme:
//   dark, light, or the system's, kept in this browser as before);
// - computers and connectors (#me-computers, from /api/my for this project and /api/me/computers for the account):
//   under 電腦 · n each computer of this project as a block (its name, the tag 寫入公共檔案 on the writing one, 撤銷;
//   a state line of three facts, connection, program, git, each dim when it is the norm and in the ink when not;
//   named lines: its agents with what they are doing or why they are offline, the quotas its program reported, how
//   and when it was authorised and where else it joined), then a quiet row for each computer of mine that has not
//   joined this project (it may be the writing one); under 連接器 · n each connector the same way. 撤銷 floats (the name
//   typed), saying the project, the agents that go offline and, for the writing computer, what happens to writing.
//   Nothing is chosen here.
// - writing shared files (#me-writing, from /api/me/writer, /api/me/computers and can-write): who commits the
//   reader's changes, a choice of one drawn as rows with the menu's ring: the server (with the GitHub authorization's
//   state and its acts: 撤銷授權 in two steps, 重新授權 and 改由伺服器寫入 leave for GitHub and come back here) and each
//   computer of the account (改用這台電腦 in two steps: the server then deletes the GitHub authorization; disabled, with
//   the reason, for one without git or with a program too old); then the outcome for this project in one sentence.
// - what others may do with my agents (#me-switches): the four permissions of my own agent group, each saved as it
//   changes.
// Both lists are drawn again from the data every 15 s (never while a button is armed or a panel is open); two failed
// refreshes in a row say so over the lists.
"use strict";
(function () {
  var A = window.Asterism, layer = document.getElementById("settings-layer");
  if (!A || !layer || layer.dataset.scope !== "me") return;
  var t = A.t, make = A.make;
  var SLUG = layer.dataset.slug, HERE = "/" + encodeURIComponent(SLUG);
  var API = HERE + "/api/", LANG = document.documentElement.lang || undefined;
  // Two sentences of the catalogue in a row: Chinese ones end with their own full stop, English ones need a space.
  var SP = /^zh/i.test(LANG || "") ? "" : " ";
  var NEED = "0.1.13";                  // the first program that says which computer it is: the one that can be chosen
  var my = A.parseJSON(layer.dataset.my, null), mine = A.parseJSON(layer.dataset.computers, null);
  var wstate = A.parseJSON(layer.dataset.writer, null);
  var LOGIN = layer.dataset.login || "", PROJECT = layer.dataset.project || SLUG, REPO = layer.dataset.repo || "";
  var raw = JSON.stringify([my, mine, wstate]);

  // ------------------------------------------------------------------ profile

  var nameForm = document.getElementById("me-name");
  if (nameForm) {
    nameForm.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var out = nameForm.querySelector(".out");
      out.textContent = "";
      var r = await A.request(API + "me/name", null, {name: nameForm.elements.name.value.trim()});
      if (!r.ok) {
        if (/^(invalid_name|conflict)$/.test(r.data.error)) A.fieldError(nameForm.elements.name, A.refusal("me.name", r.data));
        else out.textContent = A.refusal("me.name", r.data);
        return;
      }
      window.location.reload();
    });
  }

  var statusForm = document.getElementById("me-status");
  if (statusForm) {
    statusForm.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var out = statusForm.querySelector(".out");
      out.textContent = "";
      var r = await A.request(API + "me/status", null, {title: statusForm.elements.title.value});
      if (!r.ok) { A.fieldError(statusForm.elements.title, A.refusal("st.refused", r.data)); return; }
      statusForm.elements.title.value = r.data.title;
      A.saved(out);
      if (A.side) A.side.loadMembers();
    });
  }

  // The avatar: the picture as others see it, choosing another, removing it; the outcome said beside the buttons.
  var avatarBox = document.getElementById("me-avatar"), ME = A.side ? document.getElementById("rail").dataset.me : "";
  function drawAvatar(said) {
    if (!avatarBox || !A.side) return;
    var mineAv = A.side.directory[ME] || {kind: "person"}, out = make("span", "out");
    out.setAttribute("aria-live", "polite");
    avatarBox.textContent = "";
    var pick = A.button("btn", t("me.avatar_pick"), async function () {
      out.textContent = "";
      var r = await A.side.pickAvatar(API + "me/avatar");
      if (r.cancelled) return;
      if (!r.ok) { out.textContent = A.refusal("me.avatar", r.data); return; }
      drawAvatar(true);
    });
    pick.dataset.key = "avatar-pick";
    avatarBox.append(A.side.avatar(ME, 64, {kind: "person", avatar: mineAv.avatar}), pick);
    if (mineAv.avatar) {
      var drop = A.button("btn", t("me.avatar_remove"), async function () {
        out.textContent = "";
        var r = await A.side.removeAvatar(API + "me/avatar");
        if (!r.ok) { out.textContent = A.refusal("me.avatar", r.data); return; }
        drawAvatar(true);
      });
      drop.dataset.key = "avatar-remove";
      avatarBox.appendChild(drop);
    }
    avatarBox.appendChild(out);
    if (said) A.saved(out);
  }
  if (avatarBox && A.side) {
    drawAvatar(false);
    A.side.onMembers(function () { A.keepFocus(avatarBox, function () { drawAvatar(false); }); });
  }

  var locales = document.getElementById("me-locale"), localeOut = document.getElementById("me-locale-out");
  if (locales) {
    locales.addEventListener("click", async function (ev) {
      var b = ev.target.closest && ev.target.closest("[data-locale]");
      if (!b || b.getAttribute("aria-pressed") === "true") return;
      localeOut.textContent = "";
      var r = await A.request("/api/me/settings", null, {locale: b.dataset.locale});
      if (!r.ok) { localeOut.textContent = A.refusal("me.locale", r.data); return; }
      window.location.reload();
    });
  }

  var themes = document.getElementById("me-theme");
  function markTheme() {
    if (!themes || !A.theme) return;
    var now = A.theme.choice();
    Array.prototype.forEach.call(themes.querySelectorAll("[data-theme-choice]"), function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.themeChoice === now));
    });
  }
  if (themes) {
    themes.addEventListener("click", function (ev) {
      var b = ev.target.closest && ev.target.closest("[data-theme-choice]");
      if (!b || !A.theme) return;
      A.theme.choose(b.dataset.themeChoice);
      markTheme();
    });
    window.addEventListener("storage", markTheme);
    markTheme();
  }

  // ------------------------------------------------------------------ what others may do with my agents

  Array.prototype.forEach.call(layer.querySelectorAll("input[data-switch]"), function (box) {
    var out = box.parentElement.querySelector(".out");
    box.addEventListener("change", async function () {
      var body = {};
      body[box.dataset.switch] = box.checked;
      out.textContent = "";
      var r = await A.request(API + "my/switches", null, body);
      if (!r.ok) { box.checked = !box.checked; out.textContent = A.refusal("grp.change", r.data); return; }
      A.saved(out);
    });
  });

  // ------------------------------------------------------------------ shared by the two lists

  function when(iso) {
    var d = new Date(iso);
    if (!iso || isNaN(d.getTime())) return "";
    return d.toLocaleString(LANG, {month: "long", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false});
  }
  function day(iso) {
    var d = new Date(iso);
    if (!iso || isNaN(d.getTime())) return "";
    return d.toLocaleDateString(LANG, {month: "long", day: "numeric"});
  }
  function mono(text) { return make("span", "mono", text); }
  function ink(text) { return make("span", "ink", text); }
  function list(names) { return names.join(t("ag.sep")); }

  // The catalogue's sentence with its places filled: a string as text, an element as itself (a name in the mono voice,
  // a link), so that no markup is ever built from text.
  function fill(key, vars) {
    var frag = document.createDocumentFragment(), s = A.MSG[key] || key, re = /\{(\w+)\}/g, at = 0, m;
    while ((m = re.exec(s))) {
      if (m.index > at) frag.appendChild(document.createTextNode(s.slice(at, m.index)));
      var v = vars && Object.prototype.hasOwnProperty.call(vars, m[1]) ? vars[m[1]] : m[0];
      frag.appendChild(v instanceof Node ? v : document.createTextNode(String(v)));
      at = re.lastIndex;
    }
    if (at < s.length) frag.appendChild(document.createTextNode(s.slice(at)));
    return frag;
  }

  // Facts joined by " · " (each a string, or an element: dim when the norm, .ink when the exception).
  function joined(cls, parts) {
    var p = make("div", cls);
    parts.filter(function (x) { return x; }).forEach(function (x, i) {
      if (i) p.appendChild(document.createTextNode(" · "));
      p.appendChild(typeof x === "string" ? document.createTextNode(x) : x);
    });
    return p;
  }

  // The computers of the account (/api/me/computers), by machine id; a computer's other projects.
  function accountOf(machine) {
    if (!machine || !mine) return null;
    return (mine.computers || []).filter(function (x) { return x.machine === machine; })[0] || null;
  }
  function elsewhere(item) {
    return item ? item.projects.filter(function (p) { return p.slug !== SLUG; }) : [];
  }
  function latest() { return (mine && mine.program && mine.program.version) || (my && my.program && my.program.version) || null; }
  // A computer's name, and when two of mine have the same one the first four characters of its machine id after it.
  function nameOf(label, machine, labels) {
    var span = make("span", "dev-label");
    span.appendChild(make("b", "mono", label));
    if (machine && labels[label] > 1) span.appendChild(make("span", "mono dim", machine.slice(0, 4)));
    return span;
  }
  function labelCounts() {
    var n = {};
    ((mine && mine.computers) || []).forEach(function (x) { n[x.label] = (n[x.label] || 0) + 1; });
    return n;
  }
  function inviteButton() {
    if (!document.getElementById("invite-panel")) return null;
    var b = A.button("btn", t("ag.invite"));
    b.dataset.act = "invite-agent";
    b.setAttribute("aria-haspopup", "dialog");
    b.dataset.key = "invite";
    return b;
  }
  function writingHref() { return HERE + "/me/writing"; }

  // ------------------------------------------------------------------ computers and connectors

  var box = document.getElementById("me-computers"), stale = document.getElementById("me-stale");

  function subHead(key, n, act) {
    var head = make("div", "my-sub"), h = make("h3", "my-h");
    h.tabIndex = -1;
    h.appendChild(document.createTextNode(t(key)));
    if (n) h.appendChild(make("span", "dim", " · " + n));
    head.appendChild(h);
    if (act) head.appendChild(act);
    return head;
  }

  // One named line of a block: a dim label and its value (below 600 px the label sits over the value).
  function row(dl, key, lines) {
    dl.append(make("dt", "", t(key)));
    var dd = make("dd");
    lines.forEach(function (l) { dd.appendChild(l); });
    dl.appendChild(dd);
  }
  function line(parts) {
    var l = make("div", "line");
    parts.filter(function (x) { return x; }).forEach(function (x) {
      l.appendChild(typeof x === "string" ? make("span", "", x) : x);
    });
    return l;
  }

  // An agent on a computer or a connector: its presence, its name (to its page), its product, and what it is doing,
  // or, offline, the short reason (the one the person can fix in the ink).
  function agentLine(a) {
    var who = make("span", "who");
    if (A.side && A.side.presence) who.appendChild(A.side.presence({kind: "agent", online: a.online}));
    var link = make("a", "mono", a.name);
    link.href = HERE + "/agent?name=" + encodeURIComponent(a.name);
    who.appendChild(link);
    var product = A.MSG["kind." + a.kind] ? t("kind." + a.kind) : a.kind, doing = null;
    if (a.online) {
      doing = A.side && A.side.workMark ? A.side.workMark(a) : null;
    } else if (a.offline_because) {
      var why = A.MSG["my.offline." + a.offline_because] ? t("my.offline." + a.offline_because) : a.offline_because;
      doing = make("span", a.offline_because === "session_closed" ? "ink" : "", t("my.offline", {why: why}));
    }
    return line([who, product, doing]);
  }

  function quotaLines(quotas) {
    var lines = [], at = null;
    (quotas || []).forEach(function (q) {
      if (!(q.windows || []).length) return;
      var product = A.MSG["kind." + q.product] ? t("kind." + q.product) : q.product;
      lines.push(line([make("span", "q-product", product), A.quotaText(q, true), q.plan ? t("quota.plan", {plan: q.plan}) : null]));
      at = at || q.at;
    });
    if (lines.length && at) lines.push(line([t("quota.at", {time: when(at)})]));
    return lines;
  }

  function authLine(c, others) {
    var via = A.MSG["my.via." + c.via] ? t("my.via." + c.via) : (c.via || "");
    var parts = [t("my.auth", {date: day(c.created), via: via})];
    if (others.length) parts.push(t("my.also_in", {projects: list(others.map(function (p) { return p.name; }))}));
    return joined("line", parts);
  }

  function revoke(c, kind, agentsOn, others) {
    var b = A.button("btn dev-revoke", t("my.revoke"));
    b.setAttribute("aria-label", t("ag.revoke_label", {name: c.label}));
    b.dataset.key = "revoke:" + c.id;
    b.addEventListener("click", function () {
      var names = agentsOn.map(function (a) { return a.name; }), vars = {name: c.label, project: PROJECT, agents: list(names)};
      var more = null;
      if (kind === "computer" && c.writer) more = t(others.length ? "gone.computer.writer_here" : "gone.computer.writer_last", {project: PROJECT});
      A.gone({title: t("gone." + kind + ".title", {name: c.label}),
              text: t("gone." + kind + (names.length ? ".text" : ".text_none"), vars), more: more, name: c.label,
              button: t("gone.revoke.button"), opener: b,
              run: function () { return A.request(API + "my/credentials/" + encodeURIComponent(c.id) + "/revoke", null, {}); },
              done: function () {
                load(true).then(function () {
                  var h = box.querySelector(".my-h");
                  if (h) h.focus({preventScroll: true});
                });
              }});
    });
    return b;
  }

  function computerBlock(c, labels) {
    var item = accountOf(c.machine), others = elsewhere(item);
    var agentsOn = (my.agents || []).filter(function (a) { return a.credential === c.id; });
    var block = make("div", "dev"), head = make("div", "dev-head"), name = make("div", "dev-name");
    name.appendChild(nameOf(c.label, c.machine, labels));
    if (c.writer) {
      var tag = make("a", "tag", t("my.writer"));
      tag.href = writingHref();
      name.appendChild(tag);
    }
    head.append(name, revoke(c, "computer", agentsOn, others));
    block.appendChild(head);
    var newest = latest();
    block.appendChild(joined("dev-state", [
      c.connected ? t("my.on") : ink(c.last_seen ? t("my.off", {time: when(c.last_seen)}) : t("my.off_never")),
      !c.version ? ink(t("my.program_unknown")) :
        newest && newest !== c.version ? ink(t("my.program_old", {v: c.version, latest: newest})) : t("my.program", {v: c.version}),
      c.git === true ? t("my.git.yes") : c.git === false ? ink(t("my.git.no")) : t("my.git.unknown")]));
    var dl = make("dl", "facts"), lines = agentsOn.map(agentLine);
    if (c.sessions_unbound) lines.push(line([t("my.sessions_more", {n: c.sessions_unbound})]));
    if (!lines.length) lines.push(line([t("my.no_agents")]));
    row(dl, "my.row.agents", lines);
    var quotas = quotaLines(c.quotas);
    if (quotas.length) row(dl, "my.row.quota", quotas);
    row(dl, "my.row.auth", [authLine(c, others)]);
    block.appendChild(dl);
    return block;
  }

  function connectorBlock(c) {
    var agentsOn = (my.agents || []).filter(function (a) { return a.credential === c.id; });
    var block = make("div", "dev"), head = make("div", "dev-head"), name = make("div", "dev-name");
    name.appendChild(make("b", "mono", c.label));
    head.append(name, revoke(c, "connector", agentsOn, []));
    block.append(head, joined("dev-state", [t("my.connector_kind"), c.last_used ? t("my.last_used", {time: when(c.last_used)}) : null]));
    var dl = make("dl", "facts");
    if (agentsOn.length) row(dl, "my.row.agents", agentsOn.map(agentLine));
    row(dl, "my.row.auth", [authLine(c, [])]);
    block.appendChild(dl);
    return block;
  }

  // A computer of mine that has not joined this project: one quiet row, its acts where it is.
  function quietRow(item) {
    var p = make("div", "quiet-row"), there = item.projects[0];
    p.append(make("b", "mono", item.label),
             make("span", "", t("my.elsewhere", {project: PROJECT, projects: list(item.projects.map(function (x) { return x.name; }))}) +
                              " · " + (item.online ? t("my.on") : t("my.off_never"))));
    var a = make("a", "", t("my.manage_there", {project: there.name}));
    a.href = "/" + encodeURIComponent(there.slug) + "/me/computers";
    p.appendChild(a);
    return p;
  }

  function drawComputers() {
    if (!box || !my) return;
    A.keepFocus(box, function () {
      box.textContent = "";
      var creds = my.credentials || [], labels = labelCounts();
      var comps = creds.filter(function (c) { return c.kind === "computer"; });
      var conns = creds.filter(function (c) { return c.kind !== "computer"; });
      box.appendChild(subHead("my.computers", comps.length, inviteButton()));
      comps.forEach(function (c) { box.appendChild(computerBlock(c, labels)); });
      if (!comps.length) box.appendChild(make("p", "my-empty", t("my.none_computers", {project: PROJECT})));
      ((mine && mine.computers) || []).filter(function (x) {
        return x.machine && !x.projects.some(function (p) { return p.slug === SLUG; });
      }).forEach(function (x) { box.appendChild(quietRow(x)); });
      box.appendChild(subHead("my.connectors", conns.length, null));
      conns.forEach(function (c) { box.appendChild(connectorBlock(c)); });
      if (!conns.length) box.appendChild(make("p", "my-empty", t("my.none_connectors")));
    });
  }

  // ------------------------------------------------------------------ writing shared files

  var wbox = document.getElementById("me-writing"), wsec = wbox && wbox.closest(".set-sec");
  var canWrite = null, canAsked = false;     // the last answer of can-write (null: none, or it failed)
  var revokedUntil = 0;                      // "已撤銷" stays beside the server's acts until then, through redraws

  function reauthHref() {
    return "/login/github?" + new URLSearchParams({again: "1", next: writingHref()}).toString();
  }

  // One option: the ring (filled for the current one, which carries 目前), its name, its sentences, its act at the
  // right (under the sentences below 600 px). Only the button acts; its outcome or refusal is said beside it.
  function option(cur, nameNode, text, acts) {
    var o = make("div", "opt" + (cur ? " cur" : "")), ring = make("span", "ring");
    ring.setAttribute("aria-hidden", "true");
    var name = make("span", "opt-name");
    name.appendChild(nameNode);
    if (cur) name.appendChild(make("span", "opt-cur", t("wr.current")));
    var body = make("span", "opt-text");
    body.appendChild(text);
    var actBox = make("span", "opt-acts"), out = make("span", "out");
    out.setAttribute("aria-live", "polite");
    acts.forEach(function (b) { actBox.appendChild(b); });
    actBox.appendChild(out);
    o.append(ring, name, body, actBox);
    return {el: o, out: out};
  }

  function serverOption() {
    var cur = !wstate || wstate.mode === "server", gh = wstate ? wstate.github : "none";
    var text = document.createDocumentFragment(), acts = [];
    var reauth = A.button("btn", t("wr.reauth"), function () { window.location.href = reauthHref(); });
    reauth.dataset.key = "wr-reauth";
    var revokeBtn = A.button("btn", t("wr.revoke"));
    revokeBtn.dataset.key = "wr-revoke";
    if (!cur) {
      text.appendChild(document.createTextNode(t("wr.server.off")));
      var back = A.button("btn", t("wr.to_server"));
      back.dataset.key = "wr-server";
      back.addEventListener("click", async function () {
        opt.out.textContent = "";
        var r = await A.request("/api/me/writer", null, {machine: null});
        if (!r.ok) { opt.out.textContent = A.refusal("wr.refused", r.data); return; }
        window.location.href = reauthHref();          // GitHub asks for itself, and brings the reader back here
      });
      acts.push(back);
    } else if (gh === "authorised") {
      text.appendChild(fill("wr.server.kept", {login: mono(LOGIN)}));
      acts.push(revokeBtn);
    } else if (gh === "refused") {
      text.appendChild(ink(t("wr.server.refused")));
      acts.push(reauth, revokeBtn);
    } else {
      text.append(ink(t("wr.server.none")), document.createTextNode(SP + t("wr.server.none_how")));
      acts.push(reauth);
    }
    var opt = option(cur, document.createTextNode(t("wr.server")), text, acts);
    if (Date.now() < revokedUntil) opt.out.textContent = t("me.gh_revoked");
    revokeBtn.addEventListener("click", async function () {
      if (!A.twoStep(revokeBtn, t("me.gh_revoke_armed"))) return;
      opt.out.textContent = "";
      var r = await A.request("/api/me/github/revoke", null, {});
      if (!r.ok) { opt.out.textContent = A.refusal("wr.refused", r.data); return; }
      wstate = Object.assign({}, wstate, {github: "none"});
      revokedUntil = Date.now() + 2500;
      drawWriting();
      setTimeout(function () {
        var said = wbox.querySelector('.opt[data-opt="server"] .out');
        if (said && said.textContent === t("me.gh_revoked")) said.textContent = "";
      }, 2600);
      var again = wbox.querySelector('[data-key="wr-reauth"]');
      if (again) again.focus({preventScroll: true});
      askCanWrite();
    });
    opt.el.dataset.opt = "server";
    return opt.el;
  }

  function computerOption(item, labels) {
    var cur = !!(wstate && wstate.mode === "computer" && item.machine && item.machine === wstate.machine);
    var here = item.projects.some(function (p) { return p.slug === SLUG; });
    var text = document.createDocumentFragment(), can = false;
    if (!item.machine) {
      text.appendChild(document.createTextNode(item.version ? t("wr.computer.old", {v: item.version, need: NEED})
                                                            : t("wr.computer.old_unknown", {need: NEED})));
    } else if (item.git !== true) {
      text.appendChild(document.createTextNode(t("wr.computer.no_git")));
    } else {
      can = true;
      text.appendChild(document.createTextNode(t("wr.computer.how") + SP));
      text.appendChild(item.online ? document.createTextNode(t("wr.computer.ok"))
                                   : ink(item.last_seen ? t("wr.computer.off", {time: when(item.last_seen)}) : t("wr.computer.off_never")));
      // (for the current one the outcome under the list says it)
      if (!here && !cur) text.appendChild(document.createTextNode(SP + t("wr.computer.not_here", {project: PROJECT})));
    }
    var acts = [];
    if (!cur) {
      var b = A.button("btn", t("wr.choose"));
      b.dataset.key = "wr-choose:" + (item.machine || item.projects[0].slug + ":" + item.projects[0].credential);
      b.disabled = !can;
      acts.push(b);
    }
    var opt = option(cur, nameOf(item.label, item.machine, labels), text, acts);
    if (b) {
      b.addEventListener("click", async function () {
        if (!A.twoStep(b, t("wr.choose_armed", {name: item.label}))) return;
        opt.out.textContent = "";
        var r = await A.request("/api/me/writer", null, {machine: item.machine});
        if (!r.ok) { opt.out.textContent = A.refusal("wr.refused", r.data); return; }
        wstate = r.data;
        await load(true);
        await askCanWrite();
        var now = wbox.querySelector(".opt.cur");
        if (now) { now.tabIndex = -1; now.focus({preventScroll: true}); }
      });
    }
    return opt.el;
  }

  // The order of the other section (this project's computers as listed there), then the others.
  function ordered() {
    var order = {};
    ((my && my.credentials) || []).forEach(function (c, i) { if (c.kind === "computer") order[c.machine || ("cred:" + c.id)] = i; });
    function rank(x) {
      if (x.machine && order[x.machine] !== undefined) return order[x.machine];
      var here = x.projects.filter(function (p) { return p.slug === SLUG; })[0];
      if (here && order["cred:" + here.credential] !== undefined) return order["cred:" + here.credential];
      return 1e6;
    }
    return ((mine && mine.computers) || []).slice().sort(function (a, b) { return rank(a) - rank(b); });
  }

  function outcome() {
    var o = make("div", "outcome"), first = make("p"), second = null, act = null;
    o.setAttribute("aria-live", "polite");
    o.appendChild(first);
    if (!REPO) { first.textContent = t("wr.out.no_repo"); return o; }
    var cw = canWrite;
    if (!cw) {
      first.textContent = t("wr.out.unknown", {project: PROJECT});
      o.hidden = !canAsked;                         // nothing to say before the first answer
      return o;
    }
    var writer = cw.writer || {}, item = accountOf(writer.machine);
    var name = mono(writer.label || (item && item.label) || "");
    var vars = {project: PROJECT, login: mono(LOGIN), name: name};
    if (cw.can_write) {
      first.appendChild(fill(cw.writer ? "wr.out.computer" : "wr.out.server", vars));
      return o;
    }
    var why = cw.reason || "";
    first.appendChild(fill(A.MSG["wr.out." + why] ? "wr.out." + why : "wr.out.unknown", vars));
    if (A.MSG["wr.out." + why + "_how"]) second = make("p", "", t("wr.out." + why + "_how", {project: PROJECT}));
    if (why === "computer_not_here") act = inviteButton();
    if (second) o.appendChild(second);
    if (act) o.appendChild(act);
    return o;
  }

  function drawWriting() {
    if (!wbox) return;
    A.keepFocus(wbox, function () {
      wbox.textContent = "";
      var opts = make("div", "opts"), labels = labelCounts(), items = ordered();
      opts.appendChild(serverOption());
      items.forEach(function (x) { opts.appendChild(computerOption(x, labels)); });
      wbox.appendChild(opts);
      if (!items.length) {
        var link = make("a", "", t("wr.no_computers_link"));
        link.href = HERE + "/me/computers";
        var p = make("p", "dim wr-none");
        p.appendChild(fill("wr.no_computers", {link: link}));
        wbox.appendChild(p);
      }
      wbox.appendChild(outcome());
    });
  }

  function writingShown() { return !!(wsec && !wsec.hidden); }

  async function askCanWrite() {
    if (!REPO || !wbox) { drawWriting(); return; }
    var r = await A.request(API + "files/can-write");
    canAsked = true;
    canWrite = r.ok ? r.data : null;
    if (!A.isArmed(wbox)) drawWriting();
  }

  // ------------------------------------------------------------------ refreshing

  var failed = 0;
  async function load(force) {
    var got = await Promise.all([A.request(API + "my"), A.request("/api/me/computers"), A.request("/api/me/writer")]);
    if (!got.every(function (r) { return r.ok; })) {
      failed += 1;
      if (stale && failed >= 2) stale.hidden = false;
      return;
    }
    failed = 0;
    if (stale) stale.hidden = true;
    var now = JSON.stringify([got[0].data, got[1].data, got[2].data]);
    if (now === raw && !force) return;
    raw = now;
    my = got[0].data;
    mine = got[1].data;
    wstate = got[2].data;
    if (!A.isArmed(box)) drawComputers();
    if (!A.isArmed(wbox)) drawWriting();
  }

  drawComputers();
  drawWriting();
  if (writingShown()) askCanWrite();
  // The section opens in place (settings.js): the outcome is asked for then.
  if (wsec) {
    new MutationObserver(function () { if (writingShown()) askCanWrite(); }).observe(wsec, {attributes: true, attributeFilter: ["hidden"]});
  }
  setInterval(function () {
    if (document.querySelector("dialog.gone[open], dialog.panel[open]") || A.isArmed(box) || A.isArmed(wbox)) return;
    load(false);
    if (writingShown()) askCanWrite();
  }, 15000);
})();
