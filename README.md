# Prospección — Embutidos Artesanales

Sistema de prospección B2B para una fábrica familiar de embutidos en
Palmares de Alajuela, Costa Rica. 26 años operando, un solo producto.

Busca negocios en Google Places, los filtra y puntúa con código
determinista, usa modelos de lenguaje solo para clasificar y redactar,
valida cada mensaje en tres capas, y entrega el resultado en un app que
se abre desde el teléfono.

**El sistema no vende. Ordena el trabajo de quien vende.**

---

## El dato decide el canal

De 3.349 negocios candidatos, **955 tienen celular (29%)**. A los otros
2.394 no se les puede mandar un WhatsApp: tienen fijo, no tienen
número, o el número está mal formado.

> **3.349 es un piso, no un censo.** Google Places devuelve como máximo
> 20 resultados por consulta y este endpoint no pagina, así que toda
> zona con más de 20 negocios de un tipo quedó recortada. Y hasta el
> 03/11/2026 las consultas que fallaban se saltaban con un mensaje en
> pantalla y nada más, sin dejar registro de cuál zona no se había
> consultado. Las proporciones de abajo (el 29%, el 96%) se calculan
> sobre lo que hay y se sostienen; el total absoluto no es una medición
> del mercado. Desde esa fecha cada corrida anota en `bitacora.jsonl`
> cuántas consultas fallaron y cuántas llegaron al tope, así que la
> próxima sí va a poder decir cuánto piso es.

Eso parte el sistema en dos salidas, y quien decide no es un modelo
sino una función de cuatro líneas que mira el primer dígito del número
según el plan de numeración de SUTEL:

```
            prospectos_crudo.json  (3.349 candidatos)
                        |
                 es_celular(telefono)
                        |
        sí (955)                    no (2.394)
            |                            |
       grafo.py                   pantallas/Rutas.py
  calificador -> redactor              zona, puntaje,
        -> validador                 dirección, cómo llegar
            |                            |
   pantallas/Mensajes.py            el rutero visita
   enlace wa.me, lo manda
       una persona
```

Ningún mensaje se envía solo. El botón abre WhatsApp con el texto ya
escrito; una persona lo lee y decide.

---

## Cómo se corre

```bash
python -m pytest -q                 # 389 passed, o algo se rompió
python validar.py prueba            # calibra el validador: 19 de 19

python prospecto.py costo Cartago   # cuánto costaría, sin gastar
python prospecto.py buscar Cartago  # Places -> prospectos_crudo.json
python prospecto.py reetiquetar     # recalcula sin tocar la API

python grafo.py whatsapp 20 Alajuela   # celular, y de una sola provincia
python bitacora.py                  # qué dejó cada corrida, en el tiempo

python -m streamlit run app.py      # el app: rutas + mensajes
```

La provincia no es un adorno: sin ella la tanda sale con un negocio en
Escazú, uno en Heredia y dos en Alajuela, y eso no es un recorrido que
nadie pueda hacer. El filtro va antes del modelo, no al mostrar —
filtrando al mostrar ya se pagó por redactar mensajes que nadie va a
usar.

Si una corrida se interrumpe, lo ya calificado queda en disco y al
volver a arrancar retoma donde iba. No se vuelve a pagar.

El tracing es opcional: si las tres llaves de Langfuse están en el
`.env`, las corridas se trazan con la máscara puesta; si no están, todo
funciona igual. `python sonda_langfuse.py mascara` verifica la máscara
contra el pipeline real, con un negocio inventado.

`python prospecto.py` sin argumento imprime la ayuda. Es el único
comando que cuesta dinero de verdad, y antes buscaba por defecto.

Hace falta un `.env` (ver `.env.example`) y, para la hoja de Google,
un `credenciales.json`. Ninguno de los dos sube al repositorio.

### Esta copia no trae los datos

Los 3.349 negocios son datos de terceros: nombre, teléfono y dirección
de comercios reales, sacados de Google Places. **No están acá, y no
van a estar.**

Eso tiene tres consecuencias visibles:

- `prospectos_crudo.json` se nombra en el diagrama y en los comandos,
  pero hay que generarlo con `prospecto.py buscar`, que cuesta cuota de
  Google.
- `pytest` reporta **387 pasadas y 2 saltadas** en vez de 389. Las dos
  que se saltan son las que recorren el corpus completo buscando que
  ningún nombre ni teléfono real sobreviva a la máscara. Se saltan con
  el motivo escrito, no en silencio.
- El nombre de la fábrica y los de sus clientes están reemplazados por
  genéricos.

Nada de eso cambia el código. La lógica, las pruebas y las decisiones
son las mismas; lo único que falta es lo que no me corresponde
publicar.

---

## Lo que está hecho, en capas de plataforma

| capa | estado |
|---|---|
| Gateway | no existe, y a esta escala no hace falta |
| **Frontera con el modelo** | **cerrada en las dos direcciones** |
| Ruteo de modelo | manual, con regla escrita y honesta |
| Runtime de agentes | LangGraph, con ciclo y tope de 3 |
| Registro de tools | informal, por diseño |
| **Evaluación / QA** | **tres capas: reglas, Jev, Claude** |
| **Observabilidad** | **métrica propia (`bitacora.py`) + trazas con máscara verificada** |
| Despliegue | Streamlit Cloud, repo privado, con clave |
| Persistencia | backend intercambiable (archivo u hoja de Google) |

