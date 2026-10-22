# Hoja de ruta — Prospección Embutidos Artesanales

Lo que falta, en orden de dependencia. Cada punto dice **cómo se
verifica que está hecho** — no "quedó bien", sino algo comprobable.

Estado al 12 de octubre de 2026.

---

## Lo que cambió el orden: hay una restricción de materia prima

**Esto es lo más importante de esta lista y no es técnico.**

El 9 de octubre, hablando de proveedores, Apareció el dato lo que ningún
punto de esta hoja contemplaba: la fábrica **no puede tomar clientes
nuevos** porque enfrenta una restricción de materia prima. Los
proveedores limitan la compra y priorizan a los compradores grandes.

Eso invierte el valor de casi todo lo construido. El sistema encontró
3.349 negocios a los que venderles, y el cuello de botella está del
otro lado.

**La consecuencia directa:** mandar los 20 mensajes del ancla (punto
18) hoy sería **destructivo**, no neutral. Un prospecto al que se le
escribe y después no se le puede despachar no es un prospecto que
quedó pendiente: es uno quemado. Y son de un solo tiro.

Por eso el punto 18 se partió en dos, y el que se puede hacer hoy es
el que no gasta prospectos.

**Lo que esto NO significa:** que el proyecto haya sido en vano. La
lista no se vence, el app ya corre y la calidad del dato se puede
verificar sin escribirle a nadie. Lo que cambió es el orden.

---

## El giro del 5 y 6 de octubre

Esta lista se escribió para un sistema que redactaba mensajes de
WhatsApp. Ese ya no es el producto.

**Lo que se midió:** de 3.349 negocios candidatos en las siete
provincias, **955 tienen celular (29%)**. A los otros 2.394 no se les
puede mandar un WhatsApp: tienen fijo, no tienen número, o el número
está mal formado.

**Lo que cambió:** el sistema ahora tiene dos canales, y el dato decide
cuál:

```
¿tiene celular?
    sí  (955)   →  mensaje de WhatsApp, revisado por una persona
    no  (2.394) →  dirección y teléfono para llamar o visitar
```

**Quién lo usa:** ya no es el papá revisando una hoja de cálculo. Son
los repartidores, en su teléfono, decidiendo a qué negocio entrar.

El redactor y su validador no se descartaron: pasaron de ser el centro
del sistema a ser una de dos salidas, y corren sobre el 29% en vez del
100%.

---

## BLOQUE A — Estructura ✅ *completo*

| | | |
|---|---|---|
| 1 | Limpiar archivos obsoletos | ✅ |
| 2 | `AGENTS.md` | ✅ |
| 3 | `requirements.txt`, `.env.example`, `.gitignore` | ✅ |
| 4 | `ARQUITECTURA.md` | ✅ |
| 5 | `tests/test_reglas.py` | ✅ |
| 6 | `PROGRESO.md` | ✅ |
| 7 | `verificar_estructura.py` en verde | ✅ *(08/10)* |

**Punto 7, cerrado el 08/10.** Ya conoce `zonas.py`, `registro.py`,
`estilo.py`, `pantallas/` y `.streamlit/`. Se le agregaron tres chequeos
que salieron de errores reales:

- `secrets.toml` en `.gitignore` — tiene la clave del app
- toda pantalla está declarada en `app.py` — el día que `revisar.py`
  cayó en la carpeta de pantallas
- los JSON de datos **ya no deben estar ignorados**, porque el app
  hospedado los necesita; si vuelven a ignorarse, avisa

Lo único que sigue en rojo es `README.md`, que es el punto 20 y va
último a propósito.

---

## BLOQUE B — El agente

| | | |
|---|---|---|
| 8 | Sanitizar el prompt (salida) | ✅ *(03/10, lista blanca + 14 pruebas)* |
| 9 | Validador como tercer nodo | ✅ *(03/10, tope de 3)* |
| 11 | Regla escrita de elección de modelo | ✅ *(03/10)* |
| 25 | Inyección de prompt: lo que **entra** al modelo | ✅ *(14/10)* |
| 12 | Skill `actualizar-reglas` | ✅ *(03/10)* |

