(() => {
  const BASE = "/SchemaRouter/";
  const KO = BASE + "ko/";

  function targetFor(lang) {
    const path = window.location.pathname;
    const suffix = window.location.search + window.location.hash;
    if (lang === "ko") {
      if (path.startsWith(KO)) return path + suffix;
      const relative = path.startsWith(BASE) ? path.slice(BASE.length) : "";
      return KO + relative + suffix;
    }
    if (path.startsWith(KO)) return BASE + path.slice(KO.length) + suffix;
    return path + suffix;
  }

  async function navigateToCounterpart(lang) {
    const target = targetFor(lang);
    try {
      const response = await fetch(target, { method: "HEAD", credentials: "same-origin" });
      if (response.ok) {
        window.location.assign(target);
        return;
      }
    } catch (_) {
      // Network errors fall through to the stable language root.
    }
    window.location.assign((lang === "ko" ? KO : BASE) + window.location.search);
  }

  document.addEventListener("click", (event) => {
    const anchor = event.target.closest("a[hreflang]");
    if (!anchor) return;
    const lang = anchor.getAttribute("hreflang");
    if (lang !== "en" && lang !== "ko") return;
    event.preventDefault();
    void navigateToCounterpart(lang);
  });
})();
