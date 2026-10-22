"""
Capa 3 del validador: la frase exacta.

NO se corre solo. Lo llama validar.py, y solo para los mensajes que la
capa 2 (Jev) marco. Correrlo sobre todos seria pagar el modelo caro para
confirmar lo que ya sabemos.

QUE APORTA QUE LAS OTRAS CAPAS NO
Jev devuelve un numero: "menciona_clientes = 0.95". Eso alcanza para
DECIDIR, pero no para que una persona revise. Quien abre la hoja necesita
saber QUE frase esta mal.

Esta capa devuelve la cita textual. Se busca en el mensaje y aparece.

POR QUE CITAS Y NO NUMEROS
Claude no esta calibrado: si le pido una probabilidad, escribe una que
suena razonable y no corresponde a lo que sabe. Fue el problema de las
cinco sucursales de Carnes Castillo -- datos casi identicos, confianza
alta, veredictos distintos.

Una cita si es verificable: si el modelo la inventa, se nota al buscarla
en el mensaje. Un 0.73 inventado, no.

(Jev si esta calibrado, y por eso el numero quedo en la capa 2 y la cita
en esta. Cada una hace lo que puede sostener.)
"""

import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from reglas import como_dato, contexto_para

load_dotenv()

MODELO = "claude-sonnet-4-6"


class Veredicto(BaseModel):
    """Cada campo pide la frase textual, no un si/no ni un puntaje.

    Cadena vacia = no encontro nada. Si encuentra algo, tiene que poder
    copiarlo del mensaje, lo que hace el veredicto auditable.
    """

    logistica: str = Field(
        description="Frase EXACTA del mensaje que afirma o insinua algo "
        "sobre reparto, rutas, zonas de cobertura, dias u horarios de "
        "entrega, o cercania al negocio. Vacio si no hay ninguna."
    )
    capacidad: str = Field(
        description="Frase EXACTA que afirma algo sobre volumen de "
        "produccion, capacidad de suministro, precios, plazos de pago o "
        "minimos de pedido. Vacio si no hay ninguna."
    )
    certificaciones: str = Field(
        description="Frase EXACTA que menciona certificaciones, registro "
        "sanitario, permisos o cumplimiento normativo. Vacio si no hay."
    )
    clientes: str = Field(
        description="Frase EXACTA que menciona a otros negocios como "
        "clientes actuales o dice a quien mas se le vende. Vacio si no hay."
    )
    productos: str = Field(
        description="Frase EXACTA que menciona un producto distinto del "
        "salchichon criollo y sus cuatro variedades. Vacio si no hay."
    )
    otro_invento: str = Field(
        description="Cualquier OTRA afirmacion del mensaje que no se lea "
        "literalmente en el contexto de la fabrica, citada textual. "
        "Vacio si todo lo demas esta respaldado."
    )
    suena_a_marketing: bool = Field(
        description="True si suena a folleto publicitario en vez de a un "
        "productor de la zona escribiendo un WhatsApp."
    )


BANDERAS = [
    ("logistica", "afirma logistica"),
    ("capacidad", "afirma capacidad o precios"),
    ("certificaciones", "menciona certificaciones"),
    ("clientes", "menciona clientes actuales"),
    ("productos", "inventa productos"),
    ("otro_invento", "afirma algo sin respaldo"),
]

PROMPT = """\
Sos el revisor de mensajes de esta fabrica. Otro modelo escribio el
mensaje; tu trabajo es encontrar lo que afirma sin respaldo.

CONTEXTO DE LA FABRICA (unica fuente de verdad):
{contexto}

Regla: el mensaje solo puede afirmar hechos que se lean LITERALMENTE en
ese contexto. Cualquier otra cosa es un invento, por razonable que
suene, y aunque se pueda deducir de los datos del negocio.

Para cada categoria, copia la frase EXACTA del mensaje que la enciende.
No parafrasees: copia el texto tal cual, para que quien revise pueda
buscarlo. Si no hay nada en esa categoria, deja la cadena vacia.

No marques como invento el nombre de la fabrica, los 26 anos, Palmares,
el ahumado en lena, ni las cuatro variedades: todo eso esta en el
contexto. Tampoco marques saludos, cortesias ni la pregunta final.
"""


def _modelo():
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("Falta ANTHROPIC_API_KEY.")
    # temperature=0: un revisor que cambia de opinion entre corridas no
    # sirve como control de calidad.
    return ChatAnthropic(
        model=MODELO, max_tokens=1500, temperature=0
    ).with_structured_output(Veredicto)


def armar_entrada(mensaje, negocio):
    """El texto que ve el revisor. Separado para poder probarlo.

    PUNTO 25 (14/10/2026). El nombre del negocio entra al pipeline DOS
    veces: cuando se redacta (grafo.py) y cuando se revisa, aca. Viene
    de Google Places, o sea lo escribio un tercero.

    Sin como_dato(), un nombre con un salto de linea adentro agregaba
    una linea a este bloque, y una linea que empieza sola se lee como
    instruccion. Cerrar solo la mitad del redactor no cerraba nada.

    El mensaje NO se limpia: lo escribio nuestro propio redactor y los
    saltos de linea son parte del texto que hay que revisar. Si el
    redactor saliera inyectado, lo que marca eso es el veredicto, no la
    forma del prompt.
    """
    return (
        f"NEGOCIO DESTINATARIO: {como_dato(negocio.get('nombre', ''))}\n"
        f"CANTON: {como_dato(negocio.get('canton')) or 'desconocido'}\n\n"
        f"MENSAJE A REVISAR:\n{mensaje}"
    )


def validar(mensaje, negocio=None):
    """Devuelve las banderas encendidas, cada una con su cita textual.

    negocio: el dict del negocio. Hace falta el canton, porque el
    contexto que ve el revisor tiene que ser EL MISMO que vio el
    redactor. Si midiera contra otro, marcaria como invento algo cierto.
    """
    negocio = negocio or {}
    entrada = armar_entrada(mensaje, negocio)

    try:
        v = _modelo().invoke([
            ("system", PROMPT.format(contexto=contexto_para(negocio))),
            ("user", entrada),
        ])
    except Exception as e:
        # No se cae la validacion: el veredicto ya lo tomo la capa 2.
        # Esto solo lo explica, asi que un fallo tecnico se reporta
        # como una bandera mas y sigue.
        return {
            "banderas": [("error tecnico", str(e)[:120])],
            "marketing": False,
        }

    encendidas = []
    for campo, etiqueta in BANDERAS:
        cita = (getattr(v, campo) or "").strip()
        if cita:
            encendidas.append((etiqueta, cita))

    return {
        "banderas": encendidas,
        "marketing": v.suena_a_marketing,
    }