# Arquitectura: cómo construir y depurar vehículos autónomos que dependen de la conectividad

Desde la primera decisión de diseño hasta una flota que se puede depurar aunque esté a 300 km, con una señal LTE débil.

Aplica a cualquier vehículo autónomo con Linux y Python que dependa de un enlace de red: drones que viven en una estación base (drone-in-a-box), robots terrestres, robots de inspección, embarcaciones y vehículos submarinos sin tripulación, y maquinaria agrícola. Cuando algo aplica a un solo tipo de vehículo, se indica.

---

## 0. La regla de la que se desprende todo

> **El vehículo debe ser seguro y útil sin ninguna conectividad. La conectividad agrega visibilidad y control. Nunca es una dependencia para la seguridad.**

Todo lo demás se desprende de esa regla:

| Si el enlace está…   | El vehículo debe…                                                                 |
|----------------------|-----------------------------------------------------------------------------------|
| Bien                 | Transmitir su estado, cargar datos, aceptar comandos y recibir actualizaciones OTA |
| Degradado            | Enviar solo señales de vida y eventos; poner todo lo demás en cola                 |
| Perdido (segundos)   | Continuar con la acción segura en curso; seguir registrando                        |
| Perdido (minutos)    | Ejecutar el comportamiento acordado ante pérdida de enlace (volver a casa / mantenerse / volver a la estación base / detenerse) |
| Perdido (días)       | Mantenerse seguro, conservar su caja negra, recuperarse solo y enviar lo pendiente al volver |

Por lo tanto, el "estado ideal" de estos sistemas es: **cada vehículo puede responder siempre por sí mismo "¿estoy sano y, si no, por qué?", guarda la respuesta localmente y se la hace llegar a una persona en cuanto cualquier enlace lo permita.**

---

## 1. Arquitectura de punta a punta

```
 ┌───────────────────────────── VEHÍCULO ────────────────────────────┐
 │                                                                   │
 │  ┌─────────────┐  MAVLink/UART  ┌──────────────────────────────┐  │
 │  │ Control de  │◄──────────────►│ Computadora a bordo (Linux)  │  │
 │  │ vuelo/mov.  │                │  ├ misión / autonomía (Py)   │  │
 │  │ (PX4/ArduP. │                │  ├ percepción / cargas útiles│  │
 │  │  RTOS, MCU) │                │  ├ AGENTE DE SALUD ◄ este repo│ │
 │  └──────┬──────┘                │  ├ caja negra + registros    │  │
 │         │ independiente         │  ├ cliente OTA (raíz A/B)    │  │
 │  ┌──────▼──────┐                │  └ cliente de acceso remoto  │  │
 │  │ Sist. de    │                └───────┬──────────────────────┘  │
 │  │ seguridad   │   watchdog HW ─────────┘                         │
 │  │ (paracaídas)│                                                  │
 │  └─────────────┘                                                  │
 └───────────────────────────────┬───────────────────────────────────┘
                                 │ Wi-Fi / Ethernet en la estación base
 ┌──────────────── ESTACIÓN BASE / GATEWAY DE BORDE ─────────────────┐
 │  controlador de la estación (tapa, cargador, clima, meteorología) │
 │  computadora de borde: agente, caché de datos, interfaz local     │
 │  router multienlace: LTE A + LTE B (2 operadores) / 5G / satélite │
 │  canal independiente: relé celular / BMC / consola serie          │
 └───────────────────────────────┬───────────────────────────────────┘
                                 │ SOLO SALIENTE, mTLS / WireGuard
 ┌──────────────────────────── NUBE ─────────────────────────────────┐
 │  recepción (HTTPS/MQTT) ─► series de tiempo + eventos ─► alertas  │
 │  registro de flota · servicio de config · OTA (por etapas)        │
 │  acceso remoto (auditado, temporal) · almacenamiento de paquetes  │
 │  panel de operaciones ◄── consola de este repo · analítica        │
 └───────────────────────────────┬───────────────────────────────────┘
                                 │
           operadores del NOC · ingenieros de campo · guardias
```

### La división entre capas

