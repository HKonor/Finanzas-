# Finanza. | Proyecto Django compartible en GitHub

**Incluye la aplicación real**, con modelos, vistas, migraciones, pruebas y PostgreSQL; además, una **vista previa visual estática** (`docs/`) para que el equipo conozca la interfaz antes de instalar Django. Los números de la vista previa son *ficticios* y no forman parte de la aplicación real.

- **Guía de publicación**: [`SUBIR_A_GITHUB.md`](SUBIR_A_GITHUB.md).
- **Vista previa para GitHub Pages**: `docs/index.html` (activa Pages desde `main` y `/docs`).
- **Despliegue opcional**: `render.yaml` + `build.sh` + `start.sh`, con base PostgreSQL mediante variables de entorno. Si introduces `ADMIN_PASSWORD` y `ADMIN_EMAIL` en Render, se crea el administrador inicial al arrancar.
- **Pruebas automáticas**: `.github/workflows/django-tests.yml`.

> **Aviso para la demostración:** GitHub Pages muestra diseño HTML/CSS/JS, pero no puede ejecutar Django. Si publicas el servidor en Render gratis, sus puertos SMTP están bloqueados y la base PostgreSQL gratuita expira a los 30 días. Para verificación real de cuentas necesitas correo funcionando en un entorno compatible o integrar un proveedor vía API HTTPS.

---

# Finanza. — Sistema web de finanzas personales

Aplicación nueva desarrollada con **Python 3.11+ y Django 5.2**, HTML, CSS, JavaScript y base de datos relacional. Conserva como referencia la lógica del proyecto entregado en `finanzas1.zip`, con una arquitectura nueva y migraciones propias. **PostgreSQL es el motor recomendado para el servidor; SQLite facilita pruebas y uso local.**

## Instalar y ejecutar en Windows (Visual Studio Code)

1. Extrae **Finanza_Nueva.zip** y abre **la carpeta `Finanza_Nueva`** en VS Code mediante *Archivo > Abrir carpeta*.
2. Abre **Terminal > Terminal nuevo** (PowerShell) y escribe:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

3. Abre el archivo `.env` y configura lo siguiente para pruebas con SQLite:

```env
DEBUG=true
DB_ENGINE=sqlite
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
ADMIN_EMAIL=admin@finanza.local
ADMIN_USERNAME=administrador
ADMIN_PASSWORD=FinanzaDemo!2026
```

**Las credenciales anteriores son únicamente una sugerencia para tu instalación local de demostración.** El ZIP no incluye cuentas precreadas ni contraseñas reales del proyecto antiguo. La contraseña inicial se exigirá cambiar en el primer ingreso. **No uses esa contraseña ni `DEBUG=true` en producción.**

4. Ejecuta desde la misma terminal:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py cargar_categorias
.\.venv\Scripts\python.exe manage.py crear_admin
.\.venv\Scripts\python.exe manage.py runserver
```

5. Abre <http://127.0.0.1:8000/login/>.

   - Administrador: `admin@finanza.local`
   - Contraseña de demostración (si la configuraste igual): `FinanzaDemo!2026`
   - Panel administrativo: <http://127.0.0.1:8000/admin-panel/>
   - Panel del usuario: <http://127.0.0.1:8000/dashboard/>
   - Registro de usuario: <http://127.0.0.1:8000/registro/>

La instalación también puede iniciarse con **`INICIAR_WINDOWS.bat`**. Después de copiar `.env.example`, edita `.env` con `ADMIN_PASSWORD` y crea el administrador si todavía no existe.

### Activar una cuenta de usuario en desarrollo

1. Accede a `/registro/` y crea una cuenta de usuario normal.
2. Si utilizas `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`, **el enlace de activación se imprime en la terminal** en la que corre `runserver`. Cópialo y ábrelo.
3. Regresa a `/login/` e inicia sesión **con tu correo y contraseña**.
4. Los enlaces de activación caducan en 24 horas, solo se pueden usar una vez y pueden reenviarse.

## Utilizar PostgreSQL

1. Instala PostgreSQL y crea una base vacía, por ejemplo ejecutando en `psql` (con permisos adecuados):

```sql
CREATE USER finanza_app WITH PASSWORD 'elige_una_contrasena_segura';
CREATE DATABASE finanza_db OWNER finanza_app ENCODING 'UTF8';
```

2. Ajusta `.env`:

```env
DB_ENGINE=postgresql
DB_NAME=finanza_db
DB_USER=finanza_app
DB_PASSWORD=elige_una_contrasena_segura
DB_HOST=localhost
DB_PORT=5432
```

3. Ejecuta `migrate`, `cargar_categorias` y `crear_admin` contra esta nueva base. **No cambies de motor esperando que los registros de SQLite se copien automáticamente.**

En producción configura `DEBUG=false`, una `SECRET_KEY` aleatoria larga, `ALLOWED_HOSTS` adecuados, HTTPS, SMTP y las cookies seguras. El proyecto requiere una infraestructura de despliegue y servidor web para ponerse en línea; `runserver` es solo para desarrollo.

## Correo SMTP real

Por defecto se usa la consola para que puedas probar sin enviar mensajes reales. Para activar **envío auténtico**, utiliza en `.env`:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=tu-correo@gmail.com
EMAIL_HOST_PASSWORD=tu-contrasena-de-aplicacion
DEFAULT_FROM_EMAIL=tu-correo@gmail.com
DEFAULT_APP_URL=http://127.0.0.1:8000
```

