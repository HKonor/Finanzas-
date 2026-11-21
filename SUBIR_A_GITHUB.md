# Compartir Finanza. con tu equipo desde GitHub

## 1. Subir archivos (sin terminal)

1. Entra a https://github.com/new y crea un repositorio llamado `finanza-django`.
2. No inicialices el repositorio con README ni `.gitignore`, porque ya están aquí.
3. Descomprime el ZIP `Finanza_GitHub.zip`.
4. Dentro del repositorio de GitHub, usa **Add file → Upload files** y arrastra **el contenido de la carpeta `Finanza_GitHub`**, no el ZIP entero.
5. Comprueba que aparezcan en la raíz `manage.py`, `requirements.txt`, `core`, `templates`, `static`, `render.yaml`, `.github`, `docs`.
6. Pulsa **Commit changes**.
7. Envía el enlace del repositorio a tu equipo. Para limitar el acceso al código, usa un repositorio privado e invita colaboradores (Settings → Collaborators).

**Muy importante:** NO subas `.env`, `db.sqlite3`, contraseñas ni archivos de usuarios. GitHub web permite subir archivos uno por uno o arrastrar carpetas en algunos navegadores; si el navegador no conserva carpetas ocultas como `.github`, usa Git desde VS Code (método siguiente).

## 2. Subir con Git desde Visual Studio Code (recomendado)

Abre **la carpeta `Finanza_GitHub`**, NO la carpeta padre. Abre Terminal → PowerShell:

```powershell
git init
git branch -M main
git add .
git status
git commit -m "Finanza: proyecto Django y vista previa de GitHub"
git remote add origin https://github.com/TU_USUARIO/finanza-django.git
git push -u origin main
```

Antes de `git add .`, ejecuta `git status` si copiaste archivos adicionales y confirma que ningún `.env` o SQLite aparezca. Si Git pide nombre/correo de autor, configura `git config --global user.name "Tu Nombre"` y `git config --global user.email "tu@correo"`.

## 3. Activar vista visual de GitHub Pages

1. Abre tu repositorio → **Settings → Pages**.
2. En **Build and deployment**, Source = **Deploy from a branch**.
3. Branch = **main** y carpeta **/docs**, después **Save**.
4. Al terminar la publicación aparecerá un enlace parecido a: `https://TU_USUARIO.github.io/finanza-django/`.
5. Comparte el enlace: podrán alternar entre *Panel de usuario*, *Panel de administrador* e *Inicio de sesión*.

Esta vista es de solo lectura, utiliza datos inventados etiquetados como ejemplo y **no se conecta a una base de datos**. Para usar las funciones reales hay que abrir Django localmente o desplegar el servidor.

## 4. Desplegar el proyecto real con Django y PostgreSQL (opcional)

1. Usa https://dashboard.render.com/ y crea un **Blueprint**, conectando el repositorio de GitHub.
2. Render detectará `render.yaml` y propondrá un servicio Django `finanza-web` y una base `finanza-postgres`.
3. Introduce `ADMIN_EMAIL` (correo tuyo para el administrador) y `ADMIN_PASSWORD` (una contraseña inicial segura) cuando Render lo solicite. Esos valores quedan en el panel privado de Render, no en GitHub. `SECRET_KEY` se genera automáticamente. Nunca escribas claves en el repositorio.
4. Espera a que aparezca el dominio `https://<servicio>.onrender.com/login/`.
5. El proceso `start.sh` ejecuta migraciones, carga las 25 categorías y, si existe `ADMIN_PASSWORD`, crea el administrador inicial antes de arrancar Gunicorn. El admin debe cambiar su clave al primer inicio. Para evitar acceso indebido, no compartas esta cuenta públicamente.
6. El `SECRET_KEY` se genera en Render; `DATABASE_URL` se obtiene de PostgreSQL; `DEBUG=false` y los hosts/CSRF se ajustan al dominio asignado.

**Limitación REAL del plan gratis de Render:** bloquea los puertos de salida SMTP 25, 465 y 587, por lo que el registro con verificación por correo **no funcionará con Gmail SMTP** en ese plan. Para cuentas reales necesitas un proveedor de correo que use API HTTPS (requiere integración adicional), u otro alojamiento/plan que permita SMTP. Además, la base Postgres gratis **caduca después de 30 días**: no la uses para datos importantes. La vista de GitHub Pages no presenta estas limitaciones porque es puramente estática.

El proyecto NO se ha desplegado en Render desde aquí. Antes de compartir acceso real, configura el correo correctamente, crea cuentas de prueba sin datos personales y comprueba HTTPS.

## 5. Ejecutar y desarrollar en equipo

Cada integrante clona el repositorio, crea su propio `.env` a partir de `.env.example` e instala las dependencias. Los detalles están en `README.md`. Nunca se comparten contraseñas ni la base de datos con Git.

Trabajo en ramas:

```powershell
git checkout -b mejora/interfaz
# Edita y prueba código...
git add .
git commit -m "Mejora estilos"
git push -u origin mejora/interfaz
```

Después abre un Pull Request en GitHub. El workflow `.github/workflows/django-tests.yml` revisa automáticamente código, migraciones y pruebas al subir cambios.
