import json
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

APIQROO_URL = "https://servicios.apiqroo.com.mx/programacion/?unit=m"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def clean_ship_name(name):
    name = re.sub(r"^(M/S|M/V)\s+", "", name.strip(), flags=re.I)
    return name.strip()


def normalize_ship(name):
    name = clean_ship_name(name)
    return re.sub(r"[^a-z0-9]", "", name.lower())


def get_apiqroo():
    response = requests.get(APIQROO_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text(" ", strip=True)

    cruises = {}

    # Busca fechas del tipo "07/09/2026"
    dates = re.findall(r"\b\d{1,2}/\d{1,2}/\d{4}\b", text)

    # Intento de lectura de tablas
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = [
                c.get_text(" ", strip=True)
                for c in row.find_all(["td", "th"])
            ]

            if len(cells) < 3:
                continue

            row_text = " | ".join(cells)

            date_match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", row_text)
            time_matches = re.findall(r"\b\d{1,2}:\d{2}\b", row_text)

            if not date_match or len(time_matches) < 2:
                continue

            date_obj = datetime.strptime(
                date_match.group(1), "%d/%m/%Y"
            )

            ship = None
            terminal = None

            for cell in cells:
                upper = cell.upper()

                if "TERMINAL" in upper:
                    terminal = cell.strip()

                if "M/S" in upper or "M/V" in upper:
                    ship = clean_ship_name(cell)

            if not ship:
                continue

            day = date_obj.strftime("%Y-%m-%d")

            if day not in cruises:
                cruises[day] = []

            cruises[day].append({
                "terminal": terminal or "SIN TERMINAL",
                "ship": ship,
                "arrival": time_matches[0],
                "departure": time_matches[1],
                "passengers": 0
            })

    return cruises


def get_cruise_timetables():
    now = datetime.now()

    month = now.strftime("%b").lower()
    year = now.strftime("%Y")

    url = (
        f"https://www.cruisetimetables.com/"
        f"cozumelmexicoschedule-{month}{year}.html"
    )

    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text("\n", strip=True)

    passengers = {}

    # Busca cantidades de pasajeros cercanas a nombres de barcos
    pattern = re.compile(
        r"([A-Za-z0-9' .-]+?)\s+"
        r"(\d[\d,]{2,})\s*(?:passengers|pax)",
        re.I
    )

    for match in pattern.finditer(text):
        ship = clean_ship_name(match.group(1))
        value = int(match.group(2).replace(",", ""))

        if len(ship) > 3:
            passengers[normalize_ship(ship)] = value

    return passengers


def main():
    print("Descargando datos de APIQROO...")
    apiqroo = get_apiqroo()

    print("Descargando estimaciones de pasajeros...")
    passenger_data = get_cruise_timetables()

    total_records = 0

    for day, cruises in apiqroo.items():
        for cruise in cruises:
            key = normalize_ship(cruise["ship"])

            if key in passenger_data:
                cruise["passengers"] = passenger_data[key]

            total_records += 1

    output = {
        "lastUpdated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "APIQROO + CruiseTimetables",
        "cruises": apiqroo
    }

    with open("cruise-data.json", "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    print(f"Actualización terminada. Registros: {total_records}")


if __name__ == "__main__":
    main()
