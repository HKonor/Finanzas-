"""Vistas HTML y JSON: autenticación, panel financiero y administración."""
import calendar
from datetime import date
from decimal import Decimal
from functools import wraps
from uuid import UUID
from django.contrib import messages
from django.contrib.auth import authenticate,login,logout,update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q,Sum,Count
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404,render,redirect
from django.core.paginator import Paginator
from django.urls import reverse,reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from .models import Usuario,Categoria,Movimiento,Presupuesto,Ahorro,AportacionAhorro,Deuda,AbonoDeuda,GastoFijo,Alerta,CERO
from .forms import (RegistroForm,AccesoForm,PerfilForm,MovimientoForm,PresupuestoForm,AhorroForm,
                    AportacionForm,DeudaForm,GastoFijoForm,CategoriaForm,AdminUsuarioForm,decorar)
from .services import resumen,actualizar_alertas,enviar_activacion,activar_cuenta,aportar_ahorro,pagar_gasto_fijo,cancelar_pago_fijo,abonar_deuda,anular_abono_deuda,eliminar_aportacion


def solo_usuario(func):
    @login_required
    @wraps(func)
    def inner(request,*args,**kwargs):
        if request.user.is_staff:return redirect('admin_dashboard')
        if request.user.cambiar_password_obligatorio:return redirect('cambiar_password')
        return func(request,*args,**kwargs)
    return inner


def solo_admin(func):
    @login_required
    @wraps(func)
    def inner(request,*args,**kwargs):
        if not request.user.is_staff:return redirect('dashboard')
        if request.user.cambiar_password_obligatorio:return redirect('cambiar_password')
        return func(request,*args,**kwargs)
    return inner


def inicio(request):
    if not request.user.is_authenticated:return redirect('login')
    return redirect('admin_dashboard' if request.user.is_staff else 'dashboard')


def registro(request):
    if request.user.is_authenticated:return redirect('inicio')
    form=RegistroForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        u=form.save()
        try:enviar_activacion(u)
        except Exception:
            messages.warning(request,'Se creó tu cuenta, pero no se pudo enviar el correo. Revisa SMTP y usa «Reenviar activación».')
        else:messages.success(request,'Revisa tu correo: enviamos un enlace para activar tu cuenta.')
        return redirect('login')
    return render(request,'auth/registro.html',{'form':form,'titulo':'Crear cuenta'})


def login_view(request):
    if request.user.is_authenticated:return redirect('inicio')
    form=AccesoForm(request.POST or None)
    if request.GET.get('inactivo'):messages.info(request,'Tu sesión terminó por inactividad.')
    if request.method=='POST' and form.is_valid():
        email=form.cleaned_data['email'].strip().lower();passw=form.cleaned_data['password']
        u=authenticate(request,username=email,password=passw)
        if u:
            login(request,u);request.session['ultima_accion']=timezone.now().timestamp()
            return redirect('cambiar_password' if u.cambiar_password_obligatorio else ('admin_dashboard' if u.is_staff else 'dashboard'))
        messages.error(request,'Correo o contraseña incorrectos, o cuenta pendiente de verificación/inactiva.')
    return render(request,'auth/login.html',{'form':form,'titulo':'Iniciar sesión'})


@login_required
@require_POST
def logout_view(request):
    logout(request);messages.success(request,'Sesión cerrada correctamente.')
    return redirect('login')


def activar(request,token):
    if activar_cuenta(token):messages.success(request,'Correo verificado. Ya puedes iniciar sesión.')
    else:messages.error(request,'Enlace inválido, caducado o ya utilizado. Puedes solicitar uno nuevo.')
    return redirect('login')


def reenviar_activacion(request):
    if request.method=='POST':
        email=request.POST.get('email','').strip()
        u=Usuario.objects.filter(email__iexact=email,correo_verificado=False).first()
        if u:
            try:enviar_activacion(u)
            except Exception:messages.error(request,'No pudo enviarse el correo. Comprueba la configuración SMTP.')
        messages.success(request,'Si existe una cuenta pendiente para ese correo, se ha solicitado un nuevo enlace.')
        return redirect('login')
    return render(request,'auth/reenviar.html',{'titulo':'Reenviar activación'})


