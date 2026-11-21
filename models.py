"""Entidades de Finanza. Todos los importes se guardan como DECIMAL exactos."""
import calendar
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import Q, Sum
from django.db.models.functions import Lower
from django.utils import timezone

CERO = Decimal('0.00')
CENTAVO = Decimal('0.01')


class Usuario(AbstractUser):
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=25, blank=True)
    moneda = models.CharField(max_length=5, default='$')
    correo_verificado = models.BooleanField(default=False)
    cambiar_password_obligatorio = models.BooleanField(default=False)
    bloqueado_admin = models.BooleanField(default=False)
    ultima_actividad = models.DateTimeField(null=True, blank=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        constraints = [models.UniqueConstraint(Lower('email'),name='correo_unico_sin_mayusculas')]

    def __str__(self):
        return self.email


class VerificacionCorreo(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='verificaciones')
    token = models.UUIDField(unique=True, editable=False)
    vence = models.DateTimeField()
    consumido = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)


class Categoria(models.Model):
    TIPOS = [('INGRESO', 'Ingreso'), ('GASTO', 'Gasto')]
    CLASES = [('FIJO', 'Fijo'), ('VARIABLE', 'Variable'), ('IMPREVISTO', 'Imprevisto')]
    usuario = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.CASCADE, related_name='categorias')
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    clasificacion = models.CharField(max_length=12, choices=CLASES, default='VARIABLE')
    categoria_padre = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['tipo', 'clasificacion', 'nombre']
        constraints = [models.UniqueConstraint(fields=['usuario', 'nombre', 'tipo'], name='cat_unica_usuario_tipo'),
                       models.UniqueConstraint(fields=['nombre', 'tipo'], condition=Q(usuario__isnull=True), name='cat_global_unica')]

    def clean(self):
        if self.categoria_padre_id:
            p = self.categoria_padre
            if p.pk == self.pk or p.tipo != self.tipo or (p.usuario_id not in (None, self.usuario_id)):
                raise ValidationError({'categoria_padre': 'Categoría superior incompatible.'})

    def __str__(self):
        return f'{self.nombre} ({self.get_tipo_display()})'


class Movimiento(models.Model):
    TIPOS = Categoria.TIPOS
    ORIGEN = [('NORMAL','Movimiento manual'), ('GASTO_FIJO','Gasto fijo'), ('ABONO_DEUDA','Abono de deuda')]
    PERIODICIDADES = [('UNICO','Único'),('SEMANAL','Semanal'),('QUINCENAL','Quincenal'),('MENSUAL','Mensual')]
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='movimientos')
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    importe = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(CENTAVO)])
    descripcion = models.CharField(max_length=255)
    fecha = models.DateField(default=timezone.localdate)
    origen = models.CharField(max_length=12, choices=ORIGEN, default='NORMAL', editable=False)
    periodicidad = models.CharField(max_length=12,choices=PERIODICIDADES,default='UNICO')
    clave_solicitud = models.UUIDField(unique=True,null=True,blank=True,editable=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']
        indexes = [models.Index(fields=['usuario', 'fecha', 'tipo'])]
        constraints = [models.CheckConstraint(condition=Q(importe__gt=0), name='mov_importe_positivo')]

    def clean(self):
        if self.categoria_id:
            c = self.categoria
            if c.tipo != self.tipo or c.usuario_id not in (None, self.usuario_id):
                raise ValidationError({'categoria': 'La categoría no corresponde al tipo de movimiento o al usuario.'})
        if self.origen != 'NORMAL' and not self._state.adding:
            # La edición de movimientos automáticos está reservada a sus operaciones de origen.
            pass

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_tipo_display()}: {self.descripcion} (${self.importe})'


