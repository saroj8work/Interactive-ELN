from datetime import date, datetime, time, timedelta, timezone
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from dateutil.rrule import rrulestr

from eln_common.contracts import EquipmentBookingCreate


MAX_ICAL_BYTES = 5 * 1024 * 1024
MAX_ICAL_EVENTS = 100
MAX_ICAL_TEXT = 500


def _property(line: str) -> tuple[str, dict[str, str], str]:
    if ":" not in line:
        raise HTTPException(status_code=422, detail="Calendar file contains a malformed content line.")
    left, value = line.split(":", 1)
    parts = left.split(";")
    name = parts[0].rsplit(".", 1)[-1].upper()
    parameters: dict[str, str] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, parameter = part.split("=", 1)
        parameters[key.upper()] = parameter.strip('"')
    return name, parameters, value


def _text(value: str) -> str:
    decoded = re.sub(
        r"\\([nN,;\\])",
        lambda match: {"n": "\n", "N": "\n", ",": ",", ";": ";", "\\": "\\"}[match.group(1)],
        value,
    )
    return re.sub(r"[\x00-\x09\x0b\x0c\x0e-\x1f\x7f]", "", decoded)


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise HTTPException(status_code=422, detail=f"Calendar file uses an unsupported time zone: {name}.") from error


def _event_datetime(value: str, parameters: dict[str, str], fallback_zone: ZoneInfo) -> datetime:
    if parameters.get("VALUE", "").upper() == "DATE" or re.fullmatch(r"\d{8}", value):
        try:
            parsed_date = datetime.strptime(value, "%Y%m%d").date()
        except ValueError as error:
            raise HTTPException(status_code=422, detail="Calendar file contains an invalid all-day event date.") from error
        return datetime.combine(parsed_date, time.min, _zone(parameters["TZID"]) if "TZID" in parameters else fallback_zone)

    is_utc = value.endswith("Z")
    raw_value = value[:-1] if is_utc else value
    parsed: datetime | None = None
    for date_format in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
        try:
            parsed = datetime.strptime(raw_value, date_format)
            break
        except ValueError:
            continue
    if parsed is None:
        raise HTTPException(status_code=422, detail="Calendar file contains an unsupported event date-time.")
    if is_utc:
        if "TZID" in parameters:
            raise HTTPException(status_code=422, detail="Calendar date-times cannot combine UTC suffixes and TZID parameters.")
        return parsed.replace(tzinfo=timezone.utc)
    zone = _zone(parameters["TZID"]) if "TZID" in parameters else fallback_zone
    localized = parsed.replace(tzinfo=zone)
    if localized.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != parsed:
        raise HTTPException(status_code=422, detail="Calendar file contains a local time that does not exist in its time zone.")
    return localized


