"""
Herramienta: buscar_negocios(zona, tipo)
Consulta Google Places API (New) y devuelve una lista de negocios.

Requiere un archivo .env en la misma carpeta con:
    GOOGLE_PLACES_API_KEY=tu_clave_aqui
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
URL = "https://places.googleapis.com/v1/places:searchText"

# Places API (New) cobra segun los campos pedidos.
# Telefono, rating y sitio web caen en tier Enterprise: 1,000 gratis/mes.
CAMPOS = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.primaryTypeDisplayName",
    "places.rating",
    "places.userRatingCount",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.businessStatus",
])


def buscar_negocios(zona, tipo, max_resultados=20):
    """Busca negocios de un tipo en una zona."""
    if not API_KEY:
        raise RuntimeError(
            "Falta GOOGLE_PLACES_API_KEY. Revisa el archivo .env."
        )

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": CAMPOS,
    }

    body = {
        "textQuery": f"{tipo} en {zona}",
        "languageCode": "es",
        "regionCode": "CR",
        "maxResultCount": max_resultados,
    }

    respuesta = requests.post(URL, headers=headers, json=body, timeout=20)

    if respuesta.status_code != 200:
        raise RuntimeError(
            f"Places API devolvio {respuesta.status_code}: "
            f"{respuesta.text[:300]}"
        )

    resultados = []
    for lugar in respuesta.json().get("places", []):
        resultados.append({
            "place_id": lugar.get("id"),
            "nombre": lugar.get("displayName", {}).get("text"),
            "direccion": lugar.get("formattedAddress"),
            "categoria": lugar.get("primaryTypeDisplayName", {}).get("text"),
            "telefono": lugar.get("nationalPhoneNumber"),
            "sitio_web": lugar.get("websiteUri"),
            "estado": lugar.get("businessStatus"),
            "rating": lugar.get("rating"),
            "num_resenas": lugar.get("userRatingCount"),
            "lat": lugar.get("location", {}).get("latitude"),
            "lng": lugar.get("location", {}).get("longitude"),
            "zona_busqueda": zona,
            "tipo_busqueda": tipo,
        })

    return resultados


if __name__ == "__main__":
    negocios = buscar_negocios("Grecia, Alajuela, Costa Rica", "carnicerias")
    print(f"Encontrados: {len(negocios)}\n")
    for n in negocios:
        print(f"- {n['nombre']}")
        print(f"  tel: {n['telefono']} | web: {n['sitio_web']}")