@login_required
def perfil(request):
    form=PerfilForm(request.POST or None,instance=request.user)
    if request.method=='POST' and form.is_valid():
        form.save();messages.success(request,'Perfil actualizado.');return redirect('perfil')
    return render(request,'auth/perfil.html',{'form':form,'titulo':'Mi perfil'})


@login_required
def cambiar_password(request):
    form=PasswordChangeForm(request.user,request.POST or None)
    decorar(form)
    if request.method=='POST' and form.is_valid():
        u=form.save();u.cambiar_password_obligatorio=False;u.save(update_fields=['cambiar_password_obligatorio'])
        update_session_auth_hash(request,u)
        messages.success(request,'Contraseña actualizada correctamente.')
        return redirect('admin_dashboard' if u.is_staff else 'dashboard')
    return render(request,'formulario.html',{'form':form,'titulo':'Cambiar contraseña','boton':'Guardar nueva contraseña'})


def rango_fechas(request):
    hoy=timezone.localdate();inicio=hoy.replace(day=1);fin=hoy.replace(day=calendar.monthrange(hoy.year,hoy.month)[1])
    try:
        if request.GET.get('desde'):inicio=date.fromisoformat(request.GET['desde'])
        if request.GET.get('hasta'):fin=date.fromisoformat(request.GET['hasta'])
    except ValueError:return None,None,'Formato de fecha inválido.'
    if inicio>fin:return None,None,'La fecha inicial debe ser anterior a la final.'
    return inicio,fin,None


@solo_usuario
def dashboard(request):
    desde,hasta,error=rango_fechas(request)
    if error:messages.error(request,error);return redirect('dashboard')
    actualizar_alertas(request.user)
    datos=resumen(request.user,desde,hasta)
    movimientos=Movimiento.objects.filter(usuario=request.user).select_related('categoria')[:7]
    presupuestos=list(Presupuesto.objects.filter(usuario=request.user,fecha_fin__gte=desde,fecha_inicio__lte=hasta).select_related('categoria'))
    alertas=Alerta.objects.filter(usuario=request.user,activa=True,leida=False)[:6]
    datos.update({'titulo':'Resumen financiero','desde':desde,'hasta':hasta,'movimientos':movimientos,
                  'presupuestos':presupuestos,'alertas':alertas,'metas':Ahorro.objects.filter(usuario=request.user)[:3],
                  'presupuestos_activos':len(presupuestos),'alertas_total':Alerta.objects.filter(usuario=request.user,activa=True,leida=False).count()})
    return render(request,'dashboard.html',datos)


@solo_usuario
def movimientos_lista(request):
    qs=Movimiento.objects.filter(usuario=request.user).select_related('categoria')
    tipo=request.GET.get('tipo','');clasificacion=request.GET.get('clasificacion','');cat=request.GET.get('categoria','');buscar=request.GET.get('buscar','')
    if tipo in ('GASTO','INGRESO'):qs=qs.filter(tipo=tipo)
    if clasificacion in ('FIJO','VARIABLE','IMPREVISTO'):qs=qs.filter(categoria__clasificacion=clasificacion)
    if cat.isdigit():qs=qs.filter(categoria_id=cat)
    if buscar:qs=qs.filter(descripcion__icontains=buscar[:80])
    try:
        if request.GET.get('desde'):qs=qs.filter(fecha__gte=date.fromisoformat(request.GET['desde']))
        if request.GET.get('hasta'):qs=qs.filter(fecha__lte=date.fromisoformat(request.GET['hasta']))
    except ValueError:messages.error(request,'Rango de fechas inválido.')
    return render(request,'movimientos.html',{'titulo':'Movimientos','items':Paginator(qs,25).get_page(request.GET.get('page')),
        'cats':Categoria.objects.filter(Q(usuario__isnull=True)|Q(usuario=request.user)),
        'ingresos':qs.filter(tipo='INGRESO').aggregate(s=Sum('importe'))['s'] or CERO,
        'gastos':qs.filter(tipo='GASTO').aggregate(s=Sum('importe'))['s'] or CERO})


