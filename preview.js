/* Navegación de la demostración estática. No llama APIs ni almacena información. */
(function () {
  const valid = new Set(['usuario', 'administrador', 'acceso']);
  function show() {
    const requested = location.hash.slice(1);
    const screen = valid.has(requested) ? requested : 'usuario';
    document.body.dataset.screen = screen;
    document.querySelectorAll('.demo-screen').forEach(el => {el.hidden = el.id !== 'screen-' + screen;});
    document.querySelectorAll('[data-target]').forEach(el => {
      const active = el.dataset.target === screen;
      el.classList.toggle('active', active);
      if (active) el.setAttribute('aria-current', 'page'); else el.removeAttribute('aria-current');
    });
    const admin = screen === 'administrador';
    document.querySelector('#menu-user').hidden = admin;
    document.querySelector('#menu-admin').hidden = !admin;
    document.querySelector('#workspace-label').textContent = admin ? 'ESPACIO ADMINISTRATIVO' : 'MI ESPACIO FINANCIERO';
    document.querySelector('#breadcrumb').textContent = admin ? 'ADMINISTRACIÓN / RESUMEN' : 'FINANZAS PERSONALES / RESUMEN';
    document.querySelector('#role-name').textContent = admin ? 'Administrador demo' : 'Usuario demo';
    document.querySelector('#role-detail').textContent = admin ? 'Administración de ejemplo' : 'Cuenta de ejemplo';
    document.querySelector('.sidebar').classList.remove('open');
    window.scrollTo({top:0,behavior:'instant'});
  }
  window.addEventListener('hashchange', show);
  document.querySelector('#mobile-menu').addEventListener('click', () => document.querySelector('.sidebar').classList.toggle('open'));
  show();
}());
