from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class CorreoBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        correo = (kwargs.get('email') or username or '').strip()
        if not correo or password is None: return None
        try: user = get_user_model().objects.get(email__iexact=correo)
        except (get_user_model().DoesNotExist, get_user_model().MultipleObjectsReturned): return None
        if user.check_password(password) and self.user_can_authenticate(user): return user
        return None

    def user_can_authenticate(self, user):
        return bool(user.is_active and user.correo_verificado and not user.bloqueado_admin)
