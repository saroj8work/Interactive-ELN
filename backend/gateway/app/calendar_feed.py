from datetime import datetime, timezone
import re
from typing import Any


def _escape(value: str) -> str:
    value = re.sub(r"[\x00-\x09\x0b\x0c\x0e-\x1f\x7f]", "", value)
    escaped = value.replace("\\", "\\\\").replace("\r\n", "\n").replace("\r", "\n")
    return escaped.replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def _ical_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _fold(line: str) -> str:
    chunks: list[str] = []
    current = ""
    size = 0
    for character in line:
        encoded_size = len(character.encode("utf-8"))
        if size + encoded_size > 75:
            chunks.append(current)
            current = " "
            size = 1
        current += character
        size += encoded_size
    chunks.append(current)
    return "\r\n".join(chunks)


def build_equipment_calendar(
    organization_id: int,
    equipment: list[Any],
    bookings: list[Any],
    maintenance: list[Any],
) -> bytes:
    equipment_names = {item.id: item.name for item in equipment}
    stamp = _ical_time(datetime.now(timezone.utc))
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Interactive ELN//Equipment Schedule//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Interactive ELN Equipment Schedule",
    ]
    for booking in bookings:
        equipment_name = equipment_names.get(booking.equipment_id, f"Equipment #{booking.equipment_id}")
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:booking-{booking.id}@org-{organization_id}.interactive-eln",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{_ical_time(booking.starts_at)}",
            f"DTEND:{_ical_time(booking.ends_at)}",
            f"SUMMARY:{_escape('Equipment booking: ' + equipment_name)}",
            f"DESCRIPTION:{_escape(booking.purpose)}",
            f"STATUS:{'CANCELLED' if booking.status == 'cancelled' else 'CONFIRMED'}",
            "END:VEVENT",
        ])
    for record in maintenance:
        if record.status not in {"scheduled", "in_progress", "cancelled"}:
            continue
        equipment_name = equipment_names.get(record.equipment_id, f"Equipment #{record.equipment_id}")
        summary = f"Equipment maintenance: {equipment_name} - {record.title}"
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:maintenance-{record.id}@org-{organization_id}.interactive-eln",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{_ical_time(record.starts_at)}",
            f"DTEND:{_ical_time(record.ends_at)}",
            f"SUMMARY:{_escape(summary)}",
            f"DESCRIPTION:{_escape(record.notes)}",
            f"STATUS:{'CANCELLED' if record.status == 'cancelled' else 'CONFIRMED'}",
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return ("\r\n".join(_fold(line) for line in lines) + "\r\n").encode("utf-8")
