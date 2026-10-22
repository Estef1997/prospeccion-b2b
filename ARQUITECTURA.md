# Arquitectura — Prospección Embutidos Artesanales

Documento de arquitectura del sistema, escrito en las capas estándar de
una plataforma GenAI empresarial.

**Para qué sirve:** abrirlo al lado del *Production-Ready Checklist* de
TransUnion y marcar dónde este sistema cumple y dónde no.

Actualizado: 2026-10-12.

---

## El giro del 5 y 6 de octubre

El sistema se construyó para redactar mensajes de WhatsApp. Ese dejó de
ser el canal principal, y conviene entender por qué antes de leer las
capas.

**La medición:** de 3.349 negocios candidatos en las siete provincias,
955 tienen celular. Es el **29%**. Los otros 2.394 tienen fijo, no
tienen número, o el número está mal formado.

```
                negocios con teléfono, por tipo de línea
  celular (5,6,7,8)   ████████████                      29%
  fijo    (2,4)       ███████████████                   37%
  sin número          ██████████                        28%
  mal formado         ██                                 4%
```

A 7 de cada 10 no se les puede escribir. El canal alcanzaba a lo sumo a
un tercio del universo, y **nunca se midió si convierte**.

**La consecuencia:** el dato decide el canal, y lo decide el código —
`es_celular()` en `reglas.py` — no un modelo.

```
                       prospectos_crudo.json  (3.349)
                                 │
                    ┌────────────┴────────────┐
                    │                         │
            ¿tiene celular?            ¿no tiene celular?
                 955                        2.394
                    │                         │
                    ▼                         ▼
              grafo.py                  pantallas/Rutas.py
         calificador→redactor→validador   zona, puntaje,
                    │                      dirección, mapa
                    ▼                         │
        pantallas/Mensajes.py                 ▼
          enlace wa.me, lo manda         el rutero visita
            una persona
```

El redactor no se descartó. Pasó de correr sobre el 100% a correr sobre
el 29%, y de ser el centro del sistema a ser una de dos salidas.

---

## Diagrama del sistema

```
  Google Places API
         │
         ▼
  ┌─────────────────┐
  │  prospecto.py   │  CÓDIGO DETERMINISTA
  │  buscar         │  - 7 provincias, 84 cantones
  │  etiquetar      │  - dedup por place_id
  │  puntuar        │  - FUSIONA, no sobrescribe
  └────────┬────────┘
           │  prospectos_crudo.json   (3.349 candidatos)
           │
     ┌─────┴──────────────────────────┐
     │ es_celular()                   │
     │ el código decide el canal      │
     └─────┬──────────────────────┬───┘
           │ 955                  │ 2.394
           ▼                      │
  ┌──────────────────────────┐    │
  │        grafo.py          │    │
  │                          │    │
  │  calificador ──ruta()─┐  │    │
  │       │               │  │    │
  │       ▼               │  │    │
  │   redactor ◄──┐       │  │    │
  │       │       │ max 3 │  │    │
  │       ▼       │       │  │    │
  │   validador ──┘       │  │    │
  │   (reglas/Jev/Claude) │  │    │
  │       ▼               ▼  │    │
  │     (fin)          (fin) │    │
  └────────┬─────────────────┘    │
           │                      │
           ▼                      ▼
   ┌──────────────┐      ┌──────────────┐
   │  Mensajes    │      │   Rutas      │   EL PRODUCTO
   │ enlace wa.me │      │  zona, mapa  │   Streamlit Cloud,
   └──────┬───────┘      └──────┬───────┘   con clave
          │                     │
          └──────────┬──────────┘
                     ▼
              registro.py              una interfaz, dos destinos
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   respuestas.json      pestaña Respuestas     ← EL ANCLA
   (local)              (hospedado)
                              │
                              ▼
                        a_sheets.py        vista para el papá
```

**Lo que todavía no existe:** el ancla tiene dos filas, y las dos son de
prueba. Nadie ha enviado un mensaje real ni hecho una visita. Hasta que
tenga filas de verdad, el puntaje que ordena los 3.349 es una hipótesis
razonada, no una medición.

