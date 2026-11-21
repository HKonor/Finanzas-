"""Validaciones compartidas para identidad y contraseñas."""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validar_nombre(valor):
    """Acepta letras Unicode y espacios; no cifras ni signos en nombres."""
    if not valor or not all(p.isalpha() for p in valor.strip().split()):
        raise ValidationError('Solo se permiten letras y espacios en el nombre.')
    return valor.strip()


class ContrasenaSegura:
    def validate(self,password,user=None):
        if not any(c.isupper() for c in password) or not any(c.islower() for c in password) or not any(c.isdigit() for c in password):
            raise ValidationError(_('La contraseña debe incluir mayúsculas, minúsculas y números.'),code='password_fuerte')
    def get_help_text(self):
        return _('La contraseña debe incluir al menos una mayúscula, una minúscula y un número.')