Configura un servidor SMTP que admita este acceso y usa una contraseña de aplicación o credenciales compatibles con el proveedor. En producción usa el dominio HTTPS real en `DEFAULT_APP_URL`. **Jamás incorpores las claves reales al ZIP**. Si no se pueden enviar correos, el usuario permanece pendiente hasta conseguir un enlace válido.

La recuperación de contraseña utiliza el sistema nativo de tokens de Django, con validación de permisos y recuperación mediante correo.

## Módulos y comportamiento

| Módulo | Funciones |
|---|---|
| Autenticación | Registro, activación/reenvío por correo, login con correo, logout POST, restablecimiento y cambio de contraseña, sesión con límite de inactividad de 20 minutos. |
| Usuario | Panel con ingresos, gastos del periodo, caja histórica, ahorro reservado y dinero disponible. Estadísticas de gastos fijos, variables e imprevistos. |
| Movimientos | CRUD, filtros de tipo, clasificación, categoría, fecha y texto. Importes `DecimalField`. Periodicidad descriptiva de ingresos/gastos: solo se contabiliza un movimiento realmente registrado. |
| Presupuestos | Semanales (7 días), quincenales (15 días) o mensuales (un mes calendario), generales o por categoría; origen vinculado a movimientos reales de ingreso y asignación financiera no duplicada. Alertas al 80% y al superar el límite. |
| Gastos fijos | Pendiente, vencido, pagado, fecha de vencimiento y fecha de pago. Un pago genera una sola salida de caja y el siguiente vencimiento para obligaciones recurrentes. Puede anularse. |
| Deudas | Por pagar y por cobrar, vencimientos, estado, saldo restante, historial de abonos y anulación. |
| Ahorros | Metas, edición, eliminación, aportaciones, historial y anulación. Las transferencias al ahorro **no generan nuevos ingresos**. |
| Administración | Resumen global por cantidades, CRUD de usuarios, permisos, estado de cuentas y 25 categorías globales; no expone transacciones de los usuarios. |
| JSON | `/api/resumen/`, `/api/presupuestos/`, `/api/alertas/`, sujetos a autenticación y propiedad de datos. Dashboard consulta JSON con `fetch()`. |

### Reglas contables importantes

