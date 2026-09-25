# CONTEXTO
Ya implementamos la Fase 0–5 del dashboard de LeanCore (servicio que consume eventos de cola + tablero agregado). Ahora quiero un CAMBIO INCREMENTAL sobre ese mismo proyecto, no un proyecto nuevo. Usa OpenSpec para crear un **change nuevo** (propuesta + delta) sobre la capability existente del dashboard/API de métricas — no reescribas la spec original, extiéndela.

# OBJETIVO DEL CAMBIO
Dos mejoras al dashboard:

1. **Selector de ventana de tiempo:** un control en el dashboard que me permita elegir cuántos minutos hacia atrás quiero ver (p. ej. 5, 15, 30, 60 minutos, o un input numérico libre). Al cambiarlo, se debe volver a consultar el endpoint existente (`/metrics/payments?minutes=N`) con el valor elegido y refrescar la vista, sin recargar la página completa.
2. **Dos formas de visualizar el mismo dato:**
   - **Vista serie de tiempo** (la actual): conteo por minuto, procesados vs. fallidos.
   - **Vista agregada (nueva):** dos "cards" estilo Datadog que muestren el TOTAL agregado del período seleccionado — una en verde para pagos procesados/exitosos y otra en rojo para pagos fallidos (número grande, y opcionalmente el % de éxito/fallo).
   - Un toggle o tabs para cambiar entre "Serie de tiempo" y "Agregado", sin perder el minuto seleccionado.
3. Usar **Bootstrap** (vía CDN, sin bundler) para el layout, los cards y el selector, manteniendo el HTML simple como hasta ahora (no se pide SPA ni framework JS nuevo).

# REGLAS DE TRABAJO (las mismas de siempre)
1. Metodología OpenSpec: primero propuesta + delta de spec + tareas, y espera mi aprobación antes de tocar código. Al final, archiva el change.
2. Tú propones, yo decido. Si hay más de una forma razonable de resolver algo (ver "Decisiones a proponerme" abajo), preséntame opciones con pros/contras y una recomendación, y espera mi elección.
3. Registra las decisiones nuevas como ADRs cortos en `docs/decisiones/`, siguiendo la numeración que ya exista.
4. No rompas lo que ya funciona: los tests existentes deben seguir pasando; si cambias el contrato del endpoint, hazlo de forma retrocompatible o documenta el breaking change explícitamente.
5. Alcance acotado: esto es una extensión de UI + un ajuste menor de API si hace falta, no un rediseño del backend de agregación. No toques el mecanismo de dedupe/consistencia salvo que sea estrictamente necesario para soportar la ventana variable.
6. Español en documentación/specs/ADRs, inglés en código y commits.

# DECISIONES A PROPONERME (preséntalas antes de implementar)
1. **Origen del total agregado:** ¿se calcula sumando los buckets por minuto que ya devuelve el endpoint (cálculo en el cliente/JS), o se agrega en el backend y el endpoint expone un modo `?view=aggregate` adicional? Dame pros/contras (carga en cliente vs. cambio de contrato de API, reutilización del mismo endpoint, facilidad de testear).
2. **Mecanismo de refresco:** al cambiar el selector de minutos, ¿fetch bajo demanda (solo cuando cambia el valor) o hay que mantener el polling periódico existente y solo cambiar el parámetro `minutes`? Aclara qué pasa si el usuario cambia el selector mientras hay un fetch en curso (evitar condiciones de carrera / respuestas fuera de orden).
3. **Rango del selector:** valores fijos predefinidos vs. input libre con validación (mínimo/máximo razonable, p. ej. 1–1440 minutos) — recomienda uno y justifica.
4. **Cómo mantener sincronizado el estado** entre las dos vistas (serie de tiempo / agregado) y el selector: manejarlo en JS plano (como ya está) o justificar si se necesita algo más. No introduzcas un framework nuevo sin que yo lo apruebe.

# CRITERIOS DE ACEPTACIÓN
- El selector cambia la ventana consultada y ambas vistas (serie y agregado) reflejan esa ventana.
- Las cards de agregado muestran claramente: total procesados (verde), total fallidos (rojo), y quedan legibles en mobile (Bootstrap responsive, grid de 2 columnas que colapsa a 1).
- Cambiar de vista no dispara una petición redundante si el dato ya se tiene para esa ventana (evalúa cachear la última respuesta en el cliente).
- Tests (o al menos un test manual documentado en el README) que cubran: cambio de minutos refresca los datos correctos, y los totales agregados coinciden con la suma de los buckets de la serie de tiempo para el mismo período.
- README actualizado: cómo usar el selector y las dos vistas, capturas o descripción breve, y sección "Decisiones y trade-offs" ampliada con esta iteración.

# FASES (detente al final de cada una y espera mi OK)
- **Fase A – Propuesta OpenSpec:** problema, alcance, no-alcance, supuestos, y las 4 decisiones de arriba con opciones para que yo elija.
- **Fase B – Delta de spec + tareas:** una vez decidido, redacta el delta de la spec existente y desglosa tareas pequeñas.
- **Fase C – Implementación:** por tarea, con tests, sin tocar lo que no está en el alcance.
- **Fase D – Cierre:** verifica que todo corre con el mismo comando de siempre, actualiza README y ADRs, archiva el change en OpenSpec.

Empieza por la **Fase A**: dame la propuesta y las opciones de las decisiones, no implementes nada todavía.