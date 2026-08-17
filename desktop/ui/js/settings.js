// Vista Ajustes: conexiones, perfil, preferencias, acerca de / updates.
window.Settings = (function () {
  let root = null;
  let S = null;

  function init() {
    root = qs('#view-settings');
    bus.on('linkedin_done', p => {
      if (qs('#li-status')) {
        refresh();
        toast(p.ok ? 'LinkedIn conectado ✓' : 'No se detecto el login de LinkedIn', p.ok ? 'ok' : 'warn');
      }
    });
    bus.on('update_progress', p => {
      const el = qs('#upd-progress .fill');
      if (el && p.total) el.style.width = Math.round((p.done / p.total) * 100) + '%';
    });
    bus.on('update_launched', () => toast('Instalador iniciado — la app se cerrara', 'ok'));
    bus.on('update_error', p => toast('Error al descargar: ' + p.message, 'bad', 6000));
    bus.on('onboarding_done', p => {
      if (qs('#regen-btn')) {
        const b = qs('#regen-btn');
        b.disabled = false; b.textContent = 'Regenerar busquedas con IA';
        toast('Busquedas regeneradas: ' + p.queries_count + (p.from_ai ? '' : ' (fallback basico)'), p.from_ai ? 'ok' : 'warn');
        refresh();
      }
    });
  }

  async function refresh() {
    const r = await api('get_state');
    if (!r.ok) { root.innerHTML = '<div class="empty-state"><p>' + esc(r.error) + '</p></div>'; return; }
    S = r.data;
    window.appState = S;
    render();
  }

  function render() {
    const models = S.models.map(m => '<option' + (m === S.model ? ' selected' : '') + '>' + esc(m) + '</option>').join('');
    const tpls = S.templates.map(t => '<option value="' + esc(t.key) + '"' + (t.key === S.cv_template ? ' selected' : '') + '>' + esc(t.name) + ' — ' + esc(t.description) + '</option>').join('');
    root.innerHTML =
      '<div class="view-head"><h1>Ajustes</h1><p>Conexiones, perfil y preferencias de la busqueda.</p></div>' +
      '<div class="settings-grid">' +

      // conexiones
      '<div class="card"><div class="card-title">Conexiones</div>' +
        '<div class="conn-row"><span class="name">Gemini</span>' +
          '<span class="st mono">' + (S.gemini_key_masked ? esc(S.gemini_key_masked) + ' · ' + esc(S.model) : 'Sin configurar') + '</span>' +
          '<span class="badge"><span class="badge-dot' + (S.onboarding.has_key ? '' : ' off') + '"></span>' + (S.onboarding.has_key ? 'Activa' : 'Falta') + '</span>' +
          '<button class="btn btn-outline btn-sm" id="edit-key">Cambiar</button></div>' +
        '<div class="conn-row"><span class="name">Gmail</span>' +
          '<span class="st mono">' + esc(S.smtp_email || 'Sin configurar') + '</span>' +
          '<span class="badge"><span class="badge-dot' + (S.onboarding.has_smtp ? '' : ' off') + '"></span>' + (S.onboarding.has_smtp ? 'Verificado' : 'Falta') + '</span>' +
          '<button class="btn btn-outline btn-sm" id="edit-smtp">Cambiar</button></div>' +
        '<div class="conn-row"><span class="name">LinkedIn</span>' +
          '<span class="st" id="li-status">' + (S.has_session ? 'Sesion guardada en este equipo' : 'Sin sesion') + '</span>' +
          '<span class="badge"><span class="badge-dot' + (S.has_session ? '' : ' off') + '"></span>' + (S.has_session ? 'Conectado' : 'Falta') + '</span>' +
          '<button class="btn btn-outline btn-sm" id="li-relogin">' + (S.has_session ? 'Reconectar' : 'Conectar') + '</button></div>' +
      '</div>' +

      // perfil
      '<div class="card settings-form"><div class="card-title">Tu perfil</div>' +
        '<p class="card-sub">Alimenta todos los CVs generados. CV base: <span class="mono">' + esc(S.cv_path || '—') + '</span></p>' +
        '<div class="grid-2">' +
          '<div class="field"><label>Nombre</label><input class="input" id="s-name" value="' + esc(S.profile.name || '') + '"></div>' +
          '<div class="field"><label>Titulo profesional</label><input class="input" id="s-title" value="' + esc(S.profile.title || '') + '"></div>' +
        '</div>' +
        '<div class="field"><label>Resumen</label><textarea class="input" id="s-summary" rows="3">' + esc(S.profile.summary || '') + '</textarea></div>' +
        '<div class="grid-2">' +
          '<div class="field"><label>Portfolio</label><input class="input" id="s-portfolio" value="' + esc(S.links.portfolio || '') + '"></div>' +
          '<div class="field"><label>LinkedIn</label><input class="input" id="s-linkedin" value="' + esc(S.links.linkedin || '') + '"></div>' +
        '</div>' +
        '<div class="row"><button class="btn btn-primary btn-sm" id="save-profile">Guardar perfil</button>' +
        '<button class="btn btn-outline btn-sm" id="reupload-cv">Volver a leer un CV…</button></div>' +
      '</div>' +

      // preferencias
      '<div class="card settings-form"><div class="card-title">Busqueda</div>' +
        '<div class="field"><label>Tipos de empleo <span class="muted">(separados por coma)</span></label>' +
          '<input class="input" id="s-jobs" value="' + esc(S.job_types) + '"></div>' +
        '<div class="grid-2">' +
          '<div class="field"><label>Modelo de IA</label><select class="input" id="s-model">' + models + '</select></div>' +
          '<div class="field"><label>Plantilla de CV</label><select class="input" id="s-tpl">' + tpls + '</select></div>' +
        '</div>' +
        '<p class="card-sub" style="margin:0 0 .8rem">Busquedas activas: <b>' + S.queries_count + '</b> terminos generados con IA.</p>' +
        '<div class="row"><button class="btn btn-primary btn-sm" id="save-prefs">Guardar</button>' +
        '<button class="btn btn-outline btn-sm" id="regen-btn">Regenerar busquedas con IA</button></div>' +
      '</div>' +

      // acerca de
      '<div class="card"><div class="card-title">Acerca de</div>' +
        '<div class="about-row">' +
          '<span class="secondary" style="font-size:.85rem">JobHunter AI <span class="mono muted">v' + esc(S.version) + '</span> · open source (MIT)</span>' +
          '<div class="row">' +
            '<button class="btn btn-ghost btn-sm" id="open-repo">GitHub ↗</button>' +
            '<button class="btn btn-outline btn-sm" id="check-upd">Buscar actualizaciones</button>' +
          '</div>' +
        '</div>' +
        '<div id="upd-zone"></div>' +
      '</div>' +

      '</div>';

    wire();
  }

  function wire() {
    qs('#edit-key').addEventListener('click', editKey);
    qs('#edit-smtp').addEventListener('click', editSmtp);
    qs('#li-relogin').addEventListener('click', async () => {
      qs('#li-status').innerHTML = '<span class="row" style="gap:.4rem"><span class="spinner sm"></span> Esperando login en Chrome…</span>';
      const r = await api('linkedin_login_start');
      if (!r.ok) { toast(r.error, 'bad'); refresh(); }
    });
    qs('#save-profile').addEventListener('click', async () => {
      const p = Object.assign({}, S.profile);
      p.name = qs('#s-name').value.trim();
      p.title = qs('#s-title').value.trim();
      p.summary = qs('#s-summary').value.trim();
      p.portfolio = qs('#s-portfolio').value.trim();
      p.linkedin = qs('#s-linkedin').value.trim();
      const r = await api('save_profile', p);
      toast(r.ok ? 'Perfil guardado ✓' : r.error, r.ok ? 'ok' : 'bad');
      if (r.ok) refresh();
    });
    qs('#reupload-cv').addEventListener('click', async () => {
      const pick = await api('pick_cv_file');
      if (!pick.ok || !pick.data || !pick.data.path) return;
      toast('Leyendo CV con IA…', '');
      const r = await api('extract_cv_from_path', pick.data.path);
      if (!r.ok) { toast(r.error, 'bad', 6000); return; }
      const save = await api('save_profile', r.data.profile);
      toast(save.ok ? 'Perfil actualizado desde el CV ✓' : save.error, save.ok ? 'ok' : 'bad');
      refresh();
    });
    qs('#save-prefs').addEventListener('click', async () => {
      const r1 = await api('save_job_types', qs('#s-jobs').value);
      const r2 = await api('save_model', qs('#s-model').value);
      const r3 = await api('save_template', qs('#s-tpl').value);
      const bad = [r1, r2, r3].find(r => !r.ok);
      toast(bad ? bad.error : 'Preferencias guardadas ✓', bad ? 'bad' : 'ok');
    });
    qs('#regen-btn').addEventListener('click', async () => {
      const b = qs('#regen-btn');
      b.disabled = true; b.innerHTML = '<div class="spinner sm"></div>';
      const r = await api('finish_onboarding');
      if (!r.ok) { toast(r.error, 'bad'); b.disabled = false; b.textContent = 'Regenerar busquedas con IA'; }
    });
    qs('#open-repo').addEventListener('click', () => api('open_url', 'https://github.com/dev-gaspar/jobhunter'));
    qs('#check-upd').addEventListener('click', async () => {
      const b = qs('#check-upd');
      b.disabled = true; b.innerHTML = '<div class="spinner sm"></div>';
      const r = await api('check_updates');
      b.disabled = false; b.textContent = 'Buscar actualizaciones';
      if (r.ok && r.data && r.data.update_available) {
        window.latestUpdate = r.data;
        showUpdateBanner();
      } else {
        toast('Ya tienes la ultima version ✓', 'ok');
      }
    });
  }

  function editKey() {
    openModal(
      '<div class="modal-head"><div class="card-title">Cambiar clave de Gemini</div></div>' +
      '<div class="modal-body">' +
        '<div class="field"><label>Nueva clave API</label>' +
        '<input class="input mono" id="m-key" type="password" placeholder="AIza...">' +
        '<span class="hint">Creala gratis en Google AI Studio.</span></div>' +
        '<button class="btn btn-ghost btn-sm" id="m-open">Abrir Google AI Studio ↗</button>' +
        '<div class="input-msg" id="m-msg"></div>' +
      '</div>' +
      '<div class="modal-foot"><button class="btn btn-ghost" id="m-cancel">Cancelar</button>' +
      '<button class="btn btn-primary" id="m-save">Validar y guardar</button></div>'
    );
    qs('#m-open').addEventListener('click', () => api('open_url', 'https://aistudio.google.com/apikey'));
    qs('#m-cancel').addEventListener('click', closeModal);
    qs('#m-save').addEventListener('click', async () => {
      const b = qs('#m-save');
      b.disabled = true; b.innerHTML = '<div class="spinner sm"></div>';
      const r = await api('validate_gemini_key', qs('#m-key').value.trim());
      if (r.ok) { closeModal(); toast('Clave actualizada ✓', 'ok'); refresh(); }
      else {
        qs('#m-msg').innerHTML = '<span class="bad">✗ ' + esc(r.error) + '</span>';
        b.disabled = false; b.textContent = 'Validar y guardar';
      }
    });
  }

  function editSmtp() {
    openModal(
      '<div class="modal-head"><div class="card-title">Cambiar Gmail</div></div>' +
      '<div class="modal-body">' +
        '<div class="field"><label>Gmail</label><input class="input" id="m-email" type="email" value="' + esc(S.smtp_email) + '"></div>' +
        '<div class="field"><label>Contraseña de aplicacion (16 letras)</label>' +
        '<input class="input mono" id="m-pass" type="password" placeholder="xxxx xxxx xxxx xxxx">' +
        '<span class="hint">No es tu contraseña normal — se crea en Cuenta de Google → Contraseñas de aplicacion.</span></div>' +
        '<button class="btn btn-ghost btn-sm" id="m-open-g">Abrir contraseñas de aplicacion ↗</button>' +
        '<div class="input-msg" id="m-msg"></div>' +
      '</div>' +
      '<div class="modal-foot"><button class="btn btn-ghost" id="m-cancel">Cancelar</button>' +
      '<button class="btn btn-primary" id="m-save">Verificar y guardar</button></div>'
    );
    qs('#m-open-g').addEventListener('click', () => api('open_url', 'https://myaccount.google.com/apppasswords'));
    qs('#m-cancel').addEventListener('click', closeModal);
    qs('#m-save').addEventListener('click', async () => {
      const b = qs('#m-save');
      b.disabled = true; b.innerHTML = '<div class="spinner sm"></div>';
      const r = await api('verify_smtp', qs('#m-email').value.trim(), qs('#m-pass').value);
      if (r.ok) { closeModal(); toast('Gmail verificado ✓', 'ok'); refresh(); }
      else {
        qs('#m-msg').innerHTML = '<span class="bad">✗ ' + esc(r.error) + '</span>';
        b.disabled = false; b.textContent = 'Verificar y guardar';
      }
    });
  }

  function showUpdateBanner() {
    const u = window.latestUpdate;
    qs('#upd-zone').innerHTML =
      '<div class="divider"></div>' +
      '<div class="about-row"><span style="font-size:.85rem;color:var(--info)">✦ Nueva version <b>' + esc(u.latest) + '</b> disponible</span>' +
      '<button class="btn btn-primary btn-sm" id="do-upd">Descargar e instalar</button></div>' +
      '<div class="progressbar hidden" id="upd-progress" style="margin-top:.7rem"><div class="fill"></div></div>';
    qs('#do-upd').addEventListener('click', async () => {
      qs('#do-upd').disabled = true;
      qs('#upd-progress').classList.remove('hidden');
      const r = await api('download_update', u.url);
      if (!r.ok) toast(r.error, 'bad');
    });
  }

  function promptUpdate() {
    switchView('settings');
    refresh().then(() => { if (window.latestUpdate) showUpdateBanner(); });
  }

  return { init, refresh, promptUpdate };
})();