### 10. Que una corrida interrumpida no se vuelva a pagar ✅ *(22/10)*

*Este punto se llamaba "Checkpointer persistente". Se renombró al
hacerlo, porque estaba mal planteado.*

**Lo que decía:** `MemorySaver` vive en memoria, cambiar a
`SqliteSaver`.

**Lo que apareció al ir a hacerlo:** `construir()` termina en
`g.compile()`, sin checkpointer. **No había `MemorySaver`.** El punto
describía un problema que no existía en esa forma.

Y algo más importante. Se pueden perder dos cosas distintas:

| | cuánto cuesta |
|---|---|
| la invocación en curso | tres nodos, unos segundos |
| los negocios ya calificados | minutos y dinero |

Un checkpointer de LangGraph salva la primera. Es la herramienta
correcta cuando un grafo tarda mucho o espera a una persona; este no
hace ninguna de las dos. **La verificación que pedía este mismo punto
—matar el proceso y que retome donde iba— solo la cumple lo segundo**,
y eso es un problema de la tanda, no del grafo.

`reanudar.py`. Cada resultado se escribe apenas sale, a un `.parcial`
en JSONL. Al arrancar, los que ya están se saltan. Al terminar bien,
se borra.

Dos decisiones:

- **JSONL y no JSON.** Un JSON hay que reescribirlo entero cada vez, y
  morir a mitad de esa escritura pierde todo justo cuando más importa.
  Solo append: lo ya escrito no se vuelve a tocar.
- **La identidad es `place_id`.** Es exacto y lo pone Google; el
  nombre no, porque dos sucursales se llaman igual.

**Verificado** matando el proceso a mitad: 3 negocios quedaron en
disco, al reanudar procesó solo los 5 que faltaban. Sin esto habrían
sido 8 de nuevo. Más 18 pruebas.

**Costó:** 1 hora.

### 30. La tanda de WhatsApp sale repartida por todo el país ✅ *(22/10)*

**Se encontró el 14/10 y no se había anotado.**

`grafo.py whatsapp 20` ordena **los 955 del país entero** por puntaje y
se queda con los veinte primeros. No sabe de zonas. Entonces la tanda
sale con un Peri en Escazú, uno en Heredia y dos en Alajuela — y el
vendedor recibe una lista que no corresponde a ningún recorrido
posible.

**Es el mismo problema que los cinco Palís** (punto 23), en otra forma:
el puntaje ordena por lo que él cree importante y se come una dimensión
que sí le importa a quien trabaja. Allá era la marca; acá la geografía.

**Arreglo:** un argumento más.

```
python grafo.py whatsapp 20 Alajuela
```

Mejor en `grafo.py` que en la pantalla: si se filtra solo al mostrar,
igual se gastaron llamadas al modelo redactando mensajes para negocios
de siete provincias que nadie va a visitar juntos.

**Hecho el 22/10.** `python grafo.py whatsapp 20 Alajuela`.

Tres detalles que no estaban en el plan y aparecieron al hacerlo:

- **`alajuela` y `san jose` también funcionan.** `de_provincia`
  compara exacto, así que sin resolver el nombre el comando habría
  devuelto cero y no habría dicho por qué. Un filtro que falla en
  silencio es peor que uno que no existe, porque parece que funcionó.
- **Si la provincia no está en los datos, dice cuáles hay.** No basta
  con que exista en Costa Rica.
- **Se mira qué *es* cada argumento, no en qué posición vino.** Un
  número es el tope, lo demás es la provincia; da igual
  `whatsapp 20 Alajuela` que `whatsapp Alajuela 20`.

Y la bitácora guarda de qué provincia fue cada corrida: sin eso, una
tanda nacional y una de Alajuela no son comparables.

**Verificado:** 12 pruebas. La tanda sale toda de la provincia pedida,
el tope se aplica *después* del filtro (al revés se comería la
provincia), y sin argumento se comporta como antes.
**Costó:** 30 minutos.

