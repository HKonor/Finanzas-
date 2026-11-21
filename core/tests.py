"""Pruebas de regresión con base independiente y entorno de correo local."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
from django.test import TestCase,Client,override_settings
from django.core import mail
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from .models import Usuario,Categoria,Movimiento,Presupuesto,Ahorro,GastoFijo,Deuda,Alerta,VerificacionCorreo
from .forms import MovimientoForm, PresupuestoForm
from .services import (resumen,actualizar_alertas,aportar_ahorro,pagar_gasto_fijo,
                       cancelar_pago_fijo,abonar_deuda,activar_cuenta,enviar_activacion)

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class FinanzaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.u=Usuario.objects.create_user(username='ana',email='ana@ejemplo.mx',password='PruebaSeguro123!',correo_verificado=True)
        cls.u2=Usuario.objects.create_user(username='luis',email='luis@ejemplo.mx',password='PruebaSeguro123!',correo_verificado=True)
        cls.admin=Usuario.objects.create_superuser(username='admin',email='admin@ejemplo.mx',password='PruebaSeguro123!',correo_verificado=True)
        cls.ing=Categoria.objects.create(nombre='Sueldo',tipo='INGRESO',clasificacion='FIJO')
        cls.fijo=Categoria.objects.create(nombre='Renta',tipo='GASTO',clasificacion='FIJO')
        cls.variable=Categoria.objects.create(nombre='Compras',tipo='GASTO',clasificacion='VARIABLE')
        cls.otro=Categoria.objects.create(nombre='Otros Ingresos',tipo='INGRESO',clasificacion='VARIABLE')
        cls.pagar=Categoria.objects.create(nombre='Pago de Deudas y Préstamos',tipo='GASTO',clasificacion='FIJO')
        cls.hoy=date(2026,11,21)

    def ingreso(self,importe=1000,usuario=None):
        return Movimiento.objects.create(usuario=usuario or self.u,categoria=self.ing,tipo='INGRESO',importe=Decimal(str(importe)),descripcion='Sueldo',fecha=self.hoy)
    def gasto(self,importe=50,usuario=None,fecha=None,categoria=None):
        return Movimiento.objects.create(usuario=usuario or self.u,categoria=categoria or self.variable,tipo='GASTO',importe=Decimal(str(importe)),descripcion='Compras',fecha=fecha or self.hoy)
    def entrar(self,usuario=None):
        self.client.force_login(usuario or self.u)

    def test_login_correo_roles_y_logout(self):
        r=self.client.post('/login/',{'email':self.u.email,'password':'PruebaSeguro123!'})
        self.assertRedirects(r,'/dashboard/',fetch_redirect_response=False)
        self.assertEqual(self.client.get('/admin-panel/').url,'/dashboard/')
        self.assertEqual(self.client.post('/logout/').url,'/login/')
        self.assertEqual(self.client.get('/dashboard/').status_code,302)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/admin-panel/').status_code,200)
        self.assertEqual(self.client.get('/dashboard/').url,'/admin-panel/')

    def test_pendiente_no_inicia_y_verificacion_unica(self):
        u=Usuario.objects.create_user(username='pendiente',email='p@ejemplo.mx',password='PruebaSeguro123!',correo_verificado=False,is_active=False)
        t=enviar_activacion(u)
        self.assertEqual(len(mail.outbox),1)
        self.assertEqual(self.client.post('/login/',{'email':u.email,'password':'PruebaSeguro123!'}).status_code,200)
        self.assertTrue(activar_cuenta(t.token))
        self.assertFalse(activar_cuenta(t.token))
        self.assertTrue(Usuario.objects.get(pk=u.pk).correo_verificado)
        self.assertEqual(self.client.post('/login/',{'email':u.email,'password':'PruebaSeguro123!'}).status_code,302)

    def test_enlace_expirado_y_reenvio(self):
        u=Usuario.objects.create_user(username='nuevo',email='n@ejemplo.mx',password='PruebaSeguro123!',correo_verificado=False)
        a=enviar_activacion(u)
        b=enviar_activacion(u)
        self.assertNotEqual(a.token,b.token)
        self.assertFalse(activar_cuenta(a.token))
        VerificacionCorreo.objects.filter(pk=b.pk).update(vence=timezone.now()-timedelta(seconds=1))
        self.assertFalse(activar_cuenta(b.token))

    def test_registro_http_envia_email(self):
        r=self.client.post('/registro/',{'username':'registrada','first_name':'Ana','last_name':'Ramírez',
          'email':'registrada@example.mx','password1':'PruebaSeguro123!','password2':'PruebaSeguro123!'})
        self.assertEqual(r.status_code,302)
        self.assertFalse(Usuario.objects.get(username='registrada').correo_verificado)
        self.assertTrue(mail.outbox)

    def test_balance_periodo_vs_historico_y_ahorro(self):
        self.ingreso(1000)
        self.gasto(100)
        self.gasto(70,fecha=date(2026,10,14))
        r=resumen(self.u,date(2026,11,1),date(2026,11,30))
        self.assertEqual(r['ingresos'],1000)
        self.assertEqual(r['gastos'],100)
        self.assertEqual(r['balance_periodo'],900)
        self.assertEqual(r['balance_historico'],830)

    def test_editar_eliminar_movimiento_recalcula(self):
        self.ingreso(1000)
        m=self.gasto(200)
        self.entrar()
        r=self.client.post(reverse('movimiento_editar',args=[m.pk]),{'tipo':'GASTO','categoria':self.variable.pk,'importe':'120.00','descripcion':'Editado','fecha':'2026-11-21','periodicidad':'UNICO','token_operacion':str(uuid4())})
        self.assertEqual(r.status_code,302)
        self.assertEqual(resumen(self.u)['disponible'],880)
        self.client.post(reverse('movimiento_eliminar',args=[m.pk]))
        self.assertEqual(resumen(self.u)['disponible'],1000)

    def test_aislamiento_de_datos_ajenos(self):
        m=self.gasto(30,usuario=self.u2)
        self.entrar()
        self.assertEqual(self.client.get(reverse('movimiento_editar',args=[m.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse('movimiento_eliminar',args=[m.pk])).status_code,404)
        self.assertEqual(self.client.get(reverse('api_resumen')).json()['gastos'],'0.00')

    def test_categoria_de_otro_usuario_prohibida(self):
        cat=Categoria.objects.create(nombre='Solo Luis',tipo='GASTO',clasificacion='VARIABLE',usuario=self.u2)
        form=MovimientoForm(data={'tipo':'GASTO','categoria':cat.pk,'importe':'1','descripcion':'X','fecha':'2026-11-21'},usuario=self.u)
        self.assertFalse(form.is_valid())
        with self.assertRaises(ValidationError):
            Movimiento.objects.create(usuario=self.u,tipo='GASTO',categoria=cat,importe=1,descripcion='Intento',fecha=self.hoy)

    def test_validaciones_importe_tipo_categoria(self):
        with self.assertRaises(ValidationError):self.gasto(-1)
        with self.assertRaises(ValidationError):
            Movimiento.objects.create(usuario=self.u,tipo='GASTO',categoria=self.ing,importe=10,descripcion='Mal',fecha=self.hoy)

    def test_presupuesto_por_fecha_categoria_y_alerta(self):
        self.ingreso(400)
        p=Presupuesto.objects.create(usuario=self.u,nombre='Comida',categoria=self.variable,monto_limite=Decimal('100'),
                                   periodo='SEMANAL',fecha_inicio=date(2026,11,20),fecha_fin=date(2026,11,26))
        self.gasto(81)
        self.gasto(25,categoria=self.fijo)
        self.gasto(120,fecha=date(2026,10,1))
        self.assertEqual(p.gasto_actual(),81)
        actualizar_alertas(self.u)
        self.assertEqual(Alerta.objects.filter(usuario=self.u,activa=True,tipo='CERCA').count(),1)
        actualizar_alertas(self.u)
        self.assertEqual(Alerta.objects.filter(usuario=self.u,activa=True,tipo='CERCA').count(),1)
        g=self.gasto(25)
        actualizar_alertas(self.u)
        self.assertEqual(Alerta.objects.filter(usuario=self.u,activa=True,tipo='EXCESO').count(),1)
        g.delete();actualizar_alertas(self.u)
        self.assertEqual(Alerta.objects.filter(usuario=self.u,activa=True,tipo='EXCESO').count(),0)
        self.assertEqual(Alerta.objects.filter(usuario=self.u,activa=True,tipo='CERCA').count(),1)

    def test_periodicidad_valida(self):
        form=PresupuestoForm(data={'nombre':'Mal','monto_limite':'100','periodo':'SEMANAL','fecha_inicio':'2026-11-01','fecha_fin':'2026-11-30','categoria':''},usuario=self.u)
        self.assertFalse(form.is_valid())
        self.assertIn('fecha_fin',form.errors)

    def test_presupuesto_fuente_no_duplicada(self):
        f=self.ingreso(500)
        base={'usuario':self.u,'monto_limite':Decimal('300'),'periodo':'SEMANAL',
              'fecha_inicio':date(2026,11,21),'fecha_fin':date(2026,11,27),'fuente_ingreso':f}
        p=Presupuesto.objects.create(nombre='Uno',**base)
        otro=Presupuesto(nombre='Dos',**base)
        with self.assertRaises(ValidationError):otro.clean()
        self.assertEqual(p.fuente_ingreso,f)

    def test_ahorro_no_es_nuevo_ingreso(self):
        self.ingreso(1000)
        a=Ahorro.objects.create(usuario=self.u,titulo='Viaje',monto_objetivo=600)
        aportar_ahorro(a,Decimal('200.00'))
        r=resumen(self.u)
        self.assertEqual(r['ingresos'],1000)
        self.assertEqual(r['ahorrado'],200)
        self.assertEqual(r['disponible'],800)
        with self.assertRaises(ValidationError):aportar_ahorro(a,Decimal('1000'))

    def test_gasto_fijo_idempotente_y_anulable(self):
        self.ingreso(1000)
        g=GastoFijo.objects.create(usuario=self.u,categoria=self.fijo,concepto='Internet',importe=250,
                                  periodicidad='MENSUAL',fecha_vencimiento=self.hoy)
        pagar_gasto_fijo(g.pk,self.u,fecha=self.hoy)
        pagar_gasto_fijo(g.pk,self.u,fecha=self.hoy)
        self.assertEqual(Movimiento.objects.filter(usuario=self.u,tipo='GASTO').count(),1)
        self.assertEqual(resumen(self.u)['disponible'],750)
        cancelar_pago_fijo(g.pk,self.u)
        self.assertEqual(resumen(self.u)['disponible'],1000)

    def test_deuda_abono_parcial_total_sin_dup_presupuesto(self):
        self.ingreso(1000)
        p=Presupuesto.objects.create(usuario=self.u,nombre='Total',monto_limite=500,periodo='SEMANAL',fecha_inicio=self.hoy,fecha_fin=self.hoy+timedelta(days=6))
        d=Deuda.objects.create(usuario=self.u,persona='Luis',tipo='PAGAR',descripcion='Préstamo',importe_original=300,
                               fecha_registro=self.hoy,fecha_vencimiento=self.hoy+timedelta(days=1))
        abonar_deuda(d.pk,self.u,Decimal('100'),fecha=self.hoy)
        self.assertEqual(d.saldo_pendiente,Decimal('200'))
        self.assertEqual(d.estado,'Pago parcial') if timezone.localdate() <= d.fecha_vencimiento else None
        self.assertEqual(p.gasto_actual(),0)
        abonar_deuda(d.pk,self.u,Decimal('200'),fecha=self.hoy)
        self.assertEqual(d.saldo_pendiente,0)
        self.assertEqual(resumen(self.u)['disponible'],700)
        with self.assertRaises(ValidationError):abonar_deuda(d.pk,self.u,Decimal('10'))

    def test_deuda_por_cobrar_aumenta_caja(self):
        d=Deuda.objects.create(usuario=self.u,persona='Paco',tipo='COBRAR',descripcion='Pago',importe_original=80,
                               fecha_registro=self.hoy,fecha_vencimiento=self.hoy+timedelta(days=1))
        abonar_deuda(d.pk,self.u,Decimal('20'),fecha=self.hoy)
        self.assertEqual(resumen(self.u)['ingresos'],20)

    def test_api_json_y_control_acceso(self):
        self.assertEqual(self.client.get('/api/resumen/').status_code,302)
        self.entrar()
        self.assertIn('grafica',self.client.get('/api/resumen/').json())
        self.assertIn('presupuestos',self.client.get('/api/presupuestos/').json())
        self.assertEqual(self.client.post('/api/resumen/').status_code,405)
        self.assertEqual(self.client.get('/api/resumen/?desde=2026-12-31&hasta=2026-01-01').status_code,400)

    def test_ultimo_admin_no_se_desactiva(self):
        self.entrar(self.admin)
        r=self.client.post(reverse('admin_toggle_usuario',args=[self.admin.pk]))
        self.assertEqual(r.status_code,302)
        self.assertTrue(Usuario.objects.get(pk=self.admin.pk).is_active)

    def test_idempotencia_de_aportaciones_y_abonos(self):
        self.ingreso(1000)
        a=Ahorro.objects.create(usuario=self.u,titulo='Meta',monto_objetivo=300)
        x=uuid4()
        aportar_ahorro(a,Decimal('100'),x)
        aportar_ahorro(a,Decimal('100'),x)
        self.assertEqual(a.monto_actual,100)
        d=Deuda.objects.create(usuario=self.u,persona='Otro',tipo='PAGAR',descripcion='Abono',importe_original=300,fecha_registro=self.hoy,fecha_vencimiento=self.hoy)
        t=uuid4()
        abonar_deuda(d.pk,self.u,Decimal('50'),token_operacion=t)
        abonar_deuda(d.pk,self.u,Decimal('50'),token_operacion=t)
        self.assertEqual(d.saldo_pendiente,250)
        self.assertEqual(Movimiento.objects.filter(usuario=self.u,tipo='GASTO').count(),1)

    def test_actividad_y_cache(self):
        self.entrar()
        r=self.client.get('/dashboard/')
        self.assertEqual(r.status_code,200)
        self.assertIn('no-store',r['Cache-Control'])
        self.assertIsNotNone(Usuario.objects.get(pk=self.u.pk).ultima_actividad)

    def test_paginas_usuario_sin_errores_de_plantilla(self):
        self.entrar()
        for ruta in ['/dashboard/','/movimientos/','/presupuestos/','/ahorros/','/fijos/','/deudas/',
                     '/categorias/','/cuenta/perfil/','/cuenta/password/','/movimientos/nuevo/',
                     '/presupuestos/nuevo/','/ahorros/nuevo/','/fijos/nuevo/','/deudas/nueva/','/categorias/nueva/']:
            with self.subTest(ruta=ruta):self.assertEqual(self.client.get(ruta).status_code,200)

    def test_paginas_admin_sin_errores_de_plantilla(self):
        self.entrar(self.admin)
        for ruta in ['/admin-panel/','/admin-panel/usuarios/','/admin-panel/usuarios/nuevo/',
                     '/admin-panel/categorias/','/admin-panel/categorias/nueva/','/cuenta/perfil/']:
            with self.subTest(ruta=ruta):self.assertEqual(self.client.get(ruta).status_code,200)

    def test_periodicidad_fijo_genera_siguiente_solo_una_vez(self):
        g=GastoFijo.objects.create(usuario=self.u,categoria=self.fijo,concepto='Renta',importe=500,
                    periodicidad='MENSUAL',fecha_vencimiento=date(2026,1,31))
        pagar_gasto_fijo(g.pk,self.u,fecha=date(2026,2,1))
        pagar_gasto_fijo(g.pk,self.u,fecha=date(2026,2,1))
        siguiente=GastoFijo.objects.get(anterior=g)
        self.assertEqual(siguiente.fecha_vencimiento,date(2026,2,28))
        self.assertEqual(GastoFijo.objects.filter(anterior=g).count(),1)
        cancelar_pago_fijo(g.pk,self.u)
        self.assertFalse(GastoFijo.objects.filter(anterior=g).exists())

    def test_anular_abono_y_aportacion_restauran_saldos(self):
        from .services import eliminar_aportacion,anular_abono_deuda
        self.ingreso(500)
        a=Ahorro.objects.create(usuario=self.u,titulo='Casa',monto_objetivo=300)
        aporte=aportar_ahorro(a,Decimal('50'))
        self.assertEqual(resumen(self.u)['disponible'],450)
        eliminar_aportacion(aporte.pk,self.u)
        self.assertEqual(resumen(self.u)['disponible'],500)
        d=Deuda.objects.create(usuario=self.u,persona='L',tipo='PAGAR',descripcion='Préstamo',importe_original=100,fecha_registro=self.hoy,fecha_vencimiento=self.hoy)
        abono=abonar_deuda(d.pk,self.u,Decimal('30'))
        self.assertEqual(resumen(self.u)['disponible'],470)
        anular_abono_deuda(abono.pk,self.u)
        self.assertEqual(d.saldo_pendiente,100)
        self.assertEqual(resumen(self.u)['disponible'],500)

    def test_correo_unico_independiente_de_mayusculas(self):
        with self.assertRaises(IntegrityError):
            with self.captureOnCommitCallbacks(execute=True):
                Usuario.objects.create_user(username='ana2',email='ANA@EJEMPLO.MX',password='PruebaSeguro123!')

    def test_usuario_bloqueado_admin_no_se_reactiva_por_enlace(self):
        u=Usuario.objects.create_user(username='pendiente2',email='pendiente2@example.mx',password='PruebaSeguro123!',correo_verificado=False,is_active=False)
        token=enviar_activacion(u)
        Usuario.objects.filter(pk=u.pk).update(bloqueado_admin=True)
        self.assertFalse(activar_cuenta(token.token))
        self.assertFalse(Usuario.objects.get(pk=u.pk).is_active)

    def test_pago_fijo_solo_por_post(self):
        g=GastoFijo.objects.create(usuario=self.u,categoria=self.fijo,concepto='Internet',importe=200,fecha_vencimiento=self.hoy)
        self.entrar()
        self.assertEqual(self.client.get(reverse('fijo_pagar',args=[g.pk])).status_code,405)
        self.assertEqual(self.client.post(reverse('fijo_pagar',args=[g.pk])).status_code,302)
        self.assertEqual(self.client.post(reverse('fijo_pagar',args=[g.pk])).status_code,302)
        self.assertEqual(Movimiento.objects.filter(usuario=self.u,tipo='GASTO').count(),1)

    def test_cambio_password_obligatorio_admin(self):
        self.admin.cambiar_password_obligatorio=True
        self.admin.save(update_fields=['cambiar_password_obligatorio'])
        self.entrar(self.admin)
        self.assertEqual(self.client.get('/admin-panel/').url,'/cuenta/password/')

    def test_flujo_http_registro_de_movimientos_y_presupuesto(self):
        self.entrar()
        token=str(uuid4())
        datos={'tipo':'INGRESO','categoria':self.ing.pk,'importe':'600.00','descripcion':'Ingreso real','fecha':'2026-11-21',
               'periodicidad':'MENSUAL','token_operacion':token}
        r=self.client.post('/movimientos/nuevo/',datos)
        self.assertEqual(r.status_code,302)
        self.assertEqual(self.client.post('/movimientos/nuevo/',datos).status_code,302)
        self.assertEqual(Movimiento.objects.filter(usuario=self.u).count(),1)
        m=Movimiento.objects.get(usuario=self.u)
        r=self.client.post('/presupuestos/nuevo/',{'nombre':'Comida','categoria':self.variable.pk,
            'monto_limite':'250.00','periodo':'SEMANAL','fecha_inicio':'2026-11-21','fecha_fin':'2026-11-27','fuente_ingreso':m.pk})
        self.assertEqual(r.status_code,302)
        self.assertEqual(Presupuesto.objects.filter(usuario=self.u).count(),1)

    def test_flujo_http_creacion_de_categoria_personal(self):
        self.entrar()
        datos={'nombre':'Artes','tipo':'GASTO','clasificacion':'VARIABLE','categoria_padre':'','activa':'on'}
        r=self.client.post('/categorias/nueva/',datos)
        self.assertEqual(r.status_code,302)
        self.assertTrue(Categoria.objects.filter(usuario=self.u,nombre='Artes').exists())
        cat=Categoria.objects.get(usuario=self.u,nombre='Artes')
        form=MovimientoForm(data={'tipo':'GASTO','categoria':cat.pk,'importe':'12.00','descripcion':'Libros',
            'fecha':'2026-11-21','periodicidad':'UNICO','token_operacion':str(uuid4())},usuario=self.u)
        self.assertTrue(form.is_valid(),form.errors)

    def test_flujo_http_deuda_ahorro_abonos(self):
        self.entrar()
        self.ingreso(900)
        r=self.client.post('/ahorros/nuevo/',{'titulo':'Viaje','monto_objetivo':'200','porcentaje_sugerido':'10','fecha_limite':'2027-01-01'})
        self.assertEqual(r.status_code,302)
        a=Ahorro.objects.get(usuario=self.u)
        self.assertEqual(self.client.post(f'/ahorros/{a.pk}/aportar/',{'importe':'80','token_operacion':str(uuid4())}).status_code,302)
        self.assertEqual(a.monto_actual,80)
        r=self.client.post('/deudas/nueva/',{'persona':'Banco','tipo':'PAGAR','descripcion':'Crédito','importe_original':'100.00','fecha_registro':'2026-11-21','fecha_vencimiento':'2026-12-01'})
        self.assertEqual(r.status_code,302)
        d=Deuda.objects.get(usuario=self.u)
        self.assertEqual(self.client.post(f'/deudas/{d.pk}/abonar/',{'importe':'50','token_operacion':str(uuid4())}).status_code,302)
        self.assertEqual(d.saldo_pendiente,50)
        self.assertEqual(self.client.get('/deudas/').status_code,200)
        self.assertEqual(self.client.get('/ahorros/').status_code,200)

    def test_flujo_http_administrador_crea_usuario(self):
        self.entrar(self.admin)
        data={'username':'creado','email':'creado@example.mx','first_name':'Andrea','last_name':'Flores',
              'is_active':'on','correo_verificado':'on','password_nueva':'PruebaSeguro123!'}
        r=self.client.post('/admin-panel/usuarios/nuevo/',data)
        self.assertEqual(r.status_code,302)
        usuario=Usuario.objects.get(username='creado')
        self.assertTrue(usuario.check_password('PruebaSeguro123!'))
        self.assertFalse(usuario.is_staff)
        self.assertTrue(usuario.cambiar_password_obligatorio)

    def test_validacion_nombres_y_contrasenas(self):
        from .forms import RegistroForm
        form=RegistroForm(data={'username':'abc','email':'abc@example.mx','first_name':'A123','last_name':'Perez',
            'password1':'minusculas123','password2':'minusculas123'})
        self.assertFalse(form.is_valid())
        self.assertIn('first_name',form.errors)
        form2=RegistroForm(data={'username':'abcd','email':'abcd@example.mx','first_name':'Ana','last_name':'Perez',
            'password1':'minusculas123','password2':'minusculas123'})
        self.assertFalse(form2.is_valid())
        self.assertIn('password2',form2.errors)

    def test_ajax_filtro_presupuesto_y_fecha(self):
        self.entrar()
        r=self.client.get('/dashboard/?desde=2026-11-01&hasta=2026-11-30')
        self.assertEqual(r.status_code,200)
        self.assertContains(r,'2026-11-01')
        r=self.client.get('/api/resumen/?desde=2026-11-01&hasta=2026-11-30')
        self.assertEqual(r.json()['balance_periodo'],'0.00')

    def test_inactividad_autentica(self):
        self.entrar()
        session=self.client.session
        session['ultima_accion']=timezone.now().timestamp()-1300
        session.save()
        response=self.client.get('/dashboard/')
        self.assertEqual(response.status_code,302)
        self.assertTrue(response.url.startswith('/login/'))

    def test_no_hay_panel_admin_nativo_para_saltar_controles(self):
        self.entrar(self.admin)
        self.assertEqual(self.client.get('/django-admin/').status_code,404)