**Y desde el 09/10 se sabe por qué va a seguir vacío un rato:** la
fábrica enfrenta una restricción de materia prima, así que no puede
tomar clientes nuevos. Mandar mensajes hoy quemaría prospectos. Ver
"Anclas", al final.

---

## Evaluación por capa

### 1. Gateway / punto único de llamada

**Estado: no existe.**

Cada script llama a la API directamente con su propia clave desde `.env`.

Consecuencias:
- No hay atribución de costo por componente
- No hay límite de gasto más allá del saldo de la cuenta
- No hay registro centralizado de llamadas

Mitigación actual: la recarga automática está apagada a propósito, y la
clave de Places tiene cuota de 500 solicitudes/día. Es un freno de
presupuesto, no un gateway.

---

### 2. Enmascarado de datos / PII, y la frontera en sentido contrario

**Estado: implementado. Lo que sale el 03/10, lo que entra el 14/10.**

La frontera con el modelo tiene dos direcciones y se cerraron en
momentos distintos:

| dirección | qué protege | cuándo |
|---|---|---|
| **sale** | teléfono y dirección de terceros no viajan al proveedor | 03/10 |
| **entra** | el texto escrito por terceros no puede dar órdenes | 14/10 |

#### Lo que entra: inyección de prompt (14/10/2026)

El nombre de cada negocio lo escribió quien registró ese negocio en
Google. Para un modelo, instrucciones y datos llegan como el mismo
texto, así que un nombre con un salto de línea adentro convertía el
bloque de datos en una línea de más — y una línea que empieza sola se
lee como instrucción.

Dos capas, y solo una cierra:

```
como_dato()        cada valor queda en UNA linea      ← la que cierra
                   (saltos, tabuladores, controles,
                    U+202E, tope de 120)

>>> ... <<<        el bloque va delimitado y el         respaldo
+ aviso            prompt dice que eso son datos
```

Pedirle al modelo que ignore instrucciones es una súplica.
`como_dato()` le quita la **capacidad** de darlas.

No filtra palabras: una lista negra siempre se esquiva. El nombre
hostil pasa igual, pegado después de `Nombre: `, que es donde es
inofensivo.

Vive en `reglas.py` y no en `grafo.py` porque el nombre entra al
pipeline **dos veces**: al redactar y al revisar.

**Verificación:** `tests/test_inyeccion.py`, 14 pruebas. La central
compara el bloque con un nombre normal y con uno hostil y exige el
mismo número de líneas.

**Límite declarado:** ninguna prueba llama al modelo. Si obedeciera una
frase inyectada en una sola línea, eso lo atrapan el validador (capa 6)
y la persona que lee antes de mandar.

#### Lo que sale: enmascarado (03/10/2026)

Antes se enviaban al modelo, sin sanitizar, la dirección y el teléfono
de los negocios (629 entonces, 3.349 hoy). Son datos de terceros que no
dieron consentimiento.
Están publicados en Google Maps, así que no eran secretos — pero
mandarlos a un proveedor externo era una decisión que nadie había
tomado a propósito.

**Lista blanca, no lista negra.** `CAMPOS_CLASIFICADOR` y
`CAMPOS_REDACTOR` viven en `reglas.py`. `_describir()` no sabe escribir
un teléfono: no existe la línea. Si mañana `prospecto.py` agrega un
campo al JSON, no viaja solo — hay que escribirlo a mano.

| campo | clasificador | redactor |
|---|---|---|
| nombre, categoría, cantón, rating, sitio web, señales | sí | sí |
| `distancia_km` | sí | **no** |
| `telefono`, `direccion`, `place_id` | **no** | **no** |

El teléfono sigue en `prospectos_crudo.json`, en el puntaje de
`prospecto.py`, en el ranking y en la columna Teléfono de la hoja.
Salió del prompt, no del pipeline.

**Verificación:** `tests/test_privacidad.py`, 14 pruebas. No revisan la
lista de campos — eso sería tautológico. Arman el prompt con un negocio
que sí tiene teléfono y dirección, y comprueban que esos valores no
aparecen en el texto que sale.

