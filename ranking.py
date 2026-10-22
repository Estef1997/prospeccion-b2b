"""
Hoja de ranking por canton.

Crea una pestana "Ranking por canton" en la misma hoja de Sheets,
con un resumen arriba y despues los negocios de cada canton
ordenados por puntaje.

Trabaja sobre prospectos_crudo.json (los 629), no sobre lo calificado,
porque solo 128 pasaron por el grafo y un ranking con eso daria una
imagen falsa de cada canton.

Uso:
    python ranking.py
"""

import json
from collections import defaultdict

import gspread
from google.oauth2.service_account import Credentials

HOJA = "Prospectos Embutidos Artesanales"
PESTANA = "Ranking por canton"
CREDENCIALES = "credenciales.json"

ALCANCES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Cuantos negocios mostrar por canton.
TOPE = 15

# Categorias que cuentan como oportunidad real de reventa.
# Las carnicerias van aparte: pueden ser cliente o competencia.
CATEGORIAS_REVENTA = {
    "Supermercado", "Hipermercado", "Supermercado de descuentos",
    "Supermercado asiático", "Mayorista", "Mercado",
    "Tienda de alimentación",
}


def conectar():
    creds = Credentials.from_service_account_file(
        CREDENCIALES, scopes=ALCANCES
    )
    return gspread.authorize(creds).open(HOJA)


def agrupar(datos):
    """Por canton, solo lo que puede ser prospecto."""
    grupos = defaultdict(list)
    for d in datos:
        if d.get("fuera_de_rubro") or d.get("cerrado"):
            continue
        grupos[d.get("canton") or "Sin canton"].append(d)

    for canton in grupos:
        grupos[canton].sort(key=lambda x: x.get("puntaje") or 0,
                            reverse=True)
    return grupos


def resumen_cantones(grupos):
    """Una fila por canton: cuantos de cada tipo y el puntaje del mejor.

    Sirve para ver de un vistazo donde concentrar esfuerzo.
    """
    filas = [[
        "Canton", "Total", "Reventa", "Carnicerias", "Clientes",
        "Mejor puntaje", "Mejor negocio",
    ]]

    resumen = []
    for canton, negocios in grupos.items():
        reventa = [n for n in negocios
                   if n.get("categoria") in CATEGORIAS_REVENTA
                   and not n.get("es_cliente")]
        carnes = [n for n in negocios
                  if n.get("categoria") == "Carnicería"]
        clientes = [n for n in negocios if n.get("es_cliente")]

        mejor = reventa[0] if reventa else (negocios[0] if negocios else None)

        resumen.append({
            "canton": canton,
            "fila": [
                canton,
                len(negocios),
                len(reventa),
                len(carnes),
                len(clientes),
                round(mejor.get("puntaje") or 0, 1) if mejor else 0,
                (mejor.get("nombre") or "") if mejor else "",
            ],
            "orden": len(reventa),
        })

    # Mas oportunidades de reventa primero.
    resumen.sort(key=lambda x: x["orden"], reverse=True)
    filas.extend([r["fila"] for r in resumen])
    return filas, [r["canton"] for r in resumen]


def detalle_cantones(grupos, orden):
    filas = []
    for canton in orden:
        negocios = grupos[canton]
        reventa = [n for n in negocios
                   if n.get("categoria") in CATEGORIAS_REVENTA]

        filas.append([])
        filas.append([f"=== {canton.upper()} ==="])
        filas.append([
            "Negocio", "Categoria", "Puntaje", "Resenas",
            "Telefono", "Km", "Marca",
        ])

        for n in reventa[:TOPE]:
            marcas = []
            if n.get("es_cliente"):
                marcas.append("CLIENTE")
            if n.get("es_cadena"):
                marcas.append("cadena")
            if n.get("posible_competidor"):
                marcas.append("posible competidor")

            filas.append([
                n.get("nombre") or "",
                n.get("categoria") or "",
                round(n.get("puntaje") or 0, 1),
                n.get("num_resenas") or 0,
                n.get("telefono") or "",
                n.get("distancia_km") or "",
                ", ".join(marcas),
            ])

        if len(reventa) > TOPE:
            filas.append([f"... y {len(reventa) - TOPE} mas en este canton"])

    return filas


def main():
    with open("prospectos_crudo.json", encoding="utf-8") as f:
        datos = json.load(f)

    grupos = agrupar(datos)
    resumen, orden = resumen_cantones(grupos)
    detalle = detalle_cantones(grupos, orden)

    libro = conectar()
    try:
        hoja = libro.worksheet(PESTANA)
        hoja.clear()
    except gspread.WorksheetNotFound:
        hoja = libro.add_worksheet(PESTANA, rows=1000, cols=10)

    filas = [["RESUMEN POR CANTON"], []] + resumen + [[], []] + detalle
    hoja.update(values=filas, range_name="A1")

    hoja.format("A1", {"textFormat": {"bold": True, "fontSize": 12}})
    hoja.format("A3:G3", {"textFormat": {"bold": True}})
    hoja.freeze(rows=3)

    print(f"Cantones: {len(grupos)}")
    print(f"Negocios en el ranking: "
          f"{sum(len(v) for v in grupos.values())}")
    print(f"\nEscrito en la pestana '{PESTANA}'")
    print(f"URL: {libro.url}")


if __name__ == "__main__":
    main()