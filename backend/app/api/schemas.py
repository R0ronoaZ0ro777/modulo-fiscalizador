from typing import Literal

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class MfaIn(BaseModel):
    mfa_token: str
    codigo: str = Field(min_length=6, max_length=7)


class RefreshIn(BaseModel):
    refresh_token: str


class SancionIn(BaseModel):
    tipo: Literal["AMONESTACION", "MULTA"]
    monto_uf: float | None = None


class ResolverIn(BaseModel):
    resolucion: Literal["CURSAR", "DESCARTAR"]
    observaciones: str = Field(max_length=2000)
    sancion: SancionIn | None = None


class UmbralIn(BaseModel):
    valor: float
    version: int = Field(ge=1)
