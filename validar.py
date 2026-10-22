"""
Validador de mensajes en tres capas.

    python validar.py prueba     # los 7 casos conocidos, para calibrar
    python validar.py            # sobre prospectos_calificados.json

POR QUE TRES CAPAS

Cada una es mas cara que la anterior y solo recibe lo que la anterior no
resolvio:

    1. REGLAS       palabras prohibidas, largo maximo
                    gratis, instantaneo, corre sobre el 100%

    2. JEV          decide si hay una afirmacion sin respaldo
                    (TypeSafe) devuelve probabilidades CALIBRADAS: un 0.80
                    suyo significa que acierta ~80% de las veces, asi que
                    sirve de interruptor

    3. CLAUDE       da LA FRASE EXACTA que enciende cada bandera
                    caro, corre solo sobre lo que la capa 2 marco

La capa 3 existe porque la 2 devuelve un numero y una persona que revisa
necesita saber QUE frase esta mal. Un numero no se puede auditar; una
cita si: abris el mensaje y la buscas.

POR QUE JEV Y NO LAYA
Se probaron las dos contra casos_prueba.py el 01-02/10/2026: Laya 3 de 7,
Jev 7 de 7. El detalle esta en AGENTS.md. Resumen: Laya reconoce palabras
y Jev entiende frases, y este validador necesita lo segundo.

REGLA DE DISENO
El modelo reporta el HECHO; reglas.py decide si el hecho es un problema.
Mencionar reparto es cierto en Palmares, San Ramon y Naranjo y falso en
el resto -- eso lo decide el codigo, no el modelo. Asi el contrato vive
en un solo lugar.

Requiere en el .env:
    TYPESAFE_API_KEY
    ANTHROPIC_API_KEY
"""

import json
import os
import sys

from dotenv import load_dotenv

from bitacora import anotar_calibracion
from casos_prueba import CASOS_PRUEBA, esperado_valido
from reglas import MAX_PALABRAS, contexto_para, prohibidas_para, tiene_reparto_propio

load_dotenv()

# CON LOS 8 CASOS ORIGINALES el umbral no era delicado: margenes de
# +0.84, y 0.4, 0.5 o 0.6 daban el mismo resultado.
#
# ESO DEJO DE SER CIERTO EL 22/10/2026, al ampliar el banco a 19.
# Cinco dimensiones siguen con margen enorme (0.90+ contra 0.05). La
# sexta, afirma_logistica, no:
#
#     reparto FUERA de la zona       0.97   falla, correcto
#     anuncia que va a abrir         0.61   falla, correcto
#     dice salchicha ("pasemos a
#       dejar una muestra")          0.55   falla por regla, no por esto
#     nombra el canton               0.48   PASA, por dos centesimas
#
# O sea: con 0.45 el banco daria 18 de 19, y con 0.55 tambien.
#
# La causa no es el umbral: es que la pregunta de afirma_logistica
# dice "o cercania geografica al negocio" y trata igual dos cosas que
# no lo son -- afirmar que el negocio queda alcanzable (si es
# logistica) y decir donde esta (no lo es).
#
# No se toco todavia, a proposito: cambiar esa instruccion mueve los
# SEIS casos que dependen de ella, incluidos los de 0.97 y 0.98. Se
# deja medido y escrito. Si un dia la calibracion baja sin que nadie
# toque nada, este es el primer lugar donde mirar.
UMBRAL = 0.5


# ─────────────────────────────────────────────────────────────────
# CAPA 1 — reglas
# ─────────────────────────────────────────────────────────────────

def capa_1_reglas(mensaje, negocio):
    """Lo que se puede escribir como regla no necesita modelo."""
    fallos = []
    texto = mensaje.lower()

    for palabra in prohibidas_para(negocio):
        if palabra in texto:
            fallos.append(f"contiene '{palabra}'")

    palabras = len(mensaje.split())
    if palabras > MAX_PALABRAS:
        fallos.append(f"{palabras} palabras (max {MAX_PALABRAS})")

    if texto.count("?") > 1:
        fallos.append("mas de una pregunta")

    return fallos


# ─────────────────────────────────────────────────────────────────
# CAPA 2 — Jev
# ─────────────────────────────────────────────────────────────────

def _preguntas():
    from typesafe_sdk import Noul

    return {
        "afirma_logistica": Noul(
            instructions="El mensaje afirma o insinua algo sobre reparto, "
                         "rutas, zonas de cobertura, dias u horarios de "
                         "entrega, o cercania geografica al negocio"),
        "afirma_capacidad": Noul(
            instructions="El mensaje afirma algo sobre volumen de "
                         "produccion, capacidad de suministro, precios, "
                         "plazos de pago o minimos de pedido"),
        "afirma_certificaciones": Noul(
            instructions="El mensaje menciona certificaciones, registro "
                         "sanitario, permisos o cumplimiento normativo"),
        "menciona_clientes": Noul(
            instructions="El mensaje menciona a otros negocios como "
                         "clientes actuales, o dice a quien mas se le vende"),
        "inventa_productos": Noul(
            instructions="El mensaje menciona productos distintos del "
                         "salchichon criollo y sus cuatro variedades"),
        # Pregunta POSITIVA: en un mensaje bueno deberia dar alto.
        # En la calibracion separo sola: 0.03-0.12 en los malos,
        # 0.82-0.89 en los buenos.
        "todo_respaldado": Noul(
            instructions="Cada afirmacion del mensaje esta respaldada "
                         "literalmente por el contexto de la fabrica"),
    }