def _formulario(request,titulo,Form,redirecto,instance=None,kwargs=None):
    kwargs=kwargs or {}
    form=Form(request.POST or None,instance=instance,**kwargs)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            if isinstance(form,MovimientoForm) and instance is None and Movimiento.objects.filter(usuario=request.user,clave_solicitud=form.cleaned_data['token_operacion']).exists():
                messages.info(request,'Esta operación ya se había registrado; no se duplicó.')
                return redirect(redirecto)
            obj=form.save()
            if isinstance(obj,(Movimiento,Presupuesto,Deuda)):
                actualizar_alertas(request.user)
        messages.success(request,'Información guardada correctamente.')
        return redirect(redirecto)
    return render(request,'formulario.html',{'titulo':titulo,'form':form,'boton':'Guardar cambios' if instance else 'Crear registro','volver':redirecto})


def _eliminar(request,obj,redirecto):
    if request.method=='POST':
        try:
            with transaction.atomic():
                obj.delete()
                actualizar_alertas(request.user)
            messages.success(request,'Registro eliminado.')
            return redirect(redirecto)
        except Exception:
            messages.error(request,'No se puede eliminar porque está relacionado con otros registros. Elimina primero las dependencias.')
            return redirect(redirecto)
    return render(request,'eliminar.html',{'titulo':'Confirmar eliminación','obj':obj,'volver':redirecto})


@solo_usuario
def movimiento_crear(request):return _formulario(request,'Nuevo movimiento',MovimientoForm,'movimientos_lista',kwargs={'usuario':request.user})
@solo_usuario
def movimiento_editar(request,pk):
    m=get_object_or_404(Movimiento,pk=pk,usuario=request.user,origen='NORMAL')
    return _formulario(request,'Editar movimiento',MovimientoForm,'movimientos_lista',instance=m,kwargs={'usuario':request.user})
@solo_usuario
def movimiento_eliminar(request,pk):
    return _eliminar(request,get_object_or_404(Movimiento,pk=pk,usuario=request.user,origen='NORMAL'),'movimientos_lista')


@solo_usuario
def presupuestos_lista(request):
    actualizar_alertas(request.user)
    return render(request,'presupuestos.html',{'titulo':'Presupuestos','items':Presupuesto.objects.filter(usuario=request.user).select_related('categoria','fuente_ingreso')})
@solo_usuario
def presupuesto_crear(request):return _formulario(request,'Nuevo presupuesto',PresupuestoForm,'presupuestos_lista',kwargs={'usuario':request.user})
@solo_usuario
def presupuesto_editar(request,pk):return _formulario(request,'Editar presupuesto',PresupuestoForm,'presupuestos_lista',instance=get_object_or_404(Presupuesto,pk=pk,usuario=request.user),kwargs={'usuario':request.user})
@solo_usuario
def presupuesto_eliminar(request,pk):return _eliminar(request,get_object_or_404(Presupuesto,pk=pk,usuario=request.user),'presupuestos_lista')


@solo_usuario
def ahorros_lista(request):return render(request,'ahorros.html',{'titulo':'Metas de ahorro','items':Ahorro.objects.filter(usuario=request.user)})
@solo_usuario
def ahorro_crear(request):return _ahorro_form(request)
def _ahorro_form(request,pk=None):
    a=get_object_or_404(Ahorro,pk=pk,usuario=request.user) if pk else None
    form=AhorroForm(request.POST or None,instance=a)
    if request.method=='POST' and form.is_valid():
        obj=form.save(commit=False);obj.usuario=request.user;obj.save()
        messages.success(request,'Meta guardada.');return redirect('ahorros_lista')
    return render(request,'formulario.html',{'titulo':'Editar meta' if a else 'Crear meta de ahorro','form':form,'volver':'ahorros_lista'})