def parse_ical_bookings(raw: bytes, fallback_timezone: str) -> list[EquipmentBookingCreate]:
    if len(raw) > MAX_ICAL_BYTES:
        raise HTTPException(status_code=413, detail="Calendar import exceeds 5 MiB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail="Calendar file must be UTF-8 encoded.") from error
    try:
        fallback_zone = _zone(fallback_timezone)
    except HTTPException as error:
        raise HTTPException(status_code=422, detail="Choose a valid IANA time zone for floating calendar dates.") from error

    unfolded: list[str] = []
    for source_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if len(source_line) > 100_000:
            raise HTTPException(status_code=413, detail="Calendar file contains an overlong content line.")
        if source_line.startswith((" ", "\t")):
            if not unfolded:
                raise HTTPException(status_code=422, detail="Calendar file begins with a folded line.")
            unfolded[-1] += source_line[1:]
        elif source_line:
            unfolded.append(source_line)

    if not unfolded or unfolded[0].upper() != "BEGIN:VCALENDAR" or unfolded[-1].upper() != "END:VCALENDAR":
        raise HTTPException(status_code=422, detail="Upload a valid iCalendar (.ics) file.")

    bookings: list[EquipmentBookingCreate] = []
    properties: dict[str, tuple[dict[str, str], str]] | None = None
    nested_component_depth = 0
    for line in unfolded:
        upper = line.upper()
        if upper == "BEGIN:VEVENT" and properties is None:
            properties = {}
            nested_component_depth = 0
            continue
        if properties is None:
            continue
        if upper.startswith("BEGIN:") and upper != "BEGIN:VEVENT":
            nested_component_depth += 1
            continue
        if upper.startswith("END:") and upper != "END:VEVENT":
            if nested_component_depth:
                nested_component_depth -= 1
            continue
        if upper == "END:VEVENT" and nested_component_depth == 0:
            if any(name in properties for name in {"EXDATE", "RDATE", "RECURRENCE-ID"}):
                raise HTTPException(status_code=422, detail="Calendar recurrence exceptions and overrides are not supported by this import yet.")
            status = properties.get("STATUS", ({}, ""))[1].upper()
            if status != "CANCELLED":
                if "DTSTART" not in properties or "DTEND" not in properties:
                    raise HTTPException(status_code=422, detail="Every imported calendar event needs DTSTART and DTEND.")
                start_parameters, start_value = properties["DTSTART"]
                end_parameters, end_value = properties["DTEND"]
                starts_at = _event_datetime(start_value, start_parameters, fallback_zone)
                ends_at = _event_datetime(end_value, end_parameters, fallback_zone)
                summary = _text(properties.get("SUMMARY", ({}, "Imported calendar event"))[1]).strip()
                description = _text(properties.get("DESCRIPTION", ({}, ""))[1]).strip()
                purpose = summary or "Imported calendar event"
                if description:
                    purpose = f"{purpose}\n{description}"
                if len(purpose) > MAX_ICAL_TEXT:
                    raise HTTPException(status_code=422, detail="An imported calendar event's summary and description exceed 500 characters.")
                try:
                    recurrence = properties.get("RRULE", ({}, ""))[1].strip()
                    starts = [starts_at]
                    if recurrence:
                        recurrence_parts = {
                            part.split("=", 1)[0].upper(): part.split("=", 1)[1]
                            for part in recurrence.split(";")
                            if "=" in part
                        }
                        if "COUNT" in recurrence_parts and "UNTIL" in recurrence_parts:
                            raise HTTPException(status_code=422, detail="An RRULE cannot contain both COUNT and UNTIL.")
                        rule = rrulestr(recurrence, dtstart=starts_at)
                        starts = list(rule[:MAX_ICAL_EVENTS + 1])
                        if not starts or starts[0] != starts_at:
                            raise HTTPException(status_code=422, detail="Recurring event DTSTART does not match its RRULE pattern.")
                        if len(starts) > MAX_ICAL_EVENTS:
                            raise HTTPException(status_code=413, detail="A recurring event expands to more than 100 bookings.")
                    duration = ends_at - starts_at
                    for occurrence_start in starts:
                        if len(bookings) >= MAX_ICAL_EVENTS:
                            raise HTTPException(status_code=413, detail="Calendar import expands to more than 100 bookings.")
                        bookings.append(EquipmentBookingCreate(
                            starts_at=occurrence_start,
                            ends_at=occurrence_start + duration,
                            purpose=purpose,
                        ))
                except (OverflowError, TypeError, ValueError) as error:
                    raise HTTPException(status_code=422, detail=f"Calendar event has an invalid time range: {error}") from error
            properties = None
            continue
        if nested_component_depth:
            continue
        name, parameters, value = _property(line)
        if name in {"DTSTART", "DTEND", "SUMMARY", "DESCRIPTION", "STATUS", "RRULE", "EXDATE", "RDATE", "RECURRENCE-ID", "DURATION"}:
            if name in properties:
                raise HTTPException(status_code=422, detail=f"Calendar event has multiple {name} properties.")
            properties[name] = (parameters, value)

    if properties is not None:
        raise HTTPException(status_code=422, detail="Calendar file contains an incomplete VEVENT.")
    if not bookings:
        raise HTTPException(status_code=422, detail="Calendar file contains no importable active events.")
    return bookings
