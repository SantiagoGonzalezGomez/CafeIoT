"""Validación de los mensajes de los sensores según el contrato de datos v0.1.

Ver docs/contrato_datos.md.
"""

import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .config import Etapa, cargar_etapas

VERSION_CONTRATO = "0.1"

Variable = Literal[
    "temperatura", "humedad_relativa", "humedad_suelo", "humedad_grano", "ph", "co2", "radiacion_solar"
]

# Unidad acordada y rango físicamente posible por variable.
# Los rangos solo descartan errores del sensor: NO son umbrales de alerta.
UNIDADES: dict[str, str] = {
    "temperatura": "°C",
    "humedad_relativa": "%",
    "humedad_suelo": "%",
    "humedad_grano": "%",
    "ph": "pH",
    "co2": "ppm",
    "radiacion_solar": "W/m²",
}
RANGOS_VALIDOS: dict[str, tuple[float, float]] = {
    "temperatura": (-10, 80),
    "humedad_relativa": (0, 100),
    "humedad_suelo": (0, 100),
    "humedad_grano": (0, 80),
    "ph": (0, 14),
    "co2": (0, 50_000),
    "radiacion_solar": (0, 2_000),
}


class Lectura(BaseModel):
    """Una lectura de sensor válida."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["0.1"]
    sensor_id: str = Field(pattern=r"^[a-z0-9-]{3,40}$")
    etapa: str
    variable: Variable
    valor: float
    unidad: str
    timestamp: datetime
    bateria: float | None = Field(default=None, ge=0, le=100)

    @field_validator("timestamp")
    @classmethod
    def _con_zona_horaria(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("el timestamp debe indicar la zona horaria (usar UTC, terminado en Z)")
        return v.astimezone(timezone.utc)


class LecturaInvalida(Exception):
    """El mensaje no cumple el contrato. El texto explica por qué."""


def validar(tema: str, carga: bytes | str, etapas: dict[str, Etapa] | None = None) -> tuple[Lectura, Etapa]:
    """Valida un mensaje MQTT y devuelve la lectura y su etapa.

    Lanza LecturaInvalida con un motivo legible si algo no cumple el contrato.
    """
    etapas = etapas or cargar_etapas()

    partes = tema.split("/")
    if len(partes) != 4 or partes[0] != "cafe":
        raise LecturaInvalida(f"tema con formato incorrecto: '{tema}' (se espera cafe/<fase>/<etapa>/<sensor_id>)")
    _, fase_tema, etapa_tema, sensor_tema = partes

    try:
        datos = json.loads(carga)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise LecturaInvalida(f"el contenido no es JSON válido: {e}") from e

    try:
        lectura = Lectura.model_validate(datos)
    except ValidationError as e:
        errores = "; ".join(f"{'.'.join(str(x) for x in err['loc']) or 'mensaje'}: {err['msg']}" for err in e.errors())
        raise LecturaInvalida(errores) from e

    etapa = etapas.get(lectura.etapa)
    if etapa is None:
        raise LecturaInvalida(f"etapa desconocida: '{lectura.etapa}'")
    if etapa.codigo != etapa_tema or etapa.fase != fase_tema:
        raise LecturaInvalida(
            f"el tema dice {fase_tema}/{etapa_tema} pero la etapa '{etapa.codigo}' pertenece a {etapa.fase}"
            if etapa.fase != fase_tema
            else f"la etapa del mensaje ('{lectura.etapa}') no coincide con la del tema ('{etapa_tema}')"
        )
    if lectura.sensor_id != sensor_tema:
        raise LecturaInvalida(f"el sensor del mensaje ('{lectura.sensor_id}') no coincide con el del tema ('{sensor_tema}')")

    unidad_esperada = UNIDADES[lectura.variable]
    if lectura.unidad != unidad_esperada:
        raise LecturaInvalida(f"unidad '{lectura.unidad}' incorrecta para {lectura.variable}; se espera '{unidad_esperada}'")

    minimo, maximo = RANGOS_VALIDOS[lectura.variable]
    if not minimo <= lectura.valor <= maximo:
        raise LecturaInvalida(f"valor {lectura.valor} fuera del rango posible de {lectura.variable} ({minimo} a {maximo})")

    return lectura, etapa