### 28. Renombrar `rutas.py` a `zonas.py` ✅ *(19/10)*

**El error más repetido del proyecto: nueve veces.**

`zonas.py` es la lógica y `pantallas/Rutas.py` es la pantalla. Se
llaman igual salvo por una mayúscula, Windows no las distingue, y VS
Code muestra solo "Rutas.py" en la pestaña — así que al pegar no se ve
en cuál se está pegando.

El 19/10 quedaron intercambiados y el app estuvo roto seis días con un
spinner congelado, sin error y con el log limpio.

Se podía seguir teniendo cuidado, o quitar la ambigüedad. Se quitó.

**Lo que se tocó:** el `import` de las dos pantallas, `tests/test_rutas.py`
(que pasó a `test_zonas.py`), `verificar_estructura.py` y los candados de
`tests/test_reglas.py`.

**La pantalla conserva el nombre `Rutas.py`**, porque "Rutas" es lo que
lee el rutero en el menú. El nombre del archivo y el de la pantalla son
cosas distintas.

**Verificado:** 243 passed, `verificar_estructura.py` en verde, y
`grep -rn "\brutas\b" --include="*.py"` solo devuelve texto de los
prompts sobre reparto, que es correcto.

### 29. Sincronizar los archivos ⬜ *(nuevo, 19/10)*

Al comparar huellas el 19/10 apareció que **de trece archivos, solo
`prospecto.py` coincidía con la copia de referencia.** El resto es una
mezcla de versiones de distintos días, de semanas pegando contenido a
mano.

Se arregló el que rompía; los otros once siguen sin verificar.

**Verificación:** las trece huellas coinciden.
**Esfuerzo:** 15 minutos, reemplazando archivos enteros.

### 25. Inyección de prompt ✅ *(14/10)*

El punto 8 resolvió lo que **sale** hacia el modelo. Este era lo que
**entra**.

`_describir()` metía el nombre del negocio directo en el prompt, y ese
nombre viene de Google Places — o sea, lo escribió un tercero. Un
nombre con un salto de línea adentro agregaba una línea al bloque de
datos, y una línea que empieza sola se lee como instrucción.

**Lo que se hizo**, en dos capas:

| | qué | cuál cierra |
|---|---|---|
| `como_dato()` en `reglas.py` | deja cada valor en **una línea**: aplasta saltos, tabuladores y caracteres de control, y corta a 120 | **esta** |
| delimitadores + aviso en el prompt | marca el bloque y le dice al modelo que eso son datos, nunca órdenes | respaldo |

La segunda sola sería una súplica. La primera le quita la **capacidad**
de romper la estructura, que no es lo mismo que adivinar la intención.
No filtra palabras: una lista negra siempre se esquiva.

Vive en `reglas.py` porque el nombre entra al pipeline **dos veces** —
al redactar (`grafo.py`) y al revisar (`validar_claude.py`). Cerrar una
mitad no cerraba nada.

**Verificación:** `tests/test_inyeccion.py`, 14 pruebas. La que importa
compara el bloque con un nombre normal y con uno hostil: tiene que
tener el mismo número de líneas.

**Lo que NO cubre, dicho a propósito:** no llama al modelo. Si mañana
obedeciera una frase inyectada *en una sola línea*, eso no lo atrapa
ningún test — lo atrapan el validador y la persona que lee antes de
mandar.

---

## BLOQUE C — Evaluación

| | | |
|---|---|---|
| 13 | Casos de calibración en su archivo | ✅ *(ahora son 8)* |

### 14. Ampliar el conjunto de evaluación ✅ *(22/10, de 8 a 19)*

Cada vez que el redactor invente algo, ese mensaje entra **antes** de
arreglar el prompt. El caso 8 salió así el 05/10: el redactor escribió
"salchicha criolla" y dos frases después "salchichón criollo". El
validador lo aprobó; lo encontró una persona leyendo. Se agregó el
caso, dio 7 de 8, se agregó la regla, dio 8 de 8.