Antecedente: al redactor ya se le había quitado `distancia_km` por la
misma lógica. Eso estaba escrito solo en un comentario; ahora hay un
test que falla si vuelve.

**Nota abierta (03/10):** el calificador usa la distancia en su razón
("a solo 5.2 km, logísticamente muy accesible"). No es falso, pero no
es el modelo de distribución de esta fábrica: la accesibilidad la
decide `ZONAS_REPARTO_PROPIO`, no los kilómetros — Coopeatenas a 10.4
km va por un tercero igual que un negocio en Limón. La razón no la ve
el redactor, así que no llega a ningún mensaje. Se revisa cuando el
sistema esté en plataforma y se pueda medir el impacto.

---

### 3. Ruteo de modelo

**Estado: manual, con regla escrita desde el 03/10.**

`MODELO = "claude-sonnet-4-6"` fijo en `grafo.py`. Se cambió desde Opus
al notar que era desproporcionado para clasificar en tres categorías y
escribir 80 palabras con reglas estrictas.

La regla está en `AGENTS.md`, "Elección de modelo", **y dice que no se
midió**. Esa segunda parte es lo que la hace una regla honesta en vez de
un hecho aparente: no se corrieron los dos modelos contra
`casos_prueba.py` para comparar.

**Qué lo cambiaría:** si la tasa de mensajes que agotan los 3 intentos
sube de forma sostenida. Antes de eso, subir de modelo es gastar más sin
saber si sirve.

La capa 3 del validador corre con `temperature=0`: ahí no se quiere
creatividad, se quiere la misma cita siempre. Es no-determinismo
controlado a propósito, no ausencia de él.

---

### 4. Runtime de agentes

**Estado: implementado. LangGraph.**

- Estado compartido con `TypedDict`
- Nodos: `calificador`, `redactor`, `validador`
- Aristas condicionales: `ruta()` decide según `calificacion`,
  `ruta_validacion()` decide si se reescribe
- Arista de retroceso `validador -> redactor`, con `MAX_INTENTOS = 3`
- Checkpointer: `MemorySaver`

**Condición de parada.** El único ciclo del grafo tiene tres salidas y
ninguna es "seguir intentando": el mensaje pasó, el validador falló
técnicamente (reescribir no lo arregla), o se agotaron los intentos.
Verificado en `tests/test_grafo_reintentos.py` sin llamar a ningún
modelo.

**Limitación:** `MemorySaver` es en memoria. El estado se pierde al
terminar el proceso. Para reanudar desde un punto de corte haría falta
un checkpointer persistente. Con 955 negocios en cola eso dejó de ser un
detalle teórico.

**Lo que NO es runtime de agentes.** El canal de visitas no tiene grafo,
ni nodos, ni modelo:

| archivo | qué hace | llama al modelo |
|---|---|---|
| `zonas.py` | zonas, canal, avisos, enlaces a Maps | no |
| `registro.py` | qué pasó con cada mensaje enviado | no |
| `estilo.py` | las decisiones de diseño, en un lugar | no |
| `app.py`, `pantallas/*.py` | la entrada y las dos pantallas | no |

Es código determinista sobre JSON ya calificado, y eso es a propósito: el
2.394 del canal de visitas no necesita a nadie pensando: necesita un
filtro por cantón y un orden. Un agente ahí sería costo y latencia sin
nada a cambio.

Por eso la lógica vive **fuera** de las pantallas. `zonas.py` y
`registro.py` no importan Streamlit, así que se prueban con pytest sin
levantar el app — **243 pruebas** en total, en 8 archivos.

---

### 5. Registro de herramientas

**Estado: informal.**

Solo hay una herramienta real: `buscar_negocios()`. No está declarada
como tool del agente — la llama el código determinista antes del grafo.

Esto es una decisión de diseño, no una carencia: la búsqueda no necesita
que un modelo decida cuándo ejecutarla.

---

### 6. Evaluación / QA de salidas

**Estado: implementado. Es la capa más fuerte del sistema.**

`validar.py`, con tres capas de costo creciente:

