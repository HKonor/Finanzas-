# Verificación de esta edición para GitHub

- La versión base del proyecto Django se probó previamente con SQLite: 36 pruebas aprobadas (ver `REPORTE_VERIFICACION.txt`).
- Esta edición agregó configuración de producción (`settings.py`, dependencias, scripts y `render.yaml`), workflow de pruebas en GitHub y vista previa estática (`docs/`).
- Se comprobó sintaxis Python con `compileall`, estructura YAML con `PyYAML`, presencia de páginas de muestra y empaquetado sin base SQLite ni `.env`.
- **NO se han podido ejecutar nuevamente las pruebas Django** en el contenedor de esta edición: no hay Django instalado ni acceso a la red para instalarlo.
- **NO se han comprobado** el despliegue Render, PostgreSQL en la nube, correo SMTP ni el pipeline GitHub Actions.
- GitHub Actions ejecutará `manage.py check`, `makemigrations --check --dry-run` y `test core` en cada push/PR; revisa el resultado en la pestaña Actions del repositorio.
- La vista previa `docs/index.html` muestra valores ficticios y navegación de muestra; **no se conecta a la BD ni representa una sesión real**.
