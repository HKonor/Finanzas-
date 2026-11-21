from django.contrib.auth import logout
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.http import http_date

class InactividadMiddleware:
    """Inactividad en servidor; evita reutilizar vistas privadas por caché o retroceso."""
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        if request.user.is_authenticated:
            ahora = timezone.now()
            anterior = request.session.get('ultima_accion')
            if anterior is not None and ahora.timestamp() - anterior > 1200:
                logout(request)
                return redirect('/login/?inactivo=1')
            if not request.user.is_active or not request.user.correo_verificado:
                logout(request)
                return redirect('/login/')
            request.session['ultima_accion'] = ahora.timestamp()
            if not request.user.ultima_actividad or (ahora-request.user.ultima_actividad).total_seconds() >= 60:
                get_user_model().objects.filter(pk=request.user.pk).update(ultima_actividad=ahora)
                request.user.ultima_actividad = ahora
        respuesta = self.get_response(request)
        if request.user.is_authenticated or request.path.startswith(('/admin-panel/','/api/')):
            respuesta['Cache-Control'] = 'private, no-store, max-age=0'
            respuesta['Pragma'] = 'no-cache'
            respuesta['Expires'] = http_date(0)
        return respuesta