| capa | qué hace | costo |
|---|---|---|
| 1. reglas | palabras prohibidas, 80 palabras | gratis, el 100% |
| 2. **Jev** | decide si hay algo sin respaldo | barato, calibrado |
| 3. **Claude** | da la frase exacta | caro, solo lo marcado |

**Jev decide, Claude explica.** Jev devuelve probabilidades calibradas,
así que su 0.95 sirve de interruptor. Claude no está calibrado pero sí
sabe citar, y quien revisa necesita saber qué frase está mal.

Evaluado el 02/10/2026 contra `casos_prueba.py`: **7 de 7** de los casos
que existían ese día, con márgenes cercanos a +0.84 contra un mínimo
exigido de +0.30. El caso 8, agregado el 05/10, Jev lo falla — está
abajo, y es la razón de que la capa 1 siga creciendo.

Detalle de las capas 1 y 3:

1. **Reglas deterministas primero** — `PROHIBIDAS`, máximo 80 palabras.
   Si fallan, no se llama al modelo.
2. **Verificación por modelo** con contexto nuevo. No ve el razonamiento
   del redactor, solo el mensaje final.
3. **Evidencia citable** — cada bandera pide *la frase exacta* del
   mensaje que la enciende, no un número de confianza.

**Decisión de diseño central:** no se le pide al modelo una probabilidad.
Un número inventado no se puede verificar; una cita sí.

**Política ante fallo técnico:** `valido = False`. Nunca se aprueba por
defecto.

**Calibración:** 8 casos en `casos_prueba.py`. Seis deben fallar, dos
deben pasar. `python validar.py prueba` sale con código 1 si no dan 8
de 8. Si esos 8 no dan el resultado esperado, el validador está roto y
no hay que seguir hasta entender por qué.

El caso 8 (05/10) es el que más enseña: el redactor escribió "salchicha
criolla" y dos frases después "salchichón criollo". Jev le puso 0.02 —
la frase suena plausible, y un modelo de lenguaje no puede saber que acá
son dos productos distintos. Se resolvió en la **capa 1**, con una
palabra prohibida, no subiendo de modelo.

**Dentro del grafo desde el 03/10.** El validador es el tercer nodo y
el redactor recibe los problemas con la frase exacta que los encendió.
`validar.py` sigue existiendo para la calibración (`validar.py prueba`)
y para revalidar un JSON ya escrito sin reescribir nada.

---

### 7. Observabilidad

**Estado: implementada el 20–22/10/2026, en dos piezas.**

| pieza | qué responde | dónde vive |
|---|---|---|
| `bitacora.py` | ¿subió o bajó la tasa de reescritura? | `bitacora.jsonl`, en el repo, para siempre |
| Langfuse + `mascara.py` | ¿por qué **este** mensaje salió mal? | Langfuse Cloud, US, 30 días |

No se reemplazan. La bitácora guarda la historia larga sin un solo dato
de terceros adentro; Langfuse guarda el detalle reciente. El que puede
contestar "¿cómo venía esto en agosto?" es justamente el que no tiene
nombres.

#### La métrica propia

Una línea por corrida a `bitacora.jsonl`: cuántos negocios, cuántos con
mensaje, cuántos validados, cuántos reescritos, cuántos agotaron los
tres intentos, y los problemas ordenados por frecuencia. `python
bitacora.py` imprime el historial.

**La cuenta es una sola.** `medir()` es la única definición de
"reescrito" y "agotado" del proyecto; `resumen()` en `grafo.py` imprime
desde ese mismo dict. Si vivieran en dos lados, en tres meses no
coincidirían y no habría forma de saber cuál miente. Lo cuida una
prueba que falla si `resumen()` vuelve a contar por su cuenta.

`validar.py prueba` también anota. Importa más de lo que parece: cuesta
centavos y se puede correr con el pipeline en pausa, así que es la
única medición del proyecto que tiene historia desde ya. Y hay algo que
el proyecto no controla — Anthropic actualiza el modelo. Si un día la
calibración baja de 8 a 7 sobre los mismos casos y el mismo prompt, no
cambió el proyecto: cambió el modelo debajo. Sin bitácora eso se
descubre por casualidad.

