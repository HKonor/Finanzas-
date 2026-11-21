"""Crea un administrador inicial SIN imprimir ni almacenar su contraseña en el proyecto."""
import os
from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from core.models import Usuario

class Command(BaseCommand):
    help='Crea el administrador inicial a partir de ADMIN_EMAIL, ADMIN_USERNAME y ADMIN_PASSWORD.'
    def handle(self,*args,**options):
        email=os.getenv('ADMIN_EMAIL','admin@finanza.local').strip().lower()
        username=os.getenv('ADMIN_USERNAME','administrador').strip()
        password=os.getenv('ADMIN_PASSWORD','')
        if not password:raise CommandError('Configura ADMIN_PASSWORD en tu archivo .env antes de crear el admin.')
        try:validate_password(password)
        except ValidationError as e:raise CommandError('; '.join(e.messages))
        if Usuario.objects.filter(email__iexact=email).exists():
            self.stdout.write(self.style.WARNING('Ya existe una cuenta con este correo. No se alteró su contraseña.'));return
        if Usuario.objects.filter(username=username).exists():raise CommandError('Este nombre de usuario ya está ocupado.')
        u=Usuario.objects.create_superuser(username=username,email=email,password=password,correo_verificado=True,cambiar_password_obligatorio=True)
        self.stdout.write(self.style.SUCCESS(f'Administrador creado: {u.email}. Se exigirá cambiar contraseña al entrar.'))