**Por eso los casos nuevos no son defectos inventados.** Inventar doce
habría traicionado justamente eso. Lo que se hizo fue medir qué reglas
**ya existían sin un caso que las cubriera**:

| regla | existía desde | tenía caso |
|---|---|---|
| `registro sanitario` | antes | no |
| `certificad` | antes | no |
| `MAX_PALABRAS = 80` | antes | no |
| más de una pregunta | antes | no |
| inyección en el nombre | 14/10 (punto 25) | no, solo pruebas unitarias |

La última importa: el punto 25 tenía 14 pruebas unitarias y **ningún
caso de calibración**, o sea nada que verificara que el validador
entero resiste con el modelo adentro. Ese caso viola una regla de capa
2 a propósito —promete capacidad— porque si violara una de capa 1, el
código lo atraparía sin que el modelo opine y no probaría nada.

**Y un problema de método que estos casos arreglan.** El banco tenía
**6 DEBE FALLAR contra 2 DEBE PASAR**: un validador que dijera REVISAR
a todo sacaba 6 de 8, 75%, sin leer nada. Los casos que deben PASAR
son los únicos que detectan un validador demasiado estricto, que es la
forma de romperlo que no se ve.

### Lo que pasó al correrlo: 15 de 17

Los dos que no coincidieron eran **casos nuevos mal escritos**, y en
los dos el validador tenía razón:

| caso escrito como DEBE PASAR | lo que vio Jev |
|---|---|
| *"Estamos buscando abrir en Grecia"* | `afirma_logistica 0.60` |
| *"Trabajamos al por mayor con supermercados"* | `menciona_clientes 0.68` |

El primero quería probar que **nombrar** un cantón no es afirmar
logística, y la frase elegida sí lo es: anuncia distribución en una
zona donde la fábrica reparte por terceros.

El segundo es el más fino de todo el banco. El contexto dice que la
fábrica **busca vender** al por mayor a supermercados; el mensaje dice
**trabajamos con** supermercados, en presente, lo que implica que ya
los tiene. Aspiración contra hecho consumado, y la diferencia es un
verbo.

**Los dos mensajes se quedaron, del lado correcto.** Son inventos
sutiles reales —ninguna persona los marcaría leyendo rápido— y ahora
son `DEBE FALLAR`. Se escribieron dos `DEBE PASAR` nuevos en su lugar.

Quedan **19 casos: 13 fallar, 6 pasar.** Un validador perezoso saca
68%.

Vale anotar de dónde salieron esos dos: **el validador atrapó dos
errores cometidos por quien estaba escribiendo los casos a propósito,
sabiendo exactamente qué probaba.** Es la mejor evidencia que tiene el
proyecto de que la capa 2 hace un trabajo que una persona leyendo no
hace.

**Verificación:** los 19 se comprueban contra la capa 1, que es
determinista: cada uno dispara exactamente la regla que le toca, y los
6 que deben pasar no disparan ninguna. La capa 2 necesita el modelo:
`python validar.py prueba`.

**Sigue siendo continuo:** 10 minutos por caso, cada vez que aparezca
un defecto nuevo.

### 15. Métrica de tasa de fallo ✅ *(20/10)*

`bitacora.py`. Una línea por corrida a `bitacora.jsonl`, solo append:
cuántos negocios, cuántos con mensaje, cuántos validados, cuántos
reescritos, cuántos agotaron los 3 intentos, y los problemas ordenados
de más a menos frecuente. `python bitacora.py` imprime el historial.

Tres decisiones, cada una por una razón:

**La cuenta es una sola.** `medir()` es la única definición de
"reescrito" y "agotado" en el proyecto; `resumen()` en `grafo.py` dejó
de contar aparte y ahora imprime desde ese mismo dict. Si vivieran en
dos lados, en tres meses no coincidirían y no habría forma de saber
cuál de las dos miente. Lo cuida una prueba que falla si `resumen()`
vuelve a definir "reescrito" por su cuenta.

