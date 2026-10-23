/* Reino Commerce · interacciones P0 (120–180 ms controles, sin scroll
   secuestrado, sin autoplay, foco visible, Escape cierra paneles). */
(function () {
  "use strict";

  // Menú móvil accesible
  var toggle = document.querySelector("[data-menu-toggle]");
  var nav = document.getElementById("mobile-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.classList.contains("open")) {
        nav.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
        toggle.focus();
      }
    });
  }

  // Galería de ficha: cambio de imagen principal
  document.querySelectorAll("[data-gallery-thumb]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var main = document.querySelector("[data-gallery-main]");
      if (!main) return;
      main.src = btn.getAttribute("data-src");
      main.alt = btn.getAttribute("data-alt") || main.alt;
      document.querySelectorAll("[data-gallery-thumb]").forEach(function (b) {
        b.setAttribute("aria-pressed", b === btn ? "true" : "false");
      });
    });
  });

  // LookLab: tarjetas de selección única (personalidad / ocasión)
  document.querySelectorAll("[data-choice-group]").forEach(function (group) {
    var input = group.querySelector("input[type=hidden]");
    group.querySelectorAll(".choice").forEach(function (btn) {
      btn.addEventListener("click", function () {
        group.querySelectorAll(".choice").forEach(function (b) {
          b.setAttribute("aria-pressed", "false");
        });
        btn.setAttribute("aria-pressed", "true");
        if (input) input.value = btn.getAttribute("data-value");
        var submit = group.closest("form") && group.closest("form").querySelector("[data-continue]");
        if (submit) submit.removeAttribute("disabled");
      });
    });
  });

  // Asesor: envío asíncrono con estado «consultando» honesto y cancelable
  var form = document.querySelector("[data-chat-form]");
  if (form) {
    var list = document.querySelector("[data-chat-list]");
    var status = document.querySelector("[data-chat-status]");
    var input = form.querySelector("input[name=message]");
    var controller = null;
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var text = (input.value || "").trim();
      if (!text) return;
      controller = new AbortController();
      var userBubble = document.createElement("div");
      userBubble.className = "chat__msg chat__msg--user";
      userBubble.textContent = text;
      list.appendChild(userBubble);
      input.value = "";
      if (status) { status.textContent = "Consultando el catálogo…"; }
      var cancel = form.querySelector("[data-chat-cancel]");
      if (cancel) { cancel.hidden = false; }
      fetch(form.action, {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": form.querySelector("[name=csrfmiddlewaretoken]").value
        },
        body: new URLSearchParams({ message: text }),
        signal: controller.signal
      }).then(function (r) { return r.text(); })
        .then(function (html) {
          var wrap = document.createElement("div");
          wrap.innerHTML = html;
          list.appendChild(wrap);
          if (status) { status.textContent = ""; }
          if (cancel) { cancel.hidden = true; }
          list.scrollTop = list.scrollHeight;
        })
        .catch(function (err) {
          if (status) {
            status.textContent = err && err.name === "AbortError"
              ? "Consulta cancelada. Tus selecciones siguen guardadas."
              : "No pude completar la consulta. Tus selecciones siguen guardadas.";
          }
          if (cancel) { cancel.hidden = true; }
        });
    });
    var cancelBtn = form.querySelector("[data-chat-cancel]");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", function () {
        if (controller) controller.abort();
      });
    }
    // Ejemplos rápidos
    document.querySelectorAll("[data-chat-example]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        input.value = btn.getAttribute("data-chat-example");
        form.dispatchEvent(new Event("submit", { cancelable: true }));
      });
    });
  }
})();
