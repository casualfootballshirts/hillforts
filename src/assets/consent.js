(function () {
  const banner = document.getElementById("cookie-banner");
  if (!banner) return;
  const accept = document.getElementById("cookie-accept");
  const reject = document.getElementById("cookie-reject");
  if (!accept || !reject) return;

  const key = banner.getAttribute("data-consent-key") || "hillforts_consent";
  const measurementId = banner.getAttribute("data-measurement-id") || "";

  function read() {
    try {
      return window.localStorage.getItem(key);
    } catch (err) {
      return null;
    }
  }

  function store(value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (err) {
      /* The choice still applies for this page view. */
    }
  }

  function callGtag() {
    if (typeof window.gtag === "function") {
      window.gtag.apply(window, arguments);
    }
  }

  function clearAnalyticsCookies() {
    const host = window.location.hostname;
    const domains = [""];
    if (host) {
      domains.push(host, "." + host);
      const parts = host.split(".");
      if (parts.length > 1) domains.push("." + parts.slice(-2).join("."));
    }
    const secure = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie.split(";").forEach(function (item) {
      const name = item.split("=")[0].trim();
      if (name !== "_ga" && name.indexOf("_ga_") !== 0) return;
      domains.forEach(function (domain) {
        let cookie = name + "=; Max-Age=0; path=/" + secure;
        if (domain) cookie += "; domain=" + domain;
        document.cookie = cookie;
      });
    });
  }

  function syncPadding() {
    if (banner.hidden) {
      document.body.style.paddingBottom = "";
      document.documentElement.style.scrollPaddingBottom = "";
      return;
    }
    const height = banner.offsetHeight + "px";
    document.body.style.paddingBottom = height;
    document.documentElement.style.scrollPaddingBottom = height;
  }

  function show(moveFocus) {
    banner.hidden = false;
    syncPadding();
    if (moveFocus) banner.focus();
  }

  function hide() {
    banner.hidden = true;
    syncPadding();
  }

  function grantAnalytics() {
    callGtag("consent", "update", { analytics_storage: "granted" });
  }

  function denyAnalytics() {
    callGtag("consent", "update", {
      analytics_storage: "denied",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
    });
    clearAnalyticsCookies();
    window.setTimeout(clearAnalyticsCookies, 500);
  }

  accept.addEventListener("click", function () {
    const previous = read();
    store("accepted");
    grantAnalytics();
    if (previous !== "accepted" && measurementId) {
      callGtag("config", measurementId);
    }
    hide();
  });

  reject.addEventListener("click", function () {
    store("rejected");
    denyAnalytics();
    hide();
  });

  document.querySelectorAll("[data-cookie-settings]").forEach(function (button) {
    button.addEventListener("click", function () {
      show(true);
    });
  });

  window.addEventListener("resize", syncPadding);

  const choice = read();
  if (choice !== "accepted" && choice !== "rejected") show(false);
})();