**No se guarda ni un nombre de negocio.** Solo conteos y etiquetas de
problema, que las escribió este proyecto. Un nombre ahí convertiría la
bitácora en dato de terceros y le cambiaría el lugar donde puede
vivir; así se puede leer, pegar o subir sin pensarlo. Tres pruebas lo
verifican, en vez de confiar en la memoria de nadie.

**Escribir nunca rompe una corrida.** Una corrida de `grafo.py` cuesta
dinero; perderla porque el disco estaba lleno sería absurdo.
`anotar()` se come cualquier error y devuelve `False`.

`validar.py prueba` también anota. Eso importa más de lo que parece:
cuesta centavos y se puede correr hoy, con el pipeline en pausa. Es la
única medición del proyecto que empieza a tener historia desde ya.

**Verificación:** `python bitacora.py` imprime el historial; 19
pruebas en `tests/test_bitacora.py` (262 en total).
**Costó:** 1 hora.

### 16. Observabilidad ✅ *(21–22/10)*

Langfuse Cloud (US) con `mascara.py`, más la métrica propia del punto
15. Las dos piezas contestan preguntas distintas: la bitácora, "¿subió
o bajó la tasa de reescritura?"; Langfuse, "¿por qué **este** mensaje
salió mal?".

**La decisión de dónde no fue "la nube es más fácil".** Las trazas
llevan los prompts completos. Autohospedado era lo correcto, y se
descartó por una razón medible: Langfuse pide 16 GiB, la máquina tiene
5,9 disponibles, y la versión ligera (v2) está sin soporte desde Q1
2025. Un VPS propio a ~15 USD/mes sigue siendo la opción si algún día
molesta depender de un tercero.

**Lo que hizo falta para poder usar la nube** es lo que vale contar.
Antes de escribir la máscara se midió con `sonda_langfuse.py`: una
corrida de un negocio inventado con centinelas, usando el propio hook
de enmascarado como microscopio. Resultado:

- 22 atributos por span; **solo dos llevan identidad** (`input` y
  `output`). Los otros 20 son metadata del grafo y son la
  observabilidad que se quería.
- Los seis nombres de span son genéricos, así que no hace falta
  tocarlos — y menos mal, porque el hook no puede.
- **Los spans de nodo no trazan el prompt, trazan el estado.** El
  estado lleva `negocio` entero: teléfono y dirección incluidos,
  aunque `CAMPOS_PROHIBIDOS` los mantenga fuera del modelo.

Eso último es el punto. Conectar Langfuse siguiendo cualquier tutorial
habría mandado los teléfonos de 3.485 negocios a la nube, sin un solo
error en pantalla. El punto 8 protege lo que ve el modelo; no protege
lo que ve el tracing, porque son dos caminos distintos.

Segunda trampa, también medida: de los dos hooks de enmascarado de
Langfuse, el que sale en los ejemplos (`mask`) no mira los atributos de
instrumentación de terceros, que es por donde llegan los spans de
LangGraph. El que sirve es `mask_otel_spans`.

**Verificación**, en tres niveles que prueban cosas distintas:

| | qué prueba |
|---|---|
| 17 pruebas de `mascara.py` | la lógica, contra los 3.485 nombres y teléfonos reales |
| `python sonda_langfuse.py mascara` | que la máscara devuelve los parches correctos |
| el panel de Langfuse | que Langfuse **los aplica** (`neg_c594`, no `SONDANOMBRE01`) |

**Costó:** un día, casi todo en medir antes de escribir.
**Lo que no cubre:** una paráfrasis del cantón. Está escrito en
`mascara.py` en vez de quedar implícito.

### 17. Prueba de arranque en frío ⬜

Una sesión nueva lee el repo y responde: qué hace, cómo se corre, qué
falta. **Quien evalúa no puede haber participado en la construcción.**

**Verificación:** la respuesta coincide con la realidad en los tres
puntos.
**Esfuerzo:** 20 minutos.

---

## BLOQUE D — El producto *(nuevo, 05-06/10)*

