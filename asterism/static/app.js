// Sends forms marked data-api to the JSON API: the answer's data-show field into the form's [data-out], else on to
// data-next, else to the address the answer's field named by data-goto names (/{value}), else the page again; a refusal in the
// form's [data-out], in the page's words for its code (the act named by data-refusal).
// All texts come from the page's message catalogue (body data-msg); this file holds none.
"use strict";
(function () {
  var A = window.Asterism;
  if (!A) return;

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
    var out = form.querySelector("[data-out]");
    var body = collect(form, submitter);
    var res = await post(form.dataset.api, body);
    if (!res.ok) { if (out) out.textContent = A.refusal(form.dataset.refusal || "form", res.data); return; }
    if (form.dataset.show && out) out.textContent = res.data[form.dataset.show] || "";
    else if (form.dataset.next) window.location.href = form.dataset.next;
    else if (form.dataset.goto) window.location.href = "/" + encodeURIComponent(res.data[form.dataset.goto] || "");
    else window.location.reload();
  });
})();
