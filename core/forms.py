"""Formularios con filtrado por propietario y reglas de integridad de negocio."""
from decimal import Decimal
from uuid import uuid4
from django import forms
from django.db.models import Q, Sum
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm, AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import Usuario,Categoria,Movimiento,Presupuesto,Ahorro,GastoFijo,Deuda,CERO,CENTAVO
from .validators import validar_nombre


def decorar(form):
    for campo in form.fields.values():
        if not isinstance(campo.widget,forms.CheckboxInput): campo.widget.attrs.setdefault('class','control')
        if isinstance(campo,forms.DateField): campo.widget=forms.DateInput(attrs={'class':'control','type':'date'},format='%Y-%m-%d')
    return form


class RegistroForm(UserCreationForm):
    email=forms.EmailField(label='Correo electrónico')
    first_name=forms.CharField(label='Nombre',max_length=150)
    last_name=forms.CharField(label='Apellidos',max_length=150)
    class Meta(UserCreationForm.Meta):
        model=Usuario
        fields=('username','first_name','last_name','email','password1','password2')
    def __init__(self,*args,**kwargs): super().__init__(*args,**kwargs);decorar(self)
    def clean_first_name(self): return validar_nombre(self.cleaned_data['first_name'])
    def clean_last_name(self): return validar_nombre(self.cleaned_data['last_name'])
    def clean_email(self):
        e=self.cleaned_data['email'].lower().strip()
        if Usuario.objects.filter(email__iexact=e).exists():raise ValidationError('Este correo ya está registrado.')
        return e
    def save(self,commit=True):
        u=super().save(commit=False)
        u.email=self.cleaned_data['email'];u.is_active=False;u.correo_verificado=False
        if commit:u.save()
        return u


class AccesoForm(forms.Form):
    email=forms.EmailField(label='Correo electrónico')
    password=forms.CharField(label='Contraseña',widget=forms.PasswordInput)
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);decorar(self)


class PerfilForm(forms.ModelForm):
    class Meta:
        model=Usuario
        fields=('first_name','last_name','telefono','moneda')
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);decorar(self)
    def clean_first_name(self):
        valor=self.cleaned_data['first_name']
        return validar_nombre(valor) if valor else valor
    def clean_last_name(self):
        valor=self.cleaned_data['last_name']
        return validar_nombre(valor) if valor else valor


class MovimientoForm(forms.ModelForm):
    token_operacion=forms.UUIDField(widget=forms.HiddenInput(),initial=uuid4,label='Identificador de operación')
    class Meta:
        model=Movimiento
        fields=('tipo','categoria','importe','descripcion','fecha','periodicidad')
    def __init__(self,*args,usuario,**kwargs):
        super().__init__(*args,**kwargs);self.usuario=usuario
        self.fields['categoria'].queryset=Categoria.objects.filter(Q(usuario__isnull=True)|Q(usuario=usuario),activa=True)
        decorar(self)
    def clean(self):
        self.instance.usuario=self.usuario
        data=super().clean(); c=data.get('categoria'); tipo=data.get('tipo')
        if c and c.tipo!=tipo:self.add_error('categoria','La categoría debe coincidir con el tipo de movimiento.')
        if self.instance.pk and self.instance.origen!='NORMAL':raise ValidationError('Los movimientos de pagos se editan desde su módulo de origen.')
        if self.instance.pk and self.instance.presupuestos_financiados.exists():
            asignado=self.instance.presupuestos_financiados.aggregate(s=Sum('monto_limite'))['s'] or CERO
            if tipo!='INGRESO' or data.get('importe',CERO)<asignado or (data.get('fecha') and self.instance.presupuestos_financiados.filter(fecha_fin__lt=data['fecha']).exists()):
                raise ValidationError('Este ingreso financia presupuestos: no puedes cambiar su tipo ni reducirlo por debajo del importe asignado.')
        return data
    def save(self,commit=True):
        m=super().save(commit=False);m.usuario=self.usuario
        if not m.pk:m.clave_solicitud=self.cleaned_data['token_operacion']
        if commit:m.save()
        return m


class PresupuestoForm(forms.ModelForm):
    class Meta:
        model=Presupuesto
        fields=('nombre','categoria','monto_limite','periodo','fecha_inicio','fecha_fin','fuente_ingreso')
    def __init__(self,*args,usuario,**kwargs):
        super().__init__(*args,**kwargs);self.usuario=usuario
        self.fields['categoria'].queryset=Categoria.objects.filter(Q(usuario__isnull=True)|Q(usuario=usuario),tipo='GASTO',activa=True)
        self.fields['categoria'].required=False
        self.fields['categoria'].empty_label='General (todos los gastos)'
        self.fields['fuente_ingreso'].queryset=Movimiento.objects.filter(usuario=usuario,tipo='INGRESO')
        self.fields['fuente_ingreso'].required=False
        self.fields['fuente_ingreso'].empty_label='Sin fuente específica'
        decorar(self)
    def clean(self):
        data=super().clean()
        self.instance.usuario=self.usuario
        for k,v in data.items():
            if hasattr(self.instance,k):setattr(self.instance,k,v)
        try:self.instance.clean()
        except ValidationError as exc:
            if hasattr(exc,'message_dict'):
                for k,err in exc.message_dict.items():
                    for msg in err:self.add_error(k,msg)
            else:self.add_error(None,exc)
        return data
    def save(self,commit=True):
        o=super().save(commit=False);o.usuario=self.usuario
        if commit:o.save()
        return o


