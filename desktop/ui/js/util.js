// Utilidades compartidas: api(), DOM helpers, toasts.

// Promesa que resuelve cuando el puente pywebview esta listo.
window.apiReady = new Promise(resolve => {
  if (window.pywebview && window.pywebview.api) { resolve(); return; }
  window.addEventListener('pywebviewready', () => resolve());
  // fallback devmock: devmock.js define window.pywebview y dispara el evento
  setTimeout(() => { if (window.pywebview && window.pywebview.api) resolve(); }, 1500);
});

// Llama un metodo del Bridge. Retorna {ok, data, error}.
async function api(method, ...args) {
  await window.apiReady;
  const fn = window.pywebview.api[method];
  if (!fn) return { ok: false, data: null, error: 'Metodo no disponible: ' + method };
  try {
    const res = await fn.apply(window.pywebview.api, args);
    return res || { ok: false, data: null, error: 'Sin respuesta' };
  } catch (e) {
    return { ok: false, data: null, error: String(e) };
  }
}

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function qs(sel, root) { return (root || document).querySelector(sel); }
function qsa(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

function toast(msg, kind, ms) {
  const box = qs('#toasts');
  const t = document.createElement('div');
  t.className = 'toast ' + (kind || '');
  const icon = kind === 'ok' ? '✓' : kind === 'bad' ? '✗' : kind === 'warn' ? '!' : '·';
  t.innerHTML = '<span style="opacity:.7">' + icon + '</span><span>' + esc(msg) + '</span>';
  box.appendChild(t);
  setTimeout(() => {
    t.style.transition = 'opacity .4s'; t.style.opacity = '0';
    setTimeout(() => t.remove(), 450);
  }, ms || 3800);
}

// Modal generico: render(contentHtml) y devuelve el nodo; closeModal() lo quita.
function openModal(html, opts) {
  closeModal();
  const back = document.createElement('div');
  back.className = 'modal-backdrop';
  back.id = 'modal';
  back.innerHTML = '<div class="modal">' + html + '</div>';
  if (!(opts && opts.locked)) {
    back.addEventListener('click', e => { if (e.target === back) closeModal(); });
  }
  document.body.appendChild(back);
  return back;
}
function closeModal() {
  const m = qs('#modal');
  if (m) m.remove();
}