- El balance histórico es **ingresos cobrados menos gastos pagados** registrados en caja, sin mezclarlo con el balance filtrado por fechas.
- La **disponibilidad** es el balance histórico **menos las aportaciones que siguen reservadas en metas**. La meta no crea ni destruye dinero; cancelar una aportación libera la reserva.
- Los **presupuestos** delimitan consumos, **no descuentan otra vez** dinero del saldo. Su fuente de ingreso es un movimiento confirmado; la suma de asignaciones a un mismo ingreso no puede excederlo.
- Cada presupuesto totaliza los gastos de su categoría y rango. Los presupuestos general y específicos pueden cubrir gastos superpuestos, pero el balance de caja **nunca suma presupuestos** entre sí.
- Una **deuda registrada** representa una obligación y no entra en el saldo de caja hasta que se efectúa un abono. Los abonos generan una salida o entrada real y se excluyen del cálculo de consumo del presupuesto para no volver a contar compras financiadas ya registradas.
- Los gastos fijos pendientes no se contabilizan como pagos. Al marcarse pagados, aparece el movimiento una sola vez. El siguiente vencimiento recurrente es una **obligación nueva sin cargo todavía**.
- Se usan identificadores únicos para evitar abonos y aportaciones duplicados por reenvío del mismo formulario. Los movimientos manuales también reciben un identificador único de operación.
- Las alertas se generan o reactivan por cambio de condición y no se repiten constantemente.
- No se imprimen tickets ni reportes, conforme a las observaciones.

## Importar registros de la versión anterior de forma segura

**Antes:** realiza una copia de seguridad de ambas bases. El ZIP de entrega no contiene la base antigua ni sus contraseñas.

La importación **no copia usuarios, contraseñas ni roles**. Primero crea en Finanza. las cuentas correspondientes con el mismo correo de las cuentas del proyecto anterior. Solo se importarán datos de esos usuarios ya registrados. El archivo SQLite anterior se abre en **modo solo lectura**. El comando busca categorías y movimientos, y al aplicar intenta también presupuestos compatibles y metas de ahorro. Las alertas se regeneran; no se duplican las del archivo original.

```powershell
.\.venv\Scripts\python.exe manage.py importar_legado --ruta "C:\ruta\al\proyecto_viejo\db.sqlite3"
# Solo si el resumen te parece correcto:
.\.venv\Scripts\python.exe manage.py importar_legado --ruta "C:\ruta\al\proyecto_viejo\db.sqlite3" --apply
```

Las importaciones se marcan en `RegistroImportacion` para evitar duplicados al aplicar otra vez desde la misma ruta. Las filas incompatibles se omiten sin copiar contraseñas. El modelo viejo tiene una migración de `origen_dinero` que no coincide con sus modelos/base: **el importador no interpreta esa cadena como un ingreso y no la asocia automáticamente**. La fuente de los presupuestos importados se debe revisar y elegir manualmente si corresponde.

## Pruebas automatizadas

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test core -v 2
```

Se crea una base de pruebas aislada para no dañar los registros de uso. Las pruebas cubren registro y activación de cuentas, roles, privacidad, saldos, filtros, límites, fuentes de ingreso, alertas, gasto recurrente, deudas, aportaciones, JSON e inicio administrativo. En el entorno de preparación se ejecutaron con SQLite/Django 5.2; **el despliegue con PostgreSQL y el envío SMTP real deben probarse con tu servidor y credenciales**.

## Estructura principal

```text
Finanza_Nueva/
├── finanza_project/       # Configuración, URL base, ASGI y WSGI
├── core/
│   ├── models.py          # Tablas y restricciones
│   ├── forms.py           # Validaciones y aislamiento por usuario
│   ├── views.py           # Vistas, roles y endpoints JSON
│   ├── services.py        # Cálculos, pagos, alertas y transacciones atómicas
│   ├── middleware.py      # Inactividad, últimas actividades y no-cache
│   ├── migrations/        # Versiones de la base de datos nueva
│   ├── tests.py           # Pruebas automatizadas
│   └── management/commands/
│       ├── cargar_categorias.py
│       ├── crear_admin.py
│       └── importar_legado.py
├── templates/             # HTML Django: usuario, admin y acceso
├── static/css/            # Diseño responsivo
├── static/js/             # Interacción con fetch y JSON
├── requirements.txt
├── .env.example
├── INICIAR_WINDOWS.bat
└── manage.py
```

**Observaciones de entrega:** el proyecto se probó con SQLite y un backend local de correo. No se proporcionan datos personales antiguos ni credenciales SMTP reales. La periodicidad informativa de ingresos no genera depósitos automáticos: solo los ingresos efectivamente registrados se consideran dinero disponible. No hay interfaz para imprimir.
