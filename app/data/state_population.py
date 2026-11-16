"""Fixed population table for Indian states and union territories.

Single source of truth for the Policy Simulator: the model never estimates
population, the server injects these values and overwrites whatever the model
returns.

Vintage: Census of India 2011 actuals, ``year`` = 2011 on every row. No
projection is applied. An unsourced growth factor would be a made-up number,
so projecting to a later year needs an official projection series (e.g. the
National Commission on Population's 2011-2036 report) added as a deliberate
change, with its own ``source`` and ``year``.

Provenance: figures were compiled from the Wikipedia page "List of states and
union territories of India by population" (rev. 1382207687) and, for Ladakh,
the Leh and Kargil district pages. They have NOT been checked against the
Census Primary Census Abstract; do that before treating them as audited.
Rows with caveats say so in their own ``source``.
"""

import re
import unicodedata

from app.errors import UnknownStateError

_CENSUS = (
    "Census of India 2011 (compiled via Wikipedia, 'List of states and union "
    "territories of India by population', rev. 1382207687; not yet checked "
    "against the Primary Census Abstract)"
)
_YEAR = 2011


def _entry(population: int, urban_pct: float, note: str = "") -> dict:
    return {
        "population": population,
        "urban_pct": urban_pct,
        "rural_pct": round(100 - urban_pct, 2),  # sums to 100 by construction
        "source": f"{_CENSUS}. {note}" if note else _CENSUS,
        "year": _YEAR,
    }


_TELANGANA_NOTE = (
    "Telangana did not exist in 2011; figure is the Telangana districts' "
    "2011 census total."
)
_AP_NOTE = "Residual Andhra Pradesh after the 2014 bifurcation, not the 2011 undivided state."
_LADAKH_NOTE = (
    "Ladakh was part of J&K in 2011; figure is Leh (133,487) + Kargil (140,802) "
    "district totals; urban = 45,671 + 16,338 = 62,009, from the Leh and "
    "Kargil district pages."
)
_JK_NOTE = "UT of J&K as listed on the page; whether it excludes Ladakh is not stated there."
_DNHDD_NOTE = "Merged UT (2020), 2011 total as listed on the page; page does not explain the merge arithmetic."
_MANIPUR_NOTE = (
    "Excludes the Mao-Maram, Paomata and Purul subdivisions of Senapati "
    "district, as in the census totals the source lists."
)

STATE_POPULATION: dict[str, dict] = {
    # --- 28 states ---
    "Andhra Pradesh": _entry(49_577_103, 29.47, _AP_NOTE),
    "Arunachal Pradesh": _entry(1_383_727, 22.94),
    "Assam": _entry(31_205_576, 14.10),
    "Bihar": _entry(104_099_452, 11.29),
    "Chhattisgarh": _entry(25_545_198, 23.24),
    "Goa": _entry(1_458_545, 62.17),
    "Gujarat": _entry(60_439_692, 42.60),
    "Haryana": _entry(25_351_462, 34.88),
    "Himachal Pradesh": _entry(6_864_602, 10.03),
    "Jharkhand": _entry(32_988_134, 24.05),
    "Karnataka": _entry(61_095_297, 38.67),
    "Kerala": _entry(33_406_061, 47.70),
    "Madhya Pradesh": _entry(72_626_809, 27.63),
    "Maharashtra": _entry(112_374_333, 45.22),
    "Manipur": _entry(2_570_390, 30.21, _MANIPUR_NOTE),
    "Meghalaya": _entry(2_966_889, 20.07),
    "Mizoram": _entry(1_097_206, 52.11),
    "Nagaland": _entry(1_978_502, 28.86),
    "Odisha": _entry(41_974_219, 16.69),
    "Punjab": _entry(27_743_338, 37.48),
    "Rajasthan": _entry(68_548_437, 24.87),
    "Sikkim": _entry(610_577, 25.15),
    "Tamil Nadu": _entry(72_147_030, 48.40),
    "Telangana": _entry(35_003_674, 38.88, _TELANGANA_NOTE),
    "Tripura": _entry(3_673_917, 26.17),
    "Uttar Pradesh": _entry(199_812_341, 22.27),
    "Uttarakhand": _entry(10_086_292, 30.23),
    "West Bengal": _entry(91_276_115, 31.87),
    # --- 8 union territories ---
    "Andaman and Nicobar Islands": _entry(380_581, 37.70),
    "Chandigarh": _entry(1_055_450, 97.25),
    "Dadra and Nagar Haveli and Daman and Diu": _entry(585_764, 58.43, _DNHDD_NOTE),
    "Delhi": _entry(16_787_941, 97.50),
    "Jammu and Kashmir": _entry(12_267_032, 26.11, _JK_NOTE),
    "Ladakh": _entry(274_289, 22.61, _LADAKH_NOTE),
    "Lakshadweep": _entry(64_473, 78.07),
    "Puducherry": _entry(1_247_953, 68.33),
}


def _normalise(name: str) -> str:
    text = unicodedata.normalize("NFD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.casefold().replace("&", " and ")
    return re.sub(r"\s+", " ", text).strip()


_BY_NORMALISED = {_normalise(k): k for k in STATE_POPULATION}


def get_state_population(state: str) -> dict:
    """Table row for ``state``, plus its canonical name under ``"state"``.

    Case, surrounding/repeated whitespace and diacritics are ignored.
    Raises ``UnknownStateError`` if the state is not in the table.
    """
    key = _BY_NORMALISED.get(_normalise(state)) if isinstance(state, str) else None
    if key is None:
        raise UnknownStateError(str(state))
    return {"state": key, **STATE_POPULATION[key]}
