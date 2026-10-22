"""Tracing opcional, con la mascara puesta siempre.

Punto 16 (21/10/2026). Decide UNA cosa: si esta corrida manda trazas a
Langfuse o no. La regla es el .env -- estan las tres llaves, se traza;
no estan, el pipeline corre igual sin enterarse.

Que sea opcional no es comodidad, es una propiedad: el dia que no
quieras depender de un servicio de terceros, borras tres lineas del
.env y nada mas cambia. El grafo no sabe que existe Langfuse.

**La mascara no es opcional.** No hay forma de pedir trazas sin ella:
el cliente se construye con `mascara.enmascarar` y punto. Si fuera una
opcion, algun dia alguien la apagaria "un momentito para depurar" y
ese momentito serian 3.485 telefonos en la nube. Ver mascara.py para
por que eso no es exagerado.

El orden importa y costo una sonda descubrirlo: el cliente se
construye ANTES del CallbackHandler. El handler toma el cliente que ya
exista; si se crea primero, agarra uno sin hook y la mascara queda
decorativa -- sin un solo error en pantalla.
"""

import os

LLAVES = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY",
          "LANGFUSE_BASE_URL")


class Trazador:
    """Lo que grafo.py necesita saber de Langfuse: casi nada."""

    def __init__(self, cliente, handler):
        self._cliente = cliente
        self._handler = handler

    def config(self):
        """Lo que se le pasa a invoke(). Vacio si no hay tracing."""
        return {"callbacks": [self._handler]}

    def cerrar(self):
        """Sin esto el ultimo lote puede quedarse sin salir."""
        try:
            self._cliente.flush()
        except Exception as e:
            print(f"  (no se pudo cerrar el tracing: {type(e).__name__})")


class SinTrazas:
    """El caso normal: nadie configuro Langfuse."""

    def config(self):
        return {}

    def cerrar(self):
        pass


def preparar(avisar=True):
    """Devuelve un Trazador, o SinTrazas si no hay que trazar."""
    faltan = [k for k in LLAVES if not os.getenv(k)]
    if faltan:
        return SinTrazas()

    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
    except ImportError:
        if avisar:
            print("  (hay llaves de Langfuse en el .env pero falta el "
                  "paquete: pip install langfuse langchain)")
        return SinTrazas()

    import mascara

    try:
        # El cliente PRIMERO, con la mascara. Ver el docstring.
        cliente = Langfuse(mask_otel_spans=mascara.enmascarar)
        trazador = Trazador(cliente, CallbackHandler())
    except Exception as e:
        if avisar:
            print(f"  (no se pudo conectar el tracing: "
                  f"{type(e).__name__}; la corrida sigue)")
        return SinTrazas()

    if avisar:
        print(f"  Trazas a {os.getenv('LANGFUSE_BASE_URL')}, "
              f"con mascara.")
    return trazador
