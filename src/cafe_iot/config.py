"""Configuración del sistema: variables de entorno y archivos YAML."""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
DIR_CONFIG = Path(os.getenv("CAFE_DIR_CONFIG", RAIZ / "config"))


@dataclass(frozen=True)
class Ajustes:
    mqtt_host: str = os.getenv("MQTT_HOST", "localhost")
    mqtt_puerto: int = int(os.getenv("MQTT_PUERTO", "1883"))
    mqtt_usuario: str | None = os.getenv("MQTT_USUARIO") or None
    mqtt_clave: str | None = os.getenv("MQTT_CLAVE") or None
    base_datos: str = os.getenv("DATABASE_URL", "postgresql://cafe:cafe@localhost:5432/cafe_iot")


ajustes = Ajustes()


@dataclass(frozen=True)
class Etapa:
    codigo: str
    nombre: str
    fase: str
    fase_nombre: str
    tecnologia: str
    orden: int


@lru_cache
def cargar_etapas(ruta: Path | None = None) -> dict[str, Etapa]:
    """Devuelve las etapas por código, en el orden del proceso."""
    datos = yaml.safe_load((ruta or DIR_CONFIG / "etapas.yaml").read_text(encoding="utf-8"))
    etapas: dict[str, Etapa] = {}
    orden = 0
    for fase in datos["fases"]:
        for e in fase["etapas"]:
            orden += 1
            etapas[e["codigo"]] = Etapa(
                codigo=e["codigo"],
                nombre=e["nombre"],
                fase=fase["codigo"],
                fase_nombre=fase["nombre"],
                tecnologia=fase["tecnologia"],
                orden=orden,
            )
    return etapas
