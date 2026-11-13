# Contrato de datos con Ingeniería Electrónica

**Versión 0.1 · Propuesta para discutir.** Nada de este documento está acordado todavía. Su objetivo es que Electrónica y Sistemas trabajen en paralelo: si los dispositivos envían los datos en este formato, el software los recibe sin cambios.

## 1. Sensores (cultivo y beneficio)

### Transporte

- Protocolo: **MQTT** (versión 3.1.1 o 5.0).
- Servidor (*broker*): lo administra Sistemas. Dirección y credenciales por definir.
- Calidad de servicio: **QoS 1** (al menos una entrega).
- Un mensaje por lectura.

### Tema (*topic*)

```
cafe/<fase>/<etapa>/<sensor_id>
```

Ejemplo: `cafe/beneficio/secado/sec-temp-01`

Los códigos de `fase` y `etapa` están en [`config/etapas.yaml`](../config/etapas.yaml). La lista de etapas es provisional hasta que la confirme el docente orientador.

### Contenido del mensaje (JSON)

```json
{
  "version": "0.1",
  "sensor_id": "sec-temp-01",
  "etapa": "secado",
  "variable": "temperatura",
  "valor": 41.7,
  "unidad": "°C",
  "timestamp": "2026-11-13T14:30:00Z",
  "bateria": 87
}
```

| Campo | Obligatorio | Descripción |
| --- | --- | --- |
| `version` | Sí | Versión del contrato. Hoy: `"0.1"`. |
| `sensor_id` | Sí | Identificador único del sensor: minúsculas, números y guiones. |
| `etapa` | Sí | Código de la etapa. Debe coincidir con la del tema. |
| `variable` | Sí | Una de las variables de la tabla siguiente. |
| `valor` | Sí | Número (usar punto decimal). |
| `unidad` | Sí | La unidad acordada para la variable. |
| `timestamp` | Sí | Hora de la medición en UTC, ISO 8601 (termina en `Z`). |
| `bateria` | No | Porcentaje de batería, si el dispositivo lo reporta. |

El esquema formal está en [`contrato/lectura.schema.json`](../contrato/lectura.schema.json).

### Variables y unidades

| Variable | Unidad | Rango válido (descarta lecturas imposibles) |
| --- | --- | --- |
| `temperatura` | °C | −10 a 80 |
| `humedad_relativa` | % | 0 a 100 |
| `humedad_suelo` | % | 0 a 100 |
| `humedad_grano` | % | 0 a 80 |
| `ph` | pH | 0 a 14 |
| `co2` | ppm | 0 a 50 000 |
| `radiacion_solar` | W/m² | 0 a 2 000 |

Los rangos válidos solo sirven para descartar errores del sensor. **No son umbrales de alerta**: esos se definen con apoyo agronómico.

### Qué hace el software con cada mensaje

1. Revisa que el JSON cumpla el contrato, que la etapa exista y coincida con el tema, que la unidad corresponda a la variable y que el valor esté en el rango válido.
2. Si algo falla, guarda el mensaje como **rechazado**, con el motivo, para poder revisarlo con Electrónica.
3. Si es válido, guarda la lectura y evalúa las reglas de alerta de su etapa.

## 2. Cámaras (transformación)

Las imágenes no se envían por MQTT porque son pesadas. Propuesta inicial, por desarrollar en una iteración siguiente:

- La cámara (o su microcontrolador) envía cada imagen por **HTTP POST** a un servicio del software, con los datos de la etapa, la cámara y la hora.
- El software guarda la imagen, la analiza con el módulo de visión artificial y registra las detecciones.

## 3. Preguntas para Electrónica

1. ¿Qué sensores van en cada etapa y qué variables mide cada uno?
2. ¿Cada cuánto puede medir y enviar cada sensor? Propuesta inicial: una lectura por minuto.
3. ¿Los microcontroladores tienen reloj sincronizado (por ejemplo, por NTP) para el `timestamp`? Si no, el software puede usar la hora de llegada.
4. ¿Los dispositivos tendrán conexión permanente a la red del laboratorio? ¿Guardan lecturas cuando se cae la conexión?
5. Para las cámaras: ¿qué resolución, cada cuánto se captura y con qué iluminación?
6. ¿Pueden publicar en MQTT con usuario y contraseña?

## Historial

| Versión | Cambio |
| --- | --- |
| 0.1 | Propuesta inicial de Sistemas. |
