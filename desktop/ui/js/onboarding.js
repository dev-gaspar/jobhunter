// Wizard de onboarding: 10 pasos + pantalla final.
window.Onboarding = (function () {
  let S = null;          // appState
  let idx = 0;
  let extracted = null;  // perfil extraido del CV
  let chipsSel = new Set();
  let liConnected = false;

  const LEVELS = ['Nativo', 'Avanzado (C1-C2)', 'Intermedio (B1-B2)', 'Basico (A1-A2)'];

  // ── definicion de pasos ──
  const steps = [
    { id: 'welcome', title: 'Bienvenida', render: rWelcome, next: async () => true },
    { id: 'key', title: 'Gemini AI', render: rKey, next: nKey, done: () => S.onboarding.has_key },
    { id: 'cv', title: 'Tu CV', render: rCv, next: nCv, done: () => S.onboarding.has_cv && S.onboarding.has_profile },
    { id: 'links', title: 'Links', render: rLinks, next: nLinks, done: () => S.onboarding.has_profile },
    { id: 'jobs', title: 'Tipo de empleo', render: rJobs, next: nJobs, done: () => S.onboarding.has_job_types },
    { id: 'langs', title: 'Idiomas', render: rLangs, next: nLangs, done: () => S.onboarding.has_languages },
    { id: 'mode', title: 'Modalidad', render: rMode, next: nMode, done: () => S.onboarding.has_job_types },
    { id: 'tpl', title: 'Plantilla de CV', render: rTpl, next: nTpl, done: () => S.onboarding.has_job_types },
    { id: 'gmail', title: 'Gmail', render: rGmail, next: nGmail, done: () => S.onboarding.has_smtp },
    { id: 'linkedin', title: 'LinkedIn', render: rLinkedin, next: nLinkedin, done: () => S.onboarding.has_session },
    { id: 'finish', title: 'Listo', render: rFinish, next: null },
  ];

  function start(appState) {
    S = appState;
    // reanudar: primer paso obligatorio incompleto (welcome solo si no hay nada)
    idx = 0;
    const anyDone = S.onboarding.has_key || S.onboarding.has_cv || S.onboarding.has_smtp;
    if (anyDone) {
      idx = steps.findIndex(st => st.done && !st.done());
      if (idx < 0) idx = steps.length - 1;
    }
    qs('#onboarding').classList.remove('hidden');
    render();
  }

  function shell(innerHtml, opts) {
    const pct = Math.round((idx / (steps.length - 1)) * 100);
    const o = opts || {};
    qs('#onboarding').innerHTML =
      '<div class="ob-top">' +
        '<div class="row between">' +
          '<div class="row" style="gap:.55rem"><div class="logo-icon" style="width:22px;height:22px;border-radius:6px;font-size:12px">J</div>' +
          '<span class="head" style="font-weight:700;font-size:.9rem">JobHunter <span class="muted" style="font-weight:500">AI</span></span></div>' +
          '<span class="ob-pct">' + pct + '%</span>' +
        '</div>' +
        '<div class="progressbar"><div class="fill" style="width:' + pct + '%"></div></div>' +
      '</div>' +
      '<div class="ob-body"><div class="ob-step">' + innerHtml + '</div></div>' +
      '<div class="ob-foot">' +
        (idx > 0 && !o.noBack
          ? '<button class="btn btn-ghost" id="ob-back">← Atras</button>'
          : '<span></span>') +
        (o.noNext ? '<span></span>'
          : '<button class="btn btn-primary" id="ob-next">' + (o.nextLabel || 'Continuar') + '</button>') +
      '</div>';
    const back = qs('#ob-back');
    if (back) back.addEventListener('click', () => { idx = Math.max(0, idx - 1); render(); });
    const nextB = qs('#ob-next');
    if (nextB) nextB.addEventListener('click', async () => {
      const st = steps[idx];
      if (!st.next) return;
      nextB.disabled = true;
      nextB.innerHTML = '<div class="spinner sm"></div>';
      let ok = false;
      try { ok = await st.next(); } catch (e) { toast(String(e), 'bad'); }
      if (ok) { idx = Math.min(steps.length - 1, idx + 1); render(); }
      else { nextB.disabled = false; nextB.textContent = o.nextLabel || 'Continuar'; }
    });
  }

  function render() { steps[idx].render(); }

  async function refreshState() {
    const r = await api('get_state');
    if (r.ok) { S = r.data; window.appState = r.data; }
  }

  // ── paso 1: bienvenida ──
  function rWelcome() {
    shell(
      '<div class="ob-hero">' +
        '<div class="logo-icon">J</div>' +
        '<h1>Tu busqueda de empleo,<br><span class="grad">en automatico</span></h1>' +
        '<p class="lead">JobHunter escanea LinkedIn, detecta ofertas reales para tu perfil, ' +
        'genera un CV adaptado a cada una con IA y envia la aplicacion al reclutador por ti.</p>' +
        '<div class="ob-needs">' +
          '<div class="ob-need"><div class="ic">🔑</div><h3>Clave de Gemini</h3><p>Gratis, de Google. Te guiamos para crearla en 1 minuto.</p></div>' +
          '<div class="ob-need"><div class="ic">📄</div><h3>Tu CV en PDF</h3><p>La IA lo lee para conocer tu experiencia real.</p></div>' +
          '<div class="ob-need"><div class="ic">✉️</div><h3>Tu Gmail</h3><p>Desde ahi se envian tus aplicaciones.</p></div>' +
        '</div>' +
      '</div>',
      { nextLabel: 'Empezar' }
    );
  }

  // ── paso 2: API key + modelo ──
  function rKey() {
    const models = S.models.map(m =>
      '<option value="' + esc(m) + '"' + (m === S.model ? ' selected' : '') + '>' + esc(m) + '</option>').join('');
    shell(
      '<h2>Conecta la IA</h2>' +
      '<p class="sub">JobHunter usa Gemini (Google) para leer ofertas y escribir tus CVs. La clave es gratuita.</p>' +
      '<div class="card" style="margin-bottom:1rem">' +
        '<div class="row between"><div><div class="card-title">1 · Crea tu clave</div>' +
        '<p class="muted" style="font-size:.8rem">Entra con tu cuenta de Google y pulsa "Create API key".</p></div>' +
        '<button class="btn btn-outline btn-sm" id="open-aistudio">Abrir Google AI Studio ↗</button></div>' +
      '</div>' +
      '<div class="field"><label>2 · Pega tu clave aqui</label>' +
        '<input class="input mono" id="ob-key" type="password" placeholder="AIza..." value="">' +
        '<div class="input-msg" id="key-msg">' + (S.onboarding.has_key ? '<span class="ok">✓ Ya tienes una clave guardada (' + esc(S.gemini_key_masked) + '). Continua o pega una nueva.</span>' : '') + '</div>' +
      '</div>' +
      '<div class="field"><label>Modelo de IA</label>' +
        '<select class="input" id="ob-model">' + models + '</select>' +
        '<span class="hint">gemini-2.5-flash es rapido y suficiente para empezar. Puedes cambiarlo luego en Ajustes.</span>' +
      '</div>'
    );
    qs('#open-aistudio').addEventListener('click', () => api('open_url', 'https://aistudio.google.com/apikey'));
  }
  async function nKey() {
    const key = qs('#ob-key').value.trim();
    const model = qs('#ob-model').value;
    await api('save_model', model);
    if (!key && S.onboarding.has_key) return true; // conserva la existente
    if (!key) { qs('#key-msg').innerHTML = '<span class="bad">Pega tu clave para continuar.</span>'; return false; }
    const r = await api('validate_gemini_key', key);
    if (!r.ok) { qs('#key-msg').innerHTML = '<span class="bad">✗ ' + esc(r.error) + '</span>'; return false; }
    await refreshState();
    return true;
  }

  // ── paso 3: CV ──
  function rCv() {
    if (extracted) { rCvReview(); return; }
    shell(
      '<h2>Tu CV actual</h2>' +
      '<p class="sub">La IA lo lee para extraer tu experiencia REAL. Nunca inventa nada que no este aqui.</p>' +
      '<div class="dropzone" id="dz">' +
        '<div class="ic">📄</div>' +
        '<h3>Arrastra tu CV en PDF</h3>' +
        '<p>o haz clic para buscarlo en tu equipo</p>' +
      '</div>' +
      (S.cv_path ? '<p class="muted" style="margin-top:.8rem;font-size:.8rem">CV actual: <span class="mono">' + esc(S.cv_path) + '</span> — puedes continuar sin volver a subirlo.</p>' : ''),
      { noNext: !S.onboarding.has_profile }
    );
    const dz = qs('#dz');
    dz.addEventListener('click', async () => {
      const r = await api('pick_cv_file');
      if (r.ok && r.data && r.data.path) extractFrom(r.data.path);
    });
    dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('over'); });
    dz.addEventListener('dragleave', () => dz.classList.remove('over'));
    dz.addEventListener('drop', e => {
      e.preventDefault(); dz.classList.remove('over');
      const f = e.dataTransfer.files && e.dataTransfer.files[0];
      if (!f) return;
      if (!/\.pdf$/i.test(f.name)) { toast('El CV debe ser un PDF', 'warn'); return; }
      const reader = new FileReader();
      reader.onload = () => {
        const b64 = String(reader.result).split(',')[1];
        extractB64(f.name, b64);
      };
      reader.readAsDataURL(f);
    });
  }
  function rCvLoading() {
    shell(
      '<h2>Leyendo tu CV…</h2>' +
      '<p class="sub">Gemini esta extrayendo tu experiencia, habilidades y educacion.</p>' +
      '<div class="card"><div class="row"><div class="spinner"></div>' +
      '<span class="secondary">Esto toma unos segundos…</span></div></div>',
      { noNext: true, noBack: true }
    );
  }
  async function extractFrom(path) {
    rCvLoading();
    const r = await api('extract_cv_from_path', path);
    afterExtract(r);
  }
  async function extractB64(name, b64) {
    rCvLoading();
    const r = await api('extract_cv_b64', name, b64);
    afterExtract(r);
  }
  function afterExtract(r) {
    if (!r.ok) {
      toast(r.error || 'No se pudo leer el CV', 'bad', 6000);
      extracted = null;
      render();
      return;
    }
    extracted = r.data.profile;
    rCvReview();
  }
  function rCvReview() {
    const p = extracted;
    const exps = (p.experience || []).map((e, i) =>
      '<div class="exp" data-i="' + i + '">' +
        '<div class="row" style="margin-bottom:.5rem">' +
          '<input class="input" data-f="role" value="' + esc(e.role) + '" placeholder="Cargo">' +
          '<input class="input" data-f="company" value="' + esc(e.company) + '" placeholder="Empresa">' +
          '<input class="input" data-f="period" value="' + esc(e.period) + '" placeholder="Periodo" style="max-width:130px">' +
        '</div>' +
        '<textarea class="input" data-f="description" rows="2">' + esc(e.description) + '</textarea>' +
      '</div>').join('');
    shell(
      '<h2>Revisa lo que leimos</h2>' +
      '<p class="sub">Corrige cualquier dato antes de continuar — este perfil alimenta todos tus CVs.</p>' +
      '<div class="profile-review">' +
        '<div class="grid-2">' +
          '<div class="field"><label>Nombre</label><input class="input" id="pr-name" value="' + esc(p.name) + '"></div>' +
          '<div class="field"><label>Titulo profesional</label><input class="input" id="pr-title" value="' + esc(p.title) + '"></div>' +
        '</div>' +
        '<div class="field"><label>Resumen profesional</label><textarea class="input" id="pr-summary" rows="3">' + esc(p.summary) + '</textarea></div>' +
        '<div class="field"><label>Experiencia (' + (p.experience || []).length + ')</label>' + exps + '</div>' +
        '<p class="muted" style="font-size:.76rem">Habilidades, educacion y proyectos se importaron completos; podras ajustarlos en Ajustes.</p>' +
      '</div>',
      { nextLabel: 'Guardar y continuar' }
    );
  }
  async function nCv() {
    if (!extracted) return S.onboarding.has_profile; // continua con el perfil previo
    extracted.name = qs('#pr-name').value.trim();
    extracted.title = qs('#pr-title').value.trim();
    extracted.summary = qs('#pr-summary').value.trim();
    qsa('.profile-review .exp').forEach(div => {
      const i = Number(div.dataset.i);
      qsa('input, textarea', div).forEach(inp => {
        extracted.experience[i][inp.dataset.f] = inp.value.trim();
      });
    });
    if (!extracted.name) { toast('El nombre es obligatorio', 'warn'); return false; }
    const r = await api('save_profile', extracted);
    if (!r.ok) { toast(r.error, 'bad'); return false; }
    await refreshState();
    return true;
  }

  // ── paso 4: links ──
  function rLinks() {
    shell(
      '<h2>Links profesionales</h2>' +
      '<p class="sub">Opcionales — se incluyen en la firma de tus emails y en el CV.</p>' +
      '<div class="field"><label>Portfolio / web personal</label>' +
        '<input class="input" id="ob-portfolio" placeholder="https://..." value="' + esc(S.links.portfolio) + '"></div>' +
      '<div class="field"><label>Perfil de LinkedIn</label>' +
        '<input class="input" id="ob-linkedin" placeholder="https://linkedin.com/in/..." value="' + esc(S.links.linkedin) + '"></div>'
    );
  }
  async function nLinks() {
    const r = await api('save_links', qs('#ob-portfolio').value, qs('#ob-linkedin').value);
    if (!r.ok) { toast(r.error, 'bad'); return false; }
    await refreshState();
    return true;
  }

  // ── paso 5: tipo de empleo ──
  function rJobs() {
    chipsSel = new Set((S.job_types || '').split(',').map(s => s.trim()).filter(Boolean));
    shell(
      '<h2>¿Que empleo buscas?</h2>' +
      '<p class="sub">Elige sugerencias de la IA basadas en tu CV, o escribe los tuyos.</p>' +
      '<div class="field"><label>Sugerencias para ti</label>' +
        '<div class="chips" id="chips"><div class="row"><div class="spinner sm"></div><span class="muted" style="font-size:.8rem">Generando sugerencias…</span></div></div></div>' +
      '<div class="field"><label>Tipos de empleo <span class="muted">(separados por coma)</span></label>' +
        '<input class="input" id="ob-jobs" value="' + esc(S.job_types) + '" placeholder="ej: backend developer, ai engineer"></div>'
    );
    api('suggest_job_types').then(r => {
      const box = qs('#chips');
      if (!box) return;
      const list = (r.ok && r.data) || [];
      if (!list.length) { box.innerHTML = '<span class="muted" style="font-size:.8rem">Sin sugerencias — escribe los tuyos abajo.</span>'; return; }
      box.innerHTML = list.map(s => '<button class="chip' + (chipsSel.has(s) ? ' active' : '') + '">' + esc(s) + '</button>').join('');
      qsa('.chip', box).forEach(ch => ch.addEventListener('click', () => {
        const val = ch.textContent;
        if (chipsSel.has(val)) chipsSel.delete(val); else chipsSel.add(val);
        ch.classList.toggle('active');
        const manual = qs('#ob-jobs').value.split(',').map(s => s.trim()).filter(Boolean)
          .filter(v => !Array.from(chipsSel).some(c => c.toLowerCase() === v.toLowerCase()) || chipsSel.has(v));
        const merged = Array.from(new Set([...chipsSel, ...manual.filter(v => !chipsSel.has(v))]));
        qs('#ob-jobs').value = merged.join(', ');
      }));
    });
  }
  async function nJobs() {
    const raw = qs('#ob-jobs').value.trim();
    if (!raw) { toast('Indica al menos un tipo de empleo', 'warn'); return false; }
    const r = await api('save_job_types', raw);
    if (!r.ok) { toast(r.error, 'bad'); return false; }
    await refreshState();
    return true;
  }

  // ── paso 6: idiomas ──
  function rLangs() {
    const userLangs = S.user_languages.length ? S.user_languages : [{ language: 'Espanol', level: 'Nativo' }];
    const rows = userLangs.map(l => langRow(l.language, l.level)).join('');
    const sl = S.search_languages || '3';
    shell(
      '<h2>Idiomas</h2>' +
      '<p class="sub">Definen en que idiomas buscar ofertas y que nivel real puedes acreditar.</p>' +
      '<div class="field"><label>Buscar ofertas en</label>' +
        '<div class="segmented" id="ob-sl">' +
          '<button data-v="1"' + (sl === '1' ? ' class="active"' : '') + '>Español</button>' +
          '<button data-v="2"' + (sl === '2' ? ' class="active"' : '') + '>Ingles</button>' +
          '<button data-v="3"' + (sl === '3' ? ' class="active"' : '') + '>Ambos</button>' +
        '</div></div>' +
      '<div class="field"><label>Tus idiomas y nivel</label><div id="lang-rows">' + rows + '</div>' +
        '<button class="btn btn-ghost btn-sm" id="add-lang" style="align-self:flex-start">+ Agregar idioma</button></div>'
    );
    qsa('#ob-sl button').forEach(b => b.addEventListener('click', () => {
      qsa('#ob-sl button').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
    }));
    qs('#add-lang').addEventListener('click', () => {
      qs('#lang-rows').insertAdjacentHTML('beforeend', langRow('', 'Intermedio (B1-B2)'));
      wireLangRows();
    });
    wireLangRows();
  }
  function langRow(lang, level) {
    const opts = LEVELS.map(lv => '<option' + (lv === level ? ' selected' : '') + '>' + lv + '</option>').join('');
    return '<div class="row lang-row" style="margin-bottom:.55rem">' +
      '<input class="input" data-f="language" placeholder="Idioma" value="' + esc(lang) + '">' +
      '<select class="input" data-f="level" style="max-width:190px">' + opts + '</select>' +
      '<button class="btn btn-ghost btn-sm rm-lang">✕</button></div>';
  }
  function wireLangRows() {
    qsa('.rm-lang').forEach(b => {
      b.onclick = () => { if (qsa('.lang-row').length > 1) b.closest('.lang-row').remove(); };
    });
  }
  async function nLangs() {
    const sl = qs('#ob-sl button.active').dataset.v;
    const langs = qsa('.lang-row').map(row => ({
      language: qs('input[data-f="language"]', row).value.trim(),
      level: qs('select[data-f="level"]', row).value.split(' ')[0],
    })).filter(l => l.language);
    if (!langs.length) { toast('Agrega al menos un idioma', 'warn'); return false; }
    const r = await api('save_languages', sl, langs);
    if (!r.ok) { toast(r.error, 'bad'); return false; }
    await refreshState();
    return true;
  }

  // ── paso 7: modalidad ──
  function rMode() {
    const opts = [
      { v: '1', t: 'Remoto', d: 'Desde cualquier lugar' },
      { v: '2', t: 'Hibrido', d: 'Algunos dias presencial' },
      { v: '3', t: 'Presencial', d: 'En sitio' },
      { v: '4', t: 'Cualquiera', d: 'Sin preferencia' },
    ];
    const sel = S.work_mode || '4';
    shell(
      '<h2>Modalidad de trabajo</h2>' +
      '<p class="sub">Filtra las ofertas segun como quieres trabajar.</p>' +
      '<div class="opt-cards" id="modes">' +
        opts.map(o => '<div class="opt-card' + (o.v === sel ? ' active' : '') + '" data-v="' + o.v + '"><h3>' + o.t + '</h3><p>' + o.d + '</p></div>').join('') +
      '</div>' +
      '<div class="field hidden" id="loc-field" style="margin-top:1rem"><label>Tu ubicacion (ciudad, pais)</label>' +
        '<input class="input" id="ob-loc" value="' + esc(S.user_location) + '" placeholder="ej: Monteria, Colombia"></div>'
    );
    const locField = qs('#loc-field');
    const upd = v => locField.classList.toggle('hidden', !(v === '2' || v === '3'));
    upd(sel);
    qsa('#modes .opt-card').forEach(c => c.addEventListener('click', () => {
      qsa('#modes .opt-card').forEach(x => x.classList.remove('active'));
      c.classList.add('active');
      upd(c.dataset.v);
    }));
  }
  async function nMode() {
    const v = qs('#modes .opt-card.active').dataset.v;
    const loc = qs('#ob-loc').value;
    if ((v === '2' || v === '3') && !loc.trim()) { toast('Indica tu ubicacion', 'warn'); return false; }
    const r = await api('save_work_mode', v, loc);
    if (!r.ok) { toast(r.error, 'bad'); return false; }
    await refreshState();
    return true;
  }

  // ── paso 8: plantilla ──
  function thumbs(key) {
    if (key === 'modern') {
      return '<div class="t-line dark" style="width:60%"></div><div class="t-line accent" style="width:35%"></div><div style="height:4px"></div>' +
        '<div class="t-line accent" style="width:25%;height:2px"></div><div class="t-line" style="width:95%"></div><div class="t-line" style="width:88%"></div>' +
        '<div style="height:3px"></div><div class="t-line accent" style="width:25%;height:2px"></div><div class="t-line" style="width:92%"></div><div class="t-line" style="width:85%"></div><div class="t-line" style="width:90%"></div>';
    }
    if (key === 'minimal') {
      return '<div class="t-line dark" style="width:45%;margin:0 auto"></div><div class="t-line" style="width:30%;margin:0 auto"></div><div style="height:7px"></div>' +
        '<div class="t-line" style="width:85%;margin:0 auto"></div><div class="t-line" style="width:80%;margin:0 auto"></div><div style="height:6px"></div>' +
        '<div class="t-line" style="width:85%;margin:0 auto"></div><div class="t-line" style="width:78%;margin:0 auto"></div>';
    }
    if (key === 'classic') {
      return '<div class="t-line dark" style="width:55%"></div><div style="height:4px"></div>' +
        '<div class="t-line red" style="width:30%;height:2px"></div><div class="t-line" style="width:95%"></div><div class="t-line" style="width:90%"></div>' +
        '<div style="height:4px"></div><div class="t-line red" style="width:30%;height:2px"></div><div class="t-line" style="width:88%"></div><div class="t-line" style="width:93%"></div>';
    }
    return '<div class="t-line dark" style="width:55%"></div><div class="t-line" style="width:40%"></div><div style="height:3px"></div>' +
      '<div class="t-cols"><div><div class="t-line"></div><div class="t-line"></div><div class="t-line" style="width:80%"></div></div>' +
      '<div><div class="t-line"></div><div class="t-line" style="width:85%"></div><div class="t-line"></div></div></div>' +
      '<div style="height:3px"></div><div class="t-line" style="width:95%"></div><div class="t-line" style="width:92%"></div><div class="t-line" style="width:88%"></div>';
  }
  function rTpl() {
    shell(
      '<h2>Estilo de tu CV</h2>' +
      '<p class="sub">Cada aplicacion genera un PDF con este estilo, adaptado a la oferta.</p>' +
      '<div class="tpl-grid" id="tpls">' +
        S.templates.map(t =>
          '<div class="tpl' + (t.key === S.cv_template ? ' active' : '') + '" data-k="' + t.key + '">' +
            '<div class="thumb">' + thumbs(t.key) + '</div>' +
            '<div class="meta"><h4>' + esc(t.name) + '</h4><p>' + esc(t.description) + '</p></div>' +
          '</div>').join('') +
      '</div>'
    );
    qsa('#tpls .tpl').forEach(t => t.addEventListener('click', () => {
      qsa('#tpls .tpl').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
    }));
  }
  async function nTpl() {
    const k = qs('#tpls .tpl.active').dataset.k;
    const r = await api('save_template', k);
    if (!r.ok) { toast(r.error, 'bad'); return false; }
    return true;
  }

  // ── paso 9: Gmail ──
  function rGmail() {
    shell(
      '<h2>Conecta tu Gmail</h2>' +
      '<p class="sub">Tus aplicaciones se envian desde tu propio correo. Google exige una "contraseña de aplicacion" — se crea en 1 minuto:</p>' +
      '<div class="card" style="margin-bottom:1.2rem">' +
        '<div class="guide-step"><div class="step-num">1</div><div class="content">' +
          '<h3>Activa la verificacion en 2 pasos</h3>' +
          '<p>Si ya la tienes activa, salta al paso 2.</p>' +
          '<button class="btn btn-outline btn-sm" id="g-2fa">Abrir verificacion en 2 pasos ↗</button></div></div>' +
        '<div class="guide-step"><div class="step-num">2</div><div class="content">' +
          '<h3>Crea la contraseña de aplicacion</h3>' +
          '<p>En el campo del nombre escribe <span class="kbd">JobHunter</span> y pulsa <b>Crear</b>. Google te mostrara 16 letras.</p>' +
          '<button class="btn btn-outline btn-sm" id="g-app">Abrir contraseñas de aplicacion ↗</button></div></div>' +
        '<div class="guide-step"><div class="step-num">3</div><div class="content">' +
          '<h3>Pega aqui las 16 letras</h3>' +
          '<p>Con o sin espacios, da igual. No es tu contraseña normal de Gmail.</p></div></div>' +
      '</div>' +
      '<div class="grid-2">' +
        '<div class="field"><label>Tu Gmail</label><input class="input" id="ob-email" type="email" placeholder="tucorreo@gmail.com" value="' + esc(S.smtp_email) + '"></div>' +
        '<div class="field"><label>Contraseña de aplicacion</label><input class="input mono" id="ob-pass" type="password" placeholder="xxxx xxxx xxxx xxxx"></div>' +
      '</div>' +
      '<div class="input-msg" id="gmail-msg">' + (S.onboarding.has_smtp ? '<span class="ok">✓ Gmail ya verificado. Continua o actualiza los datos.</span>' : '') + '</div>'
    );
    qs('#g-2fa').addEventListener('click', () => api('open_url', 'https://myaccount.google.com/signinoptions/two-step-verification'));
    qs('#g-app').addEventListener('click', () => api('open_url', 'https://myaccount.google.com/apppasswords'));
  }
  async function nGmail() {
    const email = qs('#ob-email').value.trim();
    const pass = qs('#ob-pass').value;
    if (!pass && S.onboarding.has_smtp && email === S.smtp_email) return true;
    const msg = qs('#gmail-msg');
    msg.innerHTML = '<span class="muted">Verificando con Gmail…</span>';
    const r = await api('verify_smtp', email, pass);
    if (!r.ok) { msg.innerHTML = '<span class="bad">✗ ' + esc(r.error) + '</span>'; return false; }
    msg.innerHTML = '<span class="ok">✓ Verificado</span>';
    await refreshState();
    return true;
  }

  // ── paso 10: LinkedIn ──
  function rLinkedin() {
    liConnected = S.onboarding.has_session;
    shell(
      '<h2>Conecta LinkedIn</h2>' +
      '<p class="sub">Se abrira una ventana de Chrome para que inicies sesion una sola vez. La sesion queda guardada en tu equipo.</p>' +
      '<div class="li-box" id="li-box">' +
        (liConnected
          ? '<div class="badge"><span class="badge-dot"></span> Sesion de LinkedIn detectada</div>' +
            '<p class="muted" style="margin-top:.8rem;font-size:.8rem">Puedes continuar o volver a conectar si cambiaste de cuenta.</p>' +
            '<div style="margin-top:1rem"><button class="btn btn-outline" id="li-connect">Volver a conectar</button></div>'
          : '<button class="btn btn-primary btn-lg" id="li-connect">Conectar LinkedIn</button>' +
            '<div class="warn-note">Inicia sesion con correo y contraseña. NO uses el boton "Continuar con Google" — LinkedIn lo bloquea en navegadores automatizados.</div>') +
      '</div>',
      { nextLabel: liConnected ? 'Continuar' : 'Continuar sin conectar' }
    );
    qs('#li-connect').addEventListener('click', async () => {
      qs('#li-box').innerHTML = '<div class="row" style="justify-content:center"><div class="spinner"></div>' +
        '<span class="secondary">Esperando que completes el login en Chrome… (hasta 5 min, soporta 2FA)</span></div>';
      const off = bus.on('linkedin_done', async p => {
        off();
        await refreshState();
        liConnected = !!p.ok;
        if (!p.ok) toast('No se detecto el login. Intenta de nuevo.', 'warn', 6000);
        rLinkedin();
      });
      const r = await api('linkedin_login_start');
      if (!r.ok) { toast(r.error, 'bad'); rLinkedin(); }
    });
  }
  async function nLinkedin() {
    if (!liConnected) {
      toast('Sin LinkedIn conectado no se pueden buscar ofertas. Podras conectarlo en Ajustes.', 'warn', 6000);
    }
    return true;
  }

  // ── final ──
  function rFinish() {
    shell(
      '<h2>Ultimo paso</h2>' +
      '<p class="sub">La IA esta creando tus terminos de busqueda optimizados para LinkedIn.</p>' +
      '<div class="card"><div class="row"><div class="spinner"></div>' +
      '<span class="secondary" id="fin-msg">Generando busquedas con IA…</span></div></div>',
      { noNext: true, noBack: true }
    );
    const off = bus.on('onboarding_done', async p => {
      off();
      await refreshState();
      const warn = p.from_ai ? '' :
        '<p style="font-size:.8rem;color:var(--warn);margin-top:.8rem">La IA no respondio (¿sin cuota?): se usaron busquedas basicas. Puedes regenerarlas en Ajustes.</p>';
      shell(
        '<h2>¡Todo listo' + (S.profile_name ? ', ' + esc(S.profile_name.split(' ')[0]) : '') + '!</h2>' +
        '<p class="sub">Asi quedo tu configuracion:</p>' +
        '<div class="ob-summary">' +
          '<div class="krow"><span class="k">Perfil</span><span>' + esc(S.profile_name) + '</span></div>' +
          '<div class="krow"><span class="k">Correo</span><span>' + esc(S.smtp_email) + '</span></div>' +
          '<div class="krow"><span class="k">Modelo IA</span><span class="mono" style="font-size:.8rem">' + esc(S.model) + '</span></div>' +
          '<div class="krow"><span class="k">Plantilla CV</span><span>' + esc(S.cv_template) + '</span></div>' +
          '<div class="krow"><span class="k">Busquedas generadas</span><span>' + p.queries_count + '</span></div>' +
          '<div class="krow"><span class="k">LinkedIn</span><span>' + (S.has_session ? '✓ Conectado' : '✗ Pendiente') + '</span></div>' +
        '</div>' + warn +
        '<div style="margin-top:1.6rem"><button class="btn btn-primary btn-lg" id="ob-go">Empezar a buscar →</button></div>',
        { noNext: true, noBack: true }
      );
      qs('#ob-go').addEventListener('click', () => showApp());
    });
    api('finish_onboarding').then(r => {
      if (!r.ok) { toast(r.error, 'bad'); }
    });
  }

  return { start };
})();