| Capa | Es responsable de | Debe seguir funcionando cuando… |
|---|---|---|
| Controlador de vuelo/movimiento | Estabilización, modos seguros, geocerca | Falla la computadora a bordo |
| Sistema de seguridad | Paracaídas, terminación de vuelo, parada de emergencia | Todo lo demás falló |
| Computadora a bordo | Autonomía, cargas útiles, salud, registros | Se cae la red |
| Estación base / borde | Carga, resguardo, control por clima, caché local, **multienlace** | Se cae la nube |
| Nube | Vista de la flota, historial, OTA, alertas, personas | Un sitio queda fuera de línea |

Arriba de todo está una plataforma de operaciones o analítica (planificación de misiones, inspecciones, reportes): es la capa de **operaciones y datos**. El sistema de este repositorio es la capa de **ingeniería** debajo de ella, que responde "¿por qué falló esa misión y qué está roto en el vehículo?"

---

## 2. Cómo construirlo: las fases

### Fase 1: diseñar pensando en la depuración (antes de escribir código)

1. **Haga un AMEF (análisis de modos de falla y efectos).** Liste cada modo de falla (pérdida de GPS, pérdida de enlace, caída de voltaje, hélice dañada, tapa trabada, proceso que se cae, disco lleno, reloj desfasado…) y, para cada uno, indique **cómo se detecta, qué hace el vehículo por sí solo y qué necesita ver una persona**. Los archivos `rules.py` y `rootcause.py` de este repositorio son esa tabla convertida en código.
2. **Elija hardware que se recupere solo:**
   - Un controlador de vuelo (MCU/RTOS) separado de la computadora Linux, para que una falla de Linux no sea un aterrizaje forzoso.
   - Un watchdog de hardware en la computadora a bordo (`/dev/watchdog`, controlado por `RuntimeWatchdogSec=` de systemd).
   - Un sistema de seguridad independiente, con su propia energía y lógica de armado.
   - Almacenamiento industrial (eMMC/NVMe con protección ante cortes de energía, *no* tarjetas SD de consumo).
   - Un módem con doble SIM o dos módems de **operadores distintos**; una antena externa.
   - Control de energía independiente en la estación base (un relé controlado por celular o una PDU inteligente), para poder apagar y encender a distancia una computadora colgada.
   - Un reloj sincronizado por GPS (PPS → chrony). Sin una hora consistente no se pueden correlacionar registros entre sistemas.
3. **Defina el comportamiento ante pérdida de enlace** para cada fase de la misión y obtenga su aprobación (en drones, también forma parte del caso de seguridad regulatorio para vuelos más allá de la línea de vista).

### Fase 2: la plataforma de software a bordo

| Tema | Enfoque ideal |
|---|---|
| Sistema operativo | Sistema de archivos raíz inmutable y de solo lectura, con particiones **A/B** (RAUC, Mender, SWUpdate u OSTree). Una actualización defectuosa vuelve sola a la última imagen buena. |
| Procesos | Cada componente es una unidad systemd con `Restart=on-failure`, `WatchdogSec=` (la aplicación llama a `sd_notify("WATCHDOG=1")`), `MemoryMax=` y `CPUQuota=`. Si un nodo de percepción tiene una fuga, se reinicia ese nodo, no todo el equipo. |
| Python | Un entorno virtual con versiones fijas dentro de la imagen (nada de `pip install` en campo); `faulthandler` activado; un `excepthook` que registra los errores de forma estructurada; hilos supervisados (un hilo muerto debe terminar su proceso para que systemd lo note). |
| Middleware | ROS 2 / router MAVLink / ZeroMQ; monitoreo de la frecuencia de los tópicos (un tópico en silencio es una falla). |
| Registros | Registros estructurados (JSON) en el journal con **almacenamiento persistente** y un límite de tamaño; registros de vuelo (ULog/DataFlash) y rosbags en un búfer circular. |
| Caja negra | Un respaldo local acotado y sincronizado en disco de los reportes de salud. Sobrevive a reinicios y aterrizajes bruscos (lo implementa `uplink.py`). |
| Agente de salud | De solo lectura, con recursos limitados, funciona por su cuenta sin importar la red (`agent.py`). |
| Hora | chrony con GPS/PPS y NTP; todos los registros en UTC. |
| Configuración | Versionada, entregada por el servicio de configuración de la flota, validada antes de aplicarse y registrada en cada reporte de salud. |
| Secretos | Una identidad por dispositivo (certificado X.509 en un TPM o elemento seguro); sin contraseñas compartidas. |

