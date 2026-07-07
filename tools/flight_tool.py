import os
import re
import certifi
import airportsdata
import pycountry
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "").strip()
AVIATIONSTACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY", "").strip()

# Default origin IATA code for flight searches
# change this to your preferred default origin airport code if needed
DEFAULT_ORIGIN_IATA = os.getenv("DEFAULT_ORIGIN_IATA","DEL")

SERPAPI_BASE_URL = "https://serpapi.com/search.json"
USD_TO_INR_RATE = 95.41
BUDGET_KEYWORDS = [
    "budget",
    "inr",
    "rupee",
    "rupees",
    "₹",
    "rs",
    "rs.",
    "rupee",
    "rupees",
]

AIRPORTS = airportsdata.load("IATA")

COUNTRY_ALIASES = {
     "usa": "US",
    "u.s.a": "US",
    "u.s.": "US",
    "america": "US",
    "united states": "US",
    "uk": "GB",
    "u.k.": "GB",
    "britain": "GB",
    "england": "GB",
    "uae": "AE",
    "dubai": "AE",
    "south korea": "KR",
    "korea": "KR",
    "russia": "RU",
    "vietnam": "VN",
    "bangladesh": "BD",
    "india": "IN",
    "japan": "JP",
    "china": "CN",
    "singapore": "SG",
    "malaysia": "MY",
    "thailand": "TH",
    "indonesia": "ID",
    "nepal": "NP",
    "qatar": "QA",
    "saudi arabia": "SA",
    "turkey": "TR",
    "canada": "CA",
    "australia": "AU",
    "germany": "DE",
    "france": "FR",
    "italy": "IT",
    "spain": "ES",
}

# Preferred main airport for country-level search
COUNTRY_MAIN_AIRPORT = {
    "BD": "DAC",
    "IN": "DEL",
    "JP": "NRT",
    "US": "JFK",
    "GB": "LHR",
    "AE": "DXB",
    "SG": "SIN",
    "MY": "KUL",
    "TH": "BKK",
    "ID": "CGK",
    "CN": "PEK",
    "KR": "ICN",
    "NP": "KTM",
    "QA": "DOH",
    "SA": "JED",
    "TR": "IST",
    "CA": "YYZ",
    "AU": "SYD",
    "DE": "FRA",
    "FR": "CDG",
    "IT": "FCO",
    "ES": "MAD",
}




CITY_MAIN_AIRPORT = {
    "dhaka": "DAC",
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "kolkata": "CCU",
    "chennai": "MAA",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "tokyo": "NRT",
    "osaka": "KIX",
    "kyoto": "KIX",
    "new york": "JFK",
    "london": "LHR",
    "dubai": "DXB",
    "singapore": "SIN",
    "kuala lumpur": "KUL",
    "bangkok": "BKK",
    "doha": "DOH",
    "istanbul": "IST",
    "toronto": "YYZ",
    "sydney": "SYD",
    "paris": "CDG",
    "rome": "FCO",
    "madrid": "MAD",
    "frankfurt": "FRA",
}

def clean_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    stop_words = [
        "flight", "flights", "ticket", "tickets", "trip", "travel",
        "plan", "complete", "days", "day", "including", "hotel",
        "hotels", "sightseeing", "under", "budget", "info", "information"
    ]
    words = [w for w in text.split() if w not in stop_words]
    return " ".join(words).strip()



def country_name_to_code(text: str):
    text = clean_text(text)

    if text in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[text]

    try:
        country = pycountry.countries.lookup(text)
        return country.alpha_2
    except LookupError:
        pass

    # Detect country name inside longer text
    for country in pycountry.countries:
        country_name = country.name.lower()
        if country_name in text:
            return country.alpha_2

    for alias, code in COUNTRY_ALIASES.items():
        if alias in text:
            return code

    return None


def airport_country_matches(airport: dict, country_code: str) -> bool:
    airport_country = str(airport.get("country", "")).upper().strip()

    if airport_country == country_code:
        return True

    try:
        country = pycountry.countries.get(alpha_2=country_code)
        if country and airport_country.lower() == country.name.lower():
            return True
    except Exception:
        pass

    return False


