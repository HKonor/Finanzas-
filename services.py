"""Operaciones monetarias centralizadas, transaccionales e idempotentes."""
from datetime import timedelta
import calendar
from decimal import Decimal
from uuid import uuid4
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone
from .models import (Usuario, VerificacionCorreo, Categoria, Movimiento, Presupuesto, Ahorro,
                     AportacionAhorro, GastoFijo, Deuda, AbonoDeuda, Alerta, CERO)


def suma(qs): return qs.aggregate(s=Sum('importe'))['s'] or CERO


def resumen(usuario, desde=None, hasta=None):
    historicos = Movimiento.objects.filter(usuario=usuario)
    del_periodo = historicos
    if desde: del_periodo = del_periodo.filter(fecha__gte=desde)
    if hasta: del_periodo = del_periodo.filter(fecha__lte=hasta)
    ingresos = suma(del_periodo.filter(tipo='INGRESO'))
    gastos = suma(del_periodo.filter(tipo='GASTO'))
    balance_historico = suma(historicos.filter(tipo='INGRESO'))-suma(historicos.filter(tipo='GASTO'))
    comprometido = sum((a.monto_actual for a in Ahorro.objects.filter(usuario=usuario)), CERO)
    return {'ingresos':ingresos,'gastos':gastos,'balance_periodo':ingresos-gastos,
            'balance_historico':balance_historico,'ahorrado':comprometido,
            'disponible':balance_historico-comprometido,
            'fijos':suma(del_periodo.filter(tipo='GASTO',categoria__clasificacion='FIJO')),
            'variables':suma(del_periodo.filter(tipo='GASTO',categoria__clasificacion='VARIABLE')),
            'imprevistos':suma(del_periodo.filter(tipo='GASTO',categoria__clasificacion='IMPREVISTO')),
            'deudas_por_pagar':sum((d.saldo_pendiente for d in Deuda.objects.filter(usuario=usuario,tipo='PAGAR')), CERO),
            'por_cobrar':sum((d.saldo_pendiente for d in Deuda.objects.filter(usuario=usuario,tipo='COBRAR')), CERO)}


def actualizar_alertas(usuario):
    """Una alerta única por presupuesto y estado; reabre solo al cambiar de estado."""
    for p in Presupuesto.objects.filter(usuario=usuario):
        porcentaje = p.porcentaje_consumido()
        nuevo = 'EXCESO' if p.esta_excedido() else 'CERCA' if porcentaje >= 80 else None
        for tipo in ('CERCA','EXCESO'):
            alerta = Alerta.objects.filter(presupuesto=p,tipo=tipo).first()
            if tipo == nuevo:
                texto = f'Presupuesto «{p.nombre}»: {porcentaje}% utilizado. ' + ('Límite excedido.' if tipo == 'EXCESO' else 'Cerca de agotarse.')
                if alerta:
                    cambios = []
                    if alerta.mensaje != texto: alerta.mensaje=texto; cambios.append('mensaje')
                    if not alerta.activa: alerta.activa=True; alerta.leida=False; cambios.extend(['activa','leida'])
                    if cambios: alerta.save(update_fields=cambios)
                else: Alerta.objects.create(usuario=usuario,presupuesto=p,tipo=tipo,mensaje=texto)
            elif alerta and alerta.activa:
                alerta.activa=False; alerta.save(update_fields=['activa'])
    hoy=timezone.localdate()
    for d in Deuda.objects.filter(usuario=usuario):
        alerta = Alerta.objects.filter(deuda=d,tipo='VENCE').first()
        activa = bool(d.saldo_pendiente and d.fecha_vencimiento <= hoy+timedelta(days=3))
        if activa:
            msg=f'La deuda de {d.persona} ({d.get_tipo_display()}) vence el {d.fecha_vencimiento:%d/%m/%Y}. Saldo ${d.saldo_pendiente}.'
            if alerta:
                update=[]
                if alerta.mensaje != msg: alerta.mensaje=msg;update.append('mensaje')
                if not alerta.activa: alerta.activa=True;alerta.leida=False;update.extend(['activa','leida'])
                if update:alerta.save(update_fields=update)
            else:Alerta.objects.create(usuario=usuario,deuda=d,tipo='VENCE',mensaje=msg)
        elif alerta and alerta.activa:
            alerta.activa=False;alerta.save(update_fields=['activa'])


def enviar_activacion(usuario):
    """Token UUID distinto en cada reenvío, una sola utilización, caduca tras 24 horas."""
    VerificacionCorreo.objects.filter(usuario=usuario,consumido__isnull=True).update(consumido=timezone.now())
    v = VerificacionCorreo.objects.create(usuario=usuario, token=uuid4(), vence=timezone.now()+timedelta(hours=24))
    enlace = settings.DEFAULT_APP_URL + reverse('activar_cuenta',args=[str(v.token)])
    send_mail('Confirma tu cuenta de Finanza.', f'Hola, {usuario.first_name or usuario.username}.\nActiva tu cuenta usando este enlace (vence en 24 horas):\n{enlace}\nSi no solicitaste el registro, ignora este mensaje.', settings.DEFAULT_FROM_EMAIL,[usuario.email], fail_silently=False)
    return v


@transaction.atomic
def activar_cuenta(token):
    v = VerificacionCorreo.objects.select_for_update().select_related('usuario').filter(token=token).first()
    if not v or v.consumido or v.vence <= timezone.now() or v.usuario.bloqueado_admin: return False
    usuario=v.usuario
    usuario.correo_verificado=True
    usuario.is_active=True
    usuario.save(update_fields=['correo_verificado','is_active'])
    v.consumido=timezone.now();v.save(update_fields=['consumido'])
    return True