### Fase 3: diseño de la conectividad

**3.1 Asuma que la red es hostil e intermitente.**
- **Solo conexiones salientes.** Los vehículos se conectan *hacia* la nube. Nunca exija un puerto de entrada: el CGNAT del operador lo bloqueará de todos modos, y un puerto abierto es una superficie de ataque.
- **Multienlace.** Combine o alterne entre operadores, 5G, satélite (Starlink/Iridium para señales de vida) y radio local o malla. Registre en cada reporte qué enlace está activo.
- **Cifrado e identidad en todo.** mTLS o WireGuard, con certificados por dispositivo que se puedan revocar.

**3.2 Clasifique el tráfico por prioridad, no por tipo**

| Nivel | Ejemplo | Tamaño | Cuándo se envía |
|---|---|---|---|
| P0 señal de vida | vivo, estado, GO/NO-GO, posición | <200 B | Cada 5–30 s, por cualquier enlace, incluso satélite o SMS |
| P1 eventos | hallazgo nuevo, modo seguro, misión cancelada | ~1 KB | De inmediato, con reintentos, en cola si no hay enlace |
| P2 resúmenes | diagnóstico compacto, métricas | 1–5 KB | En cada ciclo, cuando el enlace es bueno |
| P3 estado completo | datos completos, registros principales | 10–100 KB | Cuando cambia el estado, o cada 10 min |
| P4 volumen | registros de vuelo, rosbags, imágenes, paquetes de depuración | MB–GB | **Solo en la estación base / por Wi-Fi / sin costo por datos**, con cargas reanudables |

El `Uplink` de este repositorio implementa P1–P3: compacto o completo, guardar y reenviar, entrega al menos una vez.

**3.3 Protocolos.** MQTT 5 (sesiones persistentes, QoS 1, poca sobrecarga) o lotes HTTPS (simples, funcionan a través de cualquier proxy). Evite protocolos de petición y respuesta muy conversadores sobre la red celular.

**3.4 Trate el silencio como una falla.** La nube debe distinguir "sano y callado" de "muerto". Si no llegan las señales de vida esperadas → **SILENCIOSO** → NO-GO automático, una alerta y el último estado conocido en pantalla (lo hace `console.Fleet.view()`).

### Fase 4: la plataforma en la nube y de flota

- **Recepción** → **base de series de tiempo** (Timescale/Influx/Prometheus) para métricas, un **almacén de eventos** para los hallazgos y **almacenamiento de objetos** para paquetes y registros.
- **Las reglas corren en dos lugares.** En el vehículo (funciona sin conexión y decide GO/NO-GO) y en la nube (correlación de toda la flota: "todos los vehículos del sitio X perdieron el GPS a las 14:02" indica una causa del sitio, como bloqueo de señal, un evento climático o una caída del operador, no una falla de hardware).
- **Registro de la flota**: revisión de hardware, versiones de firmware y software, huella de la configuración e historial de mantenimiento de cada vehículo. La mayoría de los errores de una flota terminan siendo "solo en la revisión C del hardware con software ≥ 2.4".
- **OTA con despliegue por etapas**: canario en 1 vehículo → 5% → 25% → 100%, con freno automático si empeoran las métricas de salud; nunca actualice un vehículo en plena misión.
- **Alertas**: alerte sobre *cambios de estado* y consumo del margen de error (SLO), no en cada consulta (`integrations.Notifier`).
- **Tendencias**: los hallazgos recurrentes por vehículo o sitio son la lista de mantenimiento pendiente (`history.py`).

### Fase 5: pruebas antes de salir a campo