class Presupuesto(models.Model):
    PERIODOS = [('SEMANAL','Semanal'), ('QUINCENAL','Quincenal'), ('MENSUAL','Mensual')]
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='presupuestos')
    nombre = models.CharField(max_length=100)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, null=True, blank=True)
    monto_limite = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(CENTAVO)])
    periodo = models.CharField(max_length=12, choices=PERIODOS)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    fuente_ingreso = models.ForeignKey(Movimiento, null=True, blank=True, on_delete=models.PROTECT, related_name='presupuestos_financiados')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_fin']
        constraints = [models.CheckConstraint(condition=Q(monto_limite__gt=0), name='pres_limite_positivo'),
                       models.CheckConstraint(condition=Q(fecha_fin__gte=models.F('fecha_inicio')), name='pres_fecha_correcta')]

    def clean(self):
        errores = {}
        if self.fecha_inicio and self.fecha_fin:
            if self.fecha_fin < self.fecha_inicio:
                errores['fecha_fin'] = 'La fecha final debe ser posterior al inicio.'
            else:
                inicio = self.fecha_inicio
                if self.periodo == 'SEMANAL' and self.fecha_fin != inicio + timedelta(days=6):
                    errores['fecha_fin'] = 'Un periodo semanal abarca siete días, ambos incluidos.'
                if self.periodo == 'QUINCENAL' and self.fecha_fin != inicio + timedelta(days=14):
                    errores['fecha_fin'] = 'Un periodo quincenal abarca quince días, ambos incluidos.'
                if self.periodo == 'MENSUAL':
                    a, m = inicio.year + (inicio.month == 12), inicio.month % 12 + 1
                    proximo = inicio.replace(year=a, month=m, day=min(inicio.day, calendar.monthrange(a,m)[1]))
                    if self.fecha_fin != proximo - timedelta(days=1):
                        errores['fecha_fin'] = 'Un mes finaliza el día anterior al mismo día del mes siguiente.'
        if self.categoria_id and (self.categoria.tipo != 'GASTO' or self.categoria.usuario_id not in (None, self.usuario_id)):
            errores['categoria'] = 'Selecciona una categoría de gasto propia o global.'
        if self.fuente_ingreso_id:
            f = self.fuente_ingreso
            if f.usuario_id != self.usuario_id or f.tipo != 'INGRESO' or (self.fecha_fin and f.fecha > self.fecha_fin):
                errores['fuente_ingreso'] = 'Selecciona un ingreso real de tu cuenta con fecha no posterior al presupuesto.'
            else:
                ocupado = Presupuesto.objects.filter(usuario_id=self.usuario_id, fuente_ingreso_id=f.id).exclude(pk=self.pk).aggregate(s=Sum('monto_limite'))['s'] or CERO
                if self.monto_limite and ocupado + self.monto_limite > f.importe:
                    errores['fuente_ingreso'] = f'La fuente dispone de ${f.importe - ocupado} sin asignar a otros presupuestos.'
        if errores:
            raise ValidationError(errores)

    def save(self,*args,**kwargs):
        # Serializa la asignación de una misma fuente en PostgreSQL para evitar doble reserva.
        with transaction.atomic():
            if self.fuente_ingreso_id: Movimiento.objects.select_for_update().get(pk=self.fuente_ingreso_id)
            self.full_clean()
            return super().save(*args,**kwargs)

    def gasto_actual(self):
        q = Movimiento.objects.filter(usuario_id=self.usuario_id, tipo='GASTO', fecha__range=(self.fecha_inicio,self.fecha_fin)).exclude(origen='ABONO_DEUDA')
        if self.categoria_id: q = q.filter(categoria_id=self.categoria_id)
        return q.aggregate(s=Sum('importe'))['s'] or CERO

    def monto_restante(self):
        return self.monto_limite - self.gasto_actual()

    def porcentaje_consumido(self):
        return ((self.gasto_actual() / self.monto_limite) * 100).quantize(Decimal('0.1')) if self.monto_limite else CERO

    def esta_excedido(self):
        return self.gasto_actual() > self.monto_limite


class Ahorro(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='ahorros')
    titulo = models.CharField(max_length=150)
    monto_objetivo = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(CENTAVO)])
    porcentaje_sugerido = models.PositiveSmallIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(100)])
    fecha_limite = models.DateField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    @property
    def monto_actual(self):
        return self.aportaciones.aggregate(s=Sum('importe'))['s'] or CERO

    def porcentaje_progreso(self):
        return min(Decimal('100.0'), (self.monto_actual/self.monto_objetivo*100).quantize(Decimal('0.1'))) if self.monto_objetivo else CERO

    def monto_restante(self):
        return max(CERO, self.monto_objetivo-self.monto_actual)

    def __str__(self): return self.titulo


