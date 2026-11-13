"""Motor de reglas agronómicas (componente 3 de la arquitectura).

Las reglas viven en config/reglas.yaml para que los umbrales se puedan ajustar
con apoyo agronómico sin cambiar el código.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from .config import DIR_CONFIG, cargar_etapas
from .contrato import UNIDADES

Condicion = Literal["mayor_que", "menor_que", "fuera_de_rango"]
SEVERIDADES = ("informativa", "advertencia", "critica")


@dataclass(frozen=True)
class Regla:
    id: str
    etapa: str
    variable: str
    condicion: Condicion
    severidad: str
    mensaje: str
    umbral: float | None = None
    minimo: float | None = None
    maximo: float | None = None
    fuente: str | None = None
    ejemplo: bool = True

    def se_incumple(self, valor: float) -> bool:
        if self.condicion == "mayor_que":
            return valor > self.umbral
        if self.condicion == "menor_que":
            return valor < self.umbral
        return not self.minimo <= valor <= self.maximo

    def describir_umbral(self) -> str:
        unidad = UNIDADES[self.variable]
        if self.condicion == "mayor_que":
            return f"> {self.umbral:g} {unidad}"
        if self.condicion == "menor_que":
            return f"< {self.umbral:g} {unidad}"
        return f"fuera de {self.minimo:g}–{self.maximo:g} {unidad}"


class ReglaInvalida(ValueError):
    pass


def _validar(datos: dict, etapas: set[str]) -> Regla:
    rid = datos.get("id", "<sin id>")
    try:
        regla = Regla(**datos)
    except TypeError as e:
        raise ReglaInvalida(f"regla '{rid}': {e}") from e
    if regla.etapa not in etapas:
        raise ReglaInvalida(f"regla '{rid}': etapa desconocida '{regla.etapa}'")
    if regla.variable not in UNIDADES:
        raise ReglaInvalida(f"regla '{rid}': variable desconocida '{regla.variable}'")
    if regla.severidad not in SEVERIDADES:
        raise ReglaInvalida(f"regla '{rid}': severidad debe ser una de {SEVERIDADES}")
    if regla.condicion in ("mayor_que", "menor_que") and regla.umbral is None:
        raise ReglaInvalida(f"regla '{rid}': la condición {regla.condicion} necesita 'umbral'")
    if regla.condicion == "fuera_de_rango":
        if regla.minimo is None or regla.maximo is None or regla.minimo >= regla.maximo:
            raise ReglaInvalida(f"regla '{rid}': fuera_de_rango necesita 'minimo' < 'maximo'")
    elif regla.condicion not in ("mayor_que", "menor_que"):
        raise ReglaInvalida(f"regla '{rid}': condición desconocida '{regla.condicion}'")
    return regla


class MotorReglas:
    def __init__(self, reglas: list[Regla]):
        ids = [r.id for r in reglas]
        repetidos = {i for i in ids if ids.count(i) > 1}
        if repetidos:
            raise ReglaInvalida(f"ids repetidos: {sorted(repetidos)}")
        self.reglas = reglas
        self._indice: dict[tuple[str, str], list[Regla]] = {}
        for r in reglas:
            self._indice.setdefault((r.etapa, r.variable), []).append(r)

    @classmethod
    def desde_archivo(cls, ruta: Path | None = None) -> "MotorReglas":
        datos = yaml.safe_load((ruta or DIR_CONFIG / "reglas.yaml").read_text(encoding="utf-8")) or {}
        etapas = set(cargar_etapas())
        return cls([_validar(d, etapas) for d in datos.get("reglas", [])])

    def aplicables(self, etapa: str, variable: str) -> list[Regla]:
        """Reglas que aplican a una etapa y variable."""
        return self._indice.get((etapa, variable), [])

    def evaluar(self, etapa: str, variable: str, valor: float) -> list[tuple[Regla, bool]]:
        """Para cada regla aplicable devuelve (regla, se_incumple)."""
        return [(r, r.se_incumple(valor)) for r in self.aplicables(etapa, variable)]