| Nivel | Qué | Herramientas |
|---|---|---|
| Unitarias | reglas, analizadores, máquinas de estado | pytest |
| SIL | todo el sistema de autonomía contra un simulador | PX4/ArduPilot SITL, Gazebo, AirSim |
| **Caos de red** | enlaces que se caen, agregan latencia, pierden paquetes o intermitencias | `tc netem`, toxiproxy; p. ej. `tc qdisc add dev wwan0 root netem loss 30% delay 800ms` |
| **Inyección de fallas** | cada falla del AMEF | las opciones `--fault` de este repositorio; detener procesos; llenar el disco; desconectar el USB |
| HIL | FC y computadora reales en banco, física simulada | PX4 HIL, una fuente a la que se le pueda bajar el voltaje |
| Resistencia | 72 h+ de misiones continuas desde la estación base | fugas, crecimiento de registros, temperatura |
| Piloto en campo | pocos sitios, ingenieros de guardia | toda la escalera de depuración de abajo |

Cualquier falla de campo que no pueda reproducir en SIL o HIL es un hueco en su simulación o en sus registros. Ciérrelo.

---

## 3. Depurar vehículos a los que no se puede llegar: la escalera de escalamiento

Use el escalón más bajo que responda la pregunta. Cada escalón más arriba cuesta más ancho de banda, más riesgo y más tiempo de personas.

```
 Escalón 0  Telemetría pasiva       paneles, señales de vida, hallazgos, tendencias  (siempre activo)
 Escalón 1  Diagnóstico automático  reglas + causas probables + GO/NO-GO             (siempre activo)
 Escalón 2  Consulta a pedido       registros, paquete de depuración, vuelos         (a pedido)
 Escalón 3  Terminal remota         túnel inverso temporal y auditado                (emergencia)
 Escalón 4  Corrección remota       reiniciar servicio, reiniciar, liberar disco     (acciones aprobadas)
 Escalón 5  Solución remota         nueva config, parche OTA, volver a la ranura A/B (control de cambios)
 Escalón 6  Recuperación independ.  apagar/encender por relé, partición de rescate   (equipo sin respuesta)
 Escalón 7  Visita en sitio         técnico en el lugar, con el paquete ya analizado
```

### Escalones 0–1: saber antes de preguntar
Cada reporte trae suficiente contexto para diagnosticar la mayoría de los incidentes **sin tocar el vehículo**: hallazgos con instrucciones de solución, causas raíz correlacionadas, versión de software y configuración, calidad del enlace y las últimas líneas de error. Ejecute la demostración (`demo`) de este repositorio para verlo.

### Escalón 2: consultar, no hurgar
- `GET /logs?unit=…`: acceso a los registros de unidades autorizadas, sin necesidad de terminal.
- `GET /bundle`: un archivo con el diagnóstico, el journal, dmesg, la lista de procesos, el árbol USB, los dispositivos de video, el estado del módem, `pip freeze` y los registros de vuelo. Adjúntelo al ticket. **Se recolecta una vez y se analiza sin conexión.**
- El análisis de registros de vuelo (`analyze-log`) da una línea de tiempo de *lo que ya estaba fallando antes del modo seguro*.

### Escalón 3: terminal remota, de forma segura
- **Solo túneles inversos**: el vehículo inicia la conexión (WireGuard/Tailscale/Teleport/AWS SSM/Cloudflare Tunnel). Sin puertos de entrada.
- **Acceso temporal**: un certificado de corta duración por sesión, vinculado a un ticket, grabado, y con aprobación de dos personas si el vehículo está armado o en vuelo.
- **Nunca en un vehículo en vuelo**, salvo que el procedimiento lo exija; mejor cuando está en su estación base.
- Use `tmux` o `mosh` para que una caída del enlace no cierre la sesión y deje un comando a medias.

### Escalón 4: correcciones aprobadas de antemano
*Implementado en `actions.py`. Vea "Cómo fluye una acción remota" abajo.*

Una lista corta y definida de acciones permitidas (`restart_service(nombre)`, `reboot`, `clear_cache`, `trigger_ffc`, `recalibrate_compass_at_base`), cada una con una condición previa (`vehículo desarmado y en su estación base`), un tiempo máximo y una verificación automática (volver a diagnosticar). Muchos equipos dejan que el **vehículo las ejecute por su cuenta** ante fallas conocidas: autorreparación que queda registrada y reportada.

#### Cómo fluye una acción remota