class AportacionAhorro(models.Model):
    clave_solicitud = models.UUIDField(unique=True,null=True,blank=True,editable=False)
    ahorro = models.ForeignKey(Ahorro, on_delete=models.CASCADE, related_name='aportaciones')
    importe = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(CENTAVO)])
    creado_en = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(importe__gt=0), name='aporte_positivo')]


class GastoFijo(models.Model):
    PERIODOS = [('MENSUAL','Mensual'), ('QUINCENAL','Quincenal'), ('SEMANAL','Semanal'), ('UNICO','Una vez')]
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='gastos_fijos')
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    concepto = models.CharField(max_length=150)
    importe = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(CENTAVO)])
    periodicidad = models.CharField(max_length=12, choices=PERIODOS, default='MENSUAL')
    fecha_vencimiento = models.DateField()
    fecha_pago = models.DateField(null=True, blank=True)
    movimiento = models.OneToOneField(Movimiento, null=True, blank=True, on_delete=models.SET_NULL)
    anterior = models.OneToOneField('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='siguiente')
    creado_en = models.DateTimeField(auto_now_add=True)

    @property
    def estado(self):
        if self.fecha_pago: return 'Pagado'
        return 'Vencido' if self.fecha_vencimiento < timezone.localdate() else 'Pendiente'

    def clean(self):
        if self.categoria_id and (self.categoria.tipo != 'GASTO' or self.categoria.clasificacion != 'FIJO' or self.categoria.usuario_id not in (None,self.usuario_id)):
            raise ValidationError({'categoria':'Selecciona una categoría de gastos fijos permitida.'})


class Deuda(models.Model):
    TIPOS = [('PAGAR','Dinero por pagar'), ('COBRAR','Dinero por cobrar')]
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='deudas')
    persona = models.CharField(max_length=150)
    tipo = models.CharField(max_length=7, choices=TIPOS)
    descripcion = models.CharField(max_length=255)
    importe_original = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(CENTAVO)])
    fecha_registro = models.DateField(default=timezone.localdate)
    fecha_vencimiento = models.DateField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha_vencimiento']

    def clean(self):
        if self.fecha_vencimiento and self.fecha_registro and self.fecha_vencimiento < self.fecha_registro:
            raise ValidationError({'fecha_vencimiento':'No puede vencer antes del registro.'})

    @property
    def abonado(self):
        return self.abonos.aggregate(s=Sum('importe'))['s'] or CERO

    @property
    def saldo_pendiente(self):
        return max(CERO,self.importe_original-self.abonado)

    @property
    def estado(self):
        if self.saldo_pendiente == 0: return 'Pagado'
        if self.fecha_vencimiento < timezone.localdate(): return 'Vencido'
        return 'Pago parcial' if self.abonado else 'Pendiente'

    def __str__(self): return self.persona


class AbonoDeuda(models.Model):
    clave_solicitud = models.UUIDField(unique=True,null=True,blank=True,editable=False)
    deuda = models.ForeignKey(Deuda, on_delete=models.PROTECT, related_name='abonos')
    importe = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(CENTAVO)])
    fecha = models.DateField(default=timezone.localdate)
    movimiento = models.OneToOneField(Movimiento, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)


class Alerta(models.Model):
    TIPOS = [('CERCA','Presupuesto por agotarse'),('EXCESO','Presupuesto excedido'),('VENCE','Vencimiento de deuda')]
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='alertas')
    presupuesto = models.ForeignKey(Presupuesto, on_delete=models.CASCADE, null=True, blank=True)
    deuda = models.ForeignKey(Deuda, on_delete=models.CASCADE, null=True, blank=True)
    tipo = models.CharField(max_length=7, choices=TIPOS)
    mensaje = models.CharField(max_length=255)
    activa = models.BooleanField(default=True)
    leida = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_creacion']
        constraints = [models.UniqueConstraint(fields=['presupuesto','tipo'],condition=Q(presupuesto__isnull=False),name='alerta_unica_presupuesto_tipo'),
                       models.UniqueConstraint(fields=['deuda','tipo'],condition=Q(deuda__isnull=False),name='alerta_unica_deuda_tipo')]


class RegistroImportacion(models.Model):
    """Evita duplicados al importar una misma base histórica más de una vez."""
    clave = models.CharField(max_length=180, unique=True)
    registrado = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = 'Registro de importación'
