"""
Vuelca los resultados calificados a Google Sheets.

Requiere:
    pip install gspread google-auth
    credenciales.json en esta carpeta
    La hoja compartida como Editor con el client_email de ese archivo

Uso:
    python a_sheets.py                  # todo lo que haya calificado
    python a_sheets.py carnicerias      # solo carnicerias_calificadas.json
"""

import json
import os
import sys

import gspread

import registro
from google.oauth2.service_account import Credentials

HOJA = "Prospectos Embutidos Artesanales"
CREDENCIALES = "credenciales.json"

ALCANCES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# El orden de las columnas en la hoja.
# "estado" y "notas" van al final: son las que llena tu papa.
COLUMNAS = [
    ("nombre", "Negocio"),
    ("categoria", "Categoria"),
    ("canton", "Canton"),
    ("telefono", "Telefono"),
    ("puntaje", "Puntaje"),
    ("num_resenas", "Resenas"),
    ("distancia_km", "Km"),
    ("calificacion", "Calificacion"),
    ("confianza", "Confianza"),
    ("razon", "Razon del agente"),
    ("mensaje", "Mensaje sugerido"),
]

# Columnas que NO escribe este script: vienen de respuestas.json.
#
# ORIGEN (03/10): antes se escribian a mano en la hoja y se leian de
# ahi. Con el app habria dos lugares donde anotar lo mismo, y se
# desincronizarian al primer cambio -- el mismo bug de CONTEXTO_FABRICA.
#
# Ahora el dueno es registro.py. La hoja es una VISTA.
COLUMNAS_MANUALES = ["Estado", "Enviado", "Mensaje", "Notas"]

def conectar():
    if not os.path.exists(CREDENCIALES):
        raise RuntimeError(
            f"Falta {CREDENCIALES} en esta carpeta."
        )
    creds = Credentials.from_service_account_file(
        CREDENCIALES, scopes=ALCANCES
    )
    cliente = gspread.authorize(creds)
    try:
        return cliente.open(HOJA)
    except gspread.SpreadsheetNotFound:
        raise RuntimeError(
            f"No encuentro la hoja '{HOJA}'. Revisa dos cosas:\n"
            f"  1. Que el nombre sea exactamente ese.\n"
            f"  2. Que este compartida como Editor con el client_email\n"
            f"     que aparece en {CREDENCIALES}."
        )


def cargar(archivos):
    """Junta varios JSON de resultados, sin duplicar por place_id."""
    vistos, datos = set(), []
    for ruta in archivos:
        if not os.path.exists(ruta):
            print(f"  (no existe {ruta}, lo salto)")
            continue
        with open(ruta, encoding="utf-8") as f:
            for d in json.load(f):
                if d.get("place_id") in vistos:
                    continue
                vistos.add(d.get("place_id"))
                datos.append(d)
        print(f"  {ruta}: acumulado {len(datos)}")
    return datos


def escribir_seguro(hoja, filas, filas_previas):
    """Escribe PRIMERO y recorta el sobrante DESPUES. Nunca al reves.

    ORIGEN (03/11/2026), de una revision externa del repo publico.

    Antes las dos escrituras del proyecto hacian `hoja.clear()` y
    despues `hoja.update()`, con un comentario que decia "o entran
    todas o no entra ninguna". El comentario era falso: son **dos
    llamadas a la API de Google**. Si la primera entra y la segunda
    falla -- se cayo la red, expiro el token, Google contesto 429 -- la
    pestaña queda VACIA.

    Vacia es el peor estado posible, porque:

    - en la pestaña Respuestas vive el unico dato que no se regenera;
    - aca viven las columnas manuales que se escribieron antes de que
      el app existiera, y que solo estan en la hoja; y
    - leer una hoja vacia no falla: devuelve vacio, y el app muestra
      "no hay nada" sin un solo error en pantalla.

    Es el mismo patron que ya se repitio cuatro veces en este proyecto:
    el codigo corrio, no lanzo excepcion, y el dato quedo mal.

    POR QUE ESTE METODO Y NO OTRO

    Se evaluaron tres:

    1. **Escribir y recortar** (este). El peor caso es que el recorte
       falle y queden filas viejas colgando mas abajo. Eso es visible
       en la hoja, se arregla volviendo a guardar, y no pierde nada.
    2. Actualizar celda por celda segun la llave. Son N llamadas en vez
       de dos, y una falla a la mitad deja la hoja mezclada: unas filas
       nuevas y otras viejas, sin forma de saber cuales.
    3. Un `batch_update` con el clear y el update en una sola peticion.
       Es lo mas correcto en teoria, pero deja el orden destructivo
       escrito en el codigo y depende de que gspread y Google lo traten
       de verdad como atomico. No se puede comprobar desde aca.

    Se eligio (1) porque su peor caso es recuperable y visible, y los
    otros dos tienen peores casos silenciosos. El criterio no es cual
    falla menos: es cual falla mejor.

    POR QUE VIVE EN UN SOLO ARCHIVO

    Lo usan a_sheets.py y almacen_sheets.py. Copiarlo en los dos seria
    el bug de CONTEXTO_FABRICA otra vez, y esta vez sobre la escritura
    del dato irrecuperable. almacen_sheets.py ya importa HOJA y
    ALCANCES de aca, asi que la dependencia va en la direccion que ya
    existia.
    """
    hoja.update(values=filas, range_name="A1")

    # Solo si antes habia MAS filas que ahora. Sin esto, borrar un
    # registro dejaria su fila vieja colgando debajo de las nuevas, y
    # quien lea la hoja la devolveria como si siguiera viva.
    if filas_previas > len(filas):
        ancho = max((len(f) for f in filas), default=1)
        ultima = chr(ord("A") + ancho - 1)
        hoja.batch_clear([f"A{len(filas) + 1}:{ultima}{filas_previas}"])


