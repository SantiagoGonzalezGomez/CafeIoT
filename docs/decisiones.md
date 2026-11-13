# Decisiones técnicas

Cada decisión indica su estado. Las marcadas **Propuesta** deben aprobarse con el director antes de fusionarse en `main`.

| N.° | Decisión | Por qué | Estado |
| --- | --- | --- | --- |
| 1 | MQTT (Mosquitto) para recibir las lecturas de los sensores | Protocolo ligero, estándar en IoT y fácil de usar desde ESP32 y Arduino. | Propuesta; confirmar con Electrónica |
| 2 | Python para la ingesta, las reglas y la API | Tiene librerías maduras para MQTT, bases de datos y visión artificial, así que todo el software queda en un solo lenguaje. | Propuesta |
| 3 | PostgreSQL, con TimescaleDB si está disponible | Base de datos libre y robusta; TimescaleDB la optimiza para series de tiempo sin cambiar el SQL. El código funciona también sin TimescaleDB. | Propuesta |
| 4 | FastAPI para la API | Documentación automática de la API (`/docs`) y validación de datos con Pydantic. | Propuesta |
| 5 | Panel web propio (HTML y JavaScript, sin herramientas externas como Grafana) | El objetivo específico 2 pide **construir** el panel. Una herramienta configurada podría no reconocerse como desarrollo propio. | Propuesta |
| 6 | Docker Compose para levantar todos los servicios | El sistema corre igual en cualquier equipo y en el servidor del laboratorio. | Propuesta |
| 7 | Reglas de alerta en un archivo de configuración (`config/reglas.yaml`) | Los umbrales los definirá el apoyo agronómico y deben poder cambiarse sin tocar el código. | Propuesta |
| 8 | Imágenes por HTTP, no por MQTT | Las imágenes son pesadas para MQTT. | Propuesta; desarrollar en la iteración de visión artificial |
