# Documentación técnica y validaciones de Finanza.

## Diseño general

El sistema se organiza con MVT (modelo–vista–plantilla) de Django. `models.py` define claves foráneas, importes `DecimalField`, categorías globales y personales, presupuestos y vínculos contables. `forms.py` valida las entradas y limita por propietario las opciones. `views.py` filtra las consultas con `usuario=request.user`, impone permisos y ofrece páginas HTML y JSON. `services.py` concentra el cálculo exacto, el registro de abonos y las alertas con `transaction.atomic`. `middleware.py` limita sesiones inactivas a 20 minutos, actualiza la actividad y evita cachear páginas privadas.

## Entidades principales

- `Usuario`: cuenta de correo única (sin distinción entre mayúsculas), hash de contraseña y roles mediante `is_staff`; cuenta pendiente, bloqueo administrativo y último acceso.
- `VerificacionCorreo`: token UUID único, caducidad y fecha de consumo.
- `Categoria`: global (`usuario=NULL`) o personal, tipo y clasificación.
- `Movimiento`: ingreso o gasto efectivo, fecha y tipo, categoría y clave de operación única; `origen` indica si proviene de gasto fijo o abono.
- `Presupuesto`: periodo de siete, quince o un mes, categoría opcional, límite y fuente de un ingreso registrado; gasto y porcentaje calculados contra los movimientos, nunca copiados a un contador inestable.
- `Ahorro` y `AportacionAhorro`: meta y aportaciones, sin simular depósitos nuevos.
- `GastoFijo`: compromiso pendiente, vencido o pagado calculado a partir de sus fechas; relación 1:1 con el movimiento del pago y con el siguiente vencimiento.
- `Deuda` y `AbonoDeuda`: tipo cobrar/pagar, importe original, abonos, saldo y vencimiento.
- `Alerta`: presupuesto/deuda y tipo con restricciones para impedir mensajes duplicados.
- `RegistroImportacion`: rastreo de filas procedentes de una fuente SQLite anterior.

## Seguridad

El inicio utiliza correo y contraseña verificados por el backend Django. Las contraseñas se almacenan con hashes y se les aplican las validaciones de Django, además de requisitos de mayúsculas, minúsculas y dígitos. Los formularios POST contienen `{% csrf_token %}`. El ORM genera las consultas parametrizadas. El middleware bloquea el acceso y el almacenamiento en caché tras logout o inactividad. Los usuarios no pueden solicitar PK de registros de terceros para obtenerlos o modificarlos. Los endpoints JSON también exigen autenticación y propiedad. El administrador únicamente ve estadísticas agregadas; el panel nativo de Django no registra tablas financieras privadas.

## Pruebas de calidad

Se agregaron pruebas automáticas sobre autenticación, recuperación del estado de las cuentas, permisos, migraciones, listados, plantillas, periodicidad, capital de ahorro, movimientos, alertas, pagos fijos, deudas, JSON, seguridad y duplicación de abonos. Ejecuta `python manage.py test core`. Para hacer una prueba de correo real cambia el backend a SMTP y verifica el funcionamiento desde el servidor; la prueba en consola no es evidencia de que SMTP externo funcione.

## Configuraciones pendientes antes de publicación

1. Establecer `DEBUG=false`, `SECRET_KEY` segura y HTTPS real.
2. Configurar PostgreSQL, roles y respaldo de la base.
3. Introducir credenciales SMTP reales y validar entrega de correos.
4. Conectar un servidor WSGI/ASGI y servir correctamente los archivos estáticos.
5. Configurar copias de seguridad, rotación de secretos, registros y monitoreo.

## Detalles de contabilidad

Todo registro de ingreso o gasto efectivo aparece una sola vez en la tabla `Movimiento`; los límites presupuestales no se tratan como gastos nuevos. Una aportación a una meta reduce dinero disponible, no el balance de caja. Al cancelar una aportación se vuelve a liberar el monto. Registrar un deudor no aumenta el disponible hasta que se cobra el abono; registrar una deuda por pagar tampoco lo reduce hasta pagarse. Los pagos de deuda son flujos reales de caja, pero no se cargan por segunda vez al presupuesto de la compra originalmente financiada.