@solo_usuario
def ahorro_editar(request,pk):return _ahorro_form(request,pk)
@solo_usuario
def ahorro_eliminar(request,pk):return _eliminar(request,get_object_or_404(Ahorro,pk=pk,usuario=request.user),'ahorros_lista')
@solo_usuario
def ahorro_aportar(request,pk):
    a=get_object_or_404(Ahorro,pk=pk,usuario=request.user);form=AportacionForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        try:aportar_ahorro(a,form.cleaned_data['importe'],form.cleaned_data['token_operacion'])
        except ValidationError as e:form.add_error(None,e)
        else:messages.success(request,'Aportación realizada sin duplicar ingresos.');return redirect('ahorros_lista')
    return render(request,'formulario.html',{'titulo':f'Aportar a {a.titulo}','form':form,'volver':'ahorros_lista'})


@solo_usuario
@require_POST
def ahorro_anular_aportacion(request,pk):
    try:eliminar_aportacion(pk,request.user)
    except AportacionAhorro.DoesNotExist:messages.error(request,'La aportación no existe.')
    else:messages.success(request,'Aportación anulada y fondos liberados.')
    return redirect('ahorros_lista')


@solo_usuario
def fijos_lista(request):return render(request,'fijos.html',{'titulo':'Gastos fijos','items':GastoFijo.objects.filter(usuario=request.user).select_related('categoria')})
@solo_usuario
def fijo_crear(request):return _formulario(request,'Nuevo gasto fijo',GastoFijoForm,'fijos_lista',kwargs={'usuario':request.user})
@solo_usuario
def fijo_editar(request,pk):
    g=get_object_or_404(GastoFijo,pk=pk,usuario=request.user)
    if g.fecha_pago:messages.error(request,'Primero anula el pago para editar el gasto fijo.');return redirect('fijos_lista')
    return _formulario(request,'Editar gasto fijo',GastoFijoForm,'fijos_lista',instance=g,kwargs={'usuario':request.user})
@solo_usuario
def fijo_eliminar(request,pk):
    g=get_object_or_404(GastoFijo,pk=pk,usuario=request.user)
    if g.fecha_pago:messages.error(request,'Anula el pago antes de eliminar la obligación.');return redirect('fijos_lista')
    return _eliminar(request,g,'fijos_lista')
@solo_usuario
@require_POST
def fijo_pagar(request,pk):
    try:pagar_gasto_fijo(pk,request.user)
    except (ValidationError,GastoFijo.DoesNotExist) as e:messages.error(request,str(e))
    else:messages.success(request,'Pago registrado una sola vez.')
    return redirect('fijos_lista')
@solo_usuario
@require_POST
def fijo_anular(request,pk):
    try:cancelar_pago_fijo(pk,request.user)
    except (ValidationError,GastoFijo.DoesNotExist) as e:messages.error(request,str(e))
    else:messages.success(request,'Pago anulado y balance actualizado.')
    return redirect('fijos_lista')
@solo_usuario
def gastos_clasificacion(request,clasificacion):
    if clasificacion not in ('FIJO','VARIABLE','IMPREVISTO'):return HttpResponseBadRequest('Clasificación inválida')
    qs=Movimiento.objects.filter(usuario=request.user,tipo='GASTO',categoria__clasificacion=clasificacion).select_related('categoria')
    return render(request,'movimientos.html',{'titulo':{'FIJO':'Gastos fijos pagados','VARIABLE':'Gastos variables','IMPREVISTO':'Gastos imprevistos'}[clasificacion], 'items':Paginator(qs,25).get_page(request.GET.get('page')), 'cats':Categoria.objects.filter(tipo='GASTO',clasificacion=clasificacion), 'ingresos':CERO,'gastos':qs.aggregate(s=Sum('importe'))['s'] or CERO})


@solo_usuario
def deudas_lista(request):
    actualizar_alertas(request.user)
    return render(request,'deudas.html',{'titulo':'Deudas y deudores','items':Deuda.objects.filter(usuario=request.user)})
@solo_usuario
def deuda_crear(request):return _deuda_form(request)
def _deuda_form(request,pk=None):
    d=get_object_or_404(Deuda,pk=pk,usuario=request.user) if pk else None
    form=DeudaForm(request.POST or None,instance=d)
    if request.method=='POST' and form.is_valid():
        obj=form.save(commit=False);obj.usuario=request.user;obj.save()
        actualizar_alertas(request.user)
        messages.success(request,'Deuda guardada.');return redirect('deudas_lista')
    return render(request,'formulario.html',{'titulo':'Editar deuda' if d else 'Registrar deuda','form':form,'volver':'deudas_lista'})
