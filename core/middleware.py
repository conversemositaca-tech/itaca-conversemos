from .tenant import set_clinica_actual


class TenantActualMiddleware:
    """Fija la clínica activa del request a partir del usuario logueado.

    Durante el procesamiento de la petición, los modelos filtran por la clínica
    del usuario autenticado. Se limpia al final para no filtrar contexto entre
    requests. Sin usuario autenticado no hay clínica (la API responde 403).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        clinica = getattr(user, "clinica", None) if (user and user.is_authenticated) else None
        set_clinica_actual(clinica)
        try:
            return self.get_response(request)
        finally:
            set_clinica_actual(None)
