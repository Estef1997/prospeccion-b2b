# Despliegue — poner el app en internet

Para que un rutero lo abra desde su teléfono.

Escrito el 08/10/2026, **hecho el 12/10/2026**. La decisión de
hospedarlo, y lo que cuesta, está en el encabezado de `app.py`.

Queda como procedimiento para rehacerlo: el app se puede borrar y volver
a crear, y hay al menos un caso en que **hay que** hacerlo (ver paso 4).

---

## Antes de empezar: la regla que no se rompe

```
Los datos de negocios SÍ suben al repo privado.
credenciales.json y .env NO suben NUNCA, ni a un repo privado.
```

Un repo privado se puede volver público por error, se comparte con
colaboradores, y **lo que se sube una vez queda en el historial de git
aunque después se borre el archivo**. Borrar un secreto subido no es
borrarlo: es dejarlo en el historial y creer que se fue.

Si alguna vez subís `credenciales.json` por accidente, lo correcto no es
borrar el archivo — es **revocar esa cuenta de servicio en Google Cloud
y crear una nueva**.

---

## Paso 1 — Preparar la carpeta

Reemplazá los archivos que te mandé y comprobá que el proyecto esté
sano:

```powershell
python -m pytest -q              # 243 passed
python verificar_estructura.py   # sin FALTAN, salvo README.md
```

Renombrá `gitignore.txt` a `.gitignore` si todavía no lo está:

```powershell
Get-ChildItem .gitignore
```

Si no existe:

```powershell
Rename-Item gitignore.txt .gitignore
```

---

## Paso 2 — Comprobar qué subiría, ANTES de subirlo

Este es el paso que más vale la pena. Si el proyecto todavía no es un
repo:

```powershell
git init
git add .
```

Y ahora, antes de hacer nada más, mirá qué quedó listo para subir:

```powershell
git status --short
```

**Buscá estas dos líneas. Si aparecen, pará:**

```
A  credenciales.json
A  .env
```

Si aparecen, el `.gitignore` no se está aplicando. Lo más probable es
que el archivo se llame `gitignore.txt` todavía, o que Windows le haya
puesto `.gitignore.txt`. Comprobalo con:

```powershell
git check-ignore -v credenciales.json
```

Si devuelve una línea, está bien ignorado. Si no devuelve nada, **no lo
está**, y hay que arreglarlo antes de seguir.

Lo que SÍ tiene que aparecer en `git status`:

```
A  prospectos_crudo.json
A  prospectos_calificados.json
A  app.py, reglas.py, zonas.py, pantallas/...
```

---

## Paso 3 — Crear el repo PRIVADO en GitHub

En github.com → New repository.

| campo | qué poner |
|---|---|
| nombre | `embutidos-prospector` |
| visibilidad | **Private** ← lo más importante de esta página |
| initialize | nada, ni README ni .gitignore |

GitHub te muestra los comandos. Son estos:

```powershell
git commit -m "App de prospección: dos canales, listo para hospedar"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/embutidos-prospector.git
git push -u origin main
```

Cuando termine, **abrí el repo en el navegador y comprobá dos cosas**:

1. Dice **Private** al lado del nombre
2. `credenciales.json` NO está en la lista de archivos

---

## Paso 4 — Desplegar en Streamlit Cloud

En share.streamlit.io → Create app → "Deploy a public app from GitHub"
(aunque el repo sea privado; la primera vez te va a pedir autorizar el
acceso a tus repos).

| campo | qué poner |
|---|---|
| Repository | `TU_USUARIO/embutidos-prospector` |
| Branch | `main` |
| **Main file path** | **`app.py`** |
| App URL | `embutidos-prospector` |