def preservar_manuales(hoja, datos):
    """Lo anotado por negocio, para las columnas manuales de la hoja.

    La fuente es respuestas.json, que escribe el app. Si un negocio
    todavia no esta ahi pero SI tiene algo escrito a mano en la hoja,
    se conserva: es lo que se anoto antes de que el app existiera.

    Precedencia: el registro gana. Si estan los dos, el de la hoja es
    el viejo.
    """
    registros = registro.cargar()

    a_mano = {}
    try:
        for fila in hoja.get_all_records():
            clave = fila.get("Negocio")
            if clave:
                a_mano[clave] = [fila.get(c, "") for c in COLUMNAS_MANUALES]
    except Exception:
        pass          # sin red o sin hoja: seguimos con el registro

    guardado = {}
    for d in datos:
        nombre = d.get("nombre")
        pid = d.get("place_id")
        del_registro = registro.para_la_hoja(registros, pid)

        if any(del_registro):
            guardado[nombre] = del_registro
        elif nombre in a_mano and any(a_mano[nombre]):
            guardado[nombre] = a_mano[nombre]

    return guardado


def volcar(datos, archivos_origen):
    libro = conectar()
    hoja = libro.sheet1

    manuales = preservar_manuales(hoja, datos)
    if manuales:
        marcados = sum(1 for v in manuales.values() if any(v))
        print(f"Preservando {marcados} filas con estado o notas ya escritos")

    # Mas puntaje primero: por ahi se empieza a contactar.
    datos.sort(key=lambda x: x.get("puntaje") or 0, reverse=True)

    encabezado = [t for _, t in COLUMNAS] + COLUMNAS_MANUALES
    filas = [encabezado]

    for d in datos:
        fila = []
        for campo, _ in COLUMNAS:
            valor = d.get(campo)
            fila.append("" if valor is None else str(valor))
        fila.extend(manuales.get(d.get("nombre"),
                                 [""] * len(COLUMNAS_MANUALES)))
        filas.append(fila)

    # Nunca clear() antes de update(): ver escribir_seguro(). Las
    # columnas manuales que preservar_manuales() acaba de leer solo
    # viven en la hoja, asi que vaciarla las borraria para siempre.
    previas = len(hoja.get_all_values())
    escribir_seguro(hoja, filas, previas)

    # Formato minimo para que se pueda leer.
    hoja.freeze(rows=1)
    hoja.format("A1:M1", {"textFormat": {"bold": True}})

    print(f"\nEscritas {len(filas) - 1} filas en '{HOJA}'")
    print(f"Origen: {', '.join(archivos_origen)}")
    print(f"\nURL: {libro.url}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "todo"

    if modo == "carnicerias":
        archivos = ["carnicerias_calificadas.json"]
    elif modo == "todo":
        archivos = ["prospectos_calificados.json",
                    "carnicerias_calificadas.json"]
    else:
        sys.exit(f"Modo desconocido: {modo}. Use 'todo' o 'carnicerias'.")

    print("Cargando resultados:")
    datos = cargar(archivos)

    if not datos:
        sys.exit("No hay datos que volcar.")

    volcar(datos, archivos)