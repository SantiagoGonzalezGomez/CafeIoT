import pytest

from cafe_iot.reglas import MotorReglas, ReglaInvalida, _validar
from cafe_iot.config import cargar_etapas

ETAPAS = set(cargar_etapas())


def regla(**cambios):
    base = dict(id="r1", etapa="secado", variable="temperatura", condicion="mayor_que", umbral=50,
                severidad="critica", mensaje="m")
    base.update(cambios)
    return _validar(base, ETAPAS)


def test_archivo_de_reglas_del_repositorio_es_valido():
    motor = MotorReglas.desde_archivo()
    assert motor.reglas
    assert all(not r.ejemplo for r in motor.reglas if r.fuente)


@pytest.mark.parametrize("valor, esperado", [(49.9, False), (50, False), (50.1, True)])
def test_mayor_que(valor, esperado):
    assert regla().se_incumple(valor) is esperado


def test_menor_que():
    r = regla(condicion="menor_que", umbral=10, variable="humedad_grano")
    assert r.se_incumple(9.5) and not r.se_incumple(10)


@pytest.mark.parametrize("valor, esperado", [(29, True), (30, False), (70, False), (71, True)])
def test_fuera_de_rango(valor, esperado):
    r = regla(condicion="fuera_de_rango", umbral=None, minimo=30, maximo=70)
    assert r.se_incumple(valor) is esperado


def test_motor_solo_evalua_reglas_de_la_etapa_y_variable():
    motor = MotorReglas([regla(), regla(id="r2", etapa="fermentacion", umbral=30)])
    resultado = motor.evaluar("secado", "temperatura", 55)
    assert [(r.id, inc) for r, inc in resultado] == [("r1", True)]
    assert motor.evaluar("secado", "humedad_grano", 5) == []


@pytest.mark.parametrize(
    "cambios, motivo",
    [
        ({"etapa": "tostado"}, "etapa desconocida"),
        ({"variable": "presion"}, "variable desconocida"),
        ({"severidad": "grave"}, "severidad"),
        ({"umbral": None}, "necesita 'umbral'"),
        ({"condicion": "fuera_de_rango", "minimo": 70, "maximo": 30}, "minimo"),
        ({"condicion": "igual_a"}, "condición desconocida"),
        ({"color": "rojo"}, "unexpected keyword"),
    ],
)
def test_reglas_mal_escritas_se_rechazan(cambios, motivo):
    with pytest.raises(ReglaInvalida, match=motivo):
        regla(**cambios)


def test_ids_repetidos():
    with pytest.raises(ReglaInvalida, match="repetidos"):
        MotorReglas([regla(), regla()])
