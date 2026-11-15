// Sends forms marked data-api to the JSON API and saves switches marked data-toggle as they change. A form with
// data-confirm confirms in place, in two steps: the first press arms its button, which then says what will happen.
// A form with data-gone (an act that cannot be undone) opens the floating confirmation, where data-gone-name is typed.
// All texts come from the page's message catalogue (body data-msg); this file holds none.
"use strict";
(function () {
  var A = window.Asterism;
  if (!A) return;
  var MSG = A.MSG, make = A.make;

  function post(url, body) { return A.request(url, null, body); }

  function collect(form, submitter) {
    var body = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.disabled || el.type === "submit" || el.tagName === "BUTTON") return;
      var value;
      if (el.type === "checkbox") value = el.checked;
      else if (el.hasAttribute("data-list")) value = el.value ? [el.value] : [];
      else if (el.value === "") return;
      else value = el.value;
      body[el.name] = value;
    });
    if (submitter && submitter.name) body[submitter.name] = submitter.value;
    return body;
  }

  document.addEventListener("submit", async function (ev) {
    var form = ev.target;
    if (!form.hasAttribute("data-api")) return;
    ev.preventDefault();
    var submitter = ev.submitter || form.querySelector("button:not([type=button])");
    if (form.dataset.gone) {            // cannot be undone: the floating confirmation, the name typed
      var kind = form.dataset.gone, name = form.dataset.goneName;
      A.gone({title: A.t("gone." + kind + ".title", {name: name}), text: A.t("gone." + kind + ".text", {name: name}),
              name: name, button: A.t("gone." + (kind === "revoke" ? "revoke" : "member") + ".button"), opener: submitter,
              run: function () { return post(form.dataset.api, {}); },
              done: function () { window.location.reload(); }});
      return;
    }
    if (form.dataset.confirm && submitter && !A.twoStep(submitter, form.dataset.confirm)) return;
    var out = form.querySelector("[data-out]");
    var res = await post(form.dataset.api, collect(form, submitter));
    if (!res.ok) { if (out) out.textContent = A.errorText(res.data.error); return; }
    if (form.dataset.show && out) out.textContent = res.data[form.dataset.show] || "";
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
    if (out) out.textContent = res.ok ? (MSG["done.saved"] || "") : A.errorText(res.data.error);
  });

  // "my agents": the button that makes an agent invitation link, and what it answers. Each click makes a
  // new link and replaces what the previous one showed.
  var copy = A.copy;

  // A line with the text to copy and its copy button.
  function copyLine(text) {
    var line = make("div", "copy-line");
    var code = make("code", null, text);
    var button = A.button("btn", MSG["invite.copy"] || "", async function () {
      // A blocker may refuse the write: then say so; the text beside stays selectable to copy by hand.
      var ok = false;
      try { ok = await copy(text); } catch (err) { ok = false; }
      button.textContent = ok ? (MSG["invite.copied"] || "") : (MSG["invite.copy_failed"] || "");
      setTimeout(function () { button.textContent = MSG["invite.copy"] || ""; }, ok ? 2000 : 5000);
    });
    button.setAttribute("aria-live", "polite");
    line.append(code, button);
    return line;
  }

  var SYSTEMS = ["macos-linux", "windows"], PRODUCTS = ["claude-code", "codex"];
  var made = 0;

  function showInvite(box, data) {
    made += 1;
    box.replaceChildren();
    box.append(make("p", null, MSG["invite.say"] || ""), copyLine(data.say));
    var until = new Date(Date.now() + data.expires_in * 1000);
    var time = until.toLocaleTimeString(document.documentElement.lang || undefined, {hour: "2-digit", minute: "2-digit"});
    box.append(make("p", "muted", (MSG["invite.expires"] || "{time}").replace("{time}", time)));
    if (!data.program || !data.program.available) {
      box.append(make("p", "muted", MSG["invite.unavailable"] || ""));
      return;
    }
    box.append(make("p", null, MSG["invite.self"] || ""));
    SYSTEMS.forEach(function (system) {
      var group = make("fieldset");
      group.append(make("legend", null, MSG["invite.system." + system] || system));
      var choices = make("div"), lines = {};
      PRODUCTS.forEach(function (product, i) {
        var label = make("label");
        var radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "invite-product-" + system + "-" + made;
        radio.value = product;
        radio.checked = i === 0;
        radio.addEventListener("change", function () {
          PRODUCTS.forEach(function (p) { lines[p].hidden = p !== product; });
        });
        label.append(radio, " " + (MSG["invite.product." + product] || product));
        choices.append(label);
      });
      group.append(choices);
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
        if (out) out.textContent = res.ok ? "" : A.errorText(res.data.error);
        if (res.ok) { showInvite(box, res.data); box.hidden = false; }
      } finally {
        inviteButton.disabled = false;
      }
    });
  }
})();
