// Sends forms marked data-api to the JSON API: the answer's data-show field into the form's [data-out], else on to
// data-next, else the page again; a refusal in the form's [data-out].
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
    var res = await post(form.dataset.api, collect(form, submitter));
    if (!res.ok) { if (out) out.textContent = A.errorText(res.data.error); return; }
    if (form.dataset.show && out) out.textContent = res.data[form.dataset.show] || "";
    else if (form.dataset.next) window.location.href = form.dataset.next;
    else window.location.reload();
  });
})();
