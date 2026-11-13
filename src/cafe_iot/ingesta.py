"""Ingesta y validación (componente 1 de la arquitectura).

Escucha los temas cafe/# en MQTT, valida cada mensaje con el contrato de datos,
guarda la lectura (o el rechazo con su motivo) y evalúa las reglas de alerta.

Uso: python -m cafe_iot.ingesta
"""

import logging
import time

import paho.mqtt.client as mqtt

from . import db
from .config import ajustes, cargar_etapas
from .contrato import LecturaInvalida, validar
from .reglas import MotorReglas

log = logging.getLogger("ingesta")
TEMA = "cafe/#"


class Ingesta:
    def __init__(self, con, motor: MotorReglas):
        self.con = con
        self.motor = motor
        self.etapas = cargar_etapas()
        self.contadores = {"validas": 0, "rechazadas": 0}

    def procesar(self, tema: str, carga: bytes) -> None:
        try:
            lectura, etapa = validar(tema, carga, self.etapas)
        except LecturaInvalida as e:
            self.contadores["rechazadas"] += 1
            log.warning("Rechazado %s: %s", tema, e)
            db.guardar_rechazo(self.con, tema, carga, str(e))
            return

        db.guardar_lectura(self.con, lectura, etapa.fase)
        self.contadores["validas"] += 1
        for regla, incumple in self.motor.evaluar(lectura.etapa, lectura.variable, lectura.valor):
            cambio = db.actualizar_alerta(self.con, regla, lectura, incumple)
            if cambio:
                log.info("Alerta %s: %s (%s, valor %s)", cambio, regla.id, lectura.sensor_id, lectura.valor)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    motor = MotorReglas.desde_archivo()
    log.info("%d reglas cargadas", len(motor.reglas))

    con = None
    for intento in range(30):  # espera a que la base de datos esté lista
        try:
            con = db.conectar()
            break
        except Exception as e:  # noqa: BLE001
            log.info("Esperando la base de datos (%s)", e.__class__.__name__)
            time.sleep(2)
    if con is None:
        raise SystemExit("No se pudo conectar a la base de datos")
    db.inicializar(con)
    ingesta = Ingesta(con, motor)

    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="cafe-ingesta")
    if ajustes.mqtt_usuario:
        cliente.username_pw_set(ajustes.mqtt_usuario, ajustes.mqtt_clave)

    def al_conectar(c, _userdata, _flags, codigo, _props):
        log.info("Conectado a MQTT %s:%s (código %s)", ajustes.mqtt_host, ajustes.mqtt_puerto, codigo)
        c.subscribe(TEMA, qos=1)

    def al_recibir(_c, _userdata, msg):
        try:
            ingesta.procesar(msg.topic, msg.payload)
        except Exception:  # noqa: BLE001 - un mensaje no debe tumbar el servicio
            log.exception("Error procesando %s", msg.topic)

    cliente.on_connect = al_conectar
    cliente.on_message = al_recibir
    cliente.reconnect_delay_set(min_delay=1, max_delay=30)
    cliente.connect_async(ajustes.mqtt_host, ajustes.mqtt_puerto)
    cliente.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
