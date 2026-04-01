(function () {
  const root = document.documentElement;
  const stored = localStorage.getItem('authentiq:theme');
  const initial = stored === 'light' ? 'light' : 'dark';
  root.setAttribute('data-theme', initial);

  document.addEventListener('DOMContentLoaded', function () {
    const btn = document.getElementById('themeToggle');
    if (!btn) return;
    btn.addEventListener('click', function () {
      const current = root.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      localStorage.setItem('authentiq:theme', next);
      btn.textContent = next === 'dark' ? '☀ Light' : '🌙 Dark';
    });
  });
})();
