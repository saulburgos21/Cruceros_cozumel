import json
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup


APIQROO_URL = "https://servicios.apiqroo.com.mx/programacion/?unit=m"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def normalizar_barco(nombre):
    nombre = nombre.upper().strip()
    nombre = re.sub(r"^(M/S|M/V)\s+", "", nombre)
    nombre = re.sub(r"\s+", " ", nombre)
    return nombre


def obtener_apiqroo():

    r = requests.get(
        APIQROO_URL,
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # Convertimos la página en texto, conservando cada línea
    texto = soup.get_text("\n", strip=True)
    lineas = [x.strip() for x in texto.splitlines() if x.strip()]

    cruceros = {}

    for linea in lineas:

        # Ejemplo:
        # TERMINAL PUERTA MAYA | ... | M/S CARNIVAL VALOR |
        # 7/09/2026 | 06:30 | 7/09/2026 | 16:00

        if "TERMINAL " not in linea.upper():
            continue

        fecha = re.search(
            r"(\d{1,2})/(\d{1,2})/(\d{4})",
            linea
        )

        if not fecha:
            continue

        horarios = re.findall(
            r"\b\d{1,2}:\d{2}\b",
            linea
        )

        if len(horarios) < 2:
            continue

        terminal_match = re.search(
            r"(TERMINAL\s+(?:SSA\s+MEXICO|PUERTA\s+MAYA|PUNTA\s+LANGOSTA))",
            linea,
            re.I
        )

        if not terminal_match:
            continue

        terminal = terminal_match.group(1).upper()

        # Todo lo que aparece después del texto de bandera
        # y antes de la fecha corresponde al barco.
        partes = [x.strip() for x in linea.split("|")]

        barco = None

        for parte in partes:

            p = parte.strip()

            if re.search(
                r"\b(M/S|M/V)\b",
                p,
                re.I
            ):
                barco = re.sub(
                    r"^(M/S|M/V)\s+",
                    "",
                    p,
                    flags=re.I
                ).strip()
                break

            # Algunos barcos aparecen sin M/S o M/V
            conocidos = [
                "MARINER OF THE SEAS",
                "RADIANCE OF THE SEAS",
                "ENCHANTMENT OF THE SEAS",
                "CELEBRITY BEYOND",
                "ICON OF THE SEAS"
            ]

            if p.upper() in conocidos:
                barco = p
                break

        if not barco:
            continue

        dia = datetime.strptime(
            fecha.group(0),
            "%d/%m/%Y"
        ).strftime("%Y-%m-%d")

        registro = {
            "terminal": terminal,
            "ship": normalizar_barco(barco),
            "arrival": horarios[0],
            "departure": horarios[1],
            "passengers": 0
        }

        if dia not in cruceros:
            cruceros[dia] = []

        # Evitar duplicados
        existe = any(
            x["terminal"] == registro["terminal"]
            and x["ship"] == registro["ship"]
            and x["arrival"] == registro["arrival"]
            and x["departure"] == registro["departure"]
            for x in cruceros[dia]
        )

        if not existe:
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

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    texto = soup.get_text("\n", strip=True)
    lineas = [x.strip() for x in texto.splitlines() if x.strip()]

    pasajeros = {}

    barcos = [
        "Carnival Paradise",
        "Harmony Of The Seas",
        "Mariner Of The Seas",
        "Carnival Breeze",
        "Icon Of The Seas",
        "MSC Seashore",
        "Carnival Jubilee",
        "Celebrity Beyond",
        "Enchantment Of The Seas",
        "Radiance Of The Seas",
        "Regal Princess",
        "Symphony Of The Seas",
        "Carnival Celebration",
        "Carnival Liberty",
        "MSC Seascape",
        "Carnival Valor",
        "Carnival Dream",
        "MSC World America",
        "Norwegian Prima",
        "Margaritaville At Sea Islander",
        "Mardi Gras",
        "Celebrity Reflection",
        "Star Of The Seas",
        "Disney Treasure",
        "Disney Destiny"
    ]

    for i, linea in enumerate(lineas):

        barco = None

        for nombre in barcos:
            if linea.lower() == nombre.lower():
                barco = nombre
                break

        if not barco:
            continue

        # CruiseTimetables coloca:
        # barco
        # a 0800 d 1600
        # pasajeros

        for siguiente in lineas[i + 1:i + 4]:

            if re.search(
                r"\b\d{4}\b",
                siguiente
            ):
                continue

            numero = re.fullmatch(
                r"\d{3,5}",
                siguiente.replace(",", "")
            )

            if numero:

                valor = int(numero.group())

                if 500 <= valor <= 20000:

                    pasajeros[
                        normalizar_barco(barco)
                    ] = valor

                    break

    return pasajeros


def main():

    print("Obteniendo datos de APIQROO...")

    cruceros = obtener_apiqroo()

    print(
        "Fechas encontradas:",
        len(cruceros)
    )

    total = sum(
        len(x)
        for x in cruceros.values()
    )

    print(
        "Cruceros encontrados:",
        total
    )

    print("Obteniendo pasajeros...")

    pasajeros = obtener_pasajeros()

    relacionados = 0

    for dia in cruceros:

        for crucero in cruceros[dia]:

            clave = normalizar_barco(
                crucero["ship"]
            )

            if clave in pasajeros:

                crucero["passengers"] = pasajeros[clave]
                relacionados += 1

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
        "Pasajeros relacionados:",
        relacionados
    )

    print("Actualización terminada.")


if __name__ == "__main__":
    main()
