"""
Guarda las respuestas en la hoja de Google en vez del disco.

POR QUE EXISTE

En Streamlit Cloud el disco es efimero. Lo que el app escribe se pierde
cuando el servidor reinicia, y solo sobrevive lo que esta en GitHub.

`respuestas.json` es el unico archivo del proyecto que **no se puede
volver a generar**. prospectos_crudo, prospectos_calificados y
carnicerias_calificadas salen de una corrida; este guarda lo que
contestaron los negocios de verdad. Perderlo es perder el ancla.

POR QUE LA HOJA Y NO UNA BASE DE DATOS

Tres razones, en orden de importancia:

1. Ya existe y ya funciona. a_sheets.py lleva semanas escribiendo ahi.
   Una base nueva serian credenciales nuevas, un proveedor mas y una
   cosa mas que puede fallar un sabado.
2. El papa la puede abrir. Una base de datos la lee quien sabe SQL;
   la hoja la lee cualquiera desde el telefono.
3. Son 20 a 200 filas. A ese tamano una base de datos es sobreingenieria.

**Cuando dejaria de servir:** si varias personas anotaran a la vez, o
si pasaran de unos miles de registros. Hoy anota una persona y son
decenas. Si eso cambia, esto se cambia -- el resto del codigo no se
entera, porque solo ve leer() y escribir().

COMO SE CONECTA

Las credenciales NO viven en un archivo aca. En Streamlit Cloud van en
los "secrets" del app; en la maquina de desarrollo, en credenciales.json.
Ninguno de los dos sube a GitHub, ni siquiera a un repo privado.

FORMATO

Una fila por negocio: place_id, estado, enviado, mensaje, notas. La
primera fila son los titulos. Se lee y se escribe la hoja entera, que a
este tamano es mas simple y mas dificil de romper que escribir celdas
sueltas.
"""

import json

NOMBRE = "la hoja de Google (pestaña Respuestas)"

# El nombre de la hoja y los permisos vienen de a_sheets.py, que lleva
# semanas conectandose bien. No se copian aca.
#
# ORIGEN (08/10/2026): los tenia escritos aparte, y con un solo permiso
# -- el de Sheets. Google contesto:
#
#     APIError [403]: Request had insufficient authentication scopes
#
# La causa: gspread.open() busca la hoja POR NOMBRE, y buscar por nombre
# es una consulta a Drive, no a Sheets. Hacen falta los dos permisos.
#
# Es el tercer caso del mismo error esta semana -- CONTEXTO_FABRICA,
# CADENAS, y ahora esto. Una constante copiada es una constante que se
# va a desincronizar.
from a_sheets import ALCANCES as ALCANCE  # noqa: E402
from a_sheets import HOJA  # noqa: E402

PESTANA = "Respuestas"

# El orden de las columnas, pensado para quien LEE la hoja.
#
# Cambio del 09/10/2026. Antes era:
#
#     place_id | estado | enviado | mensaje | notas
#
# La primera fila real decia "ChIJ_ejemplo_redactado | enviado".
# Surgio la pregunta: que hace con eso, y tenia razon: el place_id identifica
# al negocio para el sistema, pero no le dice nada a una persona.
#
# El nombre y el canton van primero; el place_id queda al final, donde
# no estorba pero sigue estando -- es la llave, y sin el no se puede
# volver a cruzar esta hoja con el resto de los datos.
COLUMNAS = ["nombre", "canton", "estado", "enviado", "mensaje", "notas",
            "place_id"]

_hoja = None


def _credenciales():
    """De los secrets de Streamlit, o del archivo local.

    En la nube no hay archivo: el contenido del JSON de servicio vive en
    los secrets del app, que Streamlit expone como un dict.
    """
    from google.oauth2.service_account import Credentials

    try:
        import streamlit as st

        if "gcp_service_account" in st.secrets:
            return Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=ALCANCE)
    except Exception:
        # Sin Streamlit, o sin secrets configurados: se intenta el
        # archivo local. No es un error todavia.
        pass

    return Credentials.from_service_account_file(
        "credenciales.json", scopes=ALCANCE)


