"""Muestra el código TOTP vigente de un usuario demo:  python -m app.tools.totp fiscalizador@mtt.cl"""
import sys

import pyotp

from ..domain.catalogo import USUARIOS_DEMO

email = sys.argv[1] if len(sys.argv) > 1 else "fiscalizador@mtt.cl"
u = next((x for x in USUARIOS_DEMO if x["email"] == email and x["totp_secret"]), None)
print(pyotp.TOTP(u["totp_secret"]).now() if u else f"{email}: sin MFA o inexistente")