@solo_usuario
def deuda_editar(request,pk):return _deuda_form(request,pk)
@solo_usuario
def deuda_eliminar(request,pk):
    d=get_object_or_404(Deuda,pk=pk,usuario=request.user)
    if d.abonos.exists():messages.error(request,'No puedes eliminar una deuda con abonos.');return redirect('deudas_lista')
    return _eliminar(request,d,'deudas_lista')
@solo_usuario
def deuda_abonar(request,pk):
    d=get_object_or_404(Deuda,pk=pk,usuario=request.user)
    form=AportacionForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        try:abonar_deuda(pk,request.user,form.cleaned_data['importe'],token_operacion=form.cleaned_data['token_operacion'])
        except ValidationError as e:form.add_error(None,e)
        else:messages.success(request,'Abono realizado y registrado en los movimientos de caja.');return redirect('deudas_lista')
    return render(request,'formulario.html',{'titulo':f'Registrar abono: {d.persona} (saldo ${d.saldo_pendiente})','form':form,'volver':'deudas_lista'})


@solo_usuario
@require_POST
def deuda_anular_abono(request,pk):
    try:anular_abono_deuda(pk,request.user)
    except AbonoDeuda.DoesNotExist:messages.error(request,'El abono no existe.')
    else:messages.success(request,'Abono anulado y balance recalculado.')
    return redirect('deudas_lista')


@solo_usuario
def categorias_lista(request):
    return render(request,'categorias.html',{'titulo':'Mis categorías','items':Categoria.objects.filter(Q(usuario=request.user)|Q(usuario__isnull=True)),'es_admin':False})
@solo_usuario
def categoria_crear(request):return _formulario(request,'Nueva categoría',CategoriaForm,'categorias_lista',kwargs={'usuario':request.user})
@solo_usuario
def categoria_editar(request,pk):return _formulario(request,'Editar categoría',CategoriaForm,'categorias_lista',instance=get_object_or_404(Categoria,pk=pk,usuario=request.user),kwargs={'usuario':request.user})
@solo_usuario
def categoria_eliminar(request,pk):return _eliminar(request,get_object_or_404(Categoria,pk=pk,usuario=request.user),'categorias_lista')


@solo_usuario
@require_POST
def marcar_alerta(request,pk):
    Alerta.objects.filter(pk=pk,usuario=request.user).update(leida=True)
    if request.headers.get('X-Requested-With')=='XMLHttpRequest':return JsonResponse({'ok':True})
    return redirect('dashboard')


@solo_usuario
@require_GET
def api_resumen(request):
    desde,hasta,error=rango_fechas(request)
    if error:return JsonResponse({'error':error},status=400)
    r=resumen(request.user,desde,hasta)
    return JsonResponse({'desde':desde.isoformat(),'hasta':hasta.isoformat(),**{k:str(v) for k,v in r.items()},
        'grafica':[{'clasificacion':x,'total':str(v)} for x,v in [('Fijos',r['fijos']),('Variables',r['variables']),('Imprevistos',r['imprevistos'])]]})


@solo_usuario
@require_GET
def api_presupuestos(request):
    actualizar_alertas(request.user)
    return JsonResponse({'presupuestos':[{'id':p.pk,'nombre':p.nombre,'limite':str(p.monto_limite),
            'gastado':str(p.gasto_actual()),'restante':str(p.monto_restante()),'porcentaje':str(p.porcentaje_consumido()),
            'excedido':p.esta_excedido()} for p in Presupuesto.objects.filter(usuario=request.user)]})


@solo_usuario
@require_GET
def api_alertas(request):
    actualizar_alertas(request.user)
    return JsonResponse({'alertas':[{'id':a.pk,'tipo':a.tipo,'mensaje':a.mensaje,'creada':a.fecha_creacion.isoformat()} for a in Alerta.objects.filter(usuario=request.user,activa=True,leida=False)[:30]]})


