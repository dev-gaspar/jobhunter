// Mock del Bridge para desarrollo en navegador (sin pywebview).
// Con #onboarding en la URL arranca sin configurar. Solo se activa si no hay pywebview.
(function () {
  if (window.pywebview) return;

  const wait = ms => new Promise(r => setTimeout(r, ms));
  const emit = (n, p) => window.bus._recv(n, p);
  const forceOnboarding = location.hash.includes('onboarding');

  const state = {
    configured: !forceOnboarding,
    version: '2.0.0',
    has_session: !forceOnboarding,
    profile_name: forceOnboarding ? '' : 'Jose Gaspar',
    profile: forceOnboarding ? {} : {
      name: 'Jose Gaspar', title: 'AI Engineer / Fullstack',
      summary: 'Ingeniero con experiencia en automatizacion, agentes de IA y desarrollo fullstack.',
      portfolio: 'https://josegaspar.dev', linkedin: 'https://linkedin.com/in/dev-gaspar',
      skills: { backend: ['Python', 'Node.js'], ia: ['Gemini', 'LangChain'] },
      experience: [{ company: 'Innovarium', role: 'AI Engineer', period: '2024-2026', description: 'Agentes y automatizaciones.' }],
      education: [{ institution: 'UniCordoba', degree: 'Ing. Sistemas', period: '2019-2024' }],
    },
    smtp_email: forceOnboarding ? '' : 'jose@gmail.com',
    smtp_set: !forceOnboarding,
    gemini_key_masked: forceOnboarding ? '' : 'AIza***',
    model: 'gemini-2.5-flash',
    models: ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.5-pro', 'gemini-3-flash-preview', 'gemini-3.1-pro-preview', 'gemini-3.1-flash-lite-preview'],
    cv_template: 'modern',
    templates: [
      { key: 'modern', name: 'Modern', description: 'Limpio con acentos de color' },
      { key: 'minimal', name: 'Minimal', description: 'Espacioso, lineas finas, elegante' },
      { key: 'classic', name: 'Classic', description: 'Tradicional con fuente serif' },
      { key: 'compact', name: 'Compact', description: 'Denso, mas contenido por pagina' },
    ],
    job_types: forceOnboarding ? '' : 'ai engineer, fullstack developer',
    search_languages: '3',
    user_languages: forceOnboarding ? [] : [{ language: 'Espanol', level: 'Nativo' }, { language: 'Ingles', level: 'B2' }],
    work_mode: '1', user_location: '',
    links: forceOnboarding ? { portfolio: '', linkedin: '' } : { portfolio: 'https://josegaspar.dev', linkedin: 'https://linkedin.com/in/dev-gaspar' },
    cv_path: forceOnboarding ? '' : 'C:/Users/joseg/cv.pdf',
    queries_count: forceOnboarding ? 0 : 14,
    onboarding: {
      has_key: !forceOnboarding, has_profile: !forceOnboarding, has_cv: !forceOnboarding,
      has_job_types: !forceOnboarding, has_languages: !forceOnboarding,
      has_smtp: !forceOnboarding, has_session: !forceOnboarding, has_queries: !forceOnboarding,
    },
  };

  const OFFERS = [
    { id: 1, job_title: 'Backend Developer Python', company: 'TechNova', contact_email: 'talento@technova.io', work_mode: 'remote', location: 'LATAM', salary: '$2500-3500 USD', language: 'es', post_url: 'https://lnkd.in/abc', query: 'backend python' },
    { id: 2, job_title: 'AI Engineer', company: 'DataMind', contact_email: 'hr@datamind.ai', work_mode: 'remote', location: 'Remote global', salary: null, language: 'en', post_url: 'https://lnkd.in/def', query: 'ai engineer' },
    { id: 3, job_title: 'Fullstack JS', company: 'Kreativa', contact_email: 'jobs@kreativa.co', work_mode: 'hybrid', location: 'Bogota', salary: '$8M COP', language: 'es', post_url: null, query: 'fullstack' },
    { id: 4, job_title: 'Automation Specialist n8n', company: 'FlowOps', contact_email: 'people@flowops.dev', work_mode: 'remote', location: 'España', salary: '€30k', language: 'es', post_url: 'https://lnkd.in/ghi', query: 'automation' },
  ];

  const DECISIONS = [
    { is_job: true, is_relevant: true, company: 'TechNova', job_title: 'Backend Developer Python', relevance_reason: 'match directo con perfil' },
    { is_job: false, is_relevant: false, company: '', job_title: '', relevance_reason: 'post promocional de curso' },
    { is_job: true, is_relevant: true, company: 'DataMind', job_title: 'AI Engineer', relevance_reason: 'skills de IA coinciden' },
    { is_job: true, is_relevant: false, company: 'BPO Global', job_title: 'Soporte bilingue', relevance_reason: 'requiere ingles C1, usuario tiene B2' },
    { is_job: true, is_relevant: true, company: 'Kreativa', job_title: 'Fullstack JS', relevance_reason: 'stack coincide' },
    { is_job: false, is_relevant: false, company: '', job_title: '', relevance_reason: 'no es oferta, es networking' },
    { is_job: true, is_relevant: true, company: 'FlowOps', job_title: 'Automation Specialist n8n', relevance_reason: 'experiencia n8n' },
  ];

  const ok = data => ({ ok: true, data: data === undefined ? null : data, error: null });
  const err = (e, data) => ({ ok: false, data: data || null, error: e });

  let busy = null;

  window.pywebview = {
    api: {
      async get_state() { return ok(JSON.parse(JSON.stringify(state))); },

      async validate_gemini_key(key) {
        await wait(900);
        if (!key || key.length < 8) return err('Clave invalida. Revisa que sea correcta.');
        state.onboarding.has_key = true; state.gemini_key_masked = key.slice(0, 4) + '***';
        return ok();
      },
      async save_model(m) { state.model = m; return ok(); },
      async pick_cv_file() { await wait(400); return ok({ path: 'C:/Users/joseg/Documents/CV_Jose.pdf' }); },
      async extract_cv_from_path(path) {
        await wait(2200);
        state.cv_path = path; state.onboarding.has_cv = true;
        return ok({ profile: { name: 'Jose Gaspar', title: 'AI Engineer / Fullstack', email: 'jose@gmail.com', phone: '+57 300 000 0000', location: 'Monteria, CO', summary: 'Ingeniero de software con foco en IA aplicada, automatizacion de procesos y desarrollo fullstack. 3+ anos construyendo agentes y plataformas.', skills: { backend: ['Python', 'FastAPI', 'Node.js'], ia: ['Gemini', 'RAG', 'n8n'], frontend: ['React', 'Vite'] }, experience: [{ company: 'Innovarium', role: 'AI Engineer', period: '2024 - 2026', description: 'Diseno de agentes conversacionales y pipelines de automatizacion para clientes enterprise.' }, { company: 'Freelance', role: 'Fullstack Developer', period: '2021 - 2024', description: 'Aplicaciones web end-to-end para pymes.' }], education: [{ institution: 'Universidad de Cordoba', degree: 'Ingenieria de Sistemas', period: '2019 - 2024' }], projects: [{ name: 'JobHunter AI', description: 'Automatizacion de busqueda de empleo', tech: ['Python', 'Playwright'] }], achievements: [] } });
      },
      async extract_cv_b64(name, b64) { return this.extract_cv_from_path('C:/upload/' + name); },
      async save_profile(p) { state.profile = p; state.profile_name = p.name; state.onboarding.has_profile = true; return ok(); },
      async save_links(a, b) { state.links = { portfolio: a, linkedin: b }; return ok(); },
      async suggest_job_types() { await wait(1400); return ok(['AI Engineer', 'Backend Developer Python', 'Automation Engineer', 'Fullstack Developer', 'Integrations Engineer', 'Solutions Engineer']); },
      async save_job_types(raw) { state.job_types = raw; state.onboarding.has_job_types = true; return ok(); },
      async save_languages(s, u) { state.search_languages = s; state.user_languages = u; state.onboarding.has_languages = true; return ok(); },
      async save_work_mode(m, loc) { state.work_mode = m; state.user_location = loc; return ok(); },
      async save_template(t) { state.cv_template = t; return ok(); },
      async verify_smtp(email, pwd) {
        await wait(1200);
        if (!/@gmail\.com$/.test(email)) return err('Debe ser una cuenta @gmail.com');
        if ((pwd || '').replace(/ /g, '').length < 10) return err('La contrasena de aplicacion tiene 16 caracteres');
        state.smtp_email = email; state.smtp_set = true; state.onboarding.has_smtp = true;
        return ok();
      },
      async linkedin_login_start() {
        (async () => { await wait(3000); state.has_session = true; state.onboarding.has_session = true; emit('linkedin_done', { ok: true }); })();
        return ok();
      },
      async finish_onboarding() {
        (async () => { await wait(2500); state.configured = true; state.queries_count = 14; state.onboarding.has_queries = true; emit('onboarding_done', { queries_count: 14, from_ai: true }); })();
        return ok();
      },

      async start_search(tf, testEmail) {
        if (busy) return err('Hay una operacion en curso');
        busy = 'search';
        (async () => {
          emit('phase', { phase: 'scrape', status: 'start', detail: 'Buscando en LinkedIn', total: 6 });
          for (let i = 0; i < 6; i++) {
            emit('progress', { phase: 'scrape', current: i, total: 6, msg: ['backend python remoto', 'ai engineer latam', 'fullstack developer', 'n8n automation', 'python developer', 'enviar cv desarrollador'][i] });
            await wait(700);
          }
          emit('phase', { phase: 'scrape', status: 'done', detail: '48 posts, 11 con email', total: 6 });
          emit('phase', { phase: 'analyze', status: 'start', detail: 'Analizando ofertas', total: DECISIONS.length });
          for (let i = 0; i < DECISIONS.length; i++) {
            emit('progress', { phase: 'analyze', current: i, total: DECISIONS.length, msg: '' });
            await wait(650);
            emit('decision', DECISIONS[i]);
          }
          emit('phase', { phase: 'analyze', status: 'done', detail: '4 ofertas', total: DECISIONS.length });
          emit('phase', { phase: 'dedupe', status: 'start', detail: 'Filtrando duplicados', total: null });
          await wait(500);
          emit('phase', { phase: 'dedupe', status: 'done', detail: '4 ofertas finales', total: null });
          busy = null;
          emit('search_done', { offers: OFFERS, stats: { posts_scraped: 48, posts_with_emails: 11, posts_no_emails: 37, filter_accepted: 4, offers_no_email: 0, batch_dupes: 1, blacklisted: 0, already_applied: 1, offers_final: 4 } });
        })();
        return ok();
      },
      async prepare_offer(id) {
        const o = OFFERS.find(x => x.id === id);
        (async () => {
          emit('apply_progress', { stage: 'cv', job_title: o.job_title, company: o.company });
          await wait(1800);
          emit('apply_progress', { stage: 'email', job_title: o.job_title, company: o.company });
          await wait(1400);
          if (id === 3) { emit('prepare_error', { id, error: 'Gemini API: max retries exceeded' }); return; }
          emit('preview_ready', {
            id, to: o.contact_email,
            subject: 'Aplicacion ' + o.job_title + ' - Jose Gaspar',
            body: 'Hola ' + (o.company) + ',\n\nVi su busqueda de ' + o.job_title + ' y me interesa mucho. En Innovarium construi agentes de IA que redujeron 40% el tiempo de respuesta al cliente y automatizaciones n8n que procesan 12k eventos/mes.\n\nAdjunto mi CV adaptado al rol. Quedo atento.\n\nJose Gaspar\nhttps://josegaspar.dev',
            cv_path: 'C:/Users/joseg/.jobhunter/output/cvs/CV_' + o.company + '.pdf',
            cv_name: 'CV_' + o.company.replace(/ /g, '_') + '_20260816.pdf',
          });
        })();
        return ok();
      },
      async send_offer(id, subject, altEmail) {
        if (id === 4 && !altEmail) return err('mx', { recruiter_email: 'people@flowops.dev' });
        (async () => { await wait(1300); emit('send_result', { id, status: 'sent', error: null }); })();
        return ok();
      },
      async skip_offer(id) { return ok(); },
      async finish_run() { return ok({ total: 4, sent: 2, skipped: 1, errors: 1 }); },

      async get_history(last, company) {
        const rows = [
          { date: '2026-08-15', job_title: 'Backend Developer Python', company: 'TechNova', recruiter_email: 'talento@technova.io', sent_to: 'talento@technova.io', mode: 'run', post_url: 'https://lnkd.in/abc', subject: 'Aplicacion Backend', cv_path: 'C:/x/cv1.pdf' },
          { date: '2026-08-14', job_title: 'AI Engineer', company: 'DataMind', recruiter_email: 'hr@datamind.ai', sent_to: 'jose@gmail.com', mode: 'test', post_url: null, subject: 'Aplicacion AI', cv_path: 'C:/x/cv2.pdf' },
          { date: '2026-08-11', job_title: 'Fullstack JS', company: 'Kreativa', recruiter_email: 'jobs@kreativa.co', sent_to: 'jobs@kreativa.co', mode: 'run', post_url: 'https://lnkd.in/xyz', subject: 'Aplicacion Fullstack', cv_path: null },
        ];
        const f = company ? rows.filter(r => r.company.toLowerCase().includes(company.toLowerCase())) : rows;
        return ok(f);
      },
      async open_cv(p) { console.log('open_cv', p); return ok(); },
      async open_url(u) { window.open(u, '_blank'); return ok(); },
      async check_updates() { await wait(800); return ok({ update_available: true, latest: 'v2.1.0', url: 'https://github.com/dev-gaspar/jobhunter/releases/download/v2.1.0/JobHunterSetup-x64.exe' }); },
      async download_update(url) {
        (async () => {
          for (let d = 0; d <= 100; d += 20) { emit('update_progress', { done: d, total: 100 }); await wait(400); }
          emit('update_launched', {});
        })();
        return ok();
      },
    },
  };
  window.dispatchEvent(new Event('pywebviewready'));
})();
