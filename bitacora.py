"""Una linea por corrida, a un archivo que no se borra.

    python bitacora.py              # el historial, mas reciente abajo
    python bitacora.py calibracion  # solo las corridas del validador

Punto 15 de la hoja de ruta. Antes de esto, grafo.py imprimia
"reescritos: 3" al terminar y ese numero se perdia al cerrar la
terminal. No habia forma de contestar "subio o bajo desde que cambie
la regla", que es exactamente la pregunta que importa.

Tres decisiones que conviene no deshacer:

1. **El numero que se imprime y el que se guarda son el mismo numero.**
   `medir()` es la unica definicion de "reescrito" y "agotado" en el
   proyecto; `resumen()` en grafo.py imprime desde ese dict. Si las
   dos cuentas vivieran en dos lados, en tres meses no coincidirian y
   no habria manera de saber cual de las dos miente.

2. **No se guarda ni un nombre de negocio.** Solo conteos y etiquetas
   de problema ("falta el canton", "reparto"). Las etiquetas las
   escribio este proyecto; los nombres son de terceros. Un nombre aca
   convertiria la bitacora en dato ajeno y le cambiaria el lugar donde
   puede vivir: hoy el archivo se puede leer, pegar en una entrevista
   o subir a un repositorio sin pensarlo dos veces.

3. **Escribir nunca rompe una corrida.** `anotar()` se come cualquier
   error. Una corrida de grafo.py cuesta dinero de verdad; perderla
   porque el disco estaba lleno seria absurdo. Medir es secundario a
   lo que se mide.

Formato: JSONL, un objeto por linea, solo append. Un campo nuevo
manana no invalida las lineas de hoy, y `historial()` salta una linea
corrupta en vez de morir.
"""

import json
import os
from collections import Counter
from datetime import datetime

ARCHIVO = os.getenv("BITACORA", "bitacora.jsonl")


# ─────────────────────────────────────────────────────────────────
# Medir
# ─────────────────────────────────────────────────────────────────

def medir(resultados: list, max_intentos: int) -> dict:
    """Las cuentas de una corrida del pipeline.

    `max_intentos` entra por argumento y no se importa de grafo.py a
    proposito: grafo.py importa este modulo, y al contrario seria un
    ciclo. El tope es politica del grafo, no de la bitacora.
    """
    con_mensaje = [r for r in resultados if r.get("mensaje")]
    ok = [r for r in con_mensaje if r.get("validacion") == "ok"]
    reescritos = [r for r in con_mensaje if (r.get("intentos") or 1) > 1]
    agotados = [r for r in con_mensaje
                if (r.get("intentos") or 0) >= max_intentos
                and r.get("validacion") != "ok"]

    problemas = Counter()
    for r in resultados:
        for p in r.get("problemas") or []:
            problemas[p] += 1

    return {
        "negocios": len(resultados),
        "calificacion": dict(Counter(r.get("calificacion")
                                     for r in resultados)),
        "con_mensaje": len(con_mensaje),
        "validados": len(ok),
        "reescritos": len(reescritos),
        "agotados": len(agotados),
        "problemas": dict(problemas.most_common()),
    }


# ─────────────────────────────────────────────────────────────────
# Escribir
# ─────────────────────────────────────────────────────────────────

def anotar(evento: str, datos: dict) -> bool:
    """Una linea. Devuelve si se escribio, sin levantar nada."""
    linea = {"cuando": datetime.now().isoformat(timespec="seconds"),
             "evento": evento, **datos}
    try:
        with open(ARCHIVO, "a", encoding="utf-8") as f:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        print(f"  (no se pudo anotar en {ARCHIVO}: {type(e).__name__})")
        return False


def anotar_corrida(resultados: list, modo: str, max_intentos: int,
                   tope=None, provincia=None) -> bool:
    """Lo que dejo una corrida de grafo.py.

    La provincia va en la linea (punto 30) porque sin ella dos
    corridas no son comparables: una tanda nacional y una de Alajuela
    tienen poblaciones distintas, y la tasa de reescritura de la
    primera no dice nada sobre la segunda.
    """
    return anotar("corrida", {"modo": modo, "tope": tope,
                              "provincia": provincia,
                              **medir(resultados, max_intentos)})


def anotar_calibracion(aciertos: int, total: int, fallados: list) -> bool:
    """Lo que dejo `validar.py prueba`.

    Vale aparte porque cuesta centavos: la calibracion deja datos
    todos los dias aunque el pipeline este en pausa, y es la que
    contesta "se movio el validador cuando toque esa regla".
    """
    return anotar("calibracion", {"aciertos": aciertos, "casos": total,
                                  "fallados": fallados})


# ─────────────────────────────────────────────────────────────────
# Leer
# ─────────────────────────────────────────────────────────────────

def historial(evento=None) -> list:
    """Las lineas del archivo, en orden. Salta las corruptas."""
    if not os.path.exists(ARCHIVO):
        return []

    lineas = []
    with open(ARCHIVO, encoding="utf-8") as f:
        for cruda in f:
            cruda = cruda.strip()
            if not cruda:
                continue
            try:
                linea = json.loads(cruda)
            except json.JSONDecodeError:
                continue
            if evento is None or linea.get("evento") == evento:
                lineas.append(linea)
    return lineas


def _fecha(linea):
    return (linea.get("cuando") or "")[:16].replace("T", " ")


def imprimir_corridas(lineas: list) -> None:
    print(f"  {'cuando':16} {'modo':9} {'provincia':11} {'neg':>4} "
          f"{'msj':>4} {'val':>4} {'reesc':>6} {'agot':>5}  problema")
    for l in lineas:
        top = next(iter(l.get("problemas") or {}), "")
        print(f"  {_fecha(l):16} {str(l.get('modo') or ''):9} "
              f"{str(l.get('provincia') or '(todo el pais)'):11} "
              f"{l.get('negocios', 0):4} {l.get('con_mensaje', 0):4} "
              f"{l.get('validados', 0):4} {l.get('reescritos', 0):6} "
              f"{l.get('agotados', 0):5}  {top[:26]}")


def imprimir_calibraciones(lineas: list) -> None:
    print(f"  {'cuando':16} {'aciertos':>8}  casos que fallaron")
    for l in lineas:
        marca = "" if l.get("aciertos") == l.get("casos") else "  <-- "
        print(f"  {_fecha(l):16} "
              f"{l.get('aciertos', 0)} de {l.get('casos', 0):<4}"
              f"{marca}{', '.join(l.get('fallados') or [])[:46]}")


if __name__ == "__main__":
    import sys

    cual = sys.argv[1] if len(sys.argv) > 1 else "todo"
    todo = historial()

    if not todo:
        print(f"{ARCHIVO} no existe todavia.\n"
              f"Se escribe solo, al terminar `grafo.py` o "
              f"`validar.py prueba`.")
        sys.exit(0)

    corridas = [l for l in todo if l.get("evento") == "corrida"]
    calibraciones = [l for l in todo if l.get("evento") == "calibracion"]

    if cual in ("todo", "corrida", "corridas") and corridas:
        print(f"\nCorridas del pipeline ({len(corridas)})\n")
        imprimir_corridas(corridas)

    if cual in ("todo", "calibracion", "calibraciones") and calibraciones:
        print(f"\nCalibraciones del validador ({len(calibraciones)})\n")
        imprimir_calibraciones(calibraciones)

    print()