@transaction.atomic
def aportar_ahorro(ahorro, importe, token_operacion=None):
    ahorro=Ahorro.objects.select_for_update().get(pk=ahorro.pk)
    Usuario.objects.select_for_update().get(pk=ahorro.usuario_id)  # bloqueo por usuario, incluso entre varias metas
    if token_operacion:
        anterior=AportacionAhorro.objects.filter(clave_solicitud=token_operacion,ahorro=ahorro).first()
        if anterior:return anterior
    if importe <= 0: raise ValidationError('El importe debe ser positivo.')
    disponible=resumen(ahorro.usuario)['disponible']
    if importe > disponible: raise ValidationError(f'Fondos disponibles insuficientes: ${disponible}.')
    if importe > ahorro.monto_restante(): raise ValidationError('La aportación excede la meta establecida.')
    return AportacionAhorro.objects.create(ahorro=ahorro,importe=importe,clave_solicitud=token_operacion)


@transaction.atomic
def pagar_gasto_fijo(pk,usuario,fecha=None):
    g=GastoFijo.objects.select_for_update().get(pk=pk,usuario=usuario)
    if g.fecha_pago: return g
    # Las obligaciones aún no pagadas no son movimientos en caja.
    m=Movimiento.objects.create(usuario=usuario,categoria=g.categoria,tipo='GASTO',importe=g.importe,
        descripcion=g.concepto,fecha=fecha or timezone.localdate(),origen='GASTO_FIJO')
    g.fecha_pago=m.fecha;g.movimiento=m;g.save(update_fields=['fecha_pago','movimiento'])
    # Cada vencimiento constituye una obligación distinta. Se crea una vez el siguiente.
    if g.periodicidad!='UNICO' and not GastoFijo.objects.filter(anterior=g).exists():
        vence=g.fecha_vencimiento
        if g.periodicidad=='SEMANAL': siguiente=vence+timedelta(days=7)
        elif g.periodicidad=='QUINCENAL': siguiente=vence+timedelta(days=15)
        else:
            anyo=vence.year + (vence.month==12)
            mes=vence.month%12+1
            siguiente=vence.replace(year=anyo,month=mes,day=min(vence.day,calendar.monthrange(anyo,mes)[1]))
        GastoFijo.objects.create(usuario=usuario,categoria=g.categoria,concepto=g.concepto,importe=g.importe,
            periodicidad=g.periodicidad,fecha_vencimiento=siguiente,anterior=g)
    actualizar_alertas(usuario)
    return g


@transaction.atomic
def cancelar_pago_fijo(pk,usuario):
    g=GastoFijo.objects.select_for_update().get(pk=pk,usuario=usuario)
    if g.movimiento_id:
        m=g.movimiento
        # Si no se pagó la siguiente obligación, anular también su generación automática.
        siguiente=GastoFijo.objects.filter(anterior=g).first()
        if siguiente and siguiente.fecha_pago:raise ValidationError('Anula primero los vencimientos posteriores pagados.')
        if siguiente:siguiente.delete()
        g.fecha_pago=None;g.movimiento=None;g.save(update_fields=['fecha_pago','movimiento'])
        m.delete()
        actualizar_alertas(usuario)
    return g


@transaction.atomic
def abonar_deuda(pk,usuario,importe,fecha=None,token_operacion=None):
    d=Deuda.objects.select_for_update().get(pk=pk,usuario=usuario)
    if token_operacion:
        anterior=AbonoDeuda.objects.filter(clave_solicitud=token_operacion,deuda=d).first()
        if anterior:return anterior
    if importe <= 0 or importe > d.saldo_pendiente:
        raise ValidationError(f'El abono debe ser positivo y no exceder el saldo pendiente (${d.saldo_pendiente}).')
    tipo='GASTO' if d.tipo=='PAGAR' else 'INGRESO'
    cat=Categoria.objects.filter(usuario__isnull=True,tipo=tipo,activa=True,nombre=('Pago de Deudas y Préstamos' if tipo=='GASTO' else 'Otros Ingresos')).first()
    if not cat:cat=Categoria.objects.filter(usuario__isnull=True,tipo=tipo,activa=True).first()
    if not cat:raise ValidationError('Carga primero las categorías globales (cargar_categorias).')
    movimiento=Movimiento.objects.create(usuario=usuario,categoria=cat,tipo=tipo,importe=importe,fecha=fecha or timezone.localdate(),
       descripcion=f'Abono {"pagado" if tipo=="GASTO" else "cobrado"}: {d.persona}',origen='ABONO_DEUDA')
    abono=AbonoDeuda.objects.create(deuda=d,importe=importe,fecha=movimiento.fecha,movimiento=movimiento,clave_solicitud=token_operacion)
    actualizar_alertas(usuario)
    return abono


@transaction.atomic
def anular_abono_deuda(pk,usuario):
    abono=AbonoDeuda.objects.select_for_update().select_related('deuda','movimiento').get(pk=pk,deuda__usuario=usuario)
    movimiento=abono.movimiento
    abono.delete()
    movimiento.delete()
    actualizar_alertas(usuario)


@transaction.atomic
def eliminar_aportacion(pk,usuario):
    aportacion=AportacionAhorro.objects.select_for_update().get(pk=pk,ahorro__usuario=usuario)
    aportacion.delete()
