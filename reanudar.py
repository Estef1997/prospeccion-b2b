"""Una corrida interrumpida no se vuelve a pagar.

Punto 10 (22/10/2026). La hoja de ruta pedia un checkpointer
persistente, y al ir a hacerlo aparecio que el problema estaba mal
planteado.

**Dos cosas distintas se pueden perder:**

  - la invocacion en curso -- tres nodos, unos segundos
  - los negocios ya calificados y redactados -- minutos y dinero

Un checkpointer de LangGraph salva la primera. Es la herramienta
correcta cuando un grafo tarda mucho o espera a una persona; este
grafo no hace ninguna de las dos. Lo caro de perder son los cincuenta
negocios que ya se pagaron, y eso es un problema de la TANDA, no del
grafo.

La verificacion que pedia la propia hoja de ruta -- matar el proceso a
mitad de corrida, volver a arrancarlo y que retome donde iba -- solo
la cumple esto.

Como funciona: cada resultado se escribe apenas sale, a un `.parcial`
en JSONL. Al arrancar, si ese archivo existe, los negocios que ya
estan se saltan. Al terminar bien, se borra.

Dos decisiones:

1. **JSONL y no JSON.** Un JSON hay que reescribirlo entero cada vez,
   y si el proceso muere a mitad de esa escritura queda un archivo
   corrupto -- o sea, se pierde todo justo cuando mas importa. Una
   linea por resultado, solo append: lo ya escrito no se vuelve a
   tocar.

2. **La identidad es `place_id`.** Es exacto y lo pone Google; el
   nombre no, porque dos sucursales se llaman igual. Si falta, se cae
   a nombre+canton, que es lo mejor disponible.

Una linea cortada por la muerte del proceso se salta al leer: ese
negocio se vuelve a calificar, que es exactamente lo correcto.
"""

import json
import os


def ruta_parcial(destino):
    """`prospectos_calificados.json` -> `...json.parcial`."""
    return destino + ".parcial"


def clave(negocio):
    """Que hace unico a un negocio. place_id si lo hay."""
    pid = (negocio.get("place_id") or "").strip()
    if pid:
        return pid
    return (f"{negocio.get('nombre') or ''}|"
            f"{negocio.get('canton') or ''}").strip("|")


def hechos(destino):
    """Los resultados ya guardados de una corrida interrumpida."""
    parcial = ruta_parcial(destino)
    if not os.path.exists(parcial):
        return []

    salida = []
    with open(parcial, encoding="utf-8") as f:
        for cruda in f:
            cruda = cruda.strip()
            if not cruda:
                continue
            try:
                salida.append(json.loads(cruda))
            except json.JSONDecodeError:
                # La ultima linea puede estar cortada si el proceso
                # murio escribiendola. Ese negocio se vuelve a hacer.
                continue
    return salida


def pendientes(negocios, ya_hechos):
    """Los que faltan, en el orden original."""
    listos = {clave(r) for r in ya_hechos}
    return [n for n in negocios if clave(n) not in listos]


def anotar(destino, resultado):
    """Un resultado, apenas sale. Nunca rompe la corrida."""
    try:
        with open(ruta_parcial(destino), "a", encoding="utf-8") as f:
            f.write(json.dumps(resultado, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        print(f"  (no se pudo guardar el avance: {type(e).__name__})")
        return False


def terminar(destino):
    """Borra el parcial. Solo cuando la corrida llego al final."""
    parcial = ruta_parcial(destino)
    try:
        if os.path.exists(parcial):
            os.remove(parcial)
    except Exception:
        pass