> ### Esta casilla no se puede corregir después
>
> **El 12/10 se puso `acceso.py` por error.** `acceso.py` es un módulo
> sin pantalla, así que el menú lateral mostraba una página en blanco
> llamada "acceso" y la portada no era alcanzable.
>
> Streamlit **no permite cambiar el archivo principal de un app ya
> desplegado**. Hubo que borrar el app (⋮ → Delete) y volver a crearlo
> reutilizando el mismo subdominio, para que el enlace no cambiara.
>
> Si el subdominio sale ocupado justo después de borrar, esperá dos
> minutos.
>
> Lo que **no** hay que hacer es renombrar archivos para acomodarse al
> despliegue: `app.py` → `Inicio.py` chocaría con `inicio.py` en
> Windows, que no distingue mayúsculas.

No le des a Deploy todavía. Primero entrá a **Advanced settings →
Secrets**.

---

## Paso 5 — Los secretos

Esta es la parte delicada. En el cuadro de Secrets va esto:

```toml
clave = "la-que-elijas"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

Los valores de `[gcp_service_account]` salen de tu `credenciales.json`,
campo por campo.

**La trampa del `private_key`:** en el JSON las líneas van separadas por
`\n` literales. Tienen que quedar igual acá — entre comillas dobles, con
los `\n` tal cual, en una sola línea. Si Google te rechaza la
autenticación, ese es el primer sospechoso.

**La clave del app** (`clave = "..."`) es la que les vas a dar a los
ruteros. Que no sea el nombre de la fábrica ni algo adivinable.

### Lo que NO va en los secretos del app desplegado

```toml
modo = "desarrollo"      # ← esto NO, nunca, en el app hospedado
```

`modo = "desarrollo"` es lo único que habilita guardar las respuestas en
el disco del servidor. **En Streamlit Cloud ese disco se borra cuando el
servidor reinicia**, así que ponerlo allá es perder las respuestas sin
enterarse.

Sin esa línea, si la hoja de Google no responde el app queda en **solo
lectura** con un error rojo en pantalla: se puede seguir viendo la lista
y los mensajes, pero no se acepta una anotación que no va a sobrevivir.
La conexión se reintenta sola.

El modo existe para correr el app en tu máquina sin tocar los secretos:

```powershell
$env:EMBUTIDOS_MODO = "desarrollo"
python -m streamlit run app.py
```

Ahora sí, **Deploy**.

---

## Paso 6 — Comprobar que quedó bien

Abrí el enlace que te da Streamlit y revisá, en este orden:

| qué | tiene que pasar |
|---|---|
| al abrir | pide la clave |
| con la clave mal | dice "Clave incorrecta" |
| con la clave bien | entra a **Rutas**, con el selector de provincia |
| el menú lateral | dice **Rutas, Mensajes** — nada más |
| Rutas | muestra negocios con botones amarillos |
| Mensajes | muestra los que tienen celular |
| al pie | **NO** aparece el aviso gris sobre el servidor |

Esa última fila es la que importa: si aparece *"Las respuestas se están
guardando en este servidor y se pierden si reinicia"*, es que no se pudo
conectar a la hoja de Google. Revisá el `private_key`.

**Y la verificación que de verdad cierra el asunto:** marcá un negocio
como "enviado" en Mensajes, guardá, y **abrí la hoja de Google**. Tiene
que aparecer la fila en la pestaña `Respuestas`, con siete columnas:

```
nombre | canton | estado | enviado | mensaje | notas | place_id
```

Si faltan columnas al final, ver `ensanchar()` en `almacen_sheets.py`:
una hoja de Google no se ensancha sola y Google recorta en silencio.

Por último: abrilo desde tu teléfono, con datos móviles, no por wifi. Es
como lo va a abrir un rutero.

**Borrá las filas de prueba** antes de empezar a medir de verdad. El
sistema las lee como envíos reales y mueven la tasa de respuesta, que es
la única cifra del proyecto que no es una hipótesis.

---

## Paso 7 — Que parezca un app

En el teléfono, Chrome o Safari → menú → **Agregar a pantalla de
inicio**.

Queda con ícono propio y abre a pantalla completa, sin barra de
direcciones. No hace falta un app nativo para esto.

---

## Después: cómo se actualiza

Cuando busques negocios nuevos o cambies una regla:

```powershell
python prospecto.py buscar Cartago
python prospecto.py reetiquetar
python -m pytest -q