# "afirma_logistica" NO esta aca: no decide sola, depende del canton.
ROJAS = [
    ("afirma_capacidad", "promete capacidad o plazos"),
    ("afirma_certificaciones", "afirma certificaciones"),
    ("menciona_clientes", "menciona clientes actuales"),
    ("inventa_productos", "producto que no se fabrica"),
]


def capa_2_jev(cliente, mensaje, negocio):
    """Devuelve las banderas encendidas y todas las dimensiones."""
    estado = (
        f"CONTEXTO DE LA FABRICA (unica fuente de verdad):\n"
        f"{contexto_para(negocio)}\n"
        f"NEGOCIO DESTINATARIO: {negocio.get('nombre', '')}\n"
        f"CANTON: {negocio.get('canton', 'desconocido')}\n\n"
        f"MENSAJE A EVALUAR:\n{mensaje}"
    )

    r = cliente.system_one(state=estado, questions=_preguntas())
    dims = {k: getattr(r.answers[k], "noul", 0.0) for k in _preguntas()}

    banderas = [etiqueta for clave, etiqueta in ROJAS
                if dims[clave] > UMBRAL]

    # El modelo reporta el hecho; el codigo decide si es problema.
    if dims["afirma_logistica"] > UMBRAL and not tiene_reparto_propio(negocio):
        banderas.append("logistica fuera de zona propia")

    if dims["todo_respaldado"] < UMBRAL:
        banderas.append("hay algo sin respaldo")

    return banderas, dims


# ─────────────────────────────────────────────────────────────────
# CAPA 3 — Claude, solo para los marcados
# ─────────────────────────────────────────────────────────────────

def capa_3_citas(mensaje, negocio):
    """La frase exacta de cada bandera, para que una persona la busque.

    Solo se llama cuando la capa 2 marco algo. Si falla tecnicamente, no
    se cae la validacion: el veredicto ya esta tomado, esto solo explica.
    """
    try:
        from validar_claude import validar as claude_validar
        return claude_validar(mensaje, negocio)["banderas"]
    except Exception as e:
        return [("sin citas", f"{type(e).__name__}: {str(e)[:80]}")]


# ─────────────────────────────────────────────────────────────────

def validar(cliente, mensaje, negocio, con_citas=True):
    negocio = negocio or {}

    fallos_regla = capa_1_reglas(mensaje, negocio)
    banderas, dims = capa_2_jev(cliente, mensaje, negocio)

    valido = not banderas and not fallos_regla

    citas = []
    if not valido and con_citas:
        citas = capa_3_citas(mensaje, negocio)

    return {
        "valido": valido,
        "fallos_regla": fallos_regla,
        "banderas": banderas,
        "citas": citas,
        "dimensiones": dims,
    }


def imprimir(titulo, r):
    print(f"\n[{'OK     ' if r['valido'] else 'REVISAR'}] {titulo}")

    for f in r["fallos_regla"]:
        print(f"   regla:    {f}")
    for b in r["banderas"]:
        print(f"   bandera:  {b}")
    for etiqueta, cita in r["citas"]:
        print(f"   {etiqueta}: \"{cita}\"")

    print("   " + "  ".join(f"{k[:14]}={v:.2f}"
                            for k, v in r["dimensiones"].items()))


if __name__ == "__main__":
    for llave in ("TYPESAFE_API_KEY", "ANTHROPIC_API_KEY"):
        if not os.getenv(llave):
            sys.exit(f"Falta {llave} en el .env")

    from typesafe_sdk import TypeSafeClient
    cliente = TypeSafeClient()

    modo = sys.argv[1] if len(sys.argv) > 1 else "archivo"

    if modo == "prueba":
        print("Calibracion contra casos_prueba.py")
        print("Cinco DEBEN salir REVISAR; dos, OK.\n")

        aciertos = 0
        fallados = []
        for titulo, negocio, mensaje in CASOS_PRUEBA:
            r = validar(cliente, mensaje, negocio)
            ok = r["valido"] == esperado_valido(titulo)
            aciertos += ok
            if not ok:
                fallados.append(titulo)
            imprimir(f"{'' if ok else '>>> NO COINCIDE <<< '}{titulo}", r)

        print(f"\n{'=' * 56}")
        print(f"Aciertos: {aciertos} de {len(CASOS_PRUEBA)}")

        # Esta linea cuesta centavos y se puede correr hoy, con el
        # pipeline en pausa. Es la unica medicion del proyecto que
        # tiene historia desde ya.
        anotar_calibracion(aciertos, len(CASOS_PRUEBA), fallados)

        if aciertos < len(CASOS_PRUEBA):
            print("\nAlgo cambio: el modelo, el prompt o las reglas.")
            print("No corras el pipeline hasta entender que.")
        sys.exit(0 if aciertos == len(CASOS_PRUEBA) else 1)

    with open("prospectos_calificados.json", encoding="utf-8") as f:
        datos = json.load(f)

    con_mensaje = [d for d in datos if d.get("mensaje")]
    if not con_mensaje:
        sys.exit("No hay mensajes que validar.")

    print(f"Validando {len(con_mensaje)} mensajes\n")

    for d in con_mensaje:
        r = validar(cliente, d["mensaje"], d)
        imprimir(d.get("nombre", ""), r)

        d["validacion"] = "ok" if r["valido"] else "revisar"
        d["validacion_detalle"] = "; ".join(
            r["fallos_regla"] + r["banderas"]
            + [f"{e}: {c}" for e, c in r["citas"]]
        )

    malos = [d for d in con_mensaje if d["validacion"] == "revisar"]
    print(f"\n{len(malos)} de {len(con_mensaje)} necesitan revision")
    print(f"Claude corrio sobre {len(malos)}, no sobre {len(con_mensaje)}")

    with open("prospectos_calificados.json", "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
