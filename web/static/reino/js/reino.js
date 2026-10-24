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

  // Revelación LookLab: subtotal que SIGUE la selección (auditoría §4).
  // El backend recalcula siempre; este cálculo es solo espejo visible.
  var revealForm = document.querySelector("[data-reveal-form]");
  if (revealForm) {
    var totalEl = revealForm.querySelector("[data-reveal-total]");
    var countEl = revealForm.querySelector("[data-reveal-count]");
    var fmtMoney = function (n) {
      return "$" + n.toFixed(2);
    };
    var recalc = function () {
      var total = 0, count = 0;
      revealForm.querySelectorAll("[data-reveal-check]:checked").forEach(function (box) {
        total += parseFloat(box.getAttribute("data-price") || "0");
        count += 1;
      });
      revealForm.querySelectorAll("[data-price-select]").forEach(function (sel) {
        var opt = sel.options[sel.selectedIndex];
        if (opt && opt.value) {
          total += parseFloat(opt.getAttribute("data-price") || "0");
          count += 1;
        }
      });
      if (totalEl) totalEl.textContent = fmtMoney(total);
      if (countEl) countEl.textContent = count === 1 ? "1 pieza" : count + " piezas";
    };
    revealForm.addEventListener("change", recalc);
    recalc();
  }

  // Ficha de producto: el precio anunciado sigue a la variante elegida
  // (radios de talla o selector); coincide con lo que entra al carrito.
  var priceEl = document.querySelector("[data-variant-price]");
  var variantSelect = document.querySelector("[data-variant-picker]");
  if (priceEl && variantSelect) {
    variantSelect.addEventListener("change", function () {
      var opt = variantSelect.options[variantSelect.selectedIndex];
      if (opt) priceEl.textContent = "$" + (opt.getAttribute("data-price") || "");
    });
  }
  var buyForm = document.getElementById("buy-form");
  if (priceEl && buyForm) {
    buyForm.addEventListener("change", function (e) {
      if (e.target && e.target.name === "variant") {
        priceEl.textContent = "$" + (e.target.getAttribute("data-price") || "");
      }
    });
  }
})();

/* === Revisión 2: control de movimiento y estados === */
(function () {
  "use strict";
/* Menú móvil */
  var toggle = document.querySelector("[data-menu-toggle]");
  if (toggle) {
    var nav = document.getElementById(toggle.getAttribute("aria-controls"));
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

  /* Control «Reducir movimiento» persistente (§10) */
  var motion = document.querySelector("[data-motion-toggle]");
  var stored = null;
  try { stored = window.localStorage.getItem("reino_rm"); } catch (e) {}
  if (stored === "1" || (stored === null &&
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches)) {
    document.documentElement.classList.add("rm");
    if (motion) motion.setAttribute("aria-pressed", "true");
  }
  if (motion) {
    motion.addEventListener("click", function () {
      var on = document.documentElement.classList.toggle("rm");
      motion.setAttribute("aria-pressed", on ? "true" : "false");
      try { window.localStorage.setItem("reino_rm", on ? "1" : "0"); } catch (e) {}
    });
  }

  /* Detener animaciones fuera de pantalla / pestaña oculta (§10) */
  if ("IntersectionObserver" in window) {
    var animated = document.querySelectorAll(".stopmotion--loop");
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        en.target.style.animationPlayState = en.isIntersecting ? "running" : "paused";
      });
    });
    animated.forEach(function (el) { io.observe(el); });
    document.addEventListener("visibilitychange", function () {
      var state = document.hidden ? "paused" : "running";
      animated.forEach(function (el) { el.style.animationPlayState = state; });
    });
  }

  /* Botones con estado pendiente real: solo confirman éxito tras el servidor.
     Aquí solo marcamos «enviando» para feedback inmediato del clic. */
  document.querySelectorAll("form[data-busy]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var btn = form.querySelector("button[type=submit]");
      if (btn && !btn.disabled) {
        btn.dataset.label = btn.textContent;
        btn.textContent = "Procesando…";
        btn.setAttribute("aria-busy", "true");
      }
    });
  });
})();
