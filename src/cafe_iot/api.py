"""API y panel único (componente 5 de la arquitectura).

Uso: uvicorn cafe_iot.api:app --port 8000
Documentación interactiva de la API: http://localhost:8000/docs
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .config import cargar_etapas
from .contrato import UNIDADES
from .reglas import MotorReglas

PANEL = Path(__file__).parent / "panel"
SIN_DATOS_RECIENTES = timedelta(minutes=10)


@asynccontextmanager
async def _inicio(_app: FastAPI):
    with db.conectar() as con:
        db.inicializar(con)
    yield


app = FastAPI(
    title="Café IoT · UCEVA",
    description="Monitoreo del proceso de elaboración del café: lecturas, alertas y estado por etapa.",
    version="0.1.0",
    lifespan=_inicio,
)
app.mount("/panel", StaticFiles(directory=PANEL), name="panel")


@app.get("/", include_in_schema=False)
def panel():
    return FileResponse(PANEL / "index.html")


@app.get("/api/estado", summary="Estado de las etapas del proceso")
def estado():
    """Por cada fase y etapa: últimas lecturas por sensor, alertas abiertas y estado general."""
    ahora = datetime.now(timezone.utc)
    with db.conectar() as con:
        ultimas = db.ultimas_por_sensor(con)
        abiertas = db.alertas(con, abiertas=True)
        rechazos = con.execute("SELECT count(*) AS n FROM rechazos WHERE recibido > now() - interval '1 hour'").fetchone()["n"]

    fases: dict[str, dict] = {}
    for etapa in cargar_etapas().values():
        lect = [l for l in ultimas if l["etapa"] == etapa.codigo]
        alr = [a for a in abiertas if a["etapa"] == etapa.codigo]
        if alr:
            est = "critica" if any(a["severidad"] == "critica" for a in alr) else "alerta"
        elif not lect:
            est = "sin_datos"
        elif ahora - max(l["ts"] for l in lect) > SIN_DATOS_RECIENTES:
            est = "desactualizada"
        else:
            est = "normal"
        fase = fases.setdefault(etapa.fase, {"codigo": etapa.fase, "nombre": etapa.fase_nombre,
                                              "tecnologia": etapa.tecnologia, "etapas": []})
        fase["etapas"].append({
            "codigo": etapa.codigo, "nombre": etapa.nombre, "estado": est,
            "alertas_abiertas": len(alr), "lecturas": lect,
        })
    return {"generado": ahora, "fases": list(fases.values()), "alertas_abiertas": abiertas,
            "rechazos_ultima_hora": rechazos}


@app.get("/api/serie", summary="Serie de tiempo de una variable en una etapa")
def serie(etapa: str, variable: str, horas: float = Query(6, gt=0, le=24 * 30)):
    if etapa not in cargar_etapas():
        raise HTTPException(404, f"etapa desconocida: {etapa}")
    if variable not in UNIDADES:
        raise HTTPException(404, f"variable desconocida: {variable}")
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    with db.conectar() as con:
        puntos = db.serie(con, etapa, variable, desde)
    return {"etapa": etapa, "variable": variable, "unidad": UNIDADES[variable], "puntos": puntos}


@app.get("/api/alertas", summary="Alertas abiertas o cerradas")
def alertas(abiertas: bool = True, limite: int = Query(100, gt=0, le=1000)):
    with db.conectar() as con:
        return db.alertas(con, abiertas, limite)


@app.get("/api/rechazos", summary="Mensajes rechazados por no cumplir el contrato")
def rechazos(limite: int = Query(20, gt=0, le=500)):
    with db.conectar() as con:
        return db.rechazos_recientes(con, limite)


@app.get("/api/reglas", summary="Reglas de alerta configuradas")
def reglas():
    return [
        {"id": r.id, "etapa": r.etapa, "variable": r.variable, "umbral": r.describir_umbral(),
         "severidad": r.severidad, "mensaje": r.mensaje, "fuente": r.fuente, "ejemplo": r.ejemplo}
        for r in MotorReglas.desde_archivo().reglas
    ]
