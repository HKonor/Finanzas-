from django.urls import path
from django.contrib.auth import views as auth_views
from . import views as v
urlpatterns = [
 path('',v.inicio,name='inicio'),path('registro/',v.registro,name='registro'),path('login/',v.login_view,name='login'),path('logout/',v.logout_view,name='logout'),
 path('activar/<uuid:token>/',v.activar,name='activar_cuenta'),path('reenviar-activacion/',v.reenviar_activacion,name='reenviar_activacion'),
 path('recuperar/',auth_views.PasswordResetView.as_view(template_name='auth/recuperar.html',email_template_name='auth/recuperar_email.txt',subject_template_name='auth/recuperar_asunto.txt',success_url='/recuperar/enviado/'),name='password_reset'),
 path('recuperar/enviado/',auth_views.PasswordResetDoneView.as_view(template_name='auth/recuperar_enviado.html'),name='password_reset_done'),
 path('recuperar/confirmar/<uidb64>/<token>/',auth_views.PasswordResetConfirmView.as_view(template_name='auth/recuperar_confirmar.html',success_url='/recuperar/listo/'),name='password_reset_confirm'),
 path('recuperar/listo/',auth_views.PasswordResetCompleteView.as_view(template_name='auth/recuperar_listo.html'),name='password_reset_complete'),
 path('cuenta/perfil/',v.perfil,name='perfil'),path('cuenta/password/',v.cambiar_password,name='cambiar_password'),
 path('dashboard/',v.dashboard,name='dashboard'),
 path('movimientos/',v.movimientos_lista,name='movimientos_lista'),path('movimientos/nuevo/',v.movimiento_crear,name='movimiento_crear'),path('movimientos/<int:pk>/editar/',v.movimiento_editar,name='movimiento_editar'),path('movimientos/<int:pk>/eliminar/',v.movimiento_eliminar,name='movimiento_eliminar'),
 path('presupuestos/',v.presupuestos_lista,name='presupuestos_lista'),path('presupuestos/nuevo/',v.presupuesto_crear,name='presupuesto_crear'),path('presupuestos/<int:pk>/editar/',v.presupuesto_editar,name='presupuesto_editar'),path('presupuestos/<int:pk>/eliminar/',v.presupuesto_eliminar,name='presupuesto_eliminar'),
 path('ahorros/',v.ahorros_lista,name='ahorros_lista'),path('ahorros/nuevo/',v.ahorro_crear,name='ahorro_crear'),path('ahorros/<int:pk>/editar/',v.ahorro_editar,name='ahorro_editar'),path('ahorros/<int:pk>/eliminar/',v.ahorro_eliminar,name='ahorro_eliminar'),path('ahorros/<int:pk>/aportar/',v.ahorro_aportar,name='ahorro_aportar'),path('aportaciones/<int:pk>/anular/',v.ahorro_anular_aportacion,name='ahorro_anular_aportacion'),
 path('fijos/',v.fijos_lista,name='fijos_lista'),path('fijos/nuevo/',v.fijo_crear,name='fijo_crear'),path('fijos/<int:pk>/editar/',v.fijo_editar,name='fijo_editar'),path('fijos/<int:pk>/eliminar/',v.fijo_eliminar,name='fijo_eliminar'),path('fijos/<int:pk>/pagar/',v.fijo_pagar,name='fijo_pagar'),path('fijos/<int:pk>/anular/',v.fijo_anular,name='fijo_anular'),
 path('gastos/fijos/',v.gastos_clasificacion,{'clasificacion':'FIJO'},name='gastos_fijos'),path('gastos/variables/',v.gastos_clasificacion,{'clasificacion':'VARIABLE'},name='gastos_variables'),path('gastos/imprevistos/',v.gastos_clasificacion,{'clasificacion':'IMPREVISTO'},name='gastos_imprevistos'),
 path('deudas/',v.deudas_lista,name='deudas_lista'),path('deudas/nueva/',v.deuda_crear,name='deuda_crear'),path('deudas/<int:pk>/editar/',v.deuda_editar,name='deuda_editar'),path('deudas/<int:pk>/eliminar/',v.deuda_eliminar,name='deuda_eliminar'),path('deudas/<int:pk>/abonar/',v.deuda_abonar,name='deuda_abonar'),path('abonos/<int:pk>/anular/',v.deuda_anular_abono,name='deuda_anular_abono'),
 path('categorias/',v.categorias_lista,name='categorias_lista'),path('categorias/nueva/',v.categoria_crear,name='categoria_crear'),path('categorias/<int:pk>/editar/',v.categoria_editar,name='categoria_editar'),path('categorias/<int:pk>/eliminar/',v.categoria_eliminar,name='categoria_eliminar'),
 path('alertas/<int:pk>/leer/',v.marcar_alerta,name='marcar_alerta'),
 path('api/resumen/',v.api_resumen,name='api_resumen'),path('api/presupuestos/',v.api_presupuestos,name='api_presupuestos'),path('api/alertas/',v.api_alertas,name='api_alertas'),
 path('admin-panel/',v.admin_dashboard,name='admin_dashboard'),path('admin-panel/usuarios/',v.admin_usuarios,name='admin_usuarios'),path('admin-panel/usuarios/nuevo/',v.admin_usuario_crear,name='admin_usuario_crear'),path('admin-panel/usuarios/<int:pk>/editar/',v.admin_usuario_editar,name='admin_usuario_editar'),path('admin-panel/usuarios/<int:pk>/toggle/',v.admin_toggle_usuario,name='admin_toggle_usuario'),
 path('admin-panel/categorias/',v.admin_categorias,name='admin_categorias'),path('admin-panel/categorias/nueva/',v.admin_categoria_crear,name='admin_categoria_crear'),path('admin-panel/categorias/<int:pk>/editar/',v.admin_categoria_editar,name='admin_categoria_editar'),path('admin-panel/categorias/<int:pk>/toggle/',v.admin_categoria_toggle,name='admin_categoria_toggle'),
]
