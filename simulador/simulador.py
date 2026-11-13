"""Simulador de sensores del laboratorio de café.

Publica lecturas falsas en MQTT con el formato del contrato de datos v0.1,
para desarrollar y probar el software mientras llegan los sensores reales.
Los valores son inventados: sirven para probar, no describen el proceso real.

Ejemplos:
    python simulador/simulador.py                       # una lectura por sensor cada 5 s
    python simulador/simulador.py --historial 120       # primero 2 horas de datos pasados
    python simulador/simulador.py --anomalia            # la temperatura de secado sube sobre 50 °C
    python simulador/simulador.py --invalidos           # de vez en cuando envía mensajes mal formados
"""

import argparse
import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt


@dataclass
class SensorSimulado:
    sensor_id: str
    fase: str
    etapa: str
    variable: str
    unidad: str
    media: float      # valor alrededor del cual oscila
    ruido: float      # variación entre lecturas
    deriva: float = 0  # cambio de la media por lectura (p. ej. el grano se seca)
    minimo: float = -1e9
    valor: float | None = None

    def siguiente(self) -> float:
        self.media = max(self.minimo, self.media + self.deriva)
        actual = self.media if self.valor is None else self.valor
        # paseo aleatorio que vuelve hacia la media
        self.valor = actual + 0.3 * (self.media - actual) + random.gauss(0, self.ruido)
        return round(self.valor, 2)


def sensores() -> list[SensorSimulado]:
    return [
        SensorSimulado("alm-temp-01", "cultivo", "almacigo", "temperatura", "°C", 24, 0.4),
        SensorSimulado("man-hsuelo-01", "cultivo", "manejo_agronomico", "humedad_suelo", "%", 48, 0.8),
        SensorSimulado("man-hr-01", "cultivo", "manejo_agronomico", "humedad_relativa", "%", 76, 1.0),
        SensorSimulado("man-temp-01", "cultivo", "manejo_agronomico", "temperatura", "°C", 22, 0.4),
        SensorSimulado("fer-temp-01", "beneficio", "fermentacion", "temperatura", "°C", 22, 0.3),
        SensorSimulado("fer-ph-01", "beneficio", "fermentacion", "ph", "pH", 5.2, 0.04, deriva=-0.002, minimo=4.2),
        SensorSimulado("sec-temp-01", "beneficio", "secado", "temperatura", "°C", 40, 0.6),
        SensorSimulado("sec-hgrano-01", "beneficio", "secado", "humedad_grano", "%", 30, 0.2, deriva=-0.05, minimo=11),
    ]


def mensaje(s: SensorSimulado, ts: datetime) -> tuple[str, str]:
    tema = f"cafe/{s.fase}/{s.etapa}/{s.sensor_id}"
    carga = {
        "version": "0.1", "sensor_id": s.sensor_id, "etapa": s.etapa, "variable": s.variable,
        "valor": s.siguiente(), "unidad": s.unidad, "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bateria": round(random.uniform(60, 100)),
    }
    return tema, json.dumps(carga, ensure_ascii=False)


def mensaje_invalido(s: SensorSimulado, ts: datetime) -> tuple[str, str]:
    tema, carga = mensaje(s, ts)
    datos = json.loads(carga)
    tipo = random.choice(["unidad", "rango", "campo", "json"])
    if tipo == "unidad":
        datos["unidad"] = "°F" if s.variable == "temperatura" else "g"
    elif tipo == "rango":
        datos["valor"] = 9999
    elif tipo == "campo":
        datos.pop("timestamp")
    else:
        return tema, carga[:-5]
    return tema, json.dumps(datos, ensure_ascii=False)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    p.add_argument("--puerto", type=int, default=int(os.getenv("MQTT_PUERTO", "1883")))
    p.add_argument("--intervalo", type=float, default=5, help="segundos entre rondas de lecturas")
    p.add_argument("--historial", type=int, default=0, help="minutos de datos pasados a enviar al iniciar")
    p.add_argument("--anomalia", action="store_true", help="la temperatura de secado sube sobre 50 °C")
    p.add_argument("--invalidos", action="store_true", help="enviar mensajes inválidos de vez en cuando")
    p.add_argument("--rondas", type=int, default=0, help="detenerse tras N rondas (0 = sin fin)")
    args = p.parse_args()

    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"simulador-{random.randint(0, 9999)}")
    if os.getenv("MQTT_USUARIO"):
        cliente.username_pw_set(os.getenv("MQTT_USUARIO"), os.getenv("MQTT_CLAVE"))
    for _ in range(30):
        try:
            cliente.connect(args.host, args.puerto)
            break
        except OSError:
            print("Esperando el servidor MQTT…")
            time.sleep(2)
    cliente.loop_start()
    lista = sensores()

    def publicar(ts: datetime) -> None:
        for s in lista:
            if args.invalidos and random.random() < 0.03:
                tema, carga = mensaje_invalido(s, ts)
            else:
                tema, carga = mensaje(s, ts)
            cliente.publish(tema, carga, qos=1).wait_for_publish()

    if args.historial:
        ahora = datetime.now(timezone.utc)
        print(f"Enviando {args.historial} minutos de historial…")
        for m in range(args.historial, 0, -1):
            publicar(ahora - timedelta(minutes=m))

    secado = next(s for s in lista if s.sensor_id == "sec-temp-01")
    ronda = 0
    print(f"Publicando {len(lista)} sensores cada {args.intervalo} s en {args.host}:{args.puerto}. Ctrl+C para salir.")
    try:
        while not args.rondas or ronda < args.rondas:
            ronda += 1
            if args.anomalia and ronda > 3:
                secado.media = min(secado.media + 2.5, 58)
            publicar(datetime.now(timezone.utc))
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        pass
    finally:
        cliente.loop_stop()
        cliente.disconnect()


if __name__ == "__main__":
    main()