"Frontera cerrada en las dos direcciones" quiere decir que el modelo no
recibe teléfono ni dirección de terceros (lo que **sale**), y que el
texto escrito por terceros no puede dar órdenes (lo que **entra**).

La observabilidad son dos piezas que contestan preguntas distintas.
`bitacora.py` guarda una línea por corrida, para siempre y en el repo:
cuántos se reescribieron, qué problema se repitió. Langfuse guarda el
detalle de los últimos 30 días: por qué **este** mensaje salió mal.

Lo que vale contar de esa segunda no es conectarla, es lo que apareció
al medir antes de conectarla:

**El tracing no traza el prompt. Traza el estado.** Y el estado lleva
el negocio entero, con teléfono y dirección adentro — justo lo que el
proyecto había sacado del prompt a propósito. Conectar Langfuse
siguiendo cualquier tutorial habría mandado los teléfonos de 3.485
negocios a la nube, sin un solo error en pantalla.

De ahí salió `mascara.py`: reemplaza cada nombre y cada teléfono por un
seudónimo antes de que el lote salga de la máquina, y no es opcional —
no hay parámetro para pedir trazas sin ella, y hay una prueba que se
pone roja si alguien lo agrega.

**Qué es y qué no es, con precisión.** El seudónimo es
`sha256(valor)[:4]`, sin llave. Eso es **seudonimización, no
anonimización fuerte**: son 4 caracteres hexadecimales, o sea 65.536
cubetas, y el universo de valores posibles son los 3.485 nombres del
archivo. Quien tenga la lista —o pueda reconstruirla desde Google
Places, que es pública— recorre los candidatos, les calcula el hash y
recupera la correspondencia. El seudónimo es estable a propósito, para
poder seguir un mismo negocio entre spans, y esa misma estabilidad es
lo que lo hace reversible.

Lo que la máscara sí logra: que el panel de un tercero no reciba los
nombres y teléfonos en claro, y que un volcado accidental de las trazas
no sea una lista de contactos. Lo que no logra: resistir a alguien que
quiera deshacerla y tenga el universo de entradas. Para eso haría falta
un HMAC con una llave que no salga de la máquina.

Está verificada en tres niveles, que prueban cosas distintas: la
lógica contra los 3.485 nombres y teléfonos reales, los parches contra
el pipeline corriendo, y **mirar el panel**, porque que el hook
devuelva un parche no prueba que el servidor lo haya aplicado.

---

## Lo que NO está validado

**El puntaje que ordena los 3.349 negocios no se ha comprobado contra
la realidad.** Nadie ha contestado todavía.

Hasta que haya respuestas, ese orden es una hipótesis razonada, no una
medición. El proyecto lo dice en voz alta en vez de esconderlo, porque
es la diferencia entre un sistema que funciona y uno que parece que
funciona.

Y hay una razón concreta por la que sigue vacío: **la fábrica no puede
tomar clientes nuevos.** No consigue comprar suficiente materia prima.
Mandar mensajes hoy quemaría prospectos que son finitos, así que ese
paso está en pausa a propósito.

---

## Los documentos

Este README es la entrada. El detalle vive en cuatro archivos, y
conviene leerlos en este orden:

| archivo | qué contiene |
|---|---|
| `AGENTS.md` | las reglas del proyecto, **cada una con el error del que salió** |
| `PROGRESO.md` | bitácora entre sesiones, lo más reciente arriba |
| `ARQUITECTURA.md` | las capas de arriba, en detalle |
| `HOJA_DE_RUTA.md` | lo que falta, con cómo se verifica cada punto |

La convención que los sostiene: **ninguna regla se escribe sin decir de
qué error salió.** Una lista de buenas prácticas sin origen es una lista
que alguien recorta en seis meses.

---

## Lo que este proyecto decidió NO construir

- **Un agente investigador de prospectos.** Se probó: las reseñas de
  Google de un cliente conocido no mencionan embutidos. Si la fuente no
  deja rastro donde la respuesta se sabe, no sirve donde no se sabe.
  Costo de la prueba: dos centavos.
- **Envío automático de WhatsApp.** Es la vía rápida a que bloqueen el
  número.
- **Una base de datos.** Las respuestas caben en una hoja de Google que
  el dueño abre desde el teléfono. A 200 filas, una base sería
  sobreingeniería.
- **App nativa.** Una web instalada da lo mismo y cuesta meses menos.

---

## Estado

```
389 pruebas en 16 archivos
19 casos de calibracion: 13 deben fallar, 6 deben pasar
app desplegado, con clave, guardando en Google Sheets
observabilidad conectada, con la identidad seudonimizada
respuestas reales: 0
```

**El código está terminado.** Lo que falta está en `HOJA_DE_RUTA.md` y
no se escribe: es que alguien recorra una zona con la lista en la mano
y anote si los negocios existen.