### 21. Las tres páginas ✅

| página | para qué |
|---|---|
| `app.py` | entrada: clave, estilo y menú *(no es una pantalla)* |
| `pantallas/Rutas.py` | prospectos por zona, para visitar |
| `pantallas/Mensajes.py` | los 955 con celular, con enlace `wa.me` |

`app.py` era una pantalla de registro que duplicaba a Mensajes haciendo
menos. quien desarrolla lo señaló. Ahora es portada: tres cifras, a dónde ir, y el
botón de recargar datos que faltaba desde que se quitó el menú de
Streamlit.

### 22. Diseño para teléfono ✅

`.streamlit/config.toml` y `estilo.py`. Fondo blanco por el sol, amarillo
señal en las acciones, una sola familia tipográfica, el nombre del
negocio como único elemento grande.

**Nota:** `estilo.py` es la parte frágil. Streamlit cambia sus clases
internas entre versiones.

### 23. El puntaje premia cadenas ✅ *(07/10)*

Descubierto el 06/10 al correr sobre las siete provincias: los 20
primeros salieron todos cadenas, porque el puntaje suma por reseñas y
rating y en un dataset nacional eso **ordena por tamaño**.

Se señaló el otro lado del mismo problema, que era peor: en la
pantalla de rutas aparecían cinco Palís seguidos en un cantón.

**Lo que se hizo:** `MARCAS` agrupa las cadenas por marca, `marca()`
dice de cuál es cada negocio y `una_por_marca()` deja una sucursal.
La pantalla muestra una por cadena (con aviso y checkbox para ver
todas), `grafo.py whatsapp` manda solo independientes, y
`grafo.py cadenas` las manda aparte y marcadas.

De paso aparecieron un patrón muerto (`"ampm"` no coincidía con
`AM PM`) y seis cadenas que faltaban en la lista.

**Sigue siendo un parche, no el arreglo.** El arreglo es el punto 19.

### 24. Hospedaje ✅ *(08–12/10)*

El app corre en **Streamlit Community Cloud**, desde un repo privado de
GitHub, con clave. Un rutero lo abre desde el teléfono.

| pieza | archivo |
|---|---|
| clave de acceso | `acceso.py` |
| arranque común de las tres pantallas | `inicio.py` |
| respuestas en la hoja de Google | `almacen_sheets.py` |
| el procedimiento completo | `DESPLIEGUE.md` |

**Lo que obligó a construir el almacén:** en Streamlit Cloud el disco
es efímero. `respuestas.json` — el único archivo del proyecto que no se
puede regenerar — se habría borrado en cada reinicio, sin aviso.
`registro.py` ahora tiene un backend intercambiable: local escribe
archivo, hospedado escribe la hoja, y el resto del código no se entera.

**Lo que se pagó, con los ojos abiertos:** los JSON de negocios ahora
viven en GitHub y en los servidores de Streamlit. El repo **tiene que
seguir siendo privado** — si alguna vez se hace público, hay que
descomentar las tres líneas de datos en `.gitignore` *antes*, y sacar
`CLIENTES_ACTUALES` del código: publicar la lista de clientes del papá
es decirle a la competencia exactamente a quién visitar.

**Verificación:** ✅ hecho — se abrió desde el teléfono, se marcó un
negocio, y la fila apareció en la pestaña `Respuestas` de la hoja.

**Falta de operación, no de código:**

- [x] ~~cambiar la clave~~ — 12/10
- [x] ~~borrar las dos filas de prueba de la hoja~~ — 12/10

---

## BLOQUE E — Anclar a la realidad

*Sin esto, todo lo anterior es una hipótesis bien construida.*

El punto 18 se partió el 09/10, cuando apareció la restricción de
materia prima. Son dos anclas con costos muy distintos.

### 18a. Que un rutero use la lista una semana ⬜ **← el ancla de hoy**

Un rutero abre el app en su zona y verifica, negocio por negocio:
¿existe?, ¿es del tipo que dice?, ¿la dirección sirve?, ¿el teléfono
es de ese negocio?

