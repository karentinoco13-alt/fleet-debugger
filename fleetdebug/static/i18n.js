// English / Spanish for the dashboard.
//
// The engine (Python) always writes English: findings, runbook steps, rules,
// work orders. This file translates on the way to the screen, so the live
// console and the static demo share one table. EXACT maps whole phrases;
// PATTERNS handle phrases with numbers or names inside. In a pattern's
// template, {1} inserts a captured group as is and {t1} translates it first.
// A phrase with no entry is shown in English rather than guessed.
window.I18N = (() => {
  const EXACT = {
    '© 2026 Karen Tinoco. Licensed under PolyForm Noncommercial 1.0.0: free to use, share and adapt for non-commercial purposes, with credit. Commercial use by permission only.': '© 2026 Karen Tinoco. Licencia PolyForm Noncommercial 1.0.0: libre para usar, compartir y adaptar con fines no comerciales, dando crédito. Uso comercial solo con permiso.',
    // ---- app chrome
    'Autonomous Fleet Debugger': 'Depurador de Flota Autónoma',
    'Fleet': 'Flota', 'Trends': 'Tendencias', 'Flight log': 'Registro de vuelo',
    'Action log': 'Registro de acciones', 'Blueprint': 'Arquitectura',
    'Loading fleet…': 'Cargando flota…', 'Select a vehicle': 'Seleccione un vehículo',
    'No vehicles yet. Waiting for first poll…': 'Aún no hay vehículos. Esperando el primer reporte…',
    'Unassigned': 'Sin asignar', 'All checks pass': 'Todas las verificaciones aprobadas',
    'Cleared to fly?': '¿Autorizado para volar?', 'Language': 'Idioma',
    // decisions
    'Send technician': 'Enviar técnico', 'Schedule visit': 'Programar visita',
    'Fix remotely': 'Solucionar a distancia', 'Fixing itself': 'Reparándose solo',
    'Wait': 'Esperar', 'OK': 'OK', 'Site visit': 'Visita en sitio',
    '{n} need a technician': '{n} necesitan técnico', '{n} to fix remotely': '{n} por solucionar a distancia',
    '{n} fixing itself': '{n} reparándose solos', '{n} OK': '{n} OK',
    // decision panel
    'What to do': 'Qué hacer',
    '1. The vehicle fixes it itself': '1. El vehículo lo repara solo',
    '2. Fix it remotely from here': '2. Solucionarlo a distancia desde aquí',
    '3. Wait for it to clear': '3. Esperar a que se resuelva',
    '4. Send someone on site': '4. Enviar a alguien al sitio',
    'Nothing for it to fix right now.': 'Por ahora no tiene nada que reparar.',
    'Fixed {n} problem(s) by itself: {list}': 'Reparó {n} problema(s) solo: {list}',
    'Tried {list}: it didn\'t hold.': 'Intentó {list}: no se mantuvo.',
    'All remote fixes have been tried.': 'Ya se intentaron todas las soluciones a distancia.',
    'None needed.': 'No se necesita ninguna.', 'Nothing to wait for.': 'Nada que esperar.',
    'Not needed.': 'No es necesario.',
    'Work order for the technician': 'Orden de trabajo para el técnico',
    'Copy work order': 'Copiar orden de trabajo', 'Copied': 'Copiado',
    'Selected: press Ctrl+C / Cmd+C': 'Seleccionado: presione Ctrl+C / Cmd+C',
    // vehicle page
    'push uplink': 'enlace de envío', 'last report {n}s ago': 'último reporte hace {n} s',
    'backfilled from spool': 'recuperado del respaldo local', 'SIMULATED': 'SIMULADO',
    'slot {s}': 'ranura {s}', 'heartbeat-only (backup link)': 'solo señal de vida (enlace de respaldo)',
    '{n} command(s) queued': '{n} comando(s) en cola',
    'Likely root cause': 'Causa raíz probable', 'Evidence: {list}': 'Evidencia: {list}',
    'Vehicle': 'Vehículo', 'FC heartbeat': 'Señal del FC', 'Battery': 'Batería',
    'GPS sats / HDOP': 'Satélites GPS / HDOP', 'Vibration max': 'Vibración máx.',
    'CPU': 'CPU', 'Memory': 'Memoria', 'SoC temp': 'Temp. SoC', 'Parachute': 'Paracaídas',
    'Base station / site': 'Estación base / sitio', 'Lid': 'Tapa', 'Charging': 'Carga',
    'Enclosure': 'Gabinete', 'Wind / gust': 'Viento / ráfaga', 'Cellular': 'Celular',
    'Upload queue': 'Cola de carga', 'Payloads': 'Cargas útiles',
    'Self-healing': 'Autorreparación', 'resolved: {list}': 'resuelto: {list}', 'nothing': 'nada',
    'Findings ({n})': 'Hallazgos ({n})', 'No problems found.': 'No se encontraron problemas.',
    'How to fix': 'Cómo solucionarlo', 'Fixed when:': 'Solucionado cuando:',
    'When to send someone:': 'Cuándo enviar a alguien:', 'Fix remotely: {label}': 'Solucionar a distancia: {label}',
    'Debug tools': 'Herramientas de depuración',
    'Debug bundles download from the installed console.': 'Los paquetes de depuración se descargan desde la consola instalada.',
    'Push-only vehicle: request bundles/logs via the remote-access tunnel (see BLUEPRINT.md).':
      'Vehículo solo de envío: solicite paquetes y registros por el túnel de acceso remoto (ver BLUEPRINT.md).',
    'Download debug bundle': 'Descargar paquete de depuración', 'View service logs': 'Ver registros del servicio',
    'Re-check now': 'Verificar ahora', 'Fault injection (simulator)': 'Inyección de fallas (simulador)',
    'Apply faults': 'Aplicar fallas', 'Remote actions': 'Acciones remotas', 'Loading…': 'Cargando…',
    'Raw snapshot': 'Datos sin procesar', 'Show JSON': 'Mostrar JSON', 'Unavailable': 'No disponible',
    'Remote actions are disabled on this vehicle (no action_secret).':
      'Las acciones remotas están desactivadas en este vehículo (sin action_secret).',
    'Push vehicle: the action is queued and runs at its next check-in (expires after 5 min).':
      'Vehículo de envío: la acción queda en cola y se ejecuta en su próximo reporte (vence a los 5 min).',
    'Run': 'Ejecutar', 'Precondition failed': 'Falló una condición previa',
    'Confirm on {v}': 'Confirmar en {v}', 'Running…': 'Ejecutando…',
    'Ticket (e.g. OPS-123)': 'Ticket (ej. OPS-123)', 'Reason': 'Motivo',
    '{name}: queued': '{name}: en cola',
    'The vehicle runs it at its next check-in; the result appears here and in the Action log.':
      'El vehículo la ejecuta en su próximo reporte; el resultado aparece aquí y en el Registro de acciones.',
    '✅ Resolved: {list}': '✅ Resuelto: {list}', '⏳ Still present: {list}': '⏳ Sigue presente: {list}',
    '⚠ New: {list}': '⚠ Nuevo: {list}', 'none': 'ninguno',
    'Didn\'t fix it.': 'No lo solucionó.', 'Follow the next step in the runbook.': 'Siga el próximo paso del procedimiento.',
    'Fleet pattern · {scope} "{group}"': 'Patrón de flota · {scope} "{group}"', '{sig} on {list}': '{sig} en {list}',
    // trends
    'How problems got resolved (last 7 days)': 'Cómo se resolvieron los problemas (últimos 7 días)',
    'When the app says to send a technician': 'Cuándo la aplicación indica enviar un técnico',
    'Pre-flight availability (7 days)': 'Disponibilidad prevuelo (7 días)',
    'Findings by subsystem': 'Hallazgos por subsistema',
    'Recurring problems (maintenance backlog)': 'Problemas recurrentes (pendientes de mantenimiento)',
    'Resolution split': 'Distribución de resoluciones',
    'fixed by the vehicle itself ({p}%)': 'reparados por el propio vehículo ({p}%)',
    'fixed remotely by an operator ({p}%)': 'solucionados a distancia por un operador ({p}%)',
    'needed a technician ({p}%)': 'necesitaron un técnico ({p}%)',
    'Simulated week for the demo.': 'Semana simulada para la demostración.',
    'Kind of problem': 'Tipo de problema', 'What happens first': 'Qué pasa primero',
    'Send a technician when…': 'Enviar un técnico cuando…',
    'Connectivity, software, settings someone changed': 'Conectividad, software, configuraciones que alguien cambió',
    'The vehicle fixes it itself, step by step (restart, reconnect, switch SIM, restore settings, roll back)':
      'El vehículo lo repara solo, paso a paso (reiniciar, reconectar, cambiar de SIM, restaurar configuración, volver a la versión anterior)',
    'Every automatic step was tried and it\'s still broken': 'Se intentaron todos los pasos automáticos y sigue fallando',
    'Has a remote fix (e.g. restart, reboot)': 'Tiene una solución a distancia (p. ej. reiniciar)',
    'An operator runs the fix from this dashboard': 'Un operador ejecuta la solución desde este panel',
    'The fix was tried {n} times and the problem is still there': 'La solución se intentó {n} veces y el problema continúa',
    'Wait: it usually clears by itself': 'Esperar: normalmente se resuelve solo',
    'Never: hold missions until it passes': 'Nunca: suspender misiones hasta que pase',
    'It lasts longer than {h}': 'Dura más de {h}',
    'Physical damage, urgent (props, dock lid, charging, parachute)': 'Daño físico, urgente (hélices, tapa de la estación, carga, paracaídas)',
    'No remote fix exists': 'No existe solución a distancia', 'Right away': 'De inmediato',
    'Physical, not urgent': 'Físico, no urgente', 'Within {h} (next scheduled visit)': 'Dentro de {h} (próxima visita programada)',
    'Thresholds are set in the console config under {code}.': 'Los umbrales se configuran en la consola, en {code}.',
    'GPS': 'GPS', 'Position estimate': 'Estimación de posición', 'Overheating': 'Sobrecalentamiento',
    'Battery / power': 'Batería / energía', 'Camera warming up': 'Cámara calentándose',
    'Vehicle not reporting': 'Vehículo sin reportar', 'Flight controller sensor': 'Sensor del controlador de vuelo',
    'Weather': 'Clima', 'Anything else': 'Cualquier otro',
    'Problem': 'Problema', 'Seen': 'Visto', 'First seen': 'Primera vez', 'No history yet': 'Aún no hay historial',
    // action log
    'Remote actions (who, what, why, result)': 'Acciones remotas (quién, qué, por qué, resultado)',
    'Time': 'Hora', 'Action': 'Acción', 'Operator': 'Operador', 'Ticket / reason': 'Ticket / motivo',
    'Result': 'Resultado', 'resolved {n}': 'resuelto(s) {n}', 'No actions yet': 'Aún no hay acciones',
    // flight log
    'Analyze sample flight': 'Analizar vuelo de ejemplo',
    'CSV with time_s plus any of: vibration_x/y/z, gps_satellites, gps_hdop, ekf_pos_variance, battery_voltage, cpu_percent, soc_temp_c, mode, event':
      'CSV con time_s y cualquiera de: vibration_x/y/z, gps_satellites, gps_hdop, ekf_pos_variance, battery_voltage, cpu_percent, soc_temp_c, mode, event',
    'Preceded by: {list}': 'Precedido por: {list}', 'Events': 'Eventos', 'Start': 'Inicio',
    'Duration': 'Duración', 'Event': 'Evento', 'Worst': 'Peor', '{w} (limit {l})': '{w} (límite {l})',
    'CSV needs a time_s column': 'El CSV necesita una columna time_s',

    // ---- severities, components, states
    'critical': 'crítico', 'warning': 'advertencia', 'info': 'info',
    'compute': 'cómputo', 'storage': 'almacenamiento', 'thermal': 'térmico', 'power': 'energía',
    'software': 'software', 'link': 'enlace', 'flight-controller': 'controlador de vuelo', 'gps': 'GPS',
    'airframe': 'estructura', 'estimator': 'estimador', 'dock': 'estación base', 'weather': 'clima',
    'payload': 'carga útil', 'safety': 'seguridad', 'data-pipeline': 'datos', 'debugger': 'depurador',
    'closed': 'cerrada', 'open': 'abierta', 'fault': 'falla', 'moving': 'en movimiento', 'full': 'llena',
    'charging': 'cargando', 'idle': 'en reposo', 'ready': 'lista', 'NOT READY': 'NO LISTO',
    'missing': 'falta', 'frozen': 'congelada', 'n/a': 'n/d', 'ok': 'ok',
    'done': 'hecho', 'failed': 'falló', 'blocked': 'bloqueado', 'queued': 'en cola', 'rejected': 'rechazado',
    'unreachable': 'inaccesible', 'direct': 'directo', 'mailbox': 'buzón', 'self-heal': 'autorreparación',
    'inactive': 'inactiva', 'activating': 'activándose', 'deactivating': 'desactivándose',
    'searching': 'buscando', 'denied': 'denegado', 'no-service': 'sin servicio', 'disabled': 'desactivado',
    'site': 'sitio', 'software version': 'versión de software', 'gnss': 'GNSS', 'cellular': 'celular',
    'compass': 'brújula', 'software-crash': 'fallas de software', 'memory': 'memoria', 'upload': 'carga de datos',
    'pos_horiz': 'posición horizontal', 'pos_vert': 'posición vertical', 'velocity': 'velocidad',
    'rgb': 'RGB', 'ogi': 'OGI', 'starting': 'comenzando', 'unknown site': 'sitio desconocido',
    'URGENT, today': 'URGENTE, hoy', 'Scheduled visit': 'Visita programada',
    'maintenance laptop (ssh)': 'laptop de mantenimiento (ssh)',
    'unknown (not via the config service)': 'desconocido (no por el servicio de configuración)',
    'disarmed': 'desarmado', 'docked': 'en estación base', 'fc_link': 'enlace FC',
    'at base station': 'en la estación base', 'vehicle is ARMED': 'el vehículo está ARMADO',
    'arming state unknown (no FC telemetry)': 'estado de armado desconocido (sin telemetría del FC)',
    'vehicle not at base station': 'el vehículo no está en la estación base',
    'base station state unknown': 'estado de la estación base desconocido', 'FC link ok': 'enlace FC ok',
    'no FC heartbeat': 'sin señal del FC', 'skipped by config': 'omitido por configuración',
    // action names as the dashboard prints them
    'restart_service': 'reiniciar servicio', 'restart service': 'reiniciar servicio',
    'reboot': 'reiniciar computadora', 'vacuum_journal': 'liberar espacio del registro', 'vacuum journal': 'liberar espacio del registro',
    'restart_modem': 'reiniciar módem', 'restart modem': 'reiniciar módem',
    'restart_network': 'reiniciar red', 'restart network': 'reiniciar red',
    'restart_vpn': 'reconectar VPN', 'restart vpn': 'reconectar VPN',
    'switch_sim': 'cambiar a la SIM de respaldo', 'switch sim': 'cambiar a la SIM de respaldo',
    'resync_time': 'corregir el reloj', 'resync time': 'corregir el reloj',
    'restore_config': 'restaurar configuración', 'restore config': 'restaurar configuración',
    'reupload_geofence': 'volver a cargar la geocerca', 'reupload geofence': 'volver a cargar la geocerca',
    'rollback_software': 'volver al software anterior', 'rollback software': 'volver al software anterior',
    'trigger_ffc': 'calibrar cámara térmica (FFC)', 'trigger ffc': 'calibrar cámara térmica (FFC)',
    // self-healing ladder names
    'clock keeps drifting': 'el reloj sigue desfasándose', 'no cellular service on any SIM': 'sin servicio celular en ninguna SIM',
    'weak cellular signal': 'señal celular débil', 'settings keep being changed': 'la configuración sigue cambiando',
    'software keeps crashing': 'el software sigue fallando', 'a service keeps failing': 'un servicio sigue fallando',
    'geofence won\'t load': 'la geocerca no se carga', 'disk keeps filling up': 'el disco se sigue llenando',
    'memory keeps running out': 'la memoria se sigue agotando', 'data still not uploading': 'los datos siguen sin cargarse',
    'can\'t reach operations': 'no se puede contactar a operaciones',

    // ---- decisions (dispatch.py)
    'Send a technician now': 'Envíe un técnico ahora',
    'Every remote option has been used or none exists for these problems.': 'Se agotaron las opciones a distancia o no existen para estos problemas.',
    'Fixing itself: no action needed': 'Reparándose solo: no hace falta hacer nada',
    'The vehicle is working through its automatic fixes. You\'ll be told only if it runs out of options.':
      'El vehículo está aplicando sus arreglos automáticos. Solo se le avisará si se le acaban las opciones.',
    'Not yet: try the remote fixes first': 'Todavía no: intente primero las soluciones a distancia',
    'Some problems can still be fixed from here. Run them, then check again.':
      'Algunos problemas todavía se pueden solucionar desde aquí. Ejecútelas y vuelva a verificar.',
    'Schedule a technician visit': 'Programe una visita del técnico',
    'Remote options are used up, but nothing is urgent.': 'Se agotaron las opciones a distancia, pero nada es urgente.',
    'Wait: these should clear by themselves': 'Espere: esto debería resolverse solo',
    'Missions are on hold. The app tells you if they last past their limit.':
      'Las misiones están en pausa. La aplicación le avisa si superan su límite.',
    'No action needed': 'No hace falta hacer nada', 'All checks pass.': 'Todas las verificaciones aprobadas.',
    'The vehicle fixes this itself, one step at a time; you\'re told if it runs out.':
      'El vehículo lo repara solo, paso a paso; se le avisa si se le acaban las opciones.',
    'Automatic fixes are used up; see that item for the next step.': 'Se agotaron los arreglos automáticos; vea ese punto para el próximo paso.',
    'Hold missions until it passes. A technician can\'t fix this.': 'Suspenda las misiones hasta que pase. Un técnico no puede arreglar esto.',
    'Physical problem; it can\'t be fixed remotely. Send someone now.': 'Problema físico; no se puede solucionar a distancia. Envíe a alguien ahora.',
    'No remote fix exists for this.': 'No existe solución a distancia para esto.',
    'Remote fix not tried yet.': 'Aún no se intentó la solución a distancia.',
    // work order
    'PROBLEMS TO FIX ON SITE': 'PROBLEMAS A RESOLVER EN SITIO', 'ALREADY TRIED REMOTELY': 'YA INTENTADO A DISTANCIA',
    'BRING': 'LLEVAR', 'SAFETY': 'SEGURIDAD', 'DONE WHEN': 'TERMINADO CUANDO',
    'Nothing: no remote fix exists for these problems.': 'Nada: no existe solución a distancia para estos problemas.',
    'Standard toolkit and laptop': 'Kit de herramientas estándar y laptop',
    'The vehicle is NO-GO. Confirm it is disarmed before opening the base station.':
      'El vehículo está en NO-GO. Confirme que está desarmado antes de abrir la estación base.',
    'Keep clear of the propellers; remove them before any work on the motors.':
      'Manténgase lejos de las hélices; retírelas antes de trabajar en los motores.',
    'The vehicle shows GO in the dashboard after a re-check.': 'El vehículo muestra GO en el panel después de volver a verificar.',

    // ---- findings (rules.py, console.py, heartbeat.py)
    'OOM kill detected in kernel log': 'El kernel cerró un proceso por falta de memoria (OOM)',
    'Under-voltage on companion computer': 'Bajo voltaje en la computadora a bordo',
    'Required Python modules missing': 'Faltan módulos de Python requeridos',
    'No serial device for the flight controller': 'No hay dispositivo serie para el controlador de vuelo',
    'No MAVLink telemetry': 'Sin telemetría MAVLink', 'Flight controller heartbeat lost': 'Se perdió la señal del controlador de vuelo',
    'FC reports unhealthy sensors': 'El FC reporta sensores con fallas', 'FC error message': 'Mensaje de error del FC',
    'Base station status is stale': 'El estado de la estación base está desactualizado',
    'Base station lid fault / actuator overcurrent': 'Falla en la tapa de la estación base / sobrecorriente del actuador',
    'Vehicle not charging at base station': 'El vehículo no carga en la estación base',
    'Base station on UPS: mains power lost': 'Estación base con UPS: se perdió la energía de red',
    'Precision-landing marker unhealthy': 'Falla en el marcador de aterrizaje de precisión',
    'Weak cellular link at the base station': 'Enlace celular débil en la estación base',
    'Precipitation detected': 'Se detectó precipitación', 'Thermal camera FFC overdue': 'Calibración FFC de la cámara térmica vencida',
    'OGI camera cooler not at temperature': 'El enfriador de la cámara OGI no está a temperatura',
    'Parachute / flight-termination system not ready': 'Paracaídas / sistema de terminación de vuelo no listo',
    'Geofence not loaded on the FC': 'Geocerca no cargada en el FC',
    'Inspection data not reaching the cloud': 'Los datos de inspección no llegan a la nube',
    'Agent unreachable': 'Agente inaccesible',
    // details
    'A watched critical process is missing.': 'Falta un proceso crítico supervisado.',
    'The process exited but its parent never reaped it.': 'El proceso terminó, pero su proceso padre nunca lo liberó.',
    'No /dev/ttyACM*, ttyUSB* or ttyTHS* present.': 'No hay /dev/ttyACM*, ttyUSB* ni ttyTHS*.',
    'Poor position accuracy.': 'Precisión de posición baja.',
    'Sustained high CPU on the onboard computer delays perception and control loops.':
      'Un uso de CPU alto y sostenido en la computadora a bordo retrasa la percepción y los ciclos de control.',
    'SoC thermal throttling reduces compute and can cause missed deadlines; common on vehicles parked in an enclosure in the sun.':
      'La limitación térmica del SoC reduce la capacidad de cómputo y puede causar retrasos; es común en vehículos estacionados en un gabinete al sol.',
    'Last known state is shown below. The vehicle keeps spooling locally and will backfill on reconnect.':
      'Abajo se muestra el último estado conocido. El vehículo sigue guardando datos localmente y los enviará al reconectarse.',
    'Last known state is shown below. The vehicle keeps logging locally and will backfill on reconnect.':
      'Abajo se muestra el último estado conocido. El vehículo sigue registrando localmente y enviará todo al reconectarse.',
    'Reported over the low-bandwidth backup link; details will arrive when the main link returns.':
      'Reportado por el enlace de respaldo de bajo ancho de banda; los detalles llegarán cuando vuelva el enlace principal.',
    'TLS: certificate is not yet valid': 'TLS: el certificado todavía no es válido',
    'timed out': 'tiempo de espera agotado',
    '[Errno 101] Network is unreachable': '[Errno 101] La red es inaccesible',
    '[Errno -3] Temporary failure in name resolution': '[Errno -3] Falla temporal en la resolución de nombres',
    // fixes
    'Run `top -H` to find the hot thread; check for runaway ROS nodes or a vision pipeline without a frame-rate cap.':
      'Ejecute `top -H` para encontrar el hilo con más carga; revise nodos ROS descontrolados o un proceso de visión sin límite de cuadros.',
    'Look for leaks with `ps aux --sort=-rss | head`; add memory limits (systemd MemoryMax=) to non-critical services.':
      'Busque fugas con `ps aux --sort=-rss | head`; agregue límites de memoria (systemd MemoryMax=) a los servicios no críticos.',
    'Identify the killed process; reduce memory use or add swap/zram.': 'Identifique el proceso cerrado; reduzca el uso de memoria o agregue swap/zram.',
    'Rotate logs (`journalctl --vacuum-size=200M`), offload rosbags, set log retention.':
      'Rote los registros (`journalctl --vacuum-size=200M`), descargue los rosbags y defina la retención de registros.',
    'Check fan/heatsink, enclosure ventilation, and ambient temperature.': 'Revise el ventilador y el disipador, la ventilación del gabinete y la temperatura ambiente.',
    'Check the BEC/5V regulator and wiring; under-voltage corrupts SD cards and causes random resets.':
      'Revise el regulador BEC/5V y el cableado; el bajo voltaje daña tarjetas SD y causa reinicios aleatorios.',
    'Restart the parent service.': 'Reinicie el servicio padre.',
    'Run `journalctl -p err --since \'15 min ago\'` for the full stack trace.': 'Ejecute `journalctl -p err --since \'15 min ago\'` para ver el error completo.',
    'Check the USB/UART cable; `dmesg -w` while replugging.': 'Revise el cable USB/UART; ejecute `dmesg -w` mientras lo vuelve a conectar.',
    'Intermittent USB usually means vibration on a connector or power brownouts. Secure the cable; use a powered hub for cameras/LTE.':
      'Un USB intermitente suele indicar vibración en un conector o caídas de voltaje. Asegure el cable; use un hub con alimentación para cámaras y LTE.',
    'Check the LTE/Wi-Fi link, VPN, and routing (`ip route`).': 'Revise el enlace LTE/Wi-Fi, la VPN y el enrutamiento (`ip route`).',
    'Set `mavlink_url` in the config, e.g. serial:/dev/ttyACM0:921600 or udpin:0.0.0.0:14550.':
      'Configure `mavlink_url`, por ejemplo serial:/dev/ttyACM0:921600 o udpin:0.0.0.0:14550.',
    'Check the FC power and serial link, the baud rate, and whether mavlink-router/MAVROS is holding the port.':
      'Revise la alimentación y el enlace serie del FC, la velocidad en baudios y si mavlink-router/MAVROS está ocupando el puerto.',
    'Check the pre-arm messages in STATUSTEXT; recalibrate if it\'s the compass/accel.':
      'Revise los mensajes de pre-armado en STATUSTEXT; recalibre si es la brújula o el acelerómetro.',
    'Check the antenna\'s sky view and RF interference from the LTE modem/camera; check the GPS cable.':
      'Revise la vista del cielo de la antena y la interferencia de RF del módem LTE o la cámara; revise el cable del GPS.',
    'Check the antenna placement and nearby RF noise sources.': 'Revise la ubicación de la antena y las fuentes de ruido de RF cercanas.',
    'Wait for a better constellation, or check for multipath near the base station.':
      'Espere una mejor constelación o revise reflexiones de señal (multitrayecto) cerca de la estación base.',
    'Inspect props for chips/imbalance, motor bearings and FC mount dampers. Clipping > 0 means the IMU is saturating.':
      'Inspeccione las hélices (astillas o desbalance), los rodamientos de los motores y los amortiguadores del FC. Clipping > 0 significa que la IMU se satura.',
    'Compass: check for magnetic interference/recalibrate. Position: GPS glitch. Velocity: vibration or optical-flow problem.':
      'Brújula: revise interferencia magnética o recalibre. Posición: falla del GPS. Velocidad: vibración o problema de flujo óptico.',
    'Land/charge. If it\'s still low after a charge at the base station, check the charging contacts and cell balance.':
      'Aterrice o cargue. Si sigue baja después de cargar en la estación base, revise los contactos de carga y el balance de celdas.',
    'Check the baud rate, cable shielding and CPU load on the companion.': 'Revise la velocidad en baudios, el blindaje del cable y la carga de CPU de la computadora a bordo.',
    'Look up this message in the PX4/ArduPilot docs.': 'Busque este mensaje en la documentación de PX4/ArduPilot.',
    'The base station controller may have hung; restart it.': 'El controlador de la estación base puede estar colgado; reinícielo.',
    'Inspect for ice, snow or debris on the rails; check the limit switches and actuator. The vehicle can\'t leave or return until it\'s cleared.':
      'Revise si hay hielo, nieve o residuos en los rieles; revise los finales de carrera y el actuador. El vehículo no puede salir ni volver hasta que se libere.',
    'Lubricate the rails and check actuator wear before it fails.': 'Lubrique los rieles y revise el desgaste del actuador antes de que falle.',
    'Clean the charging contacts and pads (corrosion/dust); check the vehicle stopped in position on its pads (landing or docking offset).':
      'Limpie los contactos y las placas de carga (corrosión o polvo); verifique que el vehículo quedó en posición sobre las placas (desvío al aterrizar o acoplarse).',
    'Service the HVAC/fans and filters. High enclosure heat degrades batteries and the companion computer.':
      'Dé mantenimiento al aire acondicionado, ventiladores y filtros. El calor en el gabinete degrada las baterías y la computadora a bordo.',
    'Don\'t fast-charge hot packs; wait for them to cool or fix the HVAC.': 'No cargue rápido baterías calientes; espere a que se enfríen o repare la climatización.',
    'Check the seals and desiccant; condensation risk for the electronics.': 'Revise los sellos y el desecante; hay riesgo de condensación en la electrónica.',
    'Restore site power.': 'Restablezca la energía del sitio.',
    'Clean the marker/beacon; the vehicle may not be able to return to its base station.':
      'Limpie el marcador o baliza; el vehículo podría no poder volver a su estación base.',
    'Usually a carrier outage or an expired SIM: fail over to the backup SIM.': 'Suele ser una caída del operador o una SIM vencida: cambie a la SIM de respaldo.',
    'Expect video dropouts and upload delays. Check the antenna, carrier outages, or add an external/MIMO antenna.':
      'Espere cortes de video y demoras en la carga. Revise la antena y caídas del operador, o agregue una antena externa/MIMO.',
    'Hold missions. If it\'s calm on site, check the weather-station anemometer.': 'Suspenda las misiones. Si en el sitio no hay viento, revise el anemómetro de la estación meteorológica.',
    'Hold missions unless the airframe is rated for rain.': 'Suspenda las misiones salvo que la estructura esté certificada para lluvia.',
    'Check the payload connector and USB/CSI cable; `v4l2-ctl --list-devices`; `dmesg | grep -i video`.':
      'Revise el conector de la carga útil y el cable USB/CSI; `v4l2-ctl --list-devices`; `dmesg | grep -i video`.',
    'Restart the capture service; check for a v4l2 `select timeout`.': 'Reinicie el servicio de captura; busque un `select timeout` de v4l2.',
    'Check USB bandwidth (move it to a separate controller) and CPU load.': 'Revise el ancho de banda USB (muévala a otro controlador) y la carga de CPU.',
    'Radiometric readings drift without FFC; trigger one, and check the shutter mechanism.':
      'Las lecturas radiométricas se desvían sin FFC; ejecute una y revise el obturador.',
    'Gas detection is unreliable until cooldown completes; if it never does, the cryocooler may be failing.':
      'La detección de gas no es confiable hasta que termine el enfriamiento; si nunca termina, el criorrefrigerador puede estar fallando.',
    'No-fly until it\'s fixed. Check the pyro/ejection continuity, battery and arming link; rerun the self-test.':
      'Prohibido volar hasta que se repare. Revise la continuidad del sistema de eyección, la batería y el enlace de armado; repita la autoprueba.',
    'Re-upload the geofence before any flight.': 'Vuelva a cargar la geocerca antes de cualquier vuelo.',
    'Resync the clock (chronyc makestep); check the GPS time source and NTP.': 'Resincronice el reloj (chronyc makestep); revise la fuente de hora del GPS y el NTP.',
    'Restore the approved version; make config changes through the fleet config service, not by hand on the vehicle.':
      'Restaure la versión aprobada; haga los cambios de configuración por el servicio de configuración de la flota, no a mano en el vehículo.',
    'Check the uploader service, cloud credentials/token expiry and bandwidth. Reports and insights will be missing these flights.':
      'Revise el servicio de carga, las credenciales o el vencimiento del token y el ancho de banda. Los reportes no incluirán estos vuelos.',
    'Every automatic fix has been tried.': 'Ya se intentaron todos los arreglos automáticos.',
    'Bug in the rule; report it.': 'Error en la regla; repórtelo.',
    'Check the vehicle and its base station are powered, the agent service is running (`systemctl status fleetdebug-agent`) and the VPN/LTE route to it.':
      'Verifique que el vehículo y su estación base tengan energía, que el servicio del agente esté activo (`systemctl status fleetdebug-agent`) y la ruta VPN/LTE hasta él.',
    'Check carrier coverage/outage at the site, modem health on the last report, and base station power.':
      'Revise la cobertura o caídas del operador en el sitio, el estado del módem en el último reporte y la energía de la estación base.',
    'Wait for the full report, or pull a bundle once connected.': 'Espere el reporte completo o descargue un paquete cuando se conecte.',

    // ---- root causes (rootcause.py)
    'Power brownout on the companion computer / FC rail': 'Caída de voltaje en la computadora a bordo / línea del FC',
    'Measure the 5V/12V rails under load; check the BEC rating and connectors. Brownouts during takeoff current spikes are typical.':
      'Mida las líneas de 5V/12V con carga; revise la capacidad del BEC y los conectores. Las caídas en los picos de corriente al despegar son típicas.',
    'Loose or vibrating flight-controller cable': 'Cable del controlador de vuelo flojo o con vibración',
    'Secure the FC USB/UART connector (hot glue / locking JST), add strain relief, and fix the vibration source.':
      'Asegure el conector USB/UART del FC (pegamento caliente o JST con traba), agregue alivio de tensión y corrija la fuente de vibración.',
    'GNSS degradation (obstruction or RF interference)': 'Degradación GNSS (obstrucción o interferencia de RF)',
    'Check the antenna\'s sky view at the base station, and keep it away from the LTE modem and camera USB3 lines (USB3 emits noise in the GPS L1 band). Try a shielded cable or a ground plane.':
      'Revise la vista del cielo de la antena en la estación base y aléjela del módem LTE y de los cables USB3 de la cámara (USB3 emite ruido en la banda L1 del GPS). Pruebe un cable blindado o un plano de tierra.',
    'Magnetic interference on the compass': 'Interferencia magnética en la brújula',
    'Look for nearby steel structures or high-current cables near the mag; recalibrate away from the base station; consider an external mast-mounted compass.':
      'Busque estructuras de acero o cables de alta corriente cerca del magnetómetro; recalibre lejos de la estación base; considere una brújula externa en mástil.',
    'Propulsion problem (damaged prop / motor bearing)': 'Problema de propulsión (hélice dañada / rodamiento del motor)',
    'Inspect and replace the props; spin each motor by hand to feel for bearing roughness; check the FC damping mount.':
      'Inspeccione y reemplace las hélices; gire cada motor a mano para sentir asperezas en los rodamientos; revise el soporte amortiguador del FC.',
    'Thermal problem degrading compute': 'Problema térmico que reduce la capacidad de cómputo',
    'Fix the cooling first (base station HVAC, companion fan); the CPU and frame symptoms should clear once temperatures drop.':
      'Corrija primero la refrigeración (climatización de la estación base, ventilador de la computadora); los síntomas de CPU y cuadros deberían desaparecer al bajar la temperatura.',
    'Software fault in the onboard Python stack': 'Falla de software en el sistema Python a bordo',
    'Pull the debug bundle and read the traceback. If memory is high too, look for a leak (tracemalloc, unbounded queues/caches in ROS callbacks). Add Restart=on-failure and MemoryMax= to the systemd unit.':
      'Descargue el paquete de depuración y lea el error. Si la memoria también está alta, busque una fuga (tracemalloc, colas o cachés sin límite en callbacks de ROS). Agregue Restart=on-failure y MemoryMax= a la unidad systemd.',
    'Base station not recharging the vehicle': 'La estación base no recarga el vehículo',
    'Clean the contacts and check the landing accuracy. A drone that lands off-center won\'t charge, and the next mission aborts on low battery.':
      'Limpie los contactos y revise la precisión del aterrizaje. Un dron que aterriza descentrado no carga y la siguiente misión se cancela por batería baja.',
    'Connectivity: cellular backhaul degraded': 'Conectividad: enlace celular degradado',
    'Check the carrier status and antenna; if it persists, move the base station antenna or add a second SIM/carrier. Data will upload once the link recovers.':
      'Revise el estado del operador y la antena; si persiste, mueva la antena de la estación base o agregue una segunda SIM u operador. Los datos se cargarán cuando se recupere el enlace.',

    // ---- fleet patterns (fleetcorr.py)
    'Several vehicles at one site: suspect RF jamming/interference, a new obstruction, or ionospheric activity, not individual antennas.':
      'Varios vehículos en un sitio: sospeche bloqueo o interferencia de RF, una nueva obstrucción o actividad ionosférica, no antenas individuales.',
    'Several vehicles at one site: suspect a carrier outage or a tower issue. Check the carrier status page; fail over to the secondary SIM.':
      'Varios vehículos en un sitio: sospeche una caída del operador o un problema en la torre. Revise la página de estado del operador; cambie a la SIM secundaria.',
    'Site-wide weather hold; expected, not a fault.': 'Pausa por clima en todo el sitio; es esperable, no es una falla.',
    'Site power problem; check the site feed and UPS.': 'Problema de energía en el sitio; revise la alimentación y el UPS.',
    'Several vehicles: suspect new site infrastructure (steel, power lines) near the base stations.':
      'Varios vehículos: sospeche nueva infraestructura en el sitio (acero, líneas eléctricas) cerca de las estaciones base.',
    'Site-wide heat: check the ambient conditions and HVAC sizing for the season.': 'Calor en todo el sitio: revise las condiciones ambientales y la capacidad de climatización para la temporada.',
    'Site uplink saturated or a cloud-side ingest problem.': 'Enlace del sitio saturado o un problema de recepción en la nube.',

    // ---- remote action descriptions (actions.py)
    'Restart one allow-listed service': 'Reiniciar un servicio autorizado',
    'Reboot the companion computer (flight controller unaffected)': 'Reiniciar la computadora a bordo (el controlador de vuelo no se afecta)',
    'Shrink the systemd journal to free disk': 'Reducir el registro de systemd para liberar disco',
    'Reset the cellular modem (link drops briefly)': 'Reiniciar el módem celular (el enlace se corta brevemente)',
    'Restart the network stack (Wi-Fi/LTE/DNS)': 'Reiniciar la red (Wi-Fi/LTE/DNS)',
    'Re-establish the VPN tunnel to operations': 'Restablecer el túnel VPN hacia operaciones',
    'Fail over to the backup SIM / second carrier': 'Cambiar a la SIM de respaldo / segundo operador',
    'Correct the system clock (fixes TLS/upload failures)': 'Corregir el reloj del sistema (soluciona fallas de TLS y carga)',
    'Restore an approved config that was edited by hand': 'Restaurar una configuración aprobada que se editó a mano',
    'Roll back to the previous software version (A/B slot) and reboot': 'Volver a la versión de software anterior (ranura A/B) y reiniciar',
    'Re-upload the geofence to the flight controller': 'Volver a cargar la geocerca en el controlador de vuelo',
    'Force a thermal-camera flat-field correction': 'Forzar una calibración de campo plano de la cámara térmica',
    // fix button labels (runbooks.py)
    'Reboot companion computer': 'Reiniciar computadora a bordo', 'Free disk space': 'Liberar espacio en disco',
    'Reset cellular modem': 'Reiniciar módem celular', 'Trigger thermal FFC': 'Calibrar cámara térmica (FFC)',
    'Restart network': 'Reiniciar red', 'Reconnect VPN': 'Reconectar VPN', 'Switch to backup SIM': 'Cambiar a la SIM de respaldo',
    'Fix the clock': 'Corregir el reloj', 'Restore approved config': 'Restaurar configuración aprobada',
    'Re-upload geofence': 'Volver a cargar la geocerca', 'Roll back to previous software': 'Volver al software anterior',
    // action results and errors
    '(sim) rebooted': '(sim) reiniciado', '(sim) VPN tunnel re-established': '(sim) túnel VPN restablecido',
    '(sim) network stack restarted': '(sim) red reiniciada', '(sim) modem reset; link dropped ~30s': '(sim) módem reiniciado; el enlace se cortó ~30 s',
    '(sim) switched to SIM 2': '(sim) cambiado a la SIM 2', '(sim) clock stepped to GPS/NTP time': '(sim) reloj ajustado a la hora GPS/NTP',
    '(sim) geofence re-uploaded to the FC': '(sim) geocerca cargada de nuevo en el FC',
    '(sim) rolled back to 2.4.1 (slot B) and rebooted': '(sim) se volvió a la 2.4.1 (ranura B) y se reinició',
    'precondition failed': 'falló una condición previa', 'bad signature': 'firma inválida',
    'replayed command': 'comando repetido', 'another action is running': 'hay otra acción en curso',
    'Not available in this demo': 'No disponible en esta demostración',
    'remote actions disabled: no action_secret configured on the vehicle': 'acciones remotas desactivadas: no hay action_secret configurado en el vehículo',

    // ---- runbook steps, checks and parts (runbooks.py)
    'The vehicle restarted the software itself and it keeps failing: this is a software bug, not hardware. A technician can\'t fix it on site.':
      'El vehículo reinició el software por su cuenta y sigue fallando: es un error de software, no de hardware. Un técnico no puede arreglarlo en el sitio.',
    'If the fleet-pattern banner shows the same crash on one software version, roll this vehicle back to the previous version (button below).':
      'Si el aviso de patrón de flota muestra la misma falla en una versión de software, vuelva este vehículo a la versión anterior (botón abajo).',
    'Pull the debug bundle for the developers and keep the faulty version paused.': 'Descargue el paquete de depuración para los desarrolladores y mantenga en pausa la versión con fallas.',
    'Only if the rollback doesn\'t help either: send someone to re-flash it.': 'Solo si volver a la versión anterior tampoco ayuda: envíe a alguien a reinstalarlo.',
    'The vehicle runs the previous version and the crash is gone.': 'El vehículo funciona con la versión anterior y la falla desapareció.',
    'Laptop with a known-good software image on USB': 'Laptop con una imagen de software confiable en USB',
    'The vehicle already tried every connection fix: restarted the network and VPN, reset the modem, and switched to the backup SIM.':
      'El vehículo ya intentó todos los arreglos de conexión: reinició la red y la VPN, reinició el módem y cambió a la SIM de respaldo.',
    'Rule out a carrier outage first (carrier status page, other vehicles at the site).': 'Descarte primero una caída del operador (página de estado, otros vehículos del sitio).',
    'If it\'s only this vehicle: the antenna, cable or modem is faulty. Send someone.': 'Si es solo este vehículo: la antena, el cable o el módem tienen falla. Envíe a alguien.',
    'Signal better than -110 dBm and the vehicle reports normally.': 'Señal mejor que -110 dBm y el vehículo reporta con normalidad.',
    'Spare LTE antenna and cable': 'Antena LTE y cable de repuesto', 'Spare modem': 'Módem de repuesto',
    'SIM from a second carrier': 'SIM de un segundo operador',
    'Open View service logs for the unit and find the last traceback: that is the bug to fix, the restart only buys time.':
      'Abra Ver registros del servicio y busque el último error: ese es el problema a corregir; reiniciar solo gana tiempo.',
    'Fix remotely: restart the service (needs the vehicle disarmed).': 'Solucionar a distancia: reinicie el servicio (requiere el vehículo desarmado).',
    'If it crashes again within minutes, don\'t loop restarts: pull the debug bundle and compare the version against vehicles that are healthy.':
      'Si vuelve a fallar en minutos, no repita reinicios: descargue el paquete de depuración y compare la versión con la de vehículos sanos.',
    'If only vehicles on one version crash (see the fleet-pattern banner), pause that rollout.':
      'Si solo fallan vehículos con una versión (vea el aviso de patrón de flota), pause ese despliegue.',
    'The process is running and the systemd unit is active on the next check.': 'El proceso está en ejecución y la unidad systemd está activa en la siguiente verificación.',
    'View service logs for the unit to see why it exited.': 'Vea los registros del servicio para saber por qué se detuvo.',
    'Fix remotely: restart the unit.': 'Solucionar a distancia: reinicie la unidad.',
    'If it fails again immediately, the cause is config or a missing dependency: check the logs for \'No such file\', \'ModuleNotFoundError\' or permission errors.':
      'Si vuelve a fallar de inmediato, la causa es la configuración o una dependencia faltante: busque en los registros \'No such file\', \'ModuleNotFoundError\' o errores de permisos.',
    'systemctl reports the unit active.': 'systemctl reporta la unidad activa.',
    'View service logs and read the full traceback; note the file and line.': 'Vea los registros del servicio y lea el error completo; anote el archivo y la línea.',
    'If the process is still running, the error may be handled. Check whether missions complete before restarting anything.':
      'Si el proceso sigue en ejecución, el error puede estar controlado. Verifique si las misiones se completan antes de reiniciar algo.',
    'If the process died, restart its service; then fix the code path in the traceback and ship it through the staged rollout.':
      'Si el proceso terminó, reinicie su servicio; luego corrija el código indicado en el error y publíquelo con un despliegue por etapas.',
    'No new Python errors in the journal over the next 15 minutes.': 'Sin errores nuevos de Python en el registro durante los próximos 15 minutos.',
    'The service runs the wrong interpreter, or the virtualenv is broken.': 'El servicio usa el intérprete equivocado o el entorno virtual está dañado.',
    'Check the interpreter path shown in the finding against the systemd unit\'s ExecStart.': 'Compare la ruta del intérprete del hallazgo con el ExecStart de la unidad systemd.',
    'Re-flash or roll back the A/B image; don\'t pip install on a field vehicle.': 'Reinstale o vuelva a la imagen A/B anterior; no use pip install en un vehículo en campo.',
    'All required modules import.': 'Todos los módulos requeridos se importan.',
    'Known-good software image on USB': 'Imagen de software confiable en USB',
    'The kernel killed a process for lack of memory. The journal line names it.': 'El kernel cerró un proceso por falta de memoria. La línea del registro lo nombra.',
    'Restart the leaking service to recover now.': 'Reinicie el servicio con la fuga para recuperarse ahora.',
    'Find the leak: memory that climbs between checks (see Trends) means a leak, usually an unbounded queue, cache or list in a ROS callback.':
      'Encuentre la fuga: si la memoria sube entre verificaciones (vea Tendencias) hay una fuga, normalmente una cola, caché o lista sin límite en un callback de ROS.',
    'Add MemoryMax= to that unit so a leak kills only it, not the flight stack.': 'Agregue MemoryMax= a esa unidad para que una fuga solo la detenga a ella y no al sistema de vuelo.',
    'Memory stays flat across several checks after the restart.': 'La memoria se mantiene estable en varias verificaciones después del reinicio.',
    'Find the biggest process: it is usually the perception or video pipeline.': 'Encuentre el proceso más grande: suele ser el de percepción o video.',
    'Restart that service to reclaim memory.': 'Reinicie ese servicio para recuperar memoria.',
    'Watch the next few checks. If memory climbs again, it\'s a leak (see the OOM runbook), not a one-off spike.':
      'Observe las próximas verificaciones. Si la memoria vuelve a subir, es una fuga (vea el procedimiento OOM), no un pico aislado.',
    'Memory below 90% and not rising.': 'Memoria por debajo del 90% y sin subir.',
    'Check the SoC temperature first. Thermal throttling looks like high CPU.': 'Revise primero la temperatura del SoC. La limitación térmica parece CPU alta.',
    'Find the hot process in the debug bundle (ps.txt is sorted by CPU).': 'Busque el proceso con más carga en el paquete de depuración (ps.txt está ordenado por CPU).',
    'Restart a runaway node; cap camera/inference frame rates in its config.': 'Reinicie un nodo descontrolado; limite los cuadros por segundo de cámara o inferencia en su configuración.',
    'CPU below 90% on the next checks.': 'CPU por debajo del 90% en las próximas verificaciones.',
    'Fix remotely: shrink the journal to free space.': 'Solucionar a distancia: reduzca el registro para liberar espacio.',
    'If still full, the culprit is flight logs or rosbags not being offloaded: check the upload queue.':
      'Si sigue lleno, la causa son registros de vuelo o rosbags que no se descargan: revise la cola de carga.',
    'Set log rotation and a retention limit so it can\'t recur.': 'Configure la rotación de registros y un límite de retención para que no se repita.',
    'Disk below 90%.': 'Disco por debajo del 90%.',
    'Check the base station\'s cellular signal first. With a weak link, data is queued, not lost.':
      'Revise primero la señal celular de la estación base. Con un enlace débil, los datos quedan en cola, no se pierden.',
    'If the link is fine, restart the uploader service.': 'Si el enlace está bien, reinicie el servicio de carga.',
    'Still stuck: check whether the cloud credentials or token expired (uploader logs show 401/403).':
      'Si sigue detenido: verifique si vencieron las credenciales o el token de la nube (los registros muestran 401/403).',
    'The upload queue shrinks on the next checks.': 'La cola de carga disminuye en las próximas verificaciones.',
    'The vehicle fixes this itself: it resyncs its clock.': 'El vehículo lo repara solo: resincroniza su reloj.',
    'If it comes back, the time source is failing: check that the GPS has a fix and that NTP (UDP 123) isn\'t blocked by the carrier.':
      'Si vuelve, la fuente de hora está fallando: verifique que el GPS tenga posición y que el operador no bloquee NTP (UDP 123).',
    'Clock offset under 5 s, and uploads and the VPN reconnect.': 'Desfase del reloj menor a 5 s, y la carga y la VPN se reconectan.',
    'The vehicle fixes this itself: it resets the modem, then switches to the backup SIM.':
      'El vehículo lo repara solo: reinicia el módem y luego cambia a la SIM de respaldo.',
    'Check the carrier\'s status page for an outage at the site.': 'Revise la página de estado del operador por una caída en el sitio.',
    'If both SIMs have no service, it\'s the antenna or the modem: send someone.': 'Si ninguna SIM tiene servicio, es la antena o el módem: envíe a alguien.',
    'The modem is \'connected\' and the vehicle reports normally.': 'El módem está \'conectado\' y el vehículo reporta con normalidad.',
    'The vehicle fixes this itself, one step at a time: restart the VPN, the network, then the modem, then switch SIM, then reboot.':
      'El vehículo lo repara solo, paso a paso: reinicia la VPN, la red, luego el módem, luego cambia de SIM y luego reinicia.',
    'The error text says which layer failed: \'name resolution\' means DNS, \'timed out\' means the VPN, \'Network is unreachable\' means the modem or carrier.':
      'El texto del error indica qué capa falló: \'name resolution\' es el DNS, \'timed out\' es la VPN y \'Network is unreachable\' es el módem o el operador.',
    'If every step has been tried and it\'s still down, send someone to check the modem, antenna and router.':
      'Si se intentaron todos los pasos y sigue caído, envíe a alguien a revisar el módem, la antena y el router.',
    'Every ops endpoint answers.': 'Todos los puntos de operaciones responden.',
    'If several vehicles at the site show it (fleet-pattern banner), it\'s the carrier: check the carrier status page and wait, or fail over to the second SIM.':
      'Si varios vehículos del sitio lo muestran (aviso de patrón de flota), es el operador: revise su página de estado y espere, o cambie a la segunda SIM.',
    'If only this base station: reset the modem remotely (the link drops ~30 s; the vehicle spools data meanwhile).':
      'Si es solo esta estación base: reinicie el módem a distancia (el enlace se corta ~30 s; el vehículo guarda los datos mientras tanto).',
    'If it persists, schedule a visit: check the antenna cable and mounting.': 'Si persiste, programe una visita: revise el cable y el montaje de la antena.',
    'RSRP better than -110 dBm and SINR above 0 dB.': 'RSRP mejor que -110 dBm y SINR por encima de 0 dB.',
    'The vehicle stopped reporting. It keeps logging locally and backfills when it reconnects.':
      'El vehículo dejó de reportar. Sigue registrando localmente y enviará todo al reconectarse.',
    'Check the last report before it went quiet: weak signal or low power there points at the cause.':
      'Revise el último reporte antes del silencio: una señal débil o poca energía ahí indican la causa.',
    'Check the carrier status for the site and the base station\'s mains power.': 'Revise el estado del operador en el sitio y la energía de red de la estación base.',
    'If still silent after an hour: power-cycle via the base station\'s out-of-band relay, then dispatch a technician.':
      'Si sigue en silencio después de una hora: apague y encienda con el relé independiente de la estación base y luego envíe un técnico.',
    'Reports resume, and the backlog is backfilled.': 'Los reportes se reanudan y los pendientes se recuperan.',
    'The console can\'t reach the agent. Check the VPN/tunnel to the vehicle first.': 'La consola no alcanza al agente. Revise primero la VPN o el túnel hacia el vehículo.',
    'If the vehicle also stopped pushing reports, treat it as silent (see above).': 'Si el vehículo también dejó de enviar reportes, trátelo como silencioso (ver arriba).',
    'If only the agent is down, its systemd unit will restart it automatically.': 'Si solo el agente está caído, su unidad systemd lo reiniciará automáticamente.',
    'The agent answers /health.': 'El agente responde en /health.',
    'The companion computer lost contact with the flight controller.': 'La computadora a bordo perdió contacto con el controlador de vuelo.',
    'Check for a USB disconnect or under-voltage finding: they tell you whether it\'s the cable or power.':
      'Busque un hallazgo de desconexión USB o de bajo voltaje: indican si es el cable o la energía.',
    'Fix remotely: reboot the companion computer (needs disarmed + docked). This re-enumerates USB and restarts the MAVLink router.':
      'Solucionar a distancia: reinicie la computadora a bordo (requiere desarmado y en estación base). Esto reconoce de nuevo el USB y reinicia el router MAVLink.',
    'If it drops again, it\'s physical: schedule a visit to reseat or replace the FC cable and check the 5V supply under load.':
      'Si vuelve a caerse, es físico: programe una visita para reconectar o reemplazar el cable del FC y revisar la fuente de 5V con carga.',
    'FC heartbeat under 3 s and no new USB disconnects.': 'Señal del FC menor a 3 s y sin nuevas desconexiones USB.',
    'Spare flight-controller cable': 'Cable de repuesto del controlador de vuelo', 'Multimeter': 'Multímetro',
    'The flight controller\'s USB/serial device has disappeared from Linux.': 'El dispositivo USB/serie del controlador de vuelo desapareció de Linux.',
    'Try a remote reboot first: sometimes the USB hub just needs re-enumerating.': 'Pruebe primero un reinicio a distancia: a veces el hub USB solo necesita reconocerse de nuevo.',
    'If the device is still missing after the reboot: site visit to reseat the cable.': 'Si el dispositivo sigue faltando después del reinicio: visita en sitio para reconectar el cable.',
    '/dev/ttyACM* or ttyTHS* is present and the FC heartbeat is back.': '/dev/ttyACM* o ttyTHS* está presente y la señal del FC volvió.',
    'Intermittent USB drops come from vibration on the connector or brownouts.': 'Las caídas intermitentes de USB vienen de vibración en el conector o caídas de voltaje.',
    'Check whether they coincide with takeoff (high current) in the flight log.': 'Verifique en el registro de vuelo si coinciden con el despegue (corriente alta).',
    'On the next visit: lock the connector, add strain relief, and power cameras and modems from a powered hub.':
      'En la próxima visita: trabe el conector, agregue alivio de tensión y alimente cámaras y módems desde un hub con alimentación.',
    'No USB disconnects over several flights.': 'Sin desconexiones USB durante varios vuelos.',
    'Spare flight-controller USB cable': 'Cable USB de repuesto del controlador de vuelo',
    'Locking connectors or hot glue': 'Conectores con traba o pegamento caliente', 'Powered USB hub': 'Hub USB con alimentación',
    'Read which sensor is flagged in the finding detail.': 'Lea qué sensor está marcado en el detalle del hallazgo.',
    'Compass: recalibrate away from the base station\'s steel. GPS: see the GPS runbook. Gyro/accel: recalibrate; if it persists, replace the FC.':
      'Brújula: recalibre lejos del acero de la estación base. GPS: vea el procedimiento de GPS. Giroscopio/acelerómetro: recalibre; si persiste, reemplace el FC.',
    'The FC sensor-health mask is clear.': 'La máscara de estado de sensores del FC está limpia.',
    'Laptop with ground-control software for calibration': 'Laptop con software de control en tierra para calibración',
    'Look up the exact message in the PX4/ArduPilot docs; pre-arm messages name the failing check.':
      'Busque el mensaje exacto en la documentación de PX4/ArduPilot; los mensajes de pre-armado nombran la verificación que falla.',
    'Most pre-arm failures need calibration or a hardware check on site.': 'La mayoría de las fallas de pre-armado requieren calibración o una revisión de hardware en sitio.',
    'Pre-arm checks pass.': 'Las verificaciones de pre-armado se aprueban.',
    'Laptop with ground-control software': 'Laptop con software de control en tierra',
    'If several vehicles at one site lose GPS together (fleet-pattern banner), it\'s environmental (jamming, an obstruction, space weather). Hold missions and wait.':
      'Si varios vehículos de un sitio pierden el GPS a la vez (aviso de patrón de flota), es ambiental (bloqueo, una obstrucción, clima espacial). Suspenda las misiones y espere.',
    'If only this vehicle: check the flight log. Did it start when the LTE modem or camera started? That\'s RF interference from the vehicle itself.':
      'Si es solo este vehículo: revise el registro de vuelo. ¿Empezó cuando arrancó el módem LTE o la cámara? Es interferencia de RF del propio vehículo.',
    'If it persists: site visit to check the antenna view and cable, and move the antenna away from USB3/LTE.':
      'Si persiste: visita en sitio para revisar la vista y el cable de la antena, y alejarla de USB3/LTE.',
    '3D fix, at least 8 satellites, HDOP under 2.': 'Posición 3D, al menos 8 satélites, HDOP menor a 2.',
    'Spare GPS antenna and cable': 'Antena GPS y cable de repuesto',
    'Magnetic interference: new steel, cables or equipment near the base station?': 'Interferencia magnética: ¿hay acero, cables o equipos nuevos cerca de la estación base?',
    'Recalibrate the compass away from the base station.': 'Recalibre la brújula lejos de la estación base.',
    'If it returns right after calibration, mount an external compass on a mast.': 'Si vuelve justo después de calibrar, instale una brújula externa en un mástil.',
    'Compass variance under 0.8.': 'Varianza de la brújula menor a 0.8.',
    'External compass mast (if it recurs)': 'Mástil para brújula externa (si se repite)',
    'The EKF doesn\'t trust its position or velocity. It usually follows a GPS glitch or high vibration.':
      'El EKF no confía en su posición o velocidad. Suele seguir a una falla del GPS o a vibración alta.',
    'Fix the underlying GPS or vibration finding; this clears by itself.': 'Corrija el hallazgo de GPS o vibración de fondo; esto se resuelve solo.',
    'EKF variances under 0.8.': 'Varianzas del EKF menores a 0.8.',
    'No remote fix: this is mechanical.': 'Sin solución a distancia: es mecánico.',
    'Keep the vehicle NO-GO. High vibration ruins the position estimate and can lead to a flyaway.':
      'Mantenga el vehículo en NO-GO. La vibración alta arruina la estimación de posición y puede causar una pérdida de control.',
    'On site: inspect and replace the props (chips, cracks), spin each motor by hand for rough bearings, and check the FC\'s damping mount.':
      'En sitio: inspeccione y reemplace las hélices (astillas, grietas), gire cada motor a mano para detectar rodamientos ásperos y revise el soporte amortiguador del FC.',
    'Vibration under 30 m/s² and no IMU clipping on a test hover.': 'Vibración menor a 30 m/s² y sin saturación de la IMU en un vuelo estacionario de prueba.',
    'Spare propeller set': 'Juego de hélices de repuesto', 'Spare motor': 'Motor de repuesto', 'Hex drivers': 'Llaves hexagonales',
    'Damping grommets': 'Arandelas amortiguadoras',
    'If the base station shows \'charging\', wait. It clears when charged.': 'Si la estación base muestra \'cargando\', espere. Se resuelve al terminar la carga.',
    'If the base station is not charging, follow the charging-contacts runbook.': 'Si la estación base no está cargando, siga el procedimiento de contactos de carga.',
    'Battery above the minimum voltage.': 'Batería por encima del voltaje mínimo.',
    'The companion computer\'s 5V supply is sagging; this corrupts storage and causes random resets.':
      'La fuente de 5V de la computadora a bordo está cayendo; esto daña el almacenamiento y causa reinicios aleatorios.',
    'On site: measure the rail under load and replace the BEC/regulator or cable.': 'En sitio: mida la línea con carga y reemplace el BEC/regulador o el cable.',
    'No under-voltage flags since boot.': 'Sin alertas de bajo voltaje desde el arranque.',
    'Spare 5V regulator (BEC)': 'Regulador de 5V de repuesto (BEC)',
    'The base station is running on its UPS. Check the site power feed.': 'La estación base funciona con su UPS. Revise la alimentación del sitio.',
    'Hold missions if the UPS charge is low, so the drone can still land and charge.': 'Suspenda las misiones si la carga del UPS es baja, para que el dron todavía pueda aterrizar y cargar.',
    'Mains power is restored.': 'Se restableció la energía de red.', 'Site electrician contact': 'Contacto del electricista del sitio',
    'Don\'t charge or fly hot packs. Wait for them to cool.': 'No cargue ni vuele con baterías calientes. Espere a que se enfríen.',
    'If the base station HVAC also failed, follow that runbook.': 'Si la climatización de la estación base también falló, siga ese procedimiento.',
    'Pack temperature under 45 °C.': 'Temperatura de la batería menor a 45 °C.',
    'Check where the drone landed: an off-center landing misses the contacts.': 'Revise dónde aterrizó el dron: un aterrizaje descentrado no toca los contactos.',
    'High contact resistance means corrosion or dirt.': 'Una resistencia de contacto alta indica corrosión o suciedad.',
    'On site: clean the contacts and pads, and check the charger output.': 'En sitio: limpie los contactos y las placas, y revise la salida del cargador.',
    'The base station reports \'charging\' and the battery rises.': 'La estación base reporta \'cargando\' y la batería sube.',
    'Contact cleaner': 'Limpiador de contactos', 'Lint-free cloths': 'Paños sin pelusa',
    'Check the weather: ice and snow are the most common cause of a jammed lid.': 'Revise el clima: el hielo y la nieve son la causa más común de una tapa trabada.',
    'Don\'t keep retrying: the motor overheats.': 'No siga reintentando: el motor se sobrecalienta.',
    'On site: clear the debris, check the limit switches, and lubricate the rails.': 'En sitio: retire los residuos, revise los finales de carrera y lubrique los rieles.',
    'The lid completes a cycle in under 40 s at normal current.': 'La tapa completa un ciclo en menos de 40 s con corriente normal.',
    'Brush and de-icer': 'Cepillo y descongelante', 'Rail lubricant': 'Lubricante para rieles', 'Spare limit switch': 'Final de carrera de repuesto',
    'The base station\'s HVAC has failed; heat damages batteries and the computer.': 'La climatización de la estación base falló; el calor daña las baterías y la computadora.',
    'Hold missions in hot weather.': 'Suspenda las misiones con calor.', 'On site: check the fans, filters and HVAC unit.': 'En sitio: revise los ventiladores, los filtros y la unidad de climatización.',
    'Enclosure under 45 °C.': 'Gabinete por debajo de 45 °C.',
    'Replacement air filters': 'Filtros de aire de repuesto', 'Spare HVAC fan': 'Ventilador de climatización de repuesto',
    'A base station fault needs a technician; the finding names the subsystem.': 'Una falla de la estación base necesita un técnico; el hallazgo indica el subsistema.',
    'The base station finding clears.': 'El hallazgo de la estación base desaparece.', 'Basic toolkit': 'Kit básico de herramientas',
    'Usually the base station\'s climate control, or direct sun on the enclosure.': 'Suele ser la climatización de la estación base o el sol directo sobre el gabinete.',
    'Hold missions until it cools; fix the HVAC if that finding is also present.': 'Suspenda las misiones hasta que se enfríe; repare la climatización si ese hallazgo también aparece.',
    'SoC temperature under 80 °C.': 'Temperatura del SoC menor a 80 °C.',
    'Fix remotely: trigger a flat-field correction.': 'Solucionar a distancia: ejecute una calibración de campo plano.',
    'If it doesn\'t run, the camera\'s shutter may be stuck: site visit.': 'Si no se ejecuta, el obturador de la cámara puede estar trabado: visita en sitio.',
    'Last FFC under 10 minutes ago.': 'Última FFC hace menos de 10 minutos.',
    'The camera has disappeared from Linux.': 'La cámara desapareció de Linux.',
    'Try a remote reboot to re-enumerate USB/CSI.': 'Pruebe un reinicio a distancia para que se reconozca de nuevo el USB/CSI.',
    'If it\'s still missing: site visit to reseat the payload connector.': 'Si sigue faltando: visita en sitio para reconectar el conector de la carga útil.',
    'The camera device is present and streaming.': 'El dispositivo de la cámara está presente y transmitiendo.',
    'The camera is present but has stopped sending frames.': 'La cámara está presente pero dejó de enviar cuadros.',
    'Try a remote reboot; if a capture service is listed, restart that instead.': 'Pruebe un reinicio a distancia; si hay un servicio de captura en la lista, reinicie ese en su lugar.',
    'A fresh frame within 5 s.': 'Un cuadro nuevo en menos de 5 s.',
    'The gas camera\'s cooler needs a few minutes to reach temperature after power-on.': 'El enfriador de la cámara de gas necesita unos minutos para llegar a temperatura después de encenderse.',
    'If it never gets there, the cryocooler is failing: site visit.': 'Si nunca llega, el criorrefrigerador está fallando: visita en sitio.',
    'Cooler at about 77 K and cooldown complete.': 'Enfriador a unos 77 K y enfriamiento completo.',
    'Check the payload connector and cable.': 'Revise el conector y el cable de la carga útil.', 'The payload finding clears.': 'El hallazgo de la carga útil desaparece.',
    'Spare payload cable': 'Cable de repuesto para la carga útil',
    'No-fly until it\'s fixed. This is the last line of defense.': 'Prohibido volar hasta que se repare. Es la última línea de defensa.',
    'On site: check pyro continuity, the safety system\'s battery and arming link, then rerun the self-test.':
      'En sitio: revise la continuidad del sistema de eyección, la batería y el enlace de armado del sistema de seguridad, y repita la autoprueba.',
    'Parachute armed and self-test passed.': 'Paracaídas armado y autoprueba aprobada.',
    'Parachute service kit': 'Kit de servicio del paracaídas', 'Continuity tester': 'Probador de continuidad',
    'The mission reached the flight controller without its geofence. The vehicle re-uploads it itself once it is docked.':
      'La misión llegó al controlador de vuelo sin su geocerca. El vehículo la vuelve a cargar solo cuando está en la estación base.',
    'If it keeps happening, check the mission-planning step that exports the fence.': 'Si sigue pasando, revise el paso de planificación de misiones que exporta la geocerca.',
    'The flight controller reports the geofence loaded.': 'El controlador de vuelo reporta la geocerca cargada.',
    'Expected: missions are on HOLD until the weather is inside limits.': 'Es lo esperado: las misiones quedan en HOLD hasta que el clima esté dentro de los límites.',
    'If it\'s calm on site but still reads high, the anemometer may be faulty.': 'Si en el sitio no hay viento pero sigue marcando alto, el anemómetro puede tener una falla.',
    'Wind and gusts inside the limits.': 'Viento y ráfagas dentro de los límites.',
    'Someone changed this file by hand on the vehicle. The vehicle restores the approved version itself and keeps the edited copy for review.':
      'Alguien cambió este archivo a mano en el vehículo. El vehículo restaura solo la versión aprobada y guarda la copia editada para revisión.',
    'Ask whoever made the change to submit it through the fleet config service, so it is reviewed and applied to every vehicle the same way.':
      'Pida a quien hizo el cambio que lo envíe por el servicio de configuración de la flota, para que se revise y se aplique igual en todos los vehículos.',
    'The file matches the approved baseline.': 'El archivo coincide con la versión aprobada.',

    // ---- flight-log analysis (logs.py)
    'High Z vibration': 'Vibración Z alta', 'High X vibration': 'Vibración X alta', 'High Y vibration': 'Vibración Y alta',
    'GPS satellite count dropped': 'Bajó la cantidad de satélites GPS', 'GPS HDOP degraded': 'HDOP del GPS degradado',
    'EKF position variance high': 'Varianza de posición del EKF alta', 'EKF compass variance high': 'Varianza de brújula del EKF alta',
    'Companion CPU saturated': 'CPU de la computadora a bordo saturada', 'Companion SoC overheating': 'SoC de la computadora a bordo sobrecalentado',
    'Weak radio link': 'Enlace de radio débil', 'Battery voltage sag': 'Caída de voltaje de la batería', 'Telemetry gap': 'Hueco en la telemetría',
    'Failsafe: GPS lost, mission aborted, RTL': 'Modo seguro: GPS perdido, misión cancelada, regreso a casa (RTL)',
    'Lid open, launch': 'Tapa abierta, despegue', 'empty log': 'registro vacío',
  };

  // [pattern, template]; {n} = group as is, {tn} = group translated.
  const PATTERNS = [
    // titles with values
    [/^CPU at (.+)%$/, 'CPU al {1}%'],
    [/^Memory at (.+)%$/, 'Memoria al {1}%'],
    [/^Disk (\S+) at (.+)%$/, 'Disco {1} al {2}%'],
    [/^Process '(.+)' is not running$/, 'El proceso \'{1}\' no se está ejecutando'],
    [/^Process '(.+)' is a zombie$/, 'El proceso \'{1}\' quedó como zombi'],
    [/^systemd unit (\S+) is (\S+)$/, 'La unidad systemd {1} está {t2}'],
    [/^(\d+) Python error line\(s\) in the journal \(last 15 min\)$/, '{1} línea(s) de error de Python en el registro (últimos 15 min)'],
    [/^(\d+) USB disconnect event\(s\)$/, '{1} desconexión(es) USB'],
    [/^Cannot reach (.+)$/, 'No se puede alcanzar {1}'],
    [/^No 3D GPS fix \(fix_type=(\d+)\)$/, 'Sin posición GPS 3D (fix_type={1})'],
    [/^Low satellite count \((.+)\)$/, 'Pocos satélites ({1})'],
    [/^High HDOP \((.+)\)$/, 'HDOP alto ({1})'],
    [/^High vibration \((.+) m\/s²\)$/, 'Vibración alta ({1} m/s²)'],
    [/^EKF (\S+) variance high \((.+)\)$/, 'Varianza del EKF de {t1} alta ({2})'],
    [/^Battery low \((.+) V\)$/, 'Batería baja ({1} V)'],
    [/^MAVLink packet drop (.+)%$/, 'Pérdida de paquetes MAVLink {1}%'],
    [/^Base station lid slow \((.+)s cycle\)$/, 'Tapa de la estación base lenta (ciclo de {1} s)'],
    [/^Base station climate control failure \((.+)°C inside\)$/, 'Falla de climatización de la estación base ({1} °C adentro)'],
    [/^Battery pack hot at base station \((.+)°C\)$/, 'Batería caliente en la estación base ({1} °C)'],
    [/^Base station humidity (.+)%$/, 'Humedad en la estación base {1}%'],
    [/^No cellular service on SIM (.+)$/, 'Sin servicio celular en la SIM {1}'],
    [/^Wind above limit \((.+) m\/s, gust (.+)\)$/, 'Viento por encima del límite ({1} m/s, ráfagas de {2})'],
    [/^(\S+) camera not detected$/, 'Cámara {t1} no detectada'],
    [/^(\S+) camera stream frozen$/, 'Transmisión de la cámara {t1} congelada'],
    [/^(\S+) dropping frames \((.+)\)$/, 'La cámara {t1} pierde cuadros ({2})'],
    [/^Clock is off by (.+) s$/, 'El reloj está desfasado {1} s'],
    [/^(\S+) edited outside the approved baseline$/, '{1} editado fuera de la versión aprobada'],
    [/^Rule (.+) crashed$/, 'La regla {1} falló'],
    [/^No heartbeat for (\d+)s$/, 'Sin señal de vida desde hace {1} s'],
    [/^(.+) critical \(heartbeat only\)$/, '{t1}: crítico (solo señal de vida)'],
    [/^Automatic fixes used up: (.+)$/, 'Arreglos automáticos agotados: {t1}'],
    [/^(\S+) at ([\d.]+)°C$/, '{1} a {2} °C'],
    // details with values
    [/^Only (\d+) MB available\. The OOM killer may terminate the flight software\.$/, 'Solo hay {1} MB disponibles. El kernel podría cerrar el software de vuelo por falta de memoria.'],
    [/^(.+) GB free\. Flight logs and rosbags stop recording when the disk fills\.$/, '{1} GB libres. Los registros de vuelo y los rosbags dejan de grabarse cuando el disco se llena.'],
    [/^Last heartbeat (.+)s ago\.$/, 'Última señal hace {1} s.'],
    [/^(\d+) files \/ (.+) GB queued, oldest (.+) h$/, '{1} archivos / {2} GB en cola, el más antiguo de hace {3} h'],
    [/^(\S+) changed (.+) h ago by (.+)$/, '{1} modificado hace {2} h por {t3}'],
    [/^(.+)s old$/, 'antigüedad de {1} s'],
    [/^UPS at (.+)%$/, 'UPS al {1}%'],
    [/^modem state: (.+)$/, 'estado del módem: {t1}'],
    [/^device (.+) missing$/, 'falta el dispositivo {1}'],
    [/^last frame (.+)s ago$/, 'último cuadro hace {1} s'],
    [/^last flat-field correction (.+)s ago$/, 'última calibración de campo plano hace {1} s'],
    [/^cooler at (.+) K$/, 'enfriador a {1} K'],
    [/^time source: (.+)\. A wrong clock makes TLS certificates look invalid, so uploads and the VPN fail; logs also stop lining up\.$/,
      'fuente de hora: {1}. Un reloj incorrecto hace que los certificados TLS parezcan inválidos, así que fallan la carga y la VPN; además, los registros dejan de coincidir.'],
    [/^The vehicle tried (.+); the problem is still there\.$/, 'El vehículo intentó {t1}; el problema continúa.'],
    [/^The automatic fix worked (\d+) times in the last hour, but the problem keeps coming back\.$/, 'El arreglo automático funcionó {1} veces en la última hora, pero el problema sigue volviendo.'],
    [/^Check `journalctl -u <unit> -n 100` and restart\. Search the logs for a Python traceback from (.+)\.$/,
      'Revise `journalctl -u <unit> -n 100` y reinicie. Busque en los registros un error de Python de {1}.'],
    [/^`systemctl status (\S+)` and `journalctl -u (\S+) -b`$/, '`systemctl status {1}` y `journalctl -u {2} -b`'],
    [/^Activate the right venv or `pip install (.+)`\. Interpreter: (.+)$/, 'Active el entorno virtual correcto o ejecute `pip install {1}`. Intérprete: {2}'],
    // decisions, rules, reasons
    [/^Every remote option has been used or none exists for these problems\. While the technician is on the way, (\d+) remote fix\(es\) can still be tried\.$/,
      'Se agotaron las opciones a distancia o no existen para estos problemas. Mientras el técnico va en camino, todavía se pueden intentar {1} solución(es) a distancia.'],
    [/^Should clear by itself; send someone if it lasts over (.+)\.$/, 'Debería resolverse solo; envíe a alguien si dura más de {1}.'],
    [/^Try the remote fix up to (\d+) times; if it doesn't hold, send someone\.$/, 'Intente la solución a distancia hasta {1} veces; si no se mantiene, envíe a alguien.'],
    [/^Physical problem, not urgent\. Fix it on a visit within (.+)\.$/, 'Problema físico, no urgente. Resuélvalo en una visita dentro de {1}.'],
    [/^Present for (.+?), over the (.+?) limit\.$/, 'Presente desde hace {1}, por encima del límite de {2}.'],
    [/^Present for (.+?)\. Send someone if it's still here in (.+?)\.$/, 'Presente desde hace {1}. Envíe a alguien si sigue en {2}.'],
    [/^Present for (.+?)\.$/, 'Presente desde hace {1}.'],
    [/^Remote fix tried (\d+) time\(s\) and the problem is still there\.$/, 'Solución a distancia intentada {1} vez/veces y el problema continúa.'],
    [/^Tried (\d+) of (\d+) times; try again or wait for the next check\.$/, 'Intentada {1} de {2} veces; vuelva a intentarlo o espere la próxima verificación.'],
    [/^Fixing itself: step (\d+) of (\d+) \(done so far: (.+)\)\.$/, 'Reparándose solo: paso {1} de {2} (hecho hasta ahora: {t3}).'],
    [/^Tried automatically: (.+)\.$/, 'Intentado automáticamente: {t1}.'],
    [/^self-heal step (\d+)\/(\d+): (.+)$/, 'autorreparación, paso {1}/{2}: {t3}'],
    [/^playbook: (.+)$/, 'procedimiento automático: {t1}'],
    [/^Restart (\S+\.service)$/, 'Reiniciar {1}'],
    [/^Common to vehicles on (.+): suspect a software regression\. Pause the rollout and compare against the previous version\.$/,
      'Común a los vehículos con {1}: sospeche un error en la nueva versión. Pause el despliegue y compare con la versión anterior.'],
    // remote action results and errors
    [/^\(sim\) restarted (.+)$/, '(sim) se reinició {1}'],
    [/^\(sim\) journal vacuumed to (.+)$/, '(sim) registro reducido a {1}'],
    [/^\(sim\) restored (.+)$/, '(sim) se restauró {1}'],
    [/^\(sim\) ran (.+)$/, '(sim) se ejecutó {t1}'],
    [/^command expired (\d+)s ago$/, 'el comando venció hace {1} s'],
    [/^unit not allow-listed: (.+)$/, 'unidad no autorizada: {1}'],
    [/^unknown action (.+)$/, 'acción desconocida: {1}'],
    // work order lines
    [/^WORK ORDER: (.+) at (.+)$/, 'ORDEN DE TRABAJO: {1} en {t2}'],
    [/^Created (\S+ \S+) · software (.+)$/, 'Creada {1} · software {2}'],
    [/^Created (\S+ \S+)$/, 'Creada {1}'],
    [/^Priority: (.+)$/, 'Prioridad: {t1}'],
    [/^(\d+)\. (.+)  \((.+)\)$/, '{1}. {t2}  ({t3})'],
    [/^- (\S+ \S+) (.+) by (.+): (\S+), problem came back$/, '- {1} {t2} por {3}: {t4}, el problema volvió'],
    [/^- (\S+ \S+) (.+) by (.+): (\S+) \((.+)\)$/, '- {1} {t2} por {3}: {t4} ({t5})'],
    [/^- (.+)$/, '- {t1}'],
    // flight-log analysis
    [/^(\d+)s flight, (\d+) event\(s\), (\d+) critical$/, 'Vuelo de {1} s, {2} evento(s), {3} crítico(s)'],
    // lists of translatable parts
    [/^(.+), then (.+)$/, '{t1}, luego {t2}'],
    [/^([^,]+), (.+)$/, '{t1}, {t2}'],
  ];

  const LANGS = ['en', 'es'];
  let lang = 'en';
  try { lang = localStorage.getItem('fleetdebug.lang') || ''; } catch (e) {}
  if (!LANGS.includes(lang)) lang = (navigator.language || 'en').toLowerCase().startsWith('es') ? 'es' : 'en';

  function trOne(s) {
    if (lang === 'en' || s == null || s === '') return s;
    const str = String(s);
    if (Object.prototype.hasOwnProperty.call(EXACT, str)) return EXACT[str];
    for (const [re, tpl] of PATTERNS) {
      const m = str.match(re);
      if (m) return tpl.replace(/\{(t?)(\d)\}/g, (_, t, n) => t ? trOne(m[+n]) : m[+n]);
    }
    return str;
  }

  return {
    get lang() { return lang; },
    locale() { return lang === 'es' ? 'es' : 'en'; },
    set(l) {
      if (!LANGS.includes(l)) return;
      lang = l;
      try { localStorage.setItem('fleetdebug.lang', l); } catch (e) {}
      document.documentElement.lang = l;
    },
    // Translate engine text (multi-line text is translated line by line).
    tr(s) {
      if (lang === 'en' || s == null) return s;
      return String(s).split('\n').map(trOne).join('\n');
    },
    // Translate a UI template, then fill its {placeholders}.
    t(s, vars) {
      const out = lang === 'en' ? s : (EXACT[s] ?? s);
      return vars ? out.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m)) : out;
    },
    _exact: EXACT, _patterns: PATTERNS,
  };
})();