```
 operador (con sesión) ──► consola: POST /api/action {vehículo, acción, parámetros, ticket, motivo}
                            │ arma el sobre {acción, parámetros, operador, hora, vencimiento, nonce}
                            │ lo firma: HMAC-SHA256 con el secreto de ese vehículo
             ┌──────────────┴───────────────┐
      vehículo de consulta           vehículo de envío (CGNAT)
   POST /actions/run ahora          queda en el buzón del vehículo; se entrega en la
                                    respuesta a su próximo envío (sin puerto de entrada)
             └──────────────┬───────────────┘
                 el vehículo verifica: firma · no vencido · nonce sin usar
                 revisa condiciones en el estado ACTUAL: desarmado · en estación · …
                 ejecuta la acción → vuelve a diagnosticar → resuelto / pendiente / nuevo
                 lo agrega a su registro de auditoría → el resultado vuelve a la consola
```

Los comandos vencen (a los 5 minutos por defecto), porque un "reiniciar" que quedó en cola mientras el vehículo estaba sin enlace no debe ejecutarse horas después, quizás en plena misión. Un estado desconocido no cumple la condición previa: sin telemetría, el vehículo no puede demostrar que está desarmado, así que se niega.

### Escalón 5: soluciones por aire (OTA)
Los cambios de configuración y las actualizaciones OTA siguen el despliegue por etapas. Con las particiones A/B, **toda actualización remota se puede deshacer a distancia**. El equipo debe confirmar que la actualización está sana (el agente dice GO) dentro de N minutos; si no, vuelve atrás por su cuenta.

### Escalón 6: cuando la computadora no responde
Aquí rinden las decisiones de hardware de la fase 1:
- El watchdog de hardware reinicia solo un kernel colgado.
- El canal independiente de la estación base (módem aparte + relé/BMC/consola serie) permite apagar y encender, o llegar a una consola, aunque el sistema principal o el enlace principal estén caídos.
- Una partición de rescate arranca una imagen mínima que se reporta y acepta una reinstalación.

### Escalón 7: visita en sitio, con todo preparado
El técnico llega con el paquete ya analizado, la pieza probable (hélice, contactos de carga, cable de GPS) en la mano y una lista de verificación generada a partir de los hallazgos. Medida de éxito: **una visita, no dos.**

### Técnicas de depuración que funcionan a distancia

| Técnica | Por qué importa a distancia |
|---|---|
| **Correlacionar capas por hora** | Registro del FC + journal + dmesg + registro de la estación base + registro del módem en una sola línea de tiempo. La mayoría de los "misterios" son un evento de energía o de enlace unos segundos antes (`rootcause.py`, el campo `preceded_by` del análisis de registros). |
| **Comparar con la flota** | "Solo este vehículo" → hardware. "Todos los vehículos de este sitio" → entorno, RF u operador. "Todos los vehículos desde la v2.4" → software. |
| **Reproducir** | Descargue el registro de vuelo o el rosbag y reprodúzcalo en el sistema de autonomía en SIL para recrear la decisión que tomó el vehículo. |
| **Aumentar los registros a distancia, por un tiempo** | Un parámetro de configuración que sube el nivel de detalle de un subsistema durante N horas y luego vuelve solo. |
| **Guardar el antes y el después** | Capture el estado cuando empieza una falla *y* cuando se resuelve; las fallas intermitentes se esconden en ese intervalo. |
| **La salud lleva la versión** | Cada reporte incluye la versión de software y la huella de la configuración, para poder aislar el problema en toda la flota. |

---

## 4. Seguridad (es un robot accesible a distancia)

- Una identidad por dispositivo en hardware (TPM o elemento seguro), mTLS y certificados revocables.
- Imágenes OTA firmadas y arranque verificado cuando el SoC lo permite.
- El agente de salud es **de solo lectura** y tiene recursos limitados (vea `deploy/fleetdebug-agent.service`); los comandos pasan por un camino aparte, autenticado y auditado.
- Mínimo privilegio: el agente corre en los grupos que necesita (`systemd-journal`, `dialout`, `video`), no como root.
- Limite la frecuencia y audite cada acción remota; alerte ante accesos inusuales.
- Prevea la detección de suplantación o bloqueo de GNSS (saltos bruscos de posición, pérdida de GPS en toda la flota de un sitio).

---

## 5. Métricas que indican si esto funciona

