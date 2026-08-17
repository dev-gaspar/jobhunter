// Vista Buscar: controles -> progreso -> tabla de ofertas -> aplicar con preview.
window.RunView = (function () {
  let root = null;
  let timeFilter = '24h';
  let testMode = false;
  let offers = [];
  let queue = [];        // ids seleccionados pendientes
  let current = null;    // id en preview
  let sendAll = false;
  let counters = { sent: 0, skipped: 0, errors: 0, total: 0 };
  let searching = false;

  function init() {
    root = qs('#view-run');
    renderIdle();
    bus.on('phase', onPhase);
    bus.on('progress', onProgress);
    bus.on('decision', onDecision);
    bus.on('search_done', onSearchDone);
    bus.on('search_error', onSearchError);
    bus.on('apply_progress', onApplyProgress);
    bus.on('preview_ready', onPreviewReady);
    bus.on('prepare_error', onPrepareError);
    bus.on('send_result', onSendResult);
  }

  // ── pantalla inicial ──
  function renderIdle() {
    const email = (window.appState && window.appState.smtp_email) || '';
    root.innerHTML =
      '<div class="view-head fade-up"><h1>Buscar ofertas</h1>' +
      '<p>Escanea LinkedIn, filtra con IA y aplica con un CV hecho a medida para cada oferta.</p></div>' +
      '<div class="card run-controls fade-up">' +
        '<div class="top-row">' +
          '<div class="segmented" id="tf">' +
            '<button data-v="24h" class="active">Ultimas 24h</button>' +
            '<button data-v="week">Esta semana</button>' +
            '<button data-v="month">Este mes</button>' +
          '</div>' +
          '<div class="spacer" style="flex:1"></div>' +
          '<button class="btn btn-primary btn-lg" id="go">Buscar ofertas</button>' +
        '</div>' +
        '<div class="test-row">' +
          '<label class="switch"><input type="checkbox" id="test-toggle"><span class="track"></span></label>' +
          '<span class="secondary" style="font-size:.84rem">Modo prueba — los emails llegan a tu correo, no al reclutador</span>' +
          '<input class="input hidden" id="test-email" type="email" placeholder="tu@gmail.com" value="' + esc(email) + '">' +
        '</div>' +
      '</div>' +
      '<div id="run-stage"></div>';

    qsa('#tf button').forEach(b => b.addEventListener('click', () => {
      qsa('#tf button').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      timeFilter = b.dataset.v;
    }));
    qs('#test-toggle').addEventListener('change', e => {
      testMode = e.target.checked;
      qs('#test-email').classList.toggle('hidden', !testMode);
    });
    qs('#go').addEventListener('click', startSearch);
  }

  async function startSearch() {
    const testEmail = testMode ? qs('#test-email').value.trim() : null;
    if (testMode && !/@/.test(testEmail || '')) { toast('Escribe el correo para el modo prueba', 'warn'); return; }
    if (window.appState && !window.appState.has_session) {
      toast('Conecta LinkedIn en Ajustes antes de buscar', 'warn', 6000);
      return;
    }
    searching = true;
    offers = []; queue = []; sendAll = false;
    counters = { sent: 0, skipped: 0, errors: 0, total: 0 };
    qs('#go').disabled = true;
    renderPhases();
    const r = await api('start_search', timeFilter, testEmail);
    if (!r.ok) {
      toast(r.error, 'bad');
      searching = false;
      qs('#go').disabled = false;
    }
  }

  // ── progreso de fases ──
  function renderPhases() {
    qs('#run-stage').innerHTML =
      '<div class="card fade-up" style="margin-top:1.1rem" id="phases-card">' +
        '<div class="phases">' +
          phaseStep(1, 'scrape', 'Buscando en LinkedIn', 'Explorando publicaciones con tus terminos') +
          phaseStep(2, 'analyze', 'Analizando con IA', 'Filtrando ofertas reales y relevantes para tu perfil') +
          phaseStep(3, 'dedupe', 'Filtrando duplicados', 'Descartando repetidas, bloqueadas y ya aplicadas') +
        '</div>' +
      '</div>' +
      '<div id="offers-zone"></div>';
  }
  function phaseStep(n, key, title, sub) {
    return '<div class="phase-step" id="ph-' + key + '">' +
      '<div class="step-num">' + n + '</div>' +
      '<div class="content"><h4>' + title + '</h4>' +
      '<div class="detail">' + sub + '</div>' +
      '<div class="bar hidden progressbar"><div class="fill"></div></div>' +
      (key === 'analyze' ? '<div class="decisions hidden" id="decisions"></div>' : '') +
      '</div></div>';
  }
  function onPhase(p) {
    const el = qs('#ph-' + p.phase);
    if (!el) return;
    const num = qs('.step-num', el);
    if (p.status === 'start') {
      num.classList.add('active');
      qs('.detail', el).textContent = p.detail + '…';
      if (p.total) qs('.bar', el).classList.remove('hidden');
      if (p.phase === 'analyze') qs('#decisions').classList.remove('hidden');
    } else if (p.status === 'done') {
      num.classList.remove('active');
      num.classList.add('done');
      num.textContent = '✓';
      qs('.detail', el).textContent = p.detail;
      const bar = qs('.bar .fill', el);
      if (bar) bar.style.width = '100%';
    }
  }
  function onProgress(p) {
    const el = qs('#ph-' + p.phase);
    if (!el || !p.total) return;
    const fill = qs('.bar .fill', el);
    if (fill) fill.style.width = Math.round((p.current / p.total) * 100) + '%';
    if (p.phase === 'scrape' && p.msg) qs('.detail', el).textContent = p.msg;
  }
  function onDecision(d) {
    const box = qs('#decisions');
    if (!box) return;
    let cls, mark, txt;
    if (d.is_job && d.is_relevant) {
      cls = 'acc'; mark = '✓';
      txt = (d.company || '-') + ' — ' + (d.job_title || '-');
    } else if (d.is_job) {
      cls = 'irr'; mark = '–';
      txt = (d.company || 'oferta') + ' · ' + (d.relevance_reason || 'no relevante');
    } else {
      cls = 'rej'; mark = '✗';
      txt = d.relevance_reason || 'no es oferta';
    }
    box.insertAdjacentHTML('beforeend',
      '<div class="d ' + cls + '"><span class="mark">' + mark + '</span><span class="txt">' + esc(txt) + '</span></div>');
    box.scrollTop = box.scrollHeight;
  }

  function onSearchError(p) {
    searching = false;
    const go = qs('#go'); if (go) go.disabled = false;
    const msgs = {
      session_expired: 'Tu sesion de LinkedIn caduco. Reconectala en Ajustes.',
      no_session: 'Sin sesion de LinkedIn. Conectala en Ajustes.',
      not_configured: 'Falta configuracion. Revisa Ajustes.',
      no_posts: 'No se encontraron posts con email de reclutador. Prueba con "Esta semana" o "Este mes".',
      cancelled: 'Busqueda cancelada.',
    };
    const zone = qs('#offers-zone');
    if (zone) zone.innerHTML =
      '<div class="empty-state fade-up" style="margin-top:1.1rem"><div class="ic">🔍</div>' +
      '<p>' + esc(msgs[p.kind] || p.message || 'Error en la busqueda') + '</p></div>';
    toast(msgs[p.kind] || p.message || 'Error', p.kind === 'no_posts' ? 'warn' : 'bad', 6000);
  }

  // ── resultados ──
  function onSearchDone(p) {
    searching = false;
    const go = qs('#go'); if (go) go.disabled = false;
    offers = p.offers || [];
    const st = p.stats || {};
    const zone = qs('#offers-zone');
    if (!offers.length) {
      zone.innerHTML =
        '<div class="empty-state fade-up" style="margin-top:1.1rem"><div class="ic">📭</div>' +
        '<p>Se analizaron ' + (st.posts_with_emails || 0) + ' posts pero ninguna oferta relevante quedo disponible.' +
        ((st.already_applied || 0) > 0 ? '<br>' + st.already_applied + ' ya las habias aplicado en los ultimos 30 dias.' : '') +
        '</p></div>';
      return;
    }
    const modePills = { remote: '<span class="pill ok">Remoto</span>', hybrid: '<span class="pill warn">Hibrido</span>', onsite: '<span class="pill accent">Presencial</span>', unknown: '<span class="pill muted">—</span>' };
    const rows = offers.map(o => {
      const salary = o.salary && !/^(null|none|n\/a|no (mencionado|especificado))$/i.test(String(o.salary)) ? esc(String(o.salary)) : '—';
      const loc = o.location && !/^(null|none|n\/a|no (especificado|mencionado))$/i.test(String(o.location)) ? esc(o.location) : '—';
      return '<tr data-id="' + o.id + '">' +
        '<td><input type="checkbox" class="offer-check" checked data-id="' + o.id + '"></td>' +
        '<td><div class="job-cell"><span class="t">' + esc(o.job_title) + '</span><span class="c">' + esc(o.company) + '</span></div></td>' +
        '<td>' + (modePills[o.work_mode] || modePills.unknown) + '</td>' +
        '<td class="muted" style="font-size:.78rem">' + loc + '</td>' +
        '<td style="color:var(--ok);font-size:.78rem">' + salary + '</td>' +
        '<td class="mono" style="font-size:.76rem;color:var(--info)">' + esc(o.contact_email) + '</td>' +
        '<td>' + (o.post_url ? '<button class="link-btn open-post" data-url="' + esc(o.post_url) + '">Ver post</button>' : '<span class="muted">—</span>') + '</td>' +
        '</tr>';
    }).join('');
    zone.innerHTML =
      '<div class="offers-head fade-up">' +
        '<div><span class="section-label">Ofertas encontradas</span>' +
        '<div class="offers-stats">' + (st.posts_scraped || 0) + ' posts · ' + (st.posts_with_emails || 0) + ' con email · ' +
          (st.batch_dupes || 0) + ' duplicadas · ' + (st.already_applied || 0) + ' ya aplicadas</div></div>' +
        '<div class="row">' +
          '<button class="btn btn-ghost btn-sm" id="sel-all">Todas</button>' +
          '<button class="btn btn-ghost btn-sm" id="sel-none">Ninguna</button>' +
          '<button class="btn btn-primary" id="apply-sel">Aplicar a <span id="sel-count">' + offers.length + '</span></button>' +
        '</div>' +
      '</div>' +
      '<div class="table-wrap fade-up"><table><thead><tr>' +
        '<th></th><th>Oferta</th><th>Modo</th><th>Ubicacion</th><th>Salario</th><th>Email</th><th>Post</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table></div>';

    const updCount = () => {
      const n = qsa('.offer-check:checked').length;
      qs('#sel-count').textContent = n;
      qs('#apply-sel').disabled = n === 0;
    };
    qsa('.offer-check').forEach(c => c.addEventListener('change', updCount));
    qs('#sel-all').addEventListener('click', () => { qsa('.offer-check').forEach(c => c.checked = true); updCount(); });
    qs('#sel-none').addEventListener('click', () => { qsa('.offer-check').forEach(c => c.checked = false); updCount(); });
    qsa('.open-post').forEach(b => b.addEventListener('click', () => api('open_url', b.dataset.url)));
    qs('#apply-sel').addEventListener('click', () => {
      queue = qsa('.offer-check:checked').map(c => Number(c.dataset.id));
      counters.total = queue.length;
      if (queue.length) nextInQueue();
    });
  }

  // ── cola de aplicacion ──
  function offerById(id) { return offers.find(o => o.id === id); }

  function nextInQueue() {
    if (!queue.length) { finishRun(); return; }
    current = queue.shift();
    const o = offerById(current);
    openModal(
      '<div class="modal-head"><div class="card-title">' + esc(o.job_title) + '</div>' +
      '<p class="muted" style="font-size:.8rem">' + esc(o.company) + '</p></div>' +
      '<div class="modal-body"><div class="row" style="justify-content:center;padding:1.6rem 0">' +
        '<div class="spinner"></div><span class="secondary" id="gen-stage">Generando CV personalizado…</span>' +
      '</div></div>' +
      '<div class="modal-foot"><span class="apply-counter">' + (counters.total - queue.length) + ' de ' + counters.total + '</span></div>',
      { locked: true }
    );
    api('prepare_offer', current).then(r => {
      if (!r.ok) { toast(r.error, 'bad'); closeModal(); counters.errors++; nextInQueue(); }
    });
  }

  function onApplyProgress(p) {
    const el = qs('#gen-stage');
    if (el) el.textContent = p.stage === 'cv' ? 'Generando CV personalizado…' : 'Redactando el email…';
  }

  function onPrepareError(p) {
    counters.errors++;
    toast('Error generando la aplicacion: ' + (p.error || ''), 'bad', 6000);
    closeModal();
    nextInQueue();
  }

  function onPreviewReady(p) {
    if (sendAll) {
      // envio directo sin preview
      doSend(p.id, null, null, true);
      const body = qs('.modal-body');
      if (body) body.innerHTML = '<div class="row" style="justify-content:center;padding:1.6rem 0">' +
        '<div class="spinner"></div><span class="secondary">Enviando…</span></div>';
      return;
    }
    const o = offerById(p.id);
    openModal(
      '<div class="modal-head"><div class="card-title">' + esc(o.job_title) + '</div>' +
      '<p class="muted" style="font-size:.8rem">' + esc(o.company) + '</p></div>' +
      '<div class="modal-body">' +
        '<div class="preview-to">Para: <span class="mono" style="color:var(--info)">' + esc(p.to) + '</span></div>' +
        '<div class="field"><label>Asunto <span class="muted">(editable)</span></label>' +
          '<input class="input" id="pv-subject" value="' + esc(p.subject) + '"></div>' +
        '<div class="preview-body">' + esc(p.body) + '</div>' +
        '<div class="cv-chip" id="pv-cv">📎 ' + esc(p.cv_name || 'CV.pdf') + ' <span class="muted">· abrir</span></div>' +
        '<div class="input-msg bad" id="pv-msg" style="margin-top:.5rem"></div>' +
      '</div>' +
      '<div class="modal-foot">' +
        '<span class="apply-counter">' + (counters.total - queue.length) + ' de ' + counters.total + '</span>' +
        '<button class="btn btn-ghost" id="pv-skip">Saltar</button>' +
        (queue.length ? '<button class="btn btn-outline" id="pv-all">Enviar todo</button>' : '') +
        '<button class="btn btn-primary" id="pv-send">Enviar</button>' +
      '</div>',
      { locked: true }
    );
    qs('#pv-cv').addEventListener('click', () => api('open_cv', p.cv_path));
    qs('#pv-skip').addEventListener('click', async () => {
      await api('skip_offer', p.id);
      counters.skipped++;
      closeModal();
      nextInQueue();
    });
    const allB = qs('#pv-all');
    if (allB) allB.addEventListener('click', () => { sendAll = true; sendFromModal(p.id); });
    qs('#pv-send').addEventListener('click', () => sendFromModal(p.id));
  }

  function sendFromModal(id, altEmail) {
    const subject = qs('#pv-subject') ? qs('#pv-subject').value.trim() : null;
    qs('#pv-send').disabled = true;
    qs('#pv-send').innerHTML = '<div class="spinner sm"></div>';
    doSend(id, subject, altEmail || null, false);
  }

  async function doSend(id, subject, altEmail, silent) {
    const r = await api('send_offer', id, subject, altEmail);
    if (!r.ok) {
      if (r.error === 'mx') {
        const rec = (r.data && r.data.recruiter_email) || '';
        const msg = qs('#pv-msg');
        if (msg) {
          msg.innerHTML = 'El dominio de <b>' + esc(rec) + '</b> no recibe correo (posible typo). ' +
            'Escribe un email alternativo y reintenta, o salta la oferta.';
          if (!qs('#pv-alt')) {
            msg.insertAdjacentHTML('afterend',
              '<div class="row" style="margin-top:.5rem"><input class="input" id="pv-alt" placeholder="email@alternativo.com">' +
              '<button class="btn btn-outline btn-sm" id="pv-alt-send">Reintentar</button></div>');
            qs('#pv-alt-send').addEventListener('click', () => {
              const alt = qs('#pv-alt').value.trim();
              if (!alt.includes('@')) { toast('Email alternativo invalido', 'warn'); return; }
              sendFromModal(id, alt);
            });
          }
          const sb = qs('#pv-send');
          if (sb) { sb.disabled = false; sb.textContent = 'Enviar'; }
        } else {
          counters.skipped++;
          await api('skip_offer', id);
          nextInQueue();
        }
        return;
      }
      toast(r.error, 'bad');
      counters.errors++;
      closeModal();
      nextInQueue();
    }
    // si ok: esperamos el evento send_result
  }

  function onSendResult(p) {
    if (p.status === 'sent') counters.sent++;
    else counters.errors++;
    if (p.status !== 'sent' && p.error) toast('Error al enviar: ' + p.error, 'bad', 6000);
    closeModal();
    nextInQueue();
  }

  // ── resumen ──
  async function finishRun() {
    const r = await api('finish_run');
    const s = (r.ok && r.data) || counters;
    const zone = qs('#offers-zone');
    zone.innerHTML =
      '<div class="fade-up" style="margin-top:1.3rem">' +
        '<span class="section-label">Resumen</span>' +
        '<div class="summary-grid">' +
          '<div class="summary-cell"><div class="n">' + (s.total || 0) + '</div><div class="l">Ofertas</div></div>' +
          '<div class="summary-cell ok"><div class="n">' + (s.sent || 0) + '</div><div class="l">Enviadas</div></div>' +
          '<div class="summary-cell warn"><div class="n">' + (s.skipped || 0) + '</div><div class="l">Saltadas</div></div>' +
          '<div class="summary-cell err"><div class="n">' + (s.errors || 0) + '</div><div class="l">Errores</div></div>' +
        '</div>' +
        '<div class="row" style="margin-top:1.2rem">' +
          '<button class="btn btn-outline" id="see-history">Ver historial</button>' +
          '<button class="btn btn-ghost" id="new-search">Nueva busqueda</button>' +
        '</div>' +
      '</div>';
    qs('#see-history').addEventListener('click', () => switchView('history'));
    qs('#new-search').addEventListener('click', () => renderIdle());
    if ((s.sent || 0) > 0) toast('Se enviaron ' + s.sent + ' aplicaciones ✓', 'ok');
  }

  return { init };
})();
