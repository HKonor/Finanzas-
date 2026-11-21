/* Finanza. Front-end progresivo. Los saldos siempre vienen del servidor Django; no hay datos falsos. */
document.addEventListener('DOMContentLoaded', () => {
  const links = document.querySelectorAll('.nav-link');
  links.forEach(link => { if (new URL(link.href).pathname === location.pathname) link.classList.add('active'); });
  const menu = document.querySelector('.sidebar');
  document.querySelector('[data-toggle-menu]')?.addEventListener('click', () => menu?.classList.toggle('open'));
  document.addEventListener('click', event => {
    if (menu && menu.classList.contains('open') && !menu.contains(event.target) && !event.target.closest('[data-toggle-menu]')) menu.classList.remove('open');
  });
  document.querySelectorAll('[data-dismiss]').forEach(button => button.addEventListener('click', () => button.closest('.notice')?.remove()));
  function renderBars(data) {
    const map = {fijos:Number(data.fijos || 0), variables:Number(data.variables || 0), imprevistos:Number(data.imprevistos || 0)};
    const total = Object.values(map).reduce((a,b)=>a+b,0);
    const mx = Math.max(1,total);
    Object.entries(map).forEach(([k,v]) => {
      const el = document.querySelector(`[data-bar="${k}"]`);
      if (el) el.style.width = `${Math.min(100,Math.max(0,100*v/mx))}%`;
    });
  }
  const bars = document.querySelector('#grafica-gastos');
  if (bars) renderBars({fijos:bars.dataset.fijos,variables:bars.dataset.variables,imprevistos:bars.dataset.imprevistos});
  const money = amount => new Intl.NumberFormat('es-MX',{style:'currency',currency:'MXN',minimumFractionDigits:2}).format(Number(amount));
  // Las peticiones GET no necesitan CSRF; Django protege por sesión y dueño del recurso.
  document.querySelector('#rango-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const qs = new URLSearchParams(new FormData(form));
    const url = `${location.pathname}?${qs}`;
    const boton = form.querySelector('button[type="submit"]');
    if (boton) boton.disabled = true;
    try {
      // Datos JSON para métricas y gráficas; HTML nuevo para tarjetas dependientes del periodo.
      const [response,htmlResponse] = await Promise.all([
        fetch(`/api/resumen/?${qs}`,{credentials:'same-origin',headers:{'Accept':'application/json'}}),
        fetch(url,{credentials:'same-origin',headers:{'Accept':'text/html'}})
      ]);
      if (!response.ok || !htmlResponse.ok) throw new Error('Respuesta no disponible');
      const datos = await response.json();
      const documento = new DOMParser().parseFromString(await htmlResponse.text(),'text/html');
      const anteriores = document.querySelectorAll('.dashboard-columns');
      const nuevos = documento.querySelectorAll('.dashboard-columns');
      if (anteriores.length !== nuevos.length) throw new Error('Secciones no encontradas');
      anteriores.forEach((anterior,i) => anterior.replaceWith(nuevos[i]));
      Object.keys(datos).forEach(k => {
        document.querySelectorAll(`[data-metric="${k}"]`).forEach(el => el.textContent = money(datos[k]));
        document.querySelectorAll(`[data-bar-value="${k}"]`).forEach(el => el.textContent = money(datos[k]));
      });
      renderBars(datos);
      history.replaceState(null,'',url);
    } catch(e) {
      // Degradación progresiva: el formulario también funciona sin JavaScript.
      location.assign(url);
    } finally {
      if (boton) boton.disabled = false;
    }
  });
});
