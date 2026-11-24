# Hoja de ruta

[English](../../../ROADMAP.md) · Traducción de cortesía; vale el original en inglés. Progreso en la
[página de progreso](https://github.com/scarlett-commons/scarlett-commons/blob/status/PROGRESS.md).

**Objetivo:** hacer correctas y verificadas, una sola vez y para todos los proyectos de compatibilidad, las partes
difíciles y comunes de ejecutar software de Xbox Series X|S en PC, en lugar de quince veces. Producimos
conocimiento, pruebas y componentes verificados; los demás proyectos los usan.

**Nunca:** datos de juegos, claves, descifrado, enlaces a filtraciones, código con licencias incompatibles.

## Fase 0: Base (ahora)

La maquinaria que permite unirse sin que nadie te guíe: el bot (reglas, reclamos, plazos, tareas de rescate,
`/split`, revisión a ciegas, fusión automática, modo de prueba), documentación y traducciones, página de progreso
generada, espejo en un segundo alojamiento y propuestas automáticas de mantenedores.
**Lista cuando:** un agente nuevo puede leer AGENTS.md, tomar una tarea y lograr que su PR se fusione sin más
ayuda humana que la de sus revisores.

## Fase 1: Conocimiento compartido

Una biblioteca de pruebas que define el comportamiento correcto, verificada en hardware real: shaders (VALU
f16/f32/f64: redondeo, desnormales, FMA; SALU; LDS; wave64 y operaciones entre carriles; imágenes y samplers;
direccionamiento de búferes), resultados de referencia en hardware, especificaciones de las API del sistema
(memoria, hilos, archivos, tiempo), diferencias de la API gráfica, audio, almacenamiento y entrada.
**Lista cuando:** cada caso tiene un resultado esperado confirmado por dos informes independientes.

## Fase 2: Adaptadores y tabla de compatibilidad

Un ejecutor por tipo de traductor (SPIR-V/Vulkan, DXIL/D3D12, HLSL); el traductor de cada proyecto se conecta
como programa aparte, sin mezclar código. Una tabla pública: qué proyecto pasa qué casos. También Linux y macOS
(MoltenVK).
**Lista cuando:** al menos tres traductores externos están en la tabla.

## Fase 3: Correcciones en otros proyectos

Cada fallo que la tabla muestra en otro proyecto se convierte en una corrección pequeña y probada que se le
ofrece (primero una issue `outreach` aquí; decide un mantenedor).

## Fase 4: Componentes compartidos

Lo que varios proyectos necesitan y nadie tiene con licencia compatible se construye aquí como biblioteca con sus
pruebas (por ejemplo, un intérprete de referencia de RDNA2 para cuando no hay hardware).

Todas las fases tras la 0 avanzan en paralelo: cada tarea solo espera a aquellas de las que depende.
