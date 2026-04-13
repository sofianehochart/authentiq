(function () {
  var banner = document.getElementById("premium-upsell-banner");
  if (!banner) return;

  var dismissBtn = banner.querySelector("[data-dismiss-premium-upsell]");
  if (!dismissBtn) return;

  dismissBtn.addEventListener("click", function () {
    fetch("/home/dismiss-premium-upsell", {
      method: "POST",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    })
      .then(function () {
        banner.style.display = "none";
      })
      .catch(function () {
        banner.style.display = "none";
      });
  });
})();