def get_best_airport_for_country(country_code: str):
    preferred = COUNTRY_MAIN_AIRPORT.get(country_code)

    if preferred and preferred in AIRPORTS:
        return preferred

    candidates = []

    for iata, airport in AIRPORTS.items():
        if not iata:
            continue

        if airport_country_matches(airport, country_code):
            name = str(airport.get("name", "")).lower()
            city = str(airport.get("city", "")).lower()

            score = 0

            if "international" in name:
                score += 50
            if "intl" in name:
                score += 40
            if "capital" in name:
                score += 20
            if city:
                score += 5

            candidates.append((score, iata))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]


def resolve_location_to_iata(location: str):
    """
    Converts country/city/airport/IATA into IATA code.

    Examples:
    Bangladesh -> DAC
    Japan -> NRT
    Dhaka -> DAC
    Tokyo -> NRT
    DAC -> DAC
    """

    if not location:
        return None

    raw_location = location.strip()

    # Direct IATA code
    if re.fullmatch(r"[A-Za-z]{3}", raw_location):
        code = raw_location.upper()
        if code in AIRPORTS:
            return code

    location_clean = clean_text(raw_location)

    if not location_clean:
        return None

    # City preferred airport
    if location_clean in CITY_MAIN_AIRPORT:
        return CITY_MAIN_AIRPORT[location_clean]

    # Country preferred airport
    country_code = country_name_to_code(location_clean)
    if country_code:
        airport = get_best_airport_for_country(country_code)
        if airport:
            return airport

    # Exact city match from airport database
    city_matches = []

    for iata, airport in AIRPORTS.items():
        city = str(airport.get("city", "")).lower().strip()
        name = str(airport.get("name", "")).lower().strip()

        score = 0

        if city == location_clean:
            score += 100
        elif location_clean in city:
            score += 70

        if location_clean in name:
            score += 50

        if "international" in name:
            score += 10

        if score > 0:
            city_matches.append((score, iata))

    if city_matches:
        city_matches.sort(reverse=True)
        return city_matches[0][1]

    return None




def find_location_mentions(query: str):
    """
    Finds country or city names inside a natural language query.
    """

    q = query.lower()
    mentions = []

    # Country aliases
    for alias in COUNTRY_ALIASES:
        if re.search(rf"\b{re.escape(alias)}\b", q):
            mentions.append(alias)

    # Country names from pycountry
    for country in pycountry.countries:
        name = country.name.lower()
        if len(name) >= 4 and re.search(rf"\b{re.escape(name)}\b", q):
            mentions.append(name)

    # City names from our preferred city map
    for city in CITY_MAIN_AIRPORT:
        if re.search(rf"\b{re.escape(city)}\b", q):
            mentions.append(city)

    # Remove duplicate while keeping order
    unique_mentions = []
    for item in mentions:
        if item not in unique_mentions:
            unique_mentions.append(item)

    return unique_mentions


