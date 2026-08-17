// Arranque y navegacion de la app.
(async function () {
  const res = await api('get_state');
  if (!res.ok) {
    qs('#loading').innerHTML = '<div class="logo-icon">J</div>' +
      '<p style="color:var(--error);max-width:420px;text-align:center">' + esc(res.error) + '</p>';
    return;
  }
  window.appState = res.data;
  qs('#version').textContent = res.data.version || '?';

  const ob = res.data.onboarding || {};
  const complete = ob.has_key && ob.has_cv && ob.has_profile && ob.has_smtp &&
    ob.has_session && ob.has_queries;

  qs('#loading').classList.add('hidden');
  if (!complete) {
    Onboarding.start(res.data);
  } else {
    showApp();
  }

  // updates: chequeo silencioso al arrancar
  api('check_updates').then(r => {
    if (r.ok && r.data && r.data.update_available) {
      window.latestUpdate = r.data;
      qs('#update-pill').classList.remove('hidden');
      qs('#update-pill').textContent = '✦ Actualizar a ' + r.data.latest;
    }
  });
  qs('#update-pill').addEventListener('click', () => Settings.promptUpdate());
})();

function showApp() {
  qs('#onboarding').classList.add('hidden');
  qs('#app').classList.remove('hidden');
  RunView.init();
  HistoryView.init();
  Settings.init();
  qsa('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => switchView(btn.dataset.view));
  });
}

function switchView(name) {
  qsa('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.view === name));
  qsa('.view').forEach(v => v.classList.add('hidden'));
  qs('#view-' + name).classList.remove('hidden');
  if (name === 'history') HistoryView.refresh();
  if (name === 'settings') Settings.refresh();
}