**No le vende a nadie.** Verifica el dato.

**Por qué este sí se puede hacer hoy:** no gasta prospectos. Nadie
recibe una oferta que la fábrica no podría despachar. Y mide lo que
nunca se midió: si los 3.349 registros de Google describen la realidad.

**Qué respondería:** si el 80% está bien, la lista sirve y el problema
es solo de abastecimiento. Si el 40% está mal, hay trabajo de datos
antes que de ventas — y eso es mejor saberlo ahora que cuando haya
carne.

**Verificación:** 20 filas en la hoja con `notas` escritas por una
persona que estuvo ahí.
**Esfuerzo:** una semana de un rutero, cero horas de código.

### 18b. Las primeras 20 de WhatsApp ⬜ **← en pausa a propósito**

De 20 mensajes, cuántos contestan.

**En pausa hasta que haya materia prima.** No por falta de tiempo ni
de herramientas: los mensajes se generan con un comando. Es que un
prospecto contactado y no atendido se quema, y la lista existe
precisamente porque esos negocios son finitos.

**Cuándo se destraba:** cuando el papá pueda comprometer volumen.
Ahí se corre `python grafo.py whatsapp 20` y se empieza.

**Verificación:** 20 filas con estado real y `enviado` con fecha.
**Esfuerzo:** una tarde + una semana de espera.

### 19. Recalibrar los pesos ⬜

Con respuestas reales se puede ver qué comparten los que contestaron.
Hoy el puntaje premia reseñas y rating porque pareció razonable, no
porque se haya medido.

El punto 23 es un parche sobre este problema; el 19 es el arreglo.

**Verificación:** los pesos nuevos tienen justificación escrita en
`AGENTS.md` con su origen.
**Esfuerzo:** 2 horas, después de tener respuestas.

### 20. README.md ✅ *(19/10)*

Fue al final a propósito: un README que promete cosas que el repo no
hace es peor que no tener README. Se escribió cuando ya no había nada
que prometer de más.

Dice en voz alta lo que no está validado —que nadie ha contestado— y
por qué sigue así: la fábrica no puede tomar clientes nuevos.

**Verificación:** alguien de afuera lo lee y entiende en un minuto.
**Esfuerzo:** 1 hora.

---

## BLOQUE F — El problema de verdad *(nuevo, 09/10)*

El cuello de botella no es encontrar clientes. Es conseguir carne.

### 26. La lista de PROVEEDORES ⬜

Hoy el modelo de datos tiene `es_cliente` (le compra a la fábrica) y
`posible_competidor` (fabrica lo suyo). **No existe "los que le venden
a la fábrica".**

Apareció el 07/10: Carnicería un proveedor regional tiene 4 sucursales en la
lista de prospectos, y un proveedor regional es una procesadora cárnica.
Mandarle un mensaje en frío a un proveedor ofreciéndole salchichón no
rompe nada técnicamente, pero es un error comercial.

**Pendiente de preguntarle al papá:** si un proveedor regional hace embutidos va
a `SENALES_COMPETIDOR`; si solo vende carne, hace falta `PROVEEDORES`,
que saca del pipeline. Lo mismo con otro proveedor.

**Verificación:** los proveedores conocidos no aparecen en la pantalla
de Mensajes, y hay una prueba que lo fija.
**Esfuerzo:** 1 hora, después de la conversación.

### 27. El vigilante de abastecimiento ⬜ *(la pieza agéntica de verdad)*

El único problema del proyecto que **sí** justifica un agente.

La pregunta de negocio no es "¿a quién le vendo?" sino **"¿cuándo
conviene negociar volumen?"**. La oferta del insumo principal, los precios y las
exportaciones se mueven, y los proveedores aprietan o aflojan con
ellos. Hoy nadie mira eso: se pide carne y se recibe lo que haya.

Por qué es un agente y no un script: la información está dispersa
(CORFOGA, SENASA, PROCOMER, prensa), cambia de formato, y lo que
importa no es el número sino el **cambio** respecto a lo normal. Eso
es vigilancia continua con juicio, no una consulta.

