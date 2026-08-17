// Vista Historial: aplicaciones enviadas desde knowledge.json.
window.HistoryView = (function () {
  let root = null;
  let loaded = false;

  function init() {
    root = qs('#view-history');
    root.innerHTML =
      '<div class="view-head"><h1>Historial</h1><p>Todas las aplicaciones que has enviado.</p></div>' +
      '<div class="hist-controls">' +
        '<input class="input" id="h-company" placeholder="Filtrar por empresa…">' +
        '<div class="segmented" id="h-limit">' +
          '<button data-v="50" class="active">Recientes</button>' +
          '<button data-v="0">Todas</button>' +
        '</div>' +
      '</div>' +
      '<div id="h-table"></div>';
    let deb = null;
    qs('#h-company').addEventListener('input', () => {
      clearTimeout(deb);
      deb = setTimeout(refresh, 300);
    });
    qsa('#h-limit button').forEach(b => b.addEventListener('click', () => {
      qsa('#h-limit button').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      refresh();
    }));
  }

  async function refresh() {
    const company = qs('#h-company').value.trim() || null;
    const limit = Number(qs('#h-limit button.active').dataset.v);
    const r = await api('get_history', limit, company);
    const box = qs('#h-table');
    if (!r.ok) { box.innerHTML = '<div class="empty-state"><p>' + esc(r.error) + '</p></div>'; return; }
    const rows = r.data || [];
    if (!rows.length) {
      box.innerHTML =
        '<div class="empty-state"><div class="ic">📬</div>' +
        '<p>' + (company ? 'Nada para ese filtro.' : 'Aun no has enviado aplicaciones.<br>Tu historial aparecera aqui.') + '</p></div>';
      return;
    }
    const trs = rows.map(a =>
      '<tr>' +
        '<td class="mono muted" style="font-size:.76rem;white-space:nowrap">' + esc(a.date) + '</td>' +
        '<td><div class="job-cell"><span class="t">' + esc(a.job_title) + '</span><span class="c">' + esc(a.company) + '</span></div></td>' +
        '<td class="mono" style="font-size:.76rem;color:var(--info)">' + esc(a.recruiter_email) + '</td>' +
        '<td>' + (a.mode === 'test' ? '<span class="pill warn">TEST</span>' : '<span class="pill ok">RUN</span>') + '</td>' +
        '<td>' + (a.post_url ? '<button class="link-btn h-post" data-url="' + esc(a.post_url) + '">Ver post</button>' : '<span class="muted">—</span>') + '</td>' +
        '<td>' + (a.cv_path ? '<button class="link-btn h-cv" data-p="' + esc(a.cv_path) + '">📎 CV</button>' : '<span class="muted">—</span>') + '</td>' +
      '</tr>').join('');
    box.innerHTML =
      '<div class="table-wrap fade-up"><table><thead><tr>' +
      '<th>Fecha</th><th>Oferta</th><th>Destinatario</th><th>Modo</th><th>Post</th><th>CV</th>' +
      '</tr></thead><tbody>' + trs + '</tbody></table></div>';
    qsa('.h-post').forEach(b => b.addEventListener('click', () => api('open_url', b.dataset.url)));
    qsa('.h-cv').forEach(b => b.addEventListener('click', async () => {
      const r2 = await api('open_cv', b.dataset.p);
      if (!r2.ok) toast(r2.error, 'warn');
    }));
    loaded = true;
  }

  return { init, refresh };
})();
