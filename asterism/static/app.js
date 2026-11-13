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
})();
