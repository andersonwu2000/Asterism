// Sends forms marked data-api to the JSON API and saves switches marked data-toggle as they change.
// All texts come from the page's message catalogue (body data-msg); this file holds none.
"use strict";
(function () {
  var MSG = {};
  try { MSG = JSON.parse(document.body.dataset.msg || "{}"); } catch (err) { MSG = {}; }

  function errorText(code) {
    return MSG["error." + code] || (MSG["error.generic"] || "{code}").replace("{code}", code || "?");
  }

  async function post(url, body) {
    var r = await fetch(url, {method: "POST", credentials: "same-origin",
                              headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    var data = {};
    try { data = await r.json(); } catch (err) { data = {}; }
    return {ok: r.ok, data: data};
  }

  function collect(form, submitter) {
    var body = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.disabled || el.type === "submit" || el.tagName === "BUTTON") return;
      var value;
      if (el.type === "checkbox") value = el.checked;
      else if (el.hasAttribute("data-list")) value = el.value ? [el.value] : [];
      else if (el.value === "") return;
      else value = el.value;
      var into = el.getAttribute("data-in");
      if (into) { body[into] = body[into] || {}; body[into][el.name] = value; }
      else body[el.name] = value;
    });
    if (submitter && submitter.name) body[submitter.name] = submitter.value;
    return body;
  }

  document.addEventListener("submit", async function (ev) {
    var form = ev.target;
    if (!form.hasAttribute("data-api")) return;
    ev.preventDefault();
    if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) return;
    var submitter = ev.submitter || null;
    var out = form.querySelector("[data-out]");
    var res = await post(form.dataset.api, collect(form, submitter));
    if (!res.ok) { if (out) out.textContent = errorText(res.data.error); return; }
    var okText = submitter && submitter.value ? form.getAttribute("data-ok-" + submitter.value) : null;
    if (form.dataset.show && out) out.textContent = res.data[form.dataset.show] || "";
    else if (okText) { var p = document.createElement("p"); p.textContent = okText; form.replaceWith(p); }
    else if (form.dataset.next) window.location.href = form.dataset.next;
    else window.location.reload();
  });

  document.addEventListener("change", async function (ev) {
    var box = ev.target;
    if (!box.hasAttribute || !box.hasAttribute("data-toggle")) return;
    var body = {};
    body[box.name] = box.checked;
    var res = await post(box.getAttribute("data-toggle"), body);
    var out = box.closest("div") && box.closest("div").querySelector("[data-out]");
    if (!res.ok) box.checked = !box.checked;
    if (out) out.textContent = res.ok ? (MSG["done.saved"] || "") : errorText(res.data.error);
  });

  // "my agents": the button that makes an agent invitation link, and what it answers. Each click makes a
  // new link and replaces what the previous one showed.
  function el(tag, text, cls) {
    var x = document.createElement(tag);
    if (text != null) x.textContent = text;
    if (cls) x.className = cls;
    return x;
  }

  async function copy(text) {
    if (navigator.clipboard && window.isSecureContext) {
      try { await navigator.clipboard.writeText(text); return true; } catch (err) { /* fall back below */ }
    }
    var area = el("textarea", text);
    area.setAttribute("readonly", "");
    area.style.position = "fixed"; area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
    area.remove();
    return ok;
  }

  // A line with the text to copy and its copy button.
  function copyLine(text) {
    var line = el("div", null, "copy-line");
    var code = el("code", text);
    var button = el("button", MSG["invite.copy"] || "");
    button.type = "button";
    button.addEventListener("click", async function () {
      button.textContent = (await copy(text)) ? (MSG["invite.copied"] || "") : (MSG["invite.copy"] || "");
      setTimeout(function () { button.textContent = MSG["invite.copy"] || ""; }, 2000);
    });
    line.append(code, " ", button);
    return line;
  }

  var SYSTEMS = ["macos-linux", "windows"], PRODUCTS = ["claude-code", "codex"];
  var made = 0;

  function showInvite(box, data) {
    made += 1;
    box.replaceChildren();
    box.append(el("p", MSG["invite.say"] || ""), copyLine(data.say));
    var until = new Date(Date.now() + data.expires_in * 1000);
    var time = until.toLocaleTimeString(document.documentElement.lang || undefined, {hour: "2-digit", minute: "2-digit"});
    box.append(el("p", (MSG["invite.expires"] || "{time}").replace("{time}", time), "muted"));
    if (!data.program || !data.program.available) {
      box.append(el("p", MSG["invite.unavailable"] || "", "muted"));
      return;
    }
    box.append(el("p", MSG["invite.self"] || ""));
    SYSTEMS.forEach(function (system) {
      var group = el("fieldset");
      group.append(el("legend", MSG["invite.system." + system] || system));
      var lines = {};
      PRODUCTS.forEach(function (product, i) {
        var label = el("label");
        var radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "invite-product-" + system + "-" + made;
        radio.value = product;
        radio.checked = i === 0;
        radio.addEventListener("change", function () {
          PRODUCTS.forEach(function (p) { lines[p].hidden = p !== product; });
        });
        label.append(radio, " " + (MSG["invite.product." + product] || product) + " ");
        group.append(label);
      });
      PRODUCTS.forEach(function (product, i) {
        lines[product] = copyLine(data.commands[system][product]);
        lines[product].hidden = i !== 0;
        group.append(lines[product]);
      });
      box.append(group);
    });
  }

  var inviteButton = document.getElementById("invite-agent");
  if (inviteButton) {
    inviteButton.addEventListener("click", async function () {
      var out = inviteButton.parentElement.querySelector("[data-out]");
      var box = document.getElementById("invite-result");
      inviteButton.disabled = true;
      try {
        var res = await post(inviteButton.dataset.api, {});
        if (out) out.textContent = res.ok ? "" : errorText(res.data.error);
        if (res.ok) { showInvite(box, res.data); box.hidden = false; }
      } finally {
        inviteButton.disabled = false;
      }
    });
  }
})();
