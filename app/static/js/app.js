const THEME_KEY = "neurolearn.theme";

function setTheme(theme) {
  document.body.dataset.theme = theme;
  localStorage.setItem(THEME_KEY, theme);
}

function initThemeToggle() {
  const saved = localStorage.getItem(THEME_KEY) || "light";
  setTheme(saved);

  const toggle = document.getElementById("theme-toggle");
  if (!toggle) return;
  toggle.addEventListener("click", () => {
    const current = document.body.dataset.theme || "light";
    setTheme(current === "light" ? "dark" : "light");
  });
}

window.addEventListener("DOMContentLoaded", initThemeToggle);
