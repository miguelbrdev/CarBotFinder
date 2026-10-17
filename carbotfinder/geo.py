"""Province normalisation and postal-code lookup for Spain."""

from __future__ import annotations

import re
import unicodedata

# Normalised names of the three island provinces (excluded by default).
ISLAND_PROVINCES: frozenset[str] = frozenset({"baleares", "las palmas", "santa cruz de tenerife"})

# Postal code prefix (first two digits) -> normalised province name.
_POSTAL_PREFIX_TO_PROVINCE: dict[str, str] = {
    "01": "alava",
    "02": "albacete",
    "03": "alicante",
    "04": "almeria",
    "05": "avila",
    "06": "badajoz",
    "07": "baleares",
    "08": "barcelona",
    "09": "burgos",
    "10": "caceres",
    "11": "cadiz",
    "12": "castellon",
    "13": "ciudad real",
    "14": "cordoba",
    "15": "a coruna",
    "16": "cuenca",
    "17": "girona",
    "18": "granada",
    "19": "guadalajara",
    "20": "gipuzkoa",
    "21": "huelva",
    "22": "huesca",
    "23": "jaen",
    "24": "leon",
    "25": "lleida",
    "26": "la rioja",
    "27": "lugo",
    "28": "madrid",
    "29": "malaga",
    "30": "murcia",
    "31": "navarra",
    "32": "ourense",
    "33": "asturias",
    "34": "palencia",
    "35": "las palmas",
    "36": "pontevedra",
    "37": "salamanca",
    "38": "santa cruz de tenerife",
    "39": "cantabria",
    "40": "segovia",
    "41": "sevilla",
    "42": "soria",
    "43": "tarragona",
    "44": "teruel",
    "45": "toledo",
    "46": "valencia",
    "47": "valladolid",
    "48": "bizkaia",
    "49": "zamora",
    "50": "zaragoza",
    "51": "ceuta",
    "52": "melilla",
}

# Spelling variants -> canonical normalised name.
# Keys are already normalised (see _basic_normalise).
_ALIASES: dict[str, str] = {
    # Islands (the ones that matter most for the default exclusion)
    "illes balears": "baleares",
    "islas baleares": "baleares",
    "balears": "baleares",
    "mallorca": "baleares",
    "menorca": "baleares",
    "ibiza": "baleares",
    "eivissa": "baleares",
    "formentera": "baleares",
    "palma de mallorca": "baleares",
    "las palmas de gran canaria": "las palmas",
    "palmas, las": "las palmas",
    "palmas": "las palmas",
    "gran canaria": "las palmas",
    "lanzarote": "las palmas",
    "fuerteventura": "las palmas",
    "sta. cruz de tenerife": "santa cruz de tenerife",
    "sta cruz de tenerife": "santa cruz de tenerife",
    "s/c de tenerife": "santa cruz de tenerife",
    "santa cruz tenerife": "santa cruz de tenerife",
    "tenerife": "santa cruz de tenerife",
    "la palma": "santa cruz de tenerife",
    "la gomera": "santa cruz de tenerife",
    "el hierro": "santa cruz de tenerife",
    "canarias": "las palmas",  # ambiguous; both Canary provinces are excluded by default anyway
    # Bilingual / official variants on the mainland
    "araba": "alava",
    "araba/alava": "alava",
    "alava/araba": "alava",
    "guipuzcoa": "gipuzkoa",
    "vizcaya": "bizkaia",
    "gerona": "girona",
    "lerida": "lleida",
    "orense": "ourense",
    "la coruna": "a coruna",
    "coruna": "a coruna",
    "coruna, a": "a coruna",
    "castellon de la plana": "castellon",
    "castello": "castellon",
    "valencia/valencia": "valencia",
    "alicante/alacant": "alicante",
    "alacant": "alicante",
    "principado de asturias": "asturias",
    "comunidad de madrid": "madrid",
    "region de murcia": "murcia",
    "rioja, la": "la rioja",
    "rioja": "la rioja",
    "comunidad foral de navarra": "navarra",
    "nafarroa": "navarra",
}


def _basic_normalise(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    lowered = ascii_only.lower().strip()
    lowered = re.sub(r"^(provincia de|prov\.)\s+", "", lowered)
    return re.sub(r"\s+", " ", lowered)


def normalise_province(text: str | None) -> str | None:
    """Return the canonical, accent-free, lower-case province name, or ``None``."""
    if not text:
        return None
    base = _basic_normalise(text)
    if not base:
        return None
    return _ALIASES.get(base, base)


def province_from_postal_code(postal_code: str | None) -> str | None:
    """Derive the normalised province from a Spanish postal code (5 digits)."""
    if not postal_code:
        return None
    digits = re.sub(r"\D", "", postal_code)
    if len(digits) < 2:
        return None
    return _POSTAL_PREFIX_TO_PROVINCE.get(digits[:2].zfill(2))
