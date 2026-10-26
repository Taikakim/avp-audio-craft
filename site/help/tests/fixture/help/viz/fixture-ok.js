// Owner: WINTERMUTE (created 2026-10-26) -- fixture viz module implementing contract C5; logs to window.__vizLog.
export function mount(container, params, help) {
  const log = (window.__vizLog = window.__vizLog || []);
  log.push('mounted:' + JSON.stringify({
    params,
    keys: Object.keys(help).sort(),
    colorKeys: Object.keys(help.colors).sort(),
    openTerm: typeof help.openTerm,
    reducedMotion: typeof help.reducedMotion,
  }));
  const root = document.createElement('div');
  root.setAttribute('data-testid', 'fixture-viz');
  root.style.cssText = 'min-height:120px;background:#e8f1f0;padding:8px;';
  const b = document.createElement('button');
  b.id = 'fixture-open-term';
  b.type = 'button';
  b.textContent = 'open momentum';
  b.addEventListener('click', () => help.openTerm('momentum'));
  root.append(b);
  container.append(root);
  return { destroy() { log.push('destroyed'); root.remove(); } };
}