git add .
git commit -m "Negocios de Cartago"
git push
```

Streamlit redespliega solo al detectar el push. Tarda un par de minutos.

**Ojo con `@st.cache_data`:** el app guarda el JSON en memoria. Después
de un redespliegue toma los datos nuevos, pero si solo cambiaste el
archivo sin redesplegar, hay que reiniciar el app desde el panel de
Streamlit.

---

## El respaldo, que conviene no saltarse

Las respuestas viven en la hoja de Google. Eso es mejor que el disco de
Streamlit, pero sigue siendo **un solo lugar** para el único dato
irrecuperable del proyecto.

Cada tanto, desde tu máquina:

```powershell
python -c "import almacen_sheets; almacen_sheets.respaldo()"
```

Te deja `respuestas_respaldo.json` en la carpeta. Está en `.gitignore`
a propósito: es una copia, no el original.

### El respaldo automático, que es otra cosa

Desde el 03/11/2026 cada guardado copia lo que la pestaña `Respuestas`
tenía **antes** a una pestaña `Respuestas_respaldo`, en la misma hoja.

Va en la hoja y no en un archivo porque allá el disco se borra: un
respaldo que no sobrevive al reinicio no es un respaldo.

Es de un paso atrás, no un historial. Si algo sale mal, se mira esa
pestaña **antes** de volver a guardar, porque el guardado siguiente la
sobrescribe. El comando de arriba sigue siendo el que te da una copia
fuera de Google.

---

## Si algo sale mal

| síntoma | causa más probable |
|---|---|
| "ModuleNotFoundError" al desplegar | falta algo en `requirements.txt` |
| el app pide clave y nunca entra | `clave` mal escrita en Secrets (sensible a mayúsculas) |
| "El app no tiene clave configurada" | falta `clave` en Secrets, o está mal el TOML |
| **error rojo "no se puede guardar"** | no conecta a la hoja. El app queda en solo lectura a propósito. Revisá `private_key` y que la hoja esté compartida |
| aviso de "modo desarrollo" en el app hospedado | sobra `modo = "desarrollo"` en los Secrets. Quitalo: allá el disco se borra |
| "Spreadsheet not found" | la hoja no está compartida con el `client_email` de la cuenta de servicio |
| **403 insufficient authentication scopes** | faltan permisos: `gspread.open()` busca **por nombre**, y eso consulta **Drive**, no Sheets. Los dos alcances vienen de `a_sheets.py` |
| una página en blanco en el menú | el *Main file path* quedó mal. No se arregla: hay que borrar y redesplegar (paso 4) |
| la hoja se llena pero `leer()` no ve nada | se perdió la columna `place_id` por ancho. Ver `ensanchar()` |
| se despliega pero sin datos | los JSON no subieron: revisá `.gitignore` |

La última es la más común y la más confusa, porque el app arranca bien y
simplemente dice que no hay negocios.

---

## Cambiar la clave

Es lo que hay que hacer antes de darle el enlace a nadie, y no requiere
redesplegar.

share.streamlit.io → ⋮ del app → **Settings → Secrets** → cambiar el
valor de `clave` → **Save**. El app se reinicia solo en unos segundos.

**Cambiar la clave expulsa a todos** (desde el 03/11/2026). Las
sesiones que estaban abiertas se caen y tienen que entrar de nuevo con la
clave nueva. Eso es el punto: antes seguían adentro, así que "cambiale la
clave porque se fue un rutero" no echaba a nadie — solo le impedía volver
a entrar la próxima vez.

Avisales antes, porque les va a pedir la clave en medio de la ruta.

Lo mismo sirve para corregir cualquier secreto: `private_key`,
`client_email`, lo que sea. **Lo único que no se puede cambiar es el
archivo principal.**