def parse_route(query: str):
    """
    Returns:
    dep_iata, arr_iata

    Can return:
    None, None  -> global live flights
    DAC, NRT    -> filtered route
    DAC, None   -> all flights from DAC
    None, NRT   -> all flights to NRT
    """

    q = query.strip()
    q_lower = q.lower()

    # Global / all-country query
    global_keywords = [
        "all country",
        "all countries",
        "global flight",
        "global flights",
        "all flight",
        "all flights",
        "worldwide flight",
        "worldwide flights",
    ]

    if any(keyword in q_lower for keyword in global_keywords):
        return None, None

    # Direct IATA code route: DAC to NRT
    codes = re.findall(r"\b[A-Z]{3}\b", q)

    if len(codes) >= 2:
        dep = codes[0].upper()
        arr = codes[1].upper()
        return dep, arr

    # Pattern: from X to Y
    match = re.search(
        r"\bfrom\s+(.+?)\s+\bto\s+(.+?)(?:\s+(?:on|for|under|including|with|in|at)\b|[.!?]|$)",
        q_lower,
    )

    if match:
        origin_text = match.group(1)
        dest_text = match.group(2)

        dep_iata = resolve_location_to_iata(origin_text)
        arr_iata = resolve_location_to_iata(dest_text)

        return dep_iata, arr_iata

    # Pattern: to Y from X
    match = re.search(
        r"\bto\s+(.+?)\s+\bfrom\s+(.+?)(?:\s+(?:on|for|under|including|with|in|at)\b|[.!?]|$)",
        q_lower,
    )

    if match:
        dest_text = match.group(1)
        origin_text = match.group(2)

        dep_iata = resolve_location_to_iata(origin_text)
        arr_iata = resolve_location_to_iata(dest_text)

        return dep_iata, arr_iata

    # Pattern: flights from X
    match = re.search(r"\bfrom\s+(.+?)(?:[.!?]|$)", q_lower)

    if match:
        origin_text = match.group(1)
        dep_iata = resolve_location_to_iata(origin_text)
        return dep_iata, None

    # Pattern: flights to X
    match = re.search(r"\bto\s+(.+?)(?:[.!?]|$)", q_lower)

    if match:
        dest_text = match.group(1)
        arr_iata = resolve_location_to_iata(dest_text)
        return None, arr_iata

    # Fallback: find country/city mentions
    mentions = find_location_mentions(q)

    if len(mentions) >= 2:
        dep_iata = resolve_location_to_iata(mentions[0])
        arr_iata = resolve_location_to_iata(mentions[1])
        return dep_iata, arr_iata

    if len(mentions) == 1:
        arr_iata = resolve_location_to_iata(mentions[0])
        return DEFAULT_ORIGIN_IATA, arr_iata

    return None, None


def format_duration(minutes: int | None):
    if not minutes or minutes <= 0:
        return "Unknown"
    hours = minutes // 60
    mins = minutes % 60
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def format_time_string(timestamp: str) -> str:
    if not timestamp or not isinstance(timestamp, str):
        return "Unknown"

    for fmt in [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%H:%M",
        "%I:%M %p",
    ]:
        try:
            dt = datetime.strptime(timestamp, fmt)
            return dt.strftime("%Y-%m-%d %I:%M %p").replace(" 0", " ")
        except ValueError:
            continue

    return timestamp


def format_price_value(price_value, show_inr: bool) -> str:
    if price_value is None:
        return "Price: unavailable"

    cleaned = re.sub(r"[^\d.]", "", str(price_value))

    try:
        amount = float(cleaned)
    except (TypeError, ValueError):
        return f"Price: {price_value}"

    if show_inr:
        inr_value = int(round(amount * USD_TO_INR_RATE))
        return f"Price: ₹{inr_value}"

    return f"Price: ${amount:g}"