#### Dónde viven las trazas, y por qué

Las trazas llevan los prompts completos. Mandarlas a un proveedor más,
justo después de que la capa 2 sacó teléfono y dirección del prompt,
sería deshacer esa decisión por comodidad. Así que la pregunta no era
"¿cuál herramienta?" sino "¿dónde corre?".

| opción | protege | costo | por qué no / sí |
|---|---|---|---|
| Langfuse autohospedado, local | todo | 0 | **No se puede:** pide 16 GiB, la máquina tiene 5,9 disponibles. La versión ligera (v2) está sin soporte desde Q1 2025 |
| Langfuse en un VPS propio | todo | ~15 USD/mes | Viable. El costo real no es la plata, es administrar un servidor |
| **Langfuse Cloud + máscara** | **la identidad, verificado** | **0** | **Elegida.** Ver abajo |
| Langfuse Cloud con DPA y retención corta | nada, técnicamente | 0 | Es un acuerdo de que alguien se porte bien, no un control |

La región es **US** (`us.cloud.langfuse.com`), elegida a propósito; no
hay requisito de residencia para datos de negocios publicados en Google
Maps. Las regiones son cuentas separadas: cambiar después obliga a
migrar.

#### El hallazgo que obligó a la máscara

Antes de escribir una línea de máscara se midió, con
`sonda_langfuse.py`: una corrida de **un negocio inventado**, con
centinelas en lugar de nombre, cantón, provincia y categoría, usando el
propio hook de enmascarado de Langfuse como microscopio.

Lo que apareció, el 21/10:

```
22 atributos por span. Dos llevan identidad:
   langfuse.observation.input
   langfuse.observation.output
Los otros 20 son metadata del grafo: nodo, modelo, tokens,
checkpoint, latencia. Esos SON la observabilidad.

Seis spans, todos con nombre genérico.

Y: los spans de nodo no trazan el prompt. Trazan el ESTADO.
```

**El estado lleva `negocio` entero, con teléfono y dirección adentro.**
La capa 2 protege lo que ve el modelo; no protege lo que ve el tracing,
porque son dos caminos distintos y nadie los había conectado. Conectar
Langfuse siguiendo cualquier tutorial habría mandado los teléfonos de
3.485 negocios a la nube, sin un solo error en pantalla.

Hay una segunda trampa, también medida: Langfuse tiene dos hooks de
enmascarado, y el que sale en los ejemplos (`mask`) **no inspecciona
los atributos de instrumentación de terceros** — que es exactamente por
donde llegan los spans de LangGraph. El que sirve es `mask_otel_spans`.

#### Cómo enmascara

`mascara.py`. `recordar(negocio)` anota los valores antes de invocar;
el hook los reemplaza en esos dos atributos:

```
Súper Dos   ->  neg_a3f2      seudónimo estable
Grecia                ->  zona_7b11
88887777              ->  [teléfono]    sin seudónimo: no sirve
200 m sur del parque  ->  [dirección]
```

Tres decisiones:

- **Sustituir, no borrar.** Borrar `input`/`output` protegería igual
  pero dejaría el panel sin el texto del mensaje, que es justo lo que
  se quiere leer cuando el validador rechaza algo. El seudónimo es
  hash del valor, así que es estable entre spans y entre corridas.
- **La categoría no se sustituye.** "Supermercado" la comparten
  cientos de negocios: no identifica a ninguno y hace la traza legible.
- **Falla cerrada.** Si el registro está vacío, el hook **borra** los
  dos atributos en vez de dejarlos pasar. Un error de cableado cuesta
  trazas, nunca datos.

`trazas.py` decide si esta corrida traza: están las tres llaves en el
`.env` o no traza. **La máscara no es opcional** — no hay parámetro
para pedir trazas sin ella, y hay una prueba que se pone roja si
alguien agrega uno. Una máscara opcional es una máscara que alguien
apaga "un momentito para depurar".

#### Verificado en tres niveles

Cada uno prueba algo que los otros no:

| | qué prueba |
|---|---|
| 17 pruebas de `mascara.py` | la lógica, incluidos los 3.485 nombres y teléfonos reales |
| `sonda_langfuse.py mascara` | que la máscara devuelve los parches correctos, sobre el pipeline real |
| mirar el panel | que Langfuse **los aplica** |

El tercero no es formalidad: que el hook devuelva un parche no prueba
que el servidor lo haya respetado.

#### Lo que esto no cubre

Una **paráfrasis**. Si el modelo escribe "la zona cafetalera" en vez de
"Grecia", no hay valor que sustituir. Es poco probable con un prompt
tan acotado — el modelo solo puede escribir sobre lo que se le dio —
pero está dicho en vez de dejarlo implícito.

Y Langfuse Cloud retiene **30 días** en el plan gratis. Por eso la
historia larga vive en la bitácora, que es también la que no tiene
nombres adentro.

---

### 8. Despliegue

**Estado: implementado el 08–12/10/2026.**

El app corre en **Streamlit Community Cloud**, desplegado desde un repo
privado de GitHub, con clave. Un rutero lo abre desde el teléfono y
"Agregar a pantalla de inicio" le da ícono y pantalla completa. No hizo
falta app nativa.

El **pipeline** sigue corriendo a mano, local, en el orden documentado
en `AGENTS.md`. Eso es deliberado: lo que tenía que estar disponible era
el app, no la corrida. Una corrida automática sobre Places gastaría
cuota sin que nadie mire el resultado.

| | dónde |
|---|---|
| código y datos | GitHub, repo **privado** |
| app | Streamlit Community Cloud |
| credenciales de Google | *secrets* del app |
| clave de acceso | *secrets* del app, `acceso.py` |
| respuestas | hoja de Google, pestaña `Respuestas` |

El procedimiento está en `DESPLIEGUE.md`.

**Lo que se pagó, escrito a propósito:** los 3.485 registros con
teléfono viven ahora en GitHub y en los servidores de Streamlit. Antes
estaban en una sola máquina. Son datos de terceros publicados en Google
Maps, pero la **lista compilada, filtrada y puntuada** es un activo
comercial y por eso el app lleva clave. La razón es comercial, no de
privacidad.

**Dos cosas que no se pueden deshacer**, y conviene saberlas antes:

1. El archivo principal de un app desplegado no se puede cambiar. Si se
   despliega con el equivocado, hay que borrar el app y recrearlo
   reutilizando el subdominio.
2. Un secreto que entró a git queda en el historial. Se revoca y se
   reemite; no se borra.

**Lo que sigue faltando:** no hay entornos (no existe un *staging*), no
hay despliegue automático con prueba previa, y la clave es una sola
compartida — no hay usuarios ni quién-hizo-qué. A esta escala es
razonable; en una plataforma empresarial no lo sería.

---

### 9. Persistencia del estado

**Estado: implementado el 08/10/2026, forzado por el despliegue.**

El sistema tiene cuatro archivos de estado. Tres se regeneran con una
corrida. El cuarto —**las respuestas**— no, porque guarda lo que
contestaron los negocios de verdad.

**En Streamlit Cloud el disco es efímero:** lo que el app escribe se
pierde al reiniciar el servidor, y solo sobrevive lo que está en
GitHub. Hospedar sin resolver esto habría borrado el único dato
irrecuperable del proyecto, en silencio.

`registro.py` pasó a tener un backend intercambiable:

```
         pantallas
             │
             ▼
        registro.py          cargar / guardar / anotar / resumen
             │
      ┌──────┴──────┐
      ▼             ▼
 respuestas.json   almacen_sheets.py
   (local)           (hospedado)
```

Un backend es cualquier objeto con `leer()` y `escribir(registros)`.
Las pantallas no saben cuál está activo; `inicio.py` lo elige al
arrancar y lo muestra en pantalla con `registro.donde()`.

**Elección de almacén, en orden de importancia:**

1. La hoja ya existe y ya funciona. Una base de datos serían
   credenciales nuevas y un proveedor más que puede fallar un sábado.
2. El papá la puede abrir desde el teléfono. Una base la lee quien sabe
   SQL.