def conectar():
    """Abre la pestaña, creandola si no existe.

    Se guarda en _hoja para no reconectar en cada interaccion: Streamlit
    vuelve a correr el script entero cada vez que alguien toca algo.
    """
    global _hoja
    if _hoja is not None:
        return _hoja

    import gspread

    libro = gspread.authorize(_credenciales()).open(HOJA)
    try:
        _hoja = libro.worksheet(PESTANA)
    except gspread.WorksheetNotFound:
        _hoja = libro.add_worksheet(PESTANA, rows=500, cols=len(COLUMNAS))
        _hoja.update([COLUMNAS], "A1")
    return _hoja


def ensanchar(hoja):
    """Agrega columnas si la hoja quedo mas angosta que COLUMNAS.

    ORIGEN (09/10/2026), y es el peor bug que ha tenido este archivo.

    La pestaña se creo con `cols=len(COLUMNAS)` cuando COLUMNAS tenia 5
    entradas. Al agregar `nombre` y `canton` pasaron a ser 7, pero una
    hoja de Google NO se ensancha sola: Google recorta lo que no cabe,
    sin avisar.

    El encabezado quedo:

        nombre | canton | estado | enviado | mensaje

    Se perdieron `notas` y -- lo grave -- **`place_id`**. Esa es la
    llave. Sin ella, leer() no encuentra ningun registro y las
    respuestas se ven vacias al abrir el app, aunque las filas esten
    ahi. Perdida de datos silenciosa sobre el unico archivo del proyecto
    que no se puede regenerar.

    Lo escondido del error: escribir() parecia funcionar. No lanzaba
    excepcion, la hoja se actualizaba, y solo faltaban dos columnas al
    final -- donde nadie mira.

    Por eso esto corre en cada escritura y no una sola vez al crear: la
    pestaña puede existir desde antes, con el ancho de entonces.
    """
    if hoja.col_count < len(COLUMNAS):
        hoja.add_cols(len(COLUMNAS) - hoja.col_count)
    return hoja


def disponible():
    """True si se puede escribir en la hoja.

    Se usa al arrancar el app para decidir si guardar alla o en disco.
    Falla en silencio a proposito: un app que no arranca es peor que un
    app que guarda local y lo dice en pantalla.
    """
    try:
        conectar()
        return True
    except Exception:
        return False


def leer():
    """Todo lo anotado, con la misma forma que daba el archivo JSON.

    {place_id: {estado, enviado, mensaje, notas}}
    """
    filas = conectar().get_all_records()
    salida = {}
    for fila in filas:
        pid = str(fila.get("place_id") or "").strip()
        if pid:
            salida[pid] = {c: str(fila.get(c) or "")
                           for c in COLUMNAS if c != "place_id"}
    return salida


def escribir(registros):
    """Reemplaza la pestaña completa.

    Se reescribe todo en vez de actualizar celdas sueltas porque a 20 o
    200 filas es instantaneo, y porque una escritura parcial que falla a
    la mitad deja la hoja en un estado que nadie sabe interpretar.

    gspread manda las filas en una sola llamada, asi que o entran todas
    o no entra ninguna.
    """
    hoja = ensanchar(conectar())
    filas = [COLUMNAS]
    for pid, datos in registros.items():
        # El place_id viene de la llave del dict, no de los datos; el
        # resto sale de los campos. Se arma siguiendo COLUMNAS, asi que
        # cambiar el orden alla cambia la hoja y nada mas.
        fila = {**datos, "place_id": pid}
        filas.append([str(fila.get(c, "")) for c in COLUMNAS])

    hoja.clear()
    hoja.update(filas, "A1")


def respaldo(ruta="respuestas_respaldo.json"):
    """Baja todo a un archivo, para tener una copia fuera de Google.

        python -c "import almacen_sheets; almacen_sheets.respaldo()"

    La hoja es el original, pero depender de un solo lugar para el unico
    dato irrecuperable del proyecto no es prudente.
    """
    datos = leer()
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    print(f"{len(datos)} registros guardados en {ruta}")
    return datos