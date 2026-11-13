import json

import pytest

from cafe_iot.contrato import LecturaInvalida, validar

TEMA = "cafe/beneficio/secado/sec-temp-01"


def mensaje(**cambios):
    base = {
        "version": "0.1",
        "sensor_id": "sec-temp-01",
        "etapa": "secado",
        "variable": "temperatura",
        "valor": 41.7,
        "unidad": "°C",
        "timestamp": "2026-11-13T14:30:00Z",
    }
    base.update(cambios)
    return json.dumps({k: v for k, v in base.items() if v is not None})


def test_lectura_valida():
    lectura, etapa = validar(TEMA, mensaje())
    assert lectura.valor == 41.7
    assert etapa.fase == "beneficio"
    assert lectura.timestamp.tzinfo is not None


def test_timestamp_con_otra_zona_se_pasa_a_utc():
    lectura, _ = validar(TEMA, mensaje(timestamp="2026-11-13T09:30:00-05:00"))
    assert lectura.timestamp.hour == 14


@pytest.mark.parametrize(
    "tema, carga, motivo",
    [
        ("cafe/secado/sec-temp-01", mensaje(), "formato incorrecto"),
        (TEMA, "{no es json", "JSON"),
        (TEMA, mensaje(valor="caliente"), "valor"),
        (TEMA, mensaje(variable="presion"), "variable"),
        (TEMA, mensaje(extra=1), "extra"),
        (TEMA, mensaje(timestamp="2026-11-13T14:30:00"), "zona horaria"),
        (TEMA, mensaje(etapa="tostado"), "etapa desconocida"),
        ("cafe/beneficio/lavado/sec-temp-01", mensaje(), "no coincide"),
        ("cafe/cultivo/secado/sec-temp-01", mensaje(), "pertenece a beneficio"),
        ("cafe/beneficio/secado/otro-01", mensaje(), "sensor del mensaje"),
        (TEMA, mensaje(unidad="°F"), "unidad"),
        (TEMA, mensaje(valor=500), "fuera del rango"),
        (TEMA, mensaje(version="0.2"), "version"),
    ],
)
def test_mensajes_invalidos(tema, carga, motivo):
    with pytest.raises(LecturaInvalida, match=motivo):
        validar(tema, carga)
