"""Errores de dominio. La capa API los traduce a respuestas HTTP controladas."""


class ErrorDominio(Exception):
    status = 400
    codigo = "ERROR"

    def __init__(self, mensaje: str, **extra):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.extra = extra


class CredencialesInvalidas(ErrorDominio):
    status, codigo = 401, "CREDENCIALES_INVALIDAS"


class TokenInvalido(ErrorDominio):
    status, codigo = 401, "TOKEN_INVALIDO"


class CuentaBloqueada(ErrorDominio):
    status, codigo = 429, "CUENTA_BLOQUEADA"


class PermisoDenegado(ErrorDominio):
    status, codigo = 403, "PERMISO_DENEGADO"


class NoEncontrado(ErrorDominio):
    status, codigo = 404, "NO_ENCONTRADO"


class ConflictoEstado(ErrorDominio):
    """La operación no es válida para el estado actual del recurso."""
    status, codigo = 409, "CONFLICTO_ESTADO"


class ConflictoVersion(ErrorDominio):
    """Versionado optimista: alguien modificó el recurso antes."""
    status, codigo = 409, "CONFLICTO_VERSION"


class ReglaNegocio(ErrorDominio):
    status, codigo = 422, "REGLA_NEGOCIO"