@solo_admin
def admin_dashboard(request):
    stats={'usuarios':Usuario.objects.count(),'activos':Usuario.objects.filter(is_active=True).count(),
           'inactivos':Usuario.objects.filter(is_active=False).count(),
           'verificados':Usuario.objects.filter(correo_verificado=True).count(),
           'pendientes':Usuario.objects.filter(correo_verificado=False).count(),
           'movimientos':Movimiento.objects.count(),'categorias':Categoria.objects.filter(usuario__isnull=True).count(),
           'presupuestos':Presupuesto.objects.count(),'ahorros':Ahorro.objects.count()}
    return render(request,'admin_panel/dashboard.html',{'titulo':'Panel administrativo','stats':stats,
        'recientes':Usuario.objects.order_by('-ultima_actividad')[:8]})


@solo_admin
def admin_usuarios(request):
    q=request.GET.get('buscar','').strip()[:80]
    qs=Usuario.objects.order_by('-date_joined')
    if q:qs=qs.filter(Q(email__icontains=q)|Q(username__icontains=q)|Q(first_name__icontains=q))
    return render(request,'admin_panel/usuarios.html',{'titulo':'Gestión de usuarios','items':Paginator(qs,25).get_page(request.GET.get('page'))})


def _admin_usuario_form(request,pk=None):
    u=get_object_or_404(Usuario,pk=pk) if pk else None
    form=AdminUsuarioForm(request.POST or None,instance=u)
    if request.method=='POST' and form.is_valid():
        d=form.cleaned_data
        admins=Usuario.objects.filter(is_staff=True,is_active=True).count()
        if u and u.pk==request.user.pk and (not d['is_active'] or not d['is_staff']):
            form.add_error(None,'No puedes quitarte los permisos ni desactivar tu propia cuenta.')
        elif u and u.is_staff and u.is_active and admins<=1 and (not d['is_staff'] or not d['is_active']):
            form.add_error(None,'Debe existir al menos un administrador activo.')
        elif d['is_staff'] and not d['correo_verificado']:
            form.add_error('correo_verificado','Un administrador debe tener el correo verificado.')
        else:
            usuario=form.save()
            usuario.bloqueado_admin=not usuario.is_active
            usuario.save(update_fields=['bloqueado_admin'])
            messages.success(request,'Usuario guardado.');return redirect('admin_usuarios')
    return render(request,'formulario.html',{'titulo':'Editar usuario' if u else 'Crear usuario','form':form,'volver':'admin_usuarios'})
@solo_admin
def admin_usuario_crear(request):return _admin_usuario_form(request)
@solo_admin
def admin_usuario_editar(request,pk):return _admin_usuario_form(request,pk)
@solo_admin
@require_POST
def admin_toggle_usuario(request,pk):
    u=get_object_or_404(Usuario,pk=pk)
    if u.pk==request.user.pk or (u.is_staff and u.is_active and Usuario.objects.filter(is_staff=True,is_active=True).count()<=1):
        messages.error(request,'No se permite desactivar tu cuenta ni al último administrador.')
    else:
        u.is_active=not u.is_active;u.bloqueado_admin=not u.is_active;u.save(update_fields=['is_active','bloqueado_admin'])
        messages.success(request,'Estado actualizado.')
    return redirect('admin_usuarios')


@solo_admin
def admin_categorias(request):return render(request,'categorias.html',{'titulo':'Categorías globales','items':Categoria.objects.filter(usuario__isnull=True),'es_admin':True})
@solo_admin
def admin_categoria_crear(request):return _formulario(request,'Nueva categoría global',CategoriaForm,'admin_categorias',kwargs={'globales':True})
@solo_admin
def admin_categoria_editar(request,pk):return _formulario(request,'Editar categoría global',CategoriaForm,'admin_categorias',instance=get_object_or_404(Categoria,pk=pk,usuario__isnull=True),kwargs={'globales':True})
@solo_admin
@require_POST
def admin_categoria_toggle(request,pk):
    c=get_object_or_404(Categoria,pk=pk,usuario__isnull=True)
    c.activa=not c.activa;c.save(update_fields=['activa']);messages.success(request,'Estado de categoría actualizado.')
    return redirect('admin_categorias')