3. Son 20 a 200 filas. A ese tamaño, una base es sobreingeniería.

**Cuándo dejaría de servir:** si varias personas anotaran a la vez, o si
pasaran de unos miles de registros. Si eso cambia, se cambia el backend
y el resto del código no se entera — que es justamente por qué está
detrás de una interfaz.

**Degradación:** si la hoja no responde al arrancar, el app guarda local
y lo dice en pantalla. Un app que no arranca es peor que uno que guarda
en otro lado y avisa. Pero hospedado eso significa pérdida al
reiniciar, así que el aviso es visible, no un log.

**Lo que esta capa enseñó, y es lo más transferible del proyecto:** de
los tres errores que costó, solo uno dio error. El 403 por permisos
insuficientes se vio enseguida. Los otros dos no: una hoja que el
sistema leía bien y una persona no, y Google recortando dos columnas sin
avisar —una de ellas la llave—, con `escribir()` devolviendo sin
excepción y la hoja actualizándose en pantalla.

**Lo que hay que revisar no es si el código corrió: es si el dato quedó
como debía.** Ver `AGENTS.md`, "Los errores que no dan error".

---

## Resumen

| Capa | Estado |
|---|---|
| 1. Gateway | no existe |
| 2. **Frontera con el modelo** | **implementada en las dos direcciones: lo que sale (03/10) y lo que entra (14/10)** |
| 3. Ruteo de modelo | manual, con regla escrita y honesta |
| 4. Runtime | implementado (LangGraph, con ciclo y tope) |
| 5. Registro de tools | informal, por diseño |
| 6. **Evaluación** | **implementado, tres capas (reglas / Jev / Claude)** |
| 7. **Observabilidad** | **implementada (métrica propia + trazas enmascaradas)** |
| 8. **Despliegue** | **implementado (Streamlit Cloud, repo privado, clave)** |
| 9. **Persistencia** | **implementada (backend intercambiable)** |

**Patrón:** la capa más difícil de construir está hecha, y las dos que
el despliegue obligó a cerrar también. Lo único que falta es lo que
solo duele a escala: el gateway, y a esta escala no hace falta.

**La observabilidad cerró el 22/10**, y lo que la hizo interesante no
fue conectarla sino medir primero qué salía: el tracing no traza el
prompt, traza el estado, y ahí viajaba lo que la capa 2 había sacado
del prompt a propósito.

**La frontera con el modelo quedó cerrada en las dos direcciones:** la
capa 2 resolvió lo que **sale** (teléfono y dirección, 03/10) y el
punto 25 lo que **entra** (14/10). Ver abajo.

---

## Lo que este sistema decidió NO construir

Se evaluó un agente investigador para resolver 73 carnicerías cuya
clasificación quedó ambigua.

**Prueba realizada:** se pidieron las reseñas de Google de D'Feria Centro
de Carnes — un cliente actual confirmado, con 101 reseñas. Ninguna de las
cinco reseñas devueltas menciona embutidos.

**Conclusión:** si en el caso donde la respuesta se conoce la fuente no
deja rastro, el método no puede funcionar sobre los casos desconocidos.

**Decisión:** no se construyó. El caso ambiguo se resuelve enviando la
oferta y observando quién responde.

**Costo de la prueba:** una llamada a la API, aproximadamente dos centavos.

---

## Anclas

El puntaje que ordena los 3.349 negocios **no ha sido validado contra la
realidad.** No se ha enviado un mensaje real ni hecho una visita.

Hasta que existan respuestas, el puntaje es una hipótesis razonada.

El ancla es la pestaña `Respuestas` de la hoja, que escribe el app. Hoy
tiene dos filas y las dos son de prueba.

### Por qué va a seguir vacía un tiempo (09/10/2026)

No es por falta de herramientas. Los mensajes se generan con un comando
y el app ya está en la calle.

**La fábrica no puede tomar clientes nuevos.** No consigue comprar
suficiente materia prima: los proveedores limitan la compra y priorizan
a los grandes. El hato nacional lleva años estable (~1,47 millones de
cabezas en 2024) mientras la exportación crece.

