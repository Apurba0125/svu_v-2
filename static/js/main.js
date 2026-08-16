/* ==========================================================================
   Swami Vivekananda University — front-end behaviour
   Vanilla JS, no dependencies, no inline handlers (keeps the CSP strict).
   Everything here is progressive enhancement: the site works without it.
   ========================================================================== */
(function () {
  "use strict";

  var $  = function (sel, ctx) { return (ctx || document).querySelector(sel); };
  var $$ = function (sel, ctx) {
    return Array.prototype.slice.call((ctx || document).querySelectorAll(sel));
  };

  var prefersReducedMotion = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;

  /* ----------------------------------------------------------------------
     1. Mobile navigation drawer
     ---------------------------------------------------------------------- */
  function initNavigation() {
    var nav = $("#site-nav");
    var toggle = $("#nav-toggle");
    var closeBtn = $("#nav-close");
    var scrim = $("#nav-scrim");
    if (!nav || !toggle) { return; }

    function openNav() {
      nav.classList.add("is-open");
      if (scrim) { scrim.classList.add("is-visible"); }
      document.body.classList.add("nav-open");
      toggle.setAttribute("aria-expanded", "true");
      var firstLink = $(".nav__link", nav);
      if (firstLink) { firstLink.focus(); }
    }

    function closeNav() {
      nav.classList.remove("is-open");
      if (scrim) { scrim.classList.remove("is-visible"); }
      document.body.classList.remove("nav-open");
      toggle.setAttribute("aria-expanded", "false");
    }

    toggle.addEventListener("click", function () {
      if (nav.classList.contains("is-open")) { closeNav(); } else { openNav(); }
    });
    if (closeBtn) { closeBtn.addEventListener("click", closeNav); }
    if (scrim) { scrim.addEventListener("click", closeNav); }

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.classList.contains("is-open")) {
        closeNav();
        toggle.focus();
      }
    });

    // Submenu behaviour: click-to-expand on touch/small screens,
    // pure CSS hover on desktop.
    $$(".nav__item--has-children", nav).forEach(function (item) {
      var link = $(".nav__link", item);
      if (!link) { return; }

      link.addEventListener("click", function (e) {
        var isMobile = window.matchMedia("(max-width: 991.98px)").matches;
        if (!isMobile) { return; }

        var submenu = $(".nav__submenu", item);
        if (!submenu) { return; }

        // First tap expands; the parent link only navigates once open.
        if (!item.classList.contains("is-open")) {
          e.preventDefault();
          $$(".nav__item--has-children.is-open", nav).forEach(function (other) {
            if (other !== item) {
              other.classList.remove("is-open");
              var l = $(".nav__link", other);
              if (l) { l.setAttribute("aria-expanded", "false"); }
            }
          });
          item.classList.add("is-open");
          link.setAttribute("aria-expanded", "true");
        } else if (!link.getAttribute("href") || link.getAttribute("href") === "#") {
          e.preventDefault();
          item.classList.remove("is-open");
          link.setAttribute("aria-expanded", "false");
        }
      });
    });

    // Reset drawer state when resizing up to desktop.
    var resizeTimer;
    window.addEventListener("resize", function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        if (window.innerWidth >= 992) {
          closeNav();
          $$(".nav__item.is-open", nav).forEach(function (i) {
            i.classList.remove("is-open");
          });
        }
      }, 150);
    });
  }

  /* ----------------------------------------------------------------------
     2. Hero carousel (transform based, with swipe + autoplay)
     ---------------------------------------------------------------------- */
  function initHero() {
    var hero = $("#hero");
    if (!hero) { return; }

    var track = $(".hero__track", hero);
    var slides = $$(".hero__slide", hero);
    var prev = $(".hero__arrow--prev", hero);
    var next = $(".hero__arrow--next", hero);
    var dotsWrap = $(".hero__dots", hero);
    if (!track || slides.length === 0) { return; }

    var index = 0;
    var timer = null;
    var interval = parseInt(hero.getAttribute("data-interval"), 10) || 6000;

    if (slides.length < 2) {
      if (prev) { prev.hidden = true; }
      if (next) { next.hidden = true; }
      if (dotsWrap) { dotsWrap.hidden = true; }
      return;
    }

    // Build the dots
    var dots = [];
    if (dotsWrap) {
      slides.forEach(function (_slide, i) {
        var b = document.createElement("button");
        b.type = "button";
        b.setAttribute("aria-label", "Go to slide " + (i + 1));
        b.addEventListener("click", function () { go(i); restart(); });
        dotsWrap.appendChild(b);
        dots.push(b);
      });
    }

    function go(i) {
      index = (i + slides.length) % slides.length;
      track.style.transform = "translateX(" + (-index * 100) + "%)";
      slides.forEach(function (s, n) {
        s.setAttribute("aria-hidden", n === index ? "false" : "true");
      });
      dots.forEach(function (d, n) {
        d.classList.toggle("is-active", n === index);
      });
    }

    function start() {
      if (prefersReducedMotion) { return; }
      timer = setInterval(function () { go(index + 1); }, interval);
    }
    function stop() { if (timer) { clearInterval(timer); timer = null; } }
    function restart() { stop(); start(); }

    if (prev) { prev.addEventListener("click", function () { go(index - 1); restart(); }); }
    if (next) { next.addEventListener("click", function () { go(index + 1); restart(); }); }

    hero.addEventListener("mouseenter", stop);
    hero.addEventListener("mouseleave", start);
    hero.addEventListener("focusin", stop);
    hero.addEventListener("focusout", start);

    // Pause when scrolled out of view / tab hidden — saves battery on phones.
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) { stop(); } else { start(); }
    });

    // Touch swipe
    var startX = 0, startY = 0, tracking = false;
    hero.addEventListener("touchstart", function (e) {
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
      tracking = true;
      stop();
    }, { passive: true });

    hero.addEventListener("touchend", function (e) {
      if (!tracking) { return; }
      tracking = false;
      var dx = e.changedTouches[0].clientX - startX;
      var dy = e.changedTouches[0].clientY - startY;
      // Ignore mostly-vertical gestures so page scrolling still works.
      if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy)) {
        go(dx < 0 ? index + 1 : index - 1);
      }
      start();
    }, { passive: true });

    hero.addEventListener("keydown", function (e) {
      if (e.key === "ArrowLeft") { go(index - 1); restart(); }
      if (e.key === "ArrowRight") { go(index + 1); restart(); }
    });

    go(0);
    start();
  }

  /* ----------------------------------------------------------------------
     3. Generic scroll-snap carousels (schools / events / testimonials)
     ---------------------------------------------------------------------- */
  function initCarousels() {
    $$(".carousel").forEach(function (carousel) {
      var track = $(".carousel__track", carousel);
      var items = $$(".carousel__item", track);
      var prev = $(".carousel__nav--prev", carousel);
      var next = $(".carousel__nav--next", carousel);
      var dotsWrap = $(".carousel__dots", carousel);
      if (!track || items.length === 0) { return; }

      function perView() {
        if (items.length < 2) { return 1; }
        var itemWidth = items[0].getBoundingClientRect().width;
        if (!itemWidth) { return 1; }
        return Math.max(1, Math.round(track.getBoundingClientRect().width / itemWidth));
      }

      function pageCount() {
        return Math.max(1, Math.ceil(items.length / perView()));
      }

      function currentPage() {
        var itemWidth = items[0].getBoundingClientRect().width + 18;
        if (!itemWidth) { return 0; }
        return Math.round(track.scrollLeft / (itemWidth * perView()));
      }

      function scrollToPage(page) {
        var itemWidth = items[0].getBoundingClientRect().width + 18;
        track.scrollTo({
          left: page * itemWidth * perView(),
          behavior: prefersReducedMotion ? "auto" : "smooth"
        });
      }

      var dots = [];
      function buildDots() {
        if (!dotsWrap) { return; }
        dotsWrap.innerHTML = "";
        dots = [];
        var total = pageCount();
        if (total < 2) { dotsWrap.hidden = true; return; }
        dotsWrap.hidden = false;
        for (var i = 0; i < total; i++) {
          (function (page) {
            var b = document.createElement("button");
            b.type = "button";
            b.setAttribute("aria-label", "Go to slide group " + (page + 1));
            b.addEventListener("click", function () { scrollToPage(page); });
            dotsWrap.appendChild(b);
            dots.push(b);
          })(i);
        }
      }

      function syncState() {
        var page = currentPage();
        dots.forEach(function (d, i) { d.classList.toggle("is-active", i === page); });
        if (prev) { prev.disabled = track.scrollLeft <= 4; }
        if (next) {
          next.disabled = track.scrollLeft + track.clientWidth >= track.scrollWidth - 4;
        }
      }

      if (prev) {
        prev.addEventListener("click", function () { scrollToPage(Math.max(0, currentPage() - 1)); });
      }
      if (next) {
        next.addEventListener("click", function () {
          scrollToPage(Math.min(pageCount() - 1, currentPage() + 1));
        });
      }

      var scrollTimer;
      track.addEventListener("scroll", function () {
        clearTimeout(scrollTimer);
        scrollTimer = setTimeout(syncState, 90);
      }, { passive: true });

      var resizeTimer;
      window.addEventListener("resize", function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () { buildDots(); syncState(); }, 180);
      });

      buildDots();
      syncState();
    });
  }

  /* ----------------------------------------------------------------------
     4. Back-to-top + sticky nav
     ---------------------------------------------------------------------- */
  function initScrollWidgets() {
    var toTop = $("#to-top");
    var nav = $("#site-nav");
    var navOffset = nav ? nav.offsetTop : 0;
    var ticking = false;

    function onScroll() {
      var y = window.pageYOffset || document.documentElement.scrollTop;
      if (toTop) { toTop.classList.toggle("is-visible", y > 400); }
      if (nav && window.innerWidth >= 992) {
        nav.classList.toggle("is-stuck", y > navOffset);
      }
      ticking = false;
    }

    window.addEventListener("scroll", function () {
      if (!ticking) {
        window.requestAnimationFrame(onScroll);
        ticking = true;
      }
    }, { passive: true });

    if (toTop) {
      toTop.addEventListener("click", function () {
        window.scrollTo({ top: 0, behavior: prefersReducedMotion ? "auto" : "smooth" });
      });
    }
    onScroll();
  }

  /* ----------------------------------------------------------------------
     5. YouTube click-to-load facade (privacy + performance)
     ---------------------------------------------------------------------- */
  function initVideoFacades() {
    $$(".video-facade").forEach(function (facade) {
      facade.addEventListener("click", function () {
        var wrap = facade.parentNode;
        var src = facade.getAttribute("data-src");
        var title = facade.getAttribute("data-title") || "Video";
        if (!src) { return; }

        var iframe = document.createElement("iframe");
        iframe.setAttribute("src", src + "&autoplay=1");
        iframe.setAttribute("title", title);
        iframe.setAttribute("loading", "lazy");
        iframe.setAttribute("allow",
          "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture");
        iframe.setAttribute("referrerpolicy", "strict-origin-when-cross-origin");
        iframe.setAttribute("allowfullscreen", "");
        wrap.replaceChild(iframe, facade);
      });
    });
  }

  /* ----------------------------------------------------------------------
     6. FAQ accordion
     ---------------------------------------------------------------------- */
  function initAccordions() {
    $$(".faq-item__q").forEach(function (button) {
      button.addEventListener("click", function () {
        var expanded = button.getAttribute("aria-expanded") === "true";
        var panel = document.getElementById(button.getAttribute("aria-controls"));
        button.setAttribute("aria-expanded", expanded ? "false" : "true");
        if (panel) { panel.hidden = expanded; }
      });
    });
  }

  /* ----------------------------------------------------------------------
     7. Enquiry form: dependent dropdowns, CAPTCHA refresh, AJAX submit
     ---------------------------------------------------------------------- */
  function getCsrfToken(form) {
    var input = form ? form.querySelector("[name=csrfmiddlewaretoken]") : null;
    return input ? input.value : "";
  }

  function setFieldError(form, fieldName, message) {
    var field = form.querySelector("[name='" + fieldName + "']");
    var wrapper = field ? field.closest(".form-field") : null;
    if (!wrapper) { return; }
    wrapper.classList.add("has-error");
    var existing = wrapper.querySelector(".field-error");
    if (!existing) {
      existing = document.createElement("span");
      existing.className = "field-error";
      wrapper.appendChild(existing);
    }
    existing.textContent = message;
  }

  function clearErrors(form) {
    $$(".form-field.has-error", form).forEach(function (w) {
      w.classList.remove("has-error");
    });
    $$(".field-error", form).forEach(function (e) { e.remove(); });
    var status = $(".form-status", form);
    if (status) { status.innerHTML = ""; }
  }

  function showStatus(form, type, message) {
    var status = $(".form-status", form);
    if (!status) { return; }
    status.innerHTML = "";
    var box = document.createElement("div");
    box.className = "alert alert--" + type;
    box.setAttribute("role", type === "error" ? "alert" : "status");
    box.textContent = message;
    status.appendChild(box);
    status.scrollIntoView({ behavior: prefersReducedMotion ? "auto" : "smooth", block: "center" });
  }

  function populateSelect(select, results, placeholder) {
    if (!select) { return; }
    var previous = select.value;
    select.innerHTML = "";
    var blank = document.createElement("option");
    blank.value = "";
    blank.textContent = placeholder;
    select.appendChild(blank);
    results.forEach(function (row) {
      var opt = document.createElement("option");
      opt.value = row.id;
      // textContent (never innerHTML) — server data is inserted as text only.
      opt.textContent = row.name;
      select.appendChild(opt);
    });
    if (previous) { select.value = previous; }
  }

  function initDependentSelect(form, parentName, childName, endpoint, param, placeholder) {
    var parent = form.querySelector("[name='" + parentName + "']");
    var child = form.querySelector("[name='" + childName + "']");
    if (!parent || !child || !endpoint) { return; }

    parent.addEventListener("change", function () {
      if (!parent.value) {
        populateSelect(child, [], placeholder);
        return;
      }
      child.disabled = true;
      fetch(endpoint + "?" + param + "=" + encodeURIComponent(parent.value), {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin"
      })
        .then(function (r) { return r.ok ? r.json() : { results: [] }; })
        .then(function (data) { populateSelect(child, data.results || [], placeholder); })
        .catch(function () { /* keep the full list on failure */ })
        .then(function () { child.disabled = false; });
    });
  }

  function initCaptchaRefresh(form) {
    var button = $(".captcha-refresh", form);
    var image = $(".captcha-image", form);
    if (!button || !image) { return; }
    var endpoint = button.getAttribute("data-endpoint");
    if (!endpoint) { return; }

    button.addEventListener("click", function () {
      button.disabled = true;
      fetch(endpoint, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin"
      })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (data && data.image) { image.setAttribute("src", data.image); }
          var input = form.querySelector("[name='captcha']");
          if (input) { input.value = ""; input.focus(); }
        })
        .catch(function () { /* silent — the user can reload the page */ })
        .then(function () { button.disabled = false; });
    });
  }

  function initEnquiryForms() {
    $$("form[data-enquiry-form]").forEach(function (form) {
      initCaptchaRefresh(form);
      initDependentSelect(
        form, "state", "city",
        form.getAttribute("data-cities-url"), "state", "Select City *"
      );
      initDependentSelect(
        form, "program", "course",
        form.getAttribute("data-courses-url"), "program", "Select Course *"
      );

      // Digits only in the mobile field.
      var mobile = form.querySelector("[name='mobile']");
      if (mobile) {
        mobile.addEventListener("input", function () {
          mobile.value = mobile.value.replace(/\D/g, "").slice(0, 10);
        });
      }

      form.addEventListener("submit", function (e) {
        if (!window.fetch || !form.getAttribute("data-ajax")) { return; }
        e.preventDefault();

        var submitBtn = form.querySelector("[type=submit]");
        var originalLabel = submitBtn ? submitBtn.textContent : "";
        clearErrors(form);
        if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Submitting…"; }

        fetch(form.getAttribute("action"), {
          method: "POST",
          body: new FormData(form),
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": getCsrfToken(form)
          },
          credentials: "same-origin"
        })
          .then(function (response) {
            return response.json().then(function (data) {
              return { status: response.status, data: data };
            });
          })
          .then(function (result) {
            var data = result.data || {};
            if (data.ok) {
              form.reset();
              showStatus(form, "success", data.message || "Thank you! Your enquiry has been received.");
              var img = $(".captcha-image", form);
              var refresh = $(".captcha-refresh", form);
              if (img && refresh) { refresh.click(); }
              return;
            }

            if (data.captcha_image) {
              var image = $(".captcha-image", form);
              if (image) { image.setAttribute("src", data.captcha_image); }
            }

            if (data.errors) {
              var first = null;
              Object.keys(data.errors).forEach(function (field) {
                var messages = data.errors[field];
                var text = (messages && messages[0] && messages[0].message) || "Invalid value.";
                if (field === "__all__" || field === "form_ts" || field === "website") {
                  showStatus(form, "error", text);
                } else {
                  setFieldError(form, field, text);
                  if (!first) { first = form.querySelector("[name='" + field + "']"); }
                }
              });
              if (first) { first.focus(); }
              else { showStatus(form, "error", "Please correct the highlighted fields."); }
            } else {
              showStatus(form, "error", data.error || "Sorry, something went wrong. Please try again.");
            }
          })
          .catch(function () {
            // Network/JSON failure — fall back to a normal page submit.
            form.removeAttribute("data-ajax");
            form.submit();
          })
          .then(function () {
            if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = originalLabel; }
          });
      });
    });
  }

  /* ----------------------------------------------------------------------
     8. Lazy images without layout shift
     ---------------------------------------------------------------------- */
  function initLazyImages() {
    $$("img[data-src]").forEach(function (img) {
      if ("IntersectionObserver" in window) {
        var observer = new IntersectionObserver(function (entries, obs) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) {
              entry.target.src = entry.target.getAttribute("data-src");
              entry.target.removeAttribute("data-src");
              obs.unobserve(entry.target);
            }
          });
        }, { rootMargin: "200px" });
        observer.observe(img);
      } else {
        img.src = img.getAttribute("data-src");
      }
    });
  }

  /* ----------------------------------------------------------------------
     Bootstrap
     ---------------------------------------------------------------------- */
  function init() {
    initNavigation();
    initHero();
    initCarousels();
    initScrollWidgets();
    initVideoFacades();
    initAccordions();
    initEnquiryForms();
    initLazyImages();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