class AhorroForm(forms.ModelForm):
    class Meta:
        model=Ahorro
        fields=('titulo','monto_objetivo','porcentaje_sugerido','fecha_limite')
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);decorar(self)
    def clean_monto_objetivo(self):
        monto=self.cleaned_data['monto_objetivo']
        if self.instance.pk and monto<self.instance.monto_actual:raise ValidationError('El objetivo no puede ser inferior a lo que ya has ahorrado.')
        return monto


class AportacionForm(forms.Form):
    token_operacion=forms.UUIDField(widget=forms.HiddenInput(),initial=uuid4,label='Identificador de operación')
    importe=forms.DecimalField(label='Aportación ($)',min_value=CENTAVO,max_digits=14,decimal_places=2)
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);decorar(self)


class GastoFijoForm(forms.ModelForm):
    class Meta:
        model=GastoFijo
        fields=('concepto','categoria','importe','periodicidad','fecha_vencimiento')
    def __init__(self,*args,usuario,**kwargs):
        super().__init__(*args,**kwargs);self.usuario=usuario
        self.fields['categoria'].queryset=Categoria.objects.filter(Q(usuario__isnull=True)|Q(usuario=usuario),tipo='GASTO',clasificacion='FIJO',activa=True)
        decorar(self)
    def clean(self):
        self.instance.usuario=self.usuario
        return super().clean()
    def save(self,commit=True):
        g=super().save(commit=False);g.usuario=self.usuario
        if commit:g.full_clean();g.save()
        return g


class DeudaForm(forms.ModelForm):
    class Meta:
        model=Deuda
        fields=('persona','tipo','descripcion','importe_original','fecha_registro','fecha_vencimiento')
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);decorar(self)
    def clean_importe_original(self):
        importe=self.cleaned_data['importe_original']
        if self.instance.pk and importe<self.instance.abonado:raise ValidationError('El importe no puede ser menor a los abonos registrados.')
        return importe
    def clean_tipo(self):
        t=self.cleaned_data['tipo']
        if self.instance.pk and self.instance.abonos.exists() and t!=self.instance.tipo:raise ValidationError('No puedes cambiar el tipo de una deuda con abonos.')
        return t


class CategoriaForm(forms.ModelForm):
    class Meta:
        model=Categoria
        fields=('nombre','tipo','clasificacion','categoria_padre','activa')
    def __init__(self,*args,usuario=None,globales=False,**kwargs):
        super().__init__(*args,**kwargs);self.usuario=usuario;self.globales=globales
        qs=Categoria.objects.filter(usuario__isnull=True) if globales else Categoria.objects.filter(Q(usuario__isnull=True)|Q(usuario=usuario))
        if self.instance.pk:qs=qs.exclude(pk=self.instance.pk)
        self.fields['categoria_padre'].queryset=qs
        decorar(self)
    def clean(self):
        self.instance.usuario=None if self.globales else self.usuario
        return super().clean()
    def save(self,commit=True):
        c=super().save(commit=False);c.usuario=None if self.globales else self.usuario
        if commit:c.full_clean();c.save()
        return c


class AdminUsuarioForm(forms.ModelForm):
    password_nueva=forms.CharField(label='Contraseña inicial',widget=forms.PasswordInput,required=False,help_text='Obligatoria solo al crear; el usuario deberá cambiarla al iniciar sesión.')
    class Meta:
        model=Usuario
        fields=('username','email','first_name','last_name','is_active','is_staff','correo_verificado')
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);decorar(self)
    def clean_first_name(self):
        valor=self.cleaned_data['first_name']
        return validar_nombre(valor) if valor else valor
    def clean_last_name(self):
        valor=self.cleaned_data['last_name']
        return validar_nombre(valor) if valor else valor
    def clean_email(self):
        email=self.cleaned_data['email'].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():raise ValidationError('Correo ya utilizado.')
        return email
    def clean_password_nueva(self):
        password=self.cleaned_data['password_nueva']
        if not self.instance.pk and not password:raise ValidationError('Indica una contraseña inicial.')
        if password:validate_password(password)
        return password
    def save(self,commit=True):
        user=super().save(commit=False)
        if self.cleaned_data.get('password_nueva'):
            user.set_password(self.cleaned_data['password_nueva']);user.cambiar_password_obligatorio=True
        if commit:user.save()
        return user
