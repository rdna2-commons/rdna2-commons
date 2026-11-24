# El plan, sin jerga

[English](../../plan-explained.md)

**El problema.** Un juego de consola es un programa escrito para el procesador, el chip gráfico y el sistema de
la consola. El procesador de una Xbox Series es del mismo tipo que el de un PC, así que la mayor parte del
programa podría ejecutarse tal cual. Lo impiden dos cosas: los pequeños programas que dibujan la imagen (shaders)
están escritos para el chip AMD de la consola, y las funciones del sistema que el juego usa (memoria, archivos,
sonido, mandos) no existen en Windows. Cada proyecto de compatibilidad tiene que traducir ambas cosas, y cada uno
lo hace por su cuenta.

**Lo que hacemos.** Escribimos como pruebas qué hace exactamente la consola: «esta instrucción con estas
entradas da estas salidas». Varias personas las ejecutan en hardware real, y un resultado solo cuenta cuando
coinciden. Así cualquier proyecto puede pasar las pruebas por su traductor y ver, línea a línea, en qué falla.

**Las fases**

0. **Base**: las reglas, el bot que revisa cada contribución, la documentación. Termina cuando alguien nuevo,
   persona o IA, puede tomar una tarea y lograr que se acepte sin ayuda.
1. **Conocimiento compartido**: las pruebas en sí, área por área: instrucciones gráficas, memoria, sonido,
   almacenamiento, mandos. Termina cuando cada prueba tiene un resultado confirmado por dos personas.
2. **Adaptadores**: conectores que ejecutan los traductores de otros proyectos con nuestras pruebas, y una tabla
   pública de quién pasa qué.
3. **Correcciones en otros proyectos**: cuando la tabla muestra un fallo en otro proyecto, le ofrecemos la corrección.
4. **Componentes compartidos**: piezas que varios proyectos necesitan y nadie tiene, hechas aquí como bibliotecas.

Desde la fase 1 todo avanza en paralelo: cada tarea solo espera a aquellas de las que depende.

**Lo que nunca hacemos:** compartir nada de ningún juego (archivos, código, imágenes, sonidos), romper
protecciones ni enlazar filtraciones. Todo lo que probamos está escrito a mano para la prueba.

**Cómo seguirlo:** la [página de progreso](https://github.com/scarlett-commons/scarlett-commons/blob/status/PROGRESS.md)
se actualiza sola cada seis horas. Cada tarea es una issue en GitHub; cualquiera puede tomarla.
