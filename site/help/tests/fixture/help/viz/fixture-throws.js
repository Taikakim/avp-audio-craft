// Owner: WINTERMUTE (created 2026-10-26) -- fixture viz module whose mount() fails after touching the DOM.
export function mount(container) {
  container.innerHTML = '<p data-testid="half-built">half built</p>';
  throw new Error('fixture boom');
}
