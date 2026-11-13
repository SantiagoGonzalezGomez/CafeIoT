"""Almacenamiento (componente 2 de la arquitectura): PostgreSQL, con TimescaleDB si está disponible."""

import logging
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

from .config import ajustes
from .contrato import Lectura
from .reglas import Regla

log = logging.getLogger(__name__)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS lecturas (
    ts          TIMESTAMPTZ      NOT NULL,
    sensor_id   TEXT             NOT NULL,
    fase        TEXT             NOT NULL,
    etapa       TEXT             NOT NULL,
    variable    TEXT             NOT NULL,
    valor       DOUBLE PRECISION NOT NULL,
    unidad      TEXT             NOT NULL,
    bateria     DOUBLE PRECISION,
    recibido    TIMESTAMPTZ      NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS lecturas_etapa_variable_ts ON lecturas (etapa, variable, ts DESC);
CREATE INDEX IF NOT EXISTS lecturas_sensor_ts ON lecturas (sensor_id, ts DESC);

CREATE TABLE IF NOT EXISTS rechazos (
    id        BIGSERIAL   PRIMARY KEY,
    tema      TEXT        NOT NULL,
    carga     TEXT        NOT NULL,
    motivo    TEXT        NOT NULL,
    recibido  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alertas (
    id          BIGSERIAL        PRIMARY KEY,
    regla_id    TEXT             NOT NULL,
    sensor_id   TEXT             NOT NULL,
    etapa       TEXT             NOT NULL,
    variable    TEXT             NOT NULL,
    severidad   TEXT             NOT NULL,
    mensaje     TEXT             NOT NULL,
    umbral      TEXT             NOT NULL,
    valor_inicial DOUBLE PRECISION NOT NULL,
    valor_ultimo  DOUBLE PRECISION NOT NULL,
    inicio      TIMESTAMPTZ      NOT NULL,
    ultima      TIMESTAMPTZ      NOT NULL,
    fin         TIMESTAMPTZ
);
-- Solo puede haber una alerta abierta por regla y sensor.
CREATE UNIQUE INDEX IF NOT EXISTS alertas_abierta_unica ON alertas (regla_id, sensor_id) WHERE fin IS NULL;
"""


def conectar() -> psycopg.Connection:
    return psycopg.connect(ajustes.base_datos, row_factory=dict_row, autocommit=True)


def inicializar(con: psycopg.Connection) -> None:
    """Crea las tablas si no existen. Usa TimescaleDB solo si la extensión está instalada."""
    con.execute(ESQUEMA)
    try:
        with con.transaction():
            con.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
            con.execute("SELECT create_hypertable('lecturas', 'ts', if_not_exists => TRUE, migrate_data => TRUE)")
        log.info("TimescaleDB activo: 'lecturas' es una hypertable")
    except psycopg.Error:
        log.info("TimescaleDB no disponible: se usa PostgreSQL sin extensión")


def guardar_lectura(con: psycopg.Connection, lectura: Lectura, fase: str) -> None:
    con.execute(
        """INSERT INTO lecturas (ts, sensor_id, fase, etapa, variable, valor, unidad, bateria)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (lectura.timestamp, lectura.sensor_id, fase, lectura.etapa, lectura.variable,
         lectura.valor, lectura.unidad, lectura.bateria),
    )


def guardar_rechazo(con: psycopg.Connection, tema: str, carga: bytes, motivo: str) -> None:
    con.execute(
        "INSERT INTO rechazos (tema, carga, motivo) VALUES (%s, %s, %s)",
        (tema, carga.decode("utf-8", errors="replace")[:4000], motivo),
    )


def actualizar_alerta(con: psycopg.Connection, regla: Regla, lectura: Lectura, incumple: bool) -> str | None:
    """Abre, actualiza o cierra la alerta de una regla para un sensor.

    Devuelve 'abierta', 'cerrada' o None si no hubo cambio de estado.
    """
    if incumple:
        fila = con.execute(
            """INSERT INTO alertas (regla_id, sensor_id, etapa, variable, severidad, mensaje, umbral,
                                    valor_inicial, valor_ultimo, inicio, ultima)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (regla_id, sensor_id) WHERE fin IS NULL
               DO UPDATE SET valor_ultimo = EXCLUDED.valor_ultimo, ultima = EXCLUDED.ultima
               RETURNING (xmax = 0) AS nueva""",
            (regla.id, lectura.sensor_id, regla.etapa, regla.variable, regla.severidad, regla.mensaje,
             regla.describir_umbral(), lectura.valor, lectura.valor, lectura.timestamp, lectura.timestamp),
        ).fetchone()
        return "abierta" if fila["nueva"] else None
    cur = con.execute(
        "UPDATE alertas SET fin = %s, valor_ultimo = %s WHERE regla_id = %s AND sensor_id = %s AND fin IS NULL",
        (lectura.timestamp, lectura.valor, regla.id, lectura.sensor_id),
    )
    return "cerrada" if cur.rowcount else None


# ---------- consultas para la API ----------

def ultimas_por_sensor(con: psycopg.Connection) -> list[dict]:
    return con.execute(
        """SELECT DISTINCT ON (sensor_id, variable) sensor_id, fase, etapa, variable, valor, unidad, ts
           FROM lecturas ORDER BY sensor_id, variable, ts DESC"""
    ).fetchall()


def serie(con: psycopg.Connection, etapa: str, variable: str, desde: datetime) -> list[dict]:
    return con.execute(
        """SELECT ts, sensor_id, valor FROM lecturas
           WHERE etapa = %s AND variable = %s AND ts >= %s ORDER BY ts""",
        (etapa, variable, desde),
    ).fetchall()


def alertas(con: psycopg.Connection, abiertas: bool, limite: int = 100) -> list[dict]:
    condicion = "fin IS NULL" if abiertas else "fin IS NOT NULL"
    return con.execute(
        f"SELECT * FROM alertas WHERE {condicion} ORDER BY inicio DESC LIMIT %s", (limite,)
    ).fetchall()


def rechazos_recientes(con: psycopg.Connection, limite: int = 20) -> list[dict]:
    return con.execute("SELECT * FROM rechazos ORDER BY recibido DESC LIMIT %s", (limite,)).fetchall()
