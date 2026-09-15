"""Strings forwarded to the UI (job message / HTTP detail)."""

from typing import FrozenSet

TILE_LIMIT_MESSAGE = (
    "Die Anzahl der Kacheln überschreitet die Grenze von 6 Kacheln. "
    "Bitte zeichnen Sie einen kleineren Umring."
)
AREA_LIMIT_MESSAGE = (
    "Der gewählte Umring ist größer als 1 km². "
    "Bitte zeichnen Sie einen kleineren Umring."
)
BOREHOLES_AREA_LIMIT_MESSAGE = (
    "Der gewählte Umring ist größer als 0,1 km². "
    "Bitte zeichnen Sie einen kleineren Umring."
)
NO_TREE_DATA_MESSAGE = (
    "Es konnten keine Baumdaten für den gewählten Umring geladen werden. "
    "Bitte wählen Sie einen anderen Bereich."
)
NO_TREES_MESSAGE = (
    "Im gewählten Umring wurden keine Bäume gefunden. "
    "Bitte zeichnen Sie einen größeren Umring oder wählen Sie einen anderen Bereich."
)
NO_BUILDINGS_MESSAGE = (
    "Im gewählten Umring wurden keine Gebäude gefunden. "
    "Bitte zeichnen Sie einen größeren Umring oder wählen Sie einen anderen Bereich."
)
NO_TERRAIN_MESSAGE = (
    "Im gewählten Umring wurden keine Geländedaten gefunden. "
    "Bitte wählen Sie einen anderen Bereich."
)
NO_FLURSTUECK_DATA_MESSAGE = (
    "Es konnten keine Flurstücksdaten für den gewählten Umring geladen werden. "
    "Bitte wählen Sie einen anderen Bereich."
)
NO_FLURSTUECKE_MESSAGE = (
    "Im gewählten Umring wurden keine Flurstücke gefunden. "
    "Bitte zeichnen Sie einen größeren Umring oder wählen Sie einen anderen Bereich."
)
LOD3_ONLY_ON_RS_MESSAGE = (
    "LoD3 steht in diesem Prozess nicht zur Verfügung. "
    "Bitte wählen Sie LoD1 oder LoD2, oder starten Sie die Erzeugung über das Rust-Stadtmodell."
)
TREES_IFC_FAILED_MESSAGE = (
    "Das Baummodell konnte nicht erzeugt werden. "
    "Bitte versuchen Sie es erneut oder wählen Sie einen anderen Umring."
)
TERRAIN_IFC_FAILED_MESSAGE = (
    "Das Geländemodell konnte nicht erzeugt werden. "
    "Bitte versuchen Sie es erneut oder wählen Sie einen anderen Umring."
)
FLURSTUECKE_IFC_FAILED_MESSAGE = (
    "Das Flurstücksmodell konnte nicht erzeugt werden. "
    "Bitte versuchen Sie es erneut oder wählen Sie einen anderen Umring."
)
NO_BOREHOLE_DATA_MESSAGE = (
    "Es konnten keine Bohrungsdaten für den gewählten Umring geladen werden. "
    "Bitte wählen Sie einen anderen Bereich."
)
NO_BOREHOLES_MESSAGE = (
    "Im gewählten Umring wurden keine Bohrungen gefunden. "
    "Bitte zeichnen Sie einen größeren Umring oder wählen Sie einen anderen Bereich."
)
BOREHOLES_IFC_FAILED_MESSAGE = (
    "Das Bohrungsmodell konnte nicht erzeugt werden. "
    "Bitte versuchen Sie es erneut oder wählen Sie einen anderen Umring."
)
CORE_BOREHOLES_MISSING_MESSAGE = (
    "Das Bohrungsmodul in bimfabrikhh-core fehlt. "
    "Bitte Core von einem Stand mit apps.boreholes installieren "
    "(aktuelles main plus feat/boreholes, nicht den alten Branch allein)."
)
INVALID_INPUT_MESSAGE = (
    "Die Eingabedaten sind ungültig. "
    "Bitte prüfen Sie den Umring und die übrigen Angaben."
)
UNEXPECTED_ERROR_MESSAGE = (
    "Die Erzeugung ist unerwartet fehlgeschlagen. "
    "Bitte versuchen Sie es erneut. Wenn der Fehler bestehen bleibt, "
    "wählen Sie einen anderen Umring."
)
JOB_FAILED_FALLBACK_MESSAGE = "Der Auftrag ist fehlgeschlagen."
JOB_CANCELLED_MESSAGE = "Der Auftrag wurde abgebrochen."
JOB_CANNOT_CANCEL_MESSAGE = "Der Auftrag kann nicht abgebrochen werden."
NO_MODEL_IN_RESULT_MESSAGE = "Für diesen Auftrag liegt kein Modell vor."
JOB_NOT_READY_MESSAGE = (
    "Der Auftrag wurde nicht gefunden oder ist noch nicht abgeschlossen."
)
JOB_TIMEOUT_MESSAGE = (
    "Der Auftrag wurde wegen Zeitüberschreitung abgebrochen. "
    "Bitte versuchen Sie es erneut oder wählen Sie einen kleineren Umring."
)
JOB_LISTING_UNAVAILABLE_MESSAGE = (
    "Die Auftragsliste steht mit dem aktuellen System nicht zur Verfügung."
)
RATE_LIMIT_MESSAGE = (
    "Zu viele Anfragen in kurzer Zeit. "
    "Bitte warten Sie einen Moment und versuchen Sie es erneut."
)


