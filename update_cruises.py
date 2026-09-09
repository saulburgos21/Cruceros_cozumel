import json
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup


APIQROO_URL = "https://servicios.apiqroo.com.mx/programacion/?unit=m"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def limpiar_barco(nombre):
    nombre = nombre.strip()
    nombre = re.sub(r"^(M/S|M/V)\s+", "", nombre, flags=re.I)
    return nombre.strip()


def obtener_apiqroo():
    respuesta = requests.get(
        APIQROO_URL,
        headers=HEADERS,
        timeout=30
    )
    respuesta.raise_for_status()

    soup = BeautifulSoup(respuesta.text, "html.parser")

    cruceros = {}

    # Buscamos todas las tablas de la página
    for tabla in soup.find_all("table"):

        for fila in tabla.find_all("tr"):

            celdas = [
                celda.get_text(" ", strip=True)
                for celda in fila.find_all(["td", "th"])
            ]

            if len(celdas) < 3:
                continue

            texto = " | ".join(celdas)

            # Fecha
            fecha = re.search(
                r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
                texto
            )

            # Horarios
            horarios = re.findall(
                r"\b\d{1,2}:\d{2}\b",
                texto
            )

            if not fecha or len(horarios) < 2:
                continue

            try:
                fecha_obj = datetime.strptime(
                    fecha.group(1),
                    "%d/%m/%Y"
                )
            except ValueError:
                continue

            terminal = None
            barco = None

            for celda in celdas:

                mayusculas = celda.upper()

                if "TERMINAL" in mayusculas:
                    terminal = celda

                if "M/S" in mayusculas or "M/V" in mayusculas:
                    barco = limpiar_barco(celda)

            if not barco:
                continue

            dia = fecha_obj.strftime("%Y-%m-%d")

            if dia not in cruceros:
                cruceros[dia] = []

            registro = {
                "terminal": terminal or "SIN TERMINAL",
                "ship": barco,
                "arrival": horarios[0],
                "departure": horarios[1],
                "passengers": 0
            }

            # Evitar duplicados exactos
            if registro not in cruceros[dia]:
                cruceros[dia].append(registro)

    return cruceros


def obtener_pasajeros():
    ahora = datetime.now()

    mes = ahora.strftime("%b").lower()
    año = ahora.strftime("%Y")

    url = (
        "https://www.cruisetimetables.com/"
        f"cozumelmexicoschedule-{mes}{año}.html"
    )

    respuesta = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )
    respuesta.raise_for_status()

    soup = BeautifulSoup(respuesta.text, "html.parser")

    texto = soup.get_text(" ", strip=True)

    pasajeros = {}

    # Buscamos nombres de barcos seguidos de una cantidad
    patron = re.compile(
        r"(Carnival|Disney|Harmony|Mariner|Icon|MSC|"
        r"Radiance|Symphony|Enchantment|Regal|Celebrity|"
        r"Norwegian|Margaritaville|Mardi Gras|Star)"
        r"[^0-9]{0,100}"
        r"(\d[\d,]{2,})",
        re.I
    )

    for coincidencia in patron.finditer(texto):

        nombre = coincidencia.group(0)

        numero = coincidencia.group(2)

        try:
            cantidad = int(numero.replace(",", ""))
        except ValueError:
            continue

        # Buscamos el nombre del barco dentro del texto encontrado
        nombres = [
            "Carnival Valor",
            "Carnival Paradise",
            "Carnival Breeze",
            "Carnival Jubilee",
            "Carnival Liberty",
            "Carnival Celebration",
            "Disney Treasure",
            "Disney Destiny",
            "Harmony Of The Seas",
            "Mariner Of The Seas",
            "Icon Of The Seas",
            "MSC Seashore",
            "MSC Seascape",
            "MSC World America",
            "Radiance Of The Seas",
            "Symphony Of The Seas",
            "Enchantment Of The Seas",
            "Regal Princess",
            "Celebrity Beyond",
            "Celebrity Reflection",
            "Norwegian Prima",
            "Margaritaville At Sea Islander",
            "Mardi Gras",
            "Star Of The Seas",
            "Carnival Dream"
        ]

        for barco in nombres:

            if barco.lower() in nombre.lower():

                clave = re.sub(
                    r"[^a-z0-9]",
                    "",
                    barco.lower()
                )

                pasajeros[clave] = cantidad

    return pasajeros


def clave_barco(nombre):
    return re.sub(
        r"[^a-z0-9]",
        "",
        nombre.lower()
    )


def main():

    print("Obteniendo programación de APIQROO...")

    cruceros = obtener_apiqroo()

    print("Obteniendo pasajeros de CruiseTimetables...")

    pasajeros = obtener_pasajeros()

    encontrados = 0

    for dia in cruceros:

        for crucero in cruceros[dia]:

            clave = clave_barco(crucero["ship"])

            if clave in pasajeros:

                crucero["passengers"] = pasajeros[clave]

                encontrados += 1

    resultado = {
        "lastUpdated": datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        ),
        "source": "APIQROO + CruiseTimetables",
        "cruises": cruceros
    }

    with open(
        "cruise-data.json",
        "w",
        encoding="utf-8"
    ) as archivo:

        json.dump(
            resultado,
            archivo,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"Actualización terminada. "
        f"Cruceros: {sum(len(x) for x in cruceros.values())}. "
        f"Pasajeros encontrados: {encontrados}."
    )


if __name__ == "__main__":
    main()