def format_serpapi_flight(flight: dict, show_inr: bool = True):
    price = flight.get("price")
    if isinstance(price, dict):
        price_value = price.get("amount") or price.get("raw") or price.get("value")
    else:
        price_value = price

    price_text = format_price_value(price_value, show_inr)

    segments = flight.get("flights") or []
    airline = flight.get("airline") or "Unknown airline"
    flight_number = "Unknown flight number"
    travel_class = flight.get("travel_class") or "Unknown class"
    route = "Unknown route"
    departure_time = "Unknown"
    arrival_time = "Unknown"
    duration_text = format_duration(flight.get("total_duration"))
    stops = "Direct"
    segment_lines = []

    if segments:
        if len(segments) > 1:
            stops = f"{len(segments) - 1} stop(s)"

        details = []
        for segment in segments:
            dep = segment.get("departure_airport") or {}
            arr = segment.get("arrival_airport") or {}
            seg_route = f"{dep.get('id') or dep.get('name', 'Unknown')} → {arr.get('id') or arr.get('name', 'Unknown')}"
            seg_dep_time = format_time_string(dep.get("time") or "Unknown")
            seg_arr_time = format_time_string(arr.get("time") or "Unknown")
            details.append(f"    • {seg_route} | {seg_dep_time} → {seg_arr_time}")

        segment_lines = details
        first_segment = segments[0]
        departure_airport = first_segment.get("departure_airport") or {}
        arrival_airport = segments[-1].get("arrival_airport") or {}
        departure_time = format_time_string(departure_airport.get("time") or "Unknown")
        arrival_time = format_time_string(arrival_airport.get("time") or "Unknown")
        route = f"{departure_airport.get('name', 'Unknown')} → {arrival_airport.get('name', 'Unknown')}"
        airline = first_segment.get("airline") or airline
        flight_number = first_segment.get("flight_number") or flight_number
        travel_class = first_segment.get("travel_class") or travel_class
        duration_text = format_duration(flight.get("total_duration") or first_segment.get("duration"))
    else:
        if flight.get("departure_airport") and flight.get("arrival_airport"):
            dep = flight.get("departure_airport")
            arr = flight.get("arrival_airport")
            route = f"{dep.get('name', dep)} → {arr.get('name', arr)}"
            departure_time = format_time_string(dep.get("time") or "Unknown")
            arrival_time = format_time_string(arr.get("time") or "Unknown")

    lines = [
        f"- Airline: {airline}",
        f"  o Flight Number: {flight_number}",
        f"  o Class: {travel_class}",
        f"  o Route: {route}",
        f"  o Departure: {departure_time}",
        f"  o Arrival: {arrival_time}",
        f"  o Duration: {duration_text}",
        f"  o Stops: {stops}",
        f"  o {price_text}",
    ]

    if segment_lines:
        lines.append("  o Segments:")
        for segment_line in segment_lines:
            lines.append(f"    {segment_line.strip()}")

    return "\n".join(lines)


def search_flights(query: str, limit: int = 10):
    if not SERPAPI_API_KEY:
        return (
            "Flight API error: SERPAPI_API_KEY is missing.\n"
            "Please add this in your .env file:\n"
            "SERPAPI_API_KEY=your_serpapi_key_here"
        )

    dep_iata, arr_iata = parse_route(query)

    params = {
        "api_key": SERPAPI_API_KEY,
        "engine": "google_flights",
        "hl": "en",
        "gl": "us",
        "currency": "USD",
        "type": "1",
        "outbound_date": "2026-07-15",
        "return_date": "2026-07-22",
    }

    if dep_iata:
        params["departure_id"] = dep_iata

    if arr_iata:
        params["arrival_id"] = arr_iata

    if not dep_iata and not arr_iata:
        params["q"] = query

    try:
        response = requests.get(SERPAPI_BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        return f"Flight API request failed: {e}"
    except ValueError:
        return "Flight API returned invalid JSON."

    if "error" in data:
        error = data.get("error", "Unknown error")
        return f"SerpAPI error: {error}"

    flight_data = data.get("best_flights") or data.get("other_flights") or []

    if not flight_data:
        route_text = ""

        if dep_iata and arr_iata:
            route_text = f" for route {dep_iata} to {arr_iata}"
        elif dep_iata:
            route_text = f" from {dep_iata}"
        elif arr_iata:
            route_text = f" to {arr_iata}"

        return (
            f"No SerpAPI flight data found{route_text}.\n\n"
            "Try a more specific route like 'Flights from Delhi to Tokyo'."
        )

    route_info = "Flight Information\nThe following flights are available"

    if dep_iata and arr_iata:
        route_info = f"Flight Information\nThe following flights are available from {dep_iata} to {arr_iata}:"
    elif dep_iata:
        route_info = f"Flight Information\nThe following flights are available from {dep_iata}:"
    elif arr_iata:
        route_info = f"Flight Information\nThe following flights are available to {arr_iata}:"

    formatted_flights = [format_serpapi_flight(flight, True) for flight in flight_data[:limit]]

    return f"{route_info}\n\n" + "\n\n---\n\n".join(formatted_flights)


if __name__ == "__main__":
    print(search_flights("Plan a 7 days Japan trip from India"))
    print("\n" + "=" * 80 + "\n")
    print(search_flights("all country flight info"))