| Métrica | Dirección buscada |
|---|---|
| Tasa de éxito de misiones (por sitio, por vehículo) | ↑ |
| Disponibilidad prevuelo (% de verificaciones = GO) | ↑ (`history.availability`) |
| MTTD: tiempo medio para detectar una falla | ↓ (minutos, no "cuando llamó el cliente") |
| MTTR: tiempo medio para resolver | ↓ |
| % de incidentes resueltos sin visita en sitio | ↑ (la más importante) |
| Minutos con vehículos en silencio | ↓ |
| Antigüedad de los datos pendientes de carga | ↓ |
| Cantidad de fallas recurrentes por vehículo | ↓ (`history.recurring`) |

---

## 6. Qué implementa este repositorio frente a la arquitectura completa

| Elemento de la arquitectura | Estado aquí |
|---|---|
| Agente de salud a bordo (Linux, Python, FC, estación base, cargas útiles, seguridad, cargas de datos) | ✅ `collectors.py`, `telemetry.py`, `dock.py`, `payloads.py`, `agent.py` |
| Reglas con instrucciones de solución | ✅ `rules.py` |
| Correlación de causas raíz | ✅ `rootcause.py` |
| Control GO / HOLD / NO-GO | ✅ `preflight.py`, `GET /preflight`, `fleetdebug preflight` (códigos de salida para scripts) |
| Caja negra con guardar y reenviar, envío saliente, detección de silencio | ✅ `uplink.py`, `console.py` |
| Línea de tiempo del registro de vuelo con contexto previo al modo seguro | ✅ `logs.py` (CSV; .ulg/.bin con pyulog/pymavlink) |
| Paquetes de depuración y registros remotos autorizados | ✅ `bundle.py`, `/bundle`, `/logs` |
| Panel de la flota, historial y tendencias, alertas | ✅ `static/index.html`, `history.py`, `integrations.py` |
| Simulador e inyección de fallas | ✅ `sim.py`, `--fault`, casillas del panel |
| Señal de vida P0 por satélite/SMS/LoRa | ✅ `heartbeat.py` (~70 bytes, con verificación), `uplink.fallback_cmd`, `POST /api/heartbeat` en la consola |
| Correcciones remotas aprobadas (escalón 4) | ✅ `actions.py`: comandos firmados con HMAC, con vencimiento y a prueba de repetición; condiciones previas (desarmado / en estación base / enlace FC); verificación antes y después; registro de auditoría |
| Comandos a vehículos detrás de CGNAT | ✅ buzón: los comandos viajan en la respuesta al envío del propio vehículo |
| Autorreparación con procedimientos | ✅ `AutoHealer`: con límites de frecuencia, y escala a una persona cuando un arreglo no se mantiene |
| Control de acceso a la consola | ✅ usuarios con HTTP Basic (`fleetdebug hash-password`); el nombre del operador queda en el registro de auditoría. En producción, use un proxy con inicio de sesión único |
| Correlación de toda la flota | ✅ `fleetcorr.py`: patrones del sitio (entorno, RF, operador) frente a patrones de versión de software (errores nuevos) |
| Visibilidad de software y OTA | ✅ versión, ranura A/B de arranque, detección de RAUC/Mender y huella de la configuración en cada reporte |
| Métricas de series de tiempo | ✅ `/metrics` de Prometheus en el agente y la consola, listo para paneles de Grafana y alertas por SLO |
| Panel en inglés y español | ✅ `static/i18n.js`: interfaz y todos los mensajes del motor, con selector EN / ES |
| Transporte MQTT | ⏳ siguiente paso: un envío por MQTT junto a HTTPS (mismo sobre, sesiones persistentes) |
| Intermediario de terminal remota (escalón 3) | 🔌 integre WireGuard/Tailscale/Teleport; no construya uno propio |
| Actualizaciones OTA / A/B (escalón 5) | 🔌 integre RAUC/Mender/SWUpdate (el agente ya reporta la ranura y la versión) |
| Freno automático de despliegues | ⏳ siguiente paso: conectar los incidentes por versión al servidor OTA para pausar un despliegue |
| Integración con una plataforma de analítica | 🔌 `integrations.event_payload` es un evento JSON versionado; apúntelo al punto de entrada de su plataforma o middleware |
