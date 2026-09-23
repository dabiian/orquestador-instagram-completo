/* Instagram UI is loaded as a small extension so the existing SEO dashboard stays isolated. */
(async () => {
  await import("/dashboard/app.core.js");
  await import("/dashboard/instagram.js");
})();
