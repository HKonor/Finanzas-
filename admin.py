"""Django admin: solo identidad y catálogos; finanzas privadas NO expuestas."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario,Categoria

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('email','username','is_staff','is_active','correo_verificado','last_login','ultima_actividad')
    fieldsets = UserAdmin.fieldsets + (('Finanza',{'fields':('correo_verificado','telefono','moneda','ultima_actividad','cambiar_password_obligatorio')}),)

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display=('nombre','tipo','clasificacion','usuario','activa')
    list_filter=('tipo','clasificacion','activa')