def too_many_jobs_message(limit: int) -> str:
    return (
        f"Die maximale Anzahl gleichzeitiger Aufträge ({limit}) ist erreicht. "
        "Bitte warten Sie, bis ein laufender Auftrag abgeschlossen ist."
    )


def process_not_found_message(process_id: str) -> str:
    return f'Der Prozess „{process_id}“ wurde nicht gefunden.'


_KNOWN_USER_MESSAGES: FrozenSet[str] = frozenset(
    {
        TILE_LIMIT_MESSAGE,
        AREA_LIMIT_MESSAGE,
        BOREHOLES_AREA_LIMIT_MESSAGE,
        NO_TREE_DATA_MESSAGE,
        NO_TREES_MESSAGE,
        NO_BUILDINGS_MESSAGE,
        NO_TERRAIN_MESSAGE,
        NO_FLURSTUECK_DATA_MESSAGE,
        NO_FLURSTUECKE_MESSAGE,
        LOD3_ONLY_ON_RS_MESSAGE,
        TREES_IFC_FAILED_MESSAGE,
        TERRAIN_IFC_FAILED_MESSAGE,
        FLURSTUECKE_IFC_FAILED_MESSAGE,
        NO_BOREHOLE_DATA_MESSAGE,
        NO_BOREHOLES_MESSAGE,
        BOREHOLES_IFC_FAILED_MESSAGE,
        CORE_BOREHOLES_MISSING_MESSAGE,
        INVALID_INPUT_MESSAGE,
        UNEXPECTED_ERROR_MESSAGE,
        JOB_TIMEOUT_MESSAGE,
    }
)


def to_user_error(exc: BaseException) -> ValueError:
    """Map an internal exception to the UI ``ValueError`` the client can show."""
    text = str(exc).strip()
    if text in _KNOWN_USER_MESSAGES:
        return exc if isinstance(exc, ValueError) else ValueError(text)

    lowered = text.lower()
    if "no buildings parsed" in lowered:
        return ValueError(NO_BUILDINGS_MESSAGE)
    if "no trees to write" in lowered:
        return ValueError(NO_TREES_MESSAGE)
    if "terrain mesh" in lowered:
        return ValueError(TERRAIN_IFC_FAILED_MESSAGE)
    if "no flurstueck records" in lowered:
        return ValueError(NO_FLURSTUECKE_MESSAGE)
    if "no borehole records" in lowered:
        return ValueError(NO_BOREHOLES_MESSAGE)
    if "borehole app is required" in lowered or "apps.boreholes" in lowered:
        return ValueError(CORE_BOREHOLES_MISSING_MESSAGE)
    if "lod3 is only available" in lowered:
        return ValueError(LOD3_ONLY_ON_RS_MESSAGE)
    if "validation error" in lowered:
        return ValueError(INVALID_INPUT_MESSAGE)
    return ValueError(UNEXPECTED_ERROR_MESSAGE)
