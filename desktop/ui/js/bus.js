// Bus de eventos Python -> JS. Python llama window.bus._recv(nombre, payload).
window.bus = {
  _handlers: {},
  on(name, fn) {
    (this._handlers[name] = this._handlers[name] || []).push(fn);
    return () => {
      this._handlers[name] = (this._handlers[name] || []).filter(f => f !== fn);
    };
  },
  _recv(name, payload) {
    (this._handlers[name] || []).forEach(fn => {
      try { fn(payload); } catch (e) { console.error('bus handler', name, e); }
    });
  },
};