Eso cambia el signo del experimento:

> Un prospecto al que se le ofrece y después no se le despacha no queda
> pendiente. Queda quemado. Y la lista es finita.

**El ancla se partió en dos:**

| | qué mide | costo | estado |
|---|---|---|---|
| 18a | ¿la lista describe la realidad? | cero prospectos | **se puede hacer hoy** |
| 18b | ¿los mensajes convierten? | 20 prospectos | en pausa |

El 18a es un rutero recorriendo su zona con el app y anotando si cada
negocio existe, si es del tipo que dice, si la dirección sirve. No le
vende a nadie. **Mide la calidad del dato, que nunca se midió**, y es
información que hace falta igual el día que haya carne.

Vale anotar el orden en que se descubrió: durante cuatro días la
recomendación fue "mandá los 20 mensajes". Era la prioridad obvia desde
dentro del sistema y era la equivocada, porque el sistema no modela el
lado de la oferta. **Una arquitectura solo puede razonar sobre lo que
representa.**

### Y hay un problema conocido con el puntaje

Descubierto el 06/10 al correr sobre las siete provincias.

El puntaje suma por reseñas y rating. En un dataset nacional eso
**ordena por tamaño**, y los 20 primeros salieron todos cadenas: Auto
Mercado, Shoppers, Peri, Saretto. El propio calificador escribe en cada
razón que son *"muy difícil el ingreso para una fábrica artesanal"*.

```
  Shoppers              7.933 reseñas   puntaje altísimo   ¿compraría? casi seguro no
  Mini Súper San Luis      40 reseñas   puntaje medio      ¿compraría? tal vez sí
```

En el minisúper el dueño está ahí y decide. Shoppers compra desde
oficinas centrales, con registro sanitario, volúmenes y plazos que la
fábrica no puede cumplir hoy.

**Por qué importa ahora:** si el ancla se gasta en esos 20, el
resultado va a ser silencio, y no se va a poder distinguir si fue el
mensaje o el destinatario. Un experimento que no se puede interpretar
es un experimento perdido.

El arreglo corto fue `una_por_marca()`, el 07/10. El arreglo real sigue
siendo el punto 19: recalibrar los pesos con datos reales.

### Lo que la medición del 09/10 corrigió

Hipótesis: las cadenas tienen celular más seguido, así que el canal de
WhatsApp está sesgado hacia los negocios que no pueden comprar.

```
Cadenas          10% tiene celular
Independientes   31% tiene celular

de los 955 alcanzables por WhatsApp, 915 son independientes  (96%)
```

Falsa, y al revés. El canal es abrumadoramente de independientes. Lo que
estaba sesgado era el **orden**, no el canal.

---

## Próximos pasos, en orden

1. ~~`tests/test_reglas.py`~~ — 30/09
2. ~~Sanitizar el prompt (salida)~~ — 03/10, lista blanca + 14 pruebas
3. ~~Validador como tercer nodo~~ — 03/10, tope de 3
4. ~~Dos canales según `es_celular()`~~ — 05/10
5. ~~El app: tres páginas, diseño para teléfono~~ — 05–06/10
6. ~~Sacar las cadenas de la tanda~~ — 07/10, `una_por_marca()`
7. ~~Hospedar el app, con clave y persistencia~~ — 08–12/10
8. **Que un rutero verifique la lista una semana** — el ancla que no
   quema prospectos
9. **Inyección de prompt** — lo que entra, 30 min
10. **Preguntar por los proveedores** — bloquea cualquier envío
11. Recalibrar los pesos con lo que conteste
12. ~~Observabilidad~~ — 20–22/10, métrica propia + trazas con máscara

El detalle de cada uno está en `HOJA_DE_RUTA.md`.

**Y uno que no es de esta lista:** el único problema del proyecto que
justifica un agente de verdad no es encontrar clientes — es vigilar el
abastecimiento para saber cuándo conviene negociar volumen. Está como
punto 27 de la hoja de ruta. Requiere primero un registro de compras que
hoy no existe: sin línea base no hay anomalía que detectar.