Es también lo mejor que podría enseñar en una entrevista: un agente
que resuelve una restricción real de un negocio real.

**Y cierra el único hueco que le queda al proyecto.** Lo construido
hasta hoy es un *pipeline* con pasos de modelo: clasificar → redactar
→ validar → reescribir. El flujo lo decide el código, y eso está bien
— la regla del proyecto es que lo que se puede escribir como regla va
como regla. Pero significa que no hay **uso de herramientas** ni
**planificación**: el modelo nunca decide qué hacer después.

El vigilante sí las necesita: buscar en fuentes que cambian, comparar
contra una línea base, decidir si lo que ve es anomalía y cuándo vale
la pena avisar. Herramientas, estado y decisión — las tres que faltan.

Dicho de frente, porque en una entrevista lo van a preguntar: **lo
construido no es agéntico, y es una decisión, no un descuido.** El
único problema del negocio que sí lo justifica es este, y está
identificado desde el 09/10.

**Lo que hace falta primero:** un registro de compras — cuánto se
compró, a quién, a qué precio, cuándo. Sin línea base no hay anomalía
que detectar. Eso hoy no existe.

**Verificación:** una alerta escrita que un humano confirme como útil
antes de automatizar nada.
**Esfuerzo:** 2 días de código, más la línea base.

---

## Resumen

| bloque | pendiente | esfuerzo |
|---|---|---|
| A — Estructura | — | ✅ |
| B — El agente | — | ✅ |
| G — Higiene del repo | — | ✅ |
| C — Evaluación | solo el 17 | 20 min |
| D — El producto | — | ✅ |
| E — Anclaje | 18a, 19 | ~2 h + una semana |
| F — Abastecimiento | 26, 27 | ~2 días + conversación |

**El código está terminado.** Lo que queda en la lista no se escribe:
se camina, se pregunta y se mide con respuestas reales.

### El orden que yo seguiría

```
17  arranque en frio           20 min  lo hace un chat nuevo    ← AHORA
18a el rutero verifica la lista   0 h     no quema prospectos
26  preguntar por los proveedores 1 h     bloquea cualquier envío
19  recalibrar con respuestas           después del 18a
27  el vigilante de abastecimiento        el problema real
```

El 23 se cerró el 07/10, el 24 el 12/10, el 20 el 19/10, el 15 el
20/10, y el 16, el 30, el 10 y el 14 el 22/10. **Ya no queda código
por escribir**: lo que viene es verificar que lo construido describe
la realidad, y mirar el lado del que no se había ocupado nadie.

El 17 va primero a propósito y **no lo puede hacer este chat**: quien
evalúa no puede haber participado en la construcción. Es el único
punto de la lista cuyo valor depende de quién lo corre.

---

## Lo que NO está en esta lista, a propósito

- **Automatizar el envío** — riesgo de bloqueo del número de WhatsApp.
  El botón `wa.me` abre el mensaje escrito; la persona lo manda.
- **App nativa** — no da nada que no dé una web instalada, y cuesta
  meses. Lo único que daría es funcionar sin señal, y para eso está el
  botón de bajar la lista en CSV.
- **RAG** — no hay corpus que consultar.
- **Agente investigador de prospectos** — se evaluó el 05/10 y se
  descartó con una prueba: las reseñas de un cliente conocido no
  mencionan embutidos. Si la fuente no deja rastro donde la respuesta
  se sabe, no sirve donde no se sabe.
- **Agente buscador de proveedores** — distinto del punto 27. El
  universo son 15 a 30 plantas en todo el país: eso es una lista, no un
  problema de agente. Lo que sí es agente es **vigilar** el mercado, y
  eso es el 27.
- **Base de datos** — las respuestas caben en una hoja de Google que el
  papá puede abrir desde el teléfono. A 20–200 filas, una base sería
  sobreingeniería. El razonamiento completo está en `almacen_sheets.py`.
- **Gateway propio** — no aporta a esta escala.
