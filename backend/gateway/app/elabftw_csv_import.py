import csv
import io
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

from fastapi import HTTPException
from pydantic import ValidationError

from eln_common.contracts import (
    ProjectImportExperiment,
    ProjectImportExperimentInfo,
    ProjectImportPayload,
    ProjectImportEntry,
    InventoryItemCreate,
    SampleCreate,
)


MAX_CSV_BYTES = 20 * 1024 * 1024
MAX_ROWS = 1000
MAX_FIELD_CHARS = 100_000


@dataclass
class ImportedSample:
    payload: SampleCreate
    tags: list[str]
    parent_external_id: str


class _HTMLText(HTMLParser):
    _BLOCKS = {"br", "div", "li", "ol", "p", "table", "tr", "ul", "h1", "h2", "h3", "h4"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden_depth += 1
        elif tag in self._BLOCKS and self.hidden_depth == 0:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.hidden_depth:
            self.hidden_depth -= 1
        elif tag in self._BLOCKS and self.hidden_depth == 0:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.hidden_depth == 0:
            self.parts.append(data)


def _html_to_text(value: str) -> str:
    parser = _HTMLText()
    try:
        parser.feed(value)
        parser.close()
    except (AssertionError, ValueError):
        return value
    text = "".join(parser.parts).replace("\r", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def import_elabftw_csv(raw: bytes, project_name: str) -> ProjectImportPayload:
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="CSV import exceeds 20 MiB.")
    try:
        decoded = raw.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(decoded, newline=""), strict=True))
    except (UnicodeDecodeError, csv.Error) as error:
        raise HTTPException(status_code=422, detail="CSV must be valid UTF-8 with well-formed quoting.") from error
    header_row = rows[0] if rows else None
    if not header_row:
        raise HTTPException(status_code=422, detail="CSV is empty.")
    headers = [header.strip() for header in header_row]
    normalized = [header.casefold() for header in headers]
    if any(not header for header in headers) or len(set(normalized)) != len(normalized):
        raise HTTPException(status_code=422, detail="CSV column names must be non-empty and unique.")
    if "title" not in normalized:
        raise HTTPException(status_code=422, detail="eLabFTW-compatible CSV requires a title column.")

    reserved = {
        "title", "body", "content_type", "date", "tags", "metadata",
        "category_title", "status_title", "location", "quantity", "unit",
        "canread", "canwrite", "rating",
    }
    experiments: list[ProjectImportExperiment] = []
    for row_number, values in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in values):
            continue
        if len(experiments) >= MAX_ROWS:
            raise HTTPException(status_code=413, detail="CSV contains more than 1,000 records.")
        if len(values) != len(headers):
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} does not match its header.")
        if any(len(value) > MAX_FIELD_CHARS for value in values):
            raise HTTPException(status_code=413, detail=f"CSV row {row_number} contains a field over 100,000 characters.")
        row = dict(zip(normalized, values, strict=True))
        title = row["title"].strip()
        if not title:
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} has an empty title.")
        if len(title) > 160:
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} title exceeds 160 characters.")

        content_type = row.get("content_type", "1").strip() or "1"
        if content_type not in {"1", "2"}:
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} has an unsupported content_type.")
        body = row.get("body", "")
        content = _html_to_text(body) if content_type == "1" else body
        metadata_json = row.get("metadata", "").strip()
        metadata: dict | list | None = None
        if metadata_json:
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError as error:
                raise HTTPException(status_code=422, detail=f"CSV row {row_number} metadata is invalid JSON.") from error
            if not isinstance(metadata, (dict, list)):
                raise HTTPException(status_code=422, detail=f"CSV row {row_number} metadata must be a JSON object or array.")

        fields = [
            (headers[index], value.strip())
            for index, value in enumerate(values)
            if normalized[index] not in reserved and value.strip()
        ]
        details = [f"{name}: {value}" for name, value in fields]
        for key in sorted(reserved - {"title", "body", "content_type", "tags", "metadata"}):
            value = row.get(key, "").strip()
            if value:
                details.append(f"{key}: {value}")
        if metadata is not None:
            details.append("Metadata JSON: " + json.dumps(metadata, ensure_ascii=False, sort_keys=True))
        if details:
            content = f"{content.rstrip()}\n\nImported CSV fields:\n" + "\n".join(details) if content.strip() else "Imported CSV fields:\n" + "\n".join(details)
        if not content.strip():
            content = "Imported from eLabFTW-compatible CSV."
        if len(content) > MAX_FIELD_CHARS:
            raise HTTPException(status_code=413, detail=f"CSV row {row_number} produces an entry over 100,000 characters.")

        tags = [tag.strip() for tag in row.get("tags", "").split("|") if tag.strip()]
        if any(len(tag) > 80 for tag in tags):
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} contains a tag over 80 characters.")
        tags = list(dict.fromkeys(tags))[:20]
        experiment_name = title
        experiments.append(ProjectImportExperiment(
            experiment=ProjectImportExperimentInfo(
                name=experiment_name,
                description=f"Imported from eLabFTW-compatible CSV row {row_number}.",
            ),
            tags=tags,
            entries=[ProjectImportEntry(title=title, content=content, tags=tags)],
        ))

    if not experiments:
        raise HTTPException(status_code=422, detail="CSV contains no non-empty records.")
    return ProjectImportPayload(
        project={"name": project_name, "description": "Records imported from eLabFTW-compatible CSV."},
        experiments=experiments,
        tasks=[],
    )


def import_elabftw_resources(raw: bytes) -> list[tuple[InventoryItemCreate, list[str]]]:
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="CSV import exceeds 20 MiB.")
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True))
    except (UnicodeDecodeError, csv.Error) as error:
        raise HTTPException(status_code=422, detail="CSV must be valid UTF-8 with well-formed quoting.") from error
    if not rows or not rows[0]:
        raise HTTPException(status_code=422, detail="CSV is empty.")
    headers = [header.strip() for header in rows[0]]
    normalized = [header.casefold() for header in headers]
    if any(not header for header in headers) or len(set(normalized)) != len(normalized):
        raise HTTPException(status_code=422, detail="CSV column names must be non-empty and unique.")
    if "title" not in normalized and "name" not in normalized:
        raise HTTPException(status_code=422, detail="Resource CSV requires a title or name column.")

    reserved = {
        "title", "name", "category", "category_title", "catalog_number", "reference",
        "lot_number", "expires_on", "expiration_date", "quantity", "unit", "location",
        "tags", "body", "content_type", "metadata", "low_stock_threshold",
    }
    result: list[tuple[InventoryItemCreate, list[str]]] = []
    for row_number, values in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in values):
            continue
        if len(result) >= MAX_ROWS:
            raise HTTPException(status_code=413, detail="CSV contains more than 1,000 records.")
        if len(values) != len(headers):
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} does not match its header.")
        if any(len(value) > MAX_FIELD_CHARS for value in values):
            raise HTTPException(status_code=413, detail=f"CSV row {row_number} contains a field over 100,000 characters.")
        row = dict(zip(normalized, values, strict=True))
        name = (row.get("title") or row.get("name") or "").strip()
        if not name or len(name) > 160:
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} has an empty or overlong resource name.")

        custom_fields: dict[str, str] = {}
        for index, value in enumerate(values):
            normalized_name = normalized[index]
            if normalized_name in reserved or not value.strip():
                continue
            custom_fields[headers[index]] = value.strip()
        metadata_json = row.get("metadata", "").strip()
        if metadata_json:
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError as error:
                raise HTTPException(status_code=422, detail=f"CSV row {row_number} metadata is invalid JSON.") from error
            if isinstance(metadata, dict):
                for key, value in metadata.items():
                    field_name = str(key).strip()
                    custom_fields[field_name] = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
            elif isinstance(metadata, list):
                custom_fields["metadata"] = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
            else:
                raise HTTPException(status_code=422, detail=f"CSV row {row_number} metadata must be a JSON object or array.")

        body = row.get("body", "")
        content_type = row.get("content_type", "1").strip() or "1"
        if content_type not in {"1", "2"}:
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} has an unsupported content_type.")
        notes = _html_to_text(body) if content_type == "1" else body
        if len(notes) > 5000:
            if len(notes) > 10_000:
                raise HTTPException(status_code=413, detail=f"CSV row {row_number} body exceeds resource field limits.")
            custom_fields["Body"] = notes
            notes = ""

        tags = list(dict.fromkeys(tag.strip() for tag in row.get("tags", "").split("|") if tag.strip()))
        if any(len(tag) > 80 for tag in tags):
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} contains a tag over 80 characters.")
        if len(tags) > 20:
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} contains more than 20 tags.")
        try:
            quantity = Decimal(row.get("quantity", "0").strip() or "0")
            payload = InventoryItemCreate(
                name=name,
                category=(row.get("category_title") or row.get("category") or "imported").strip() or "imported",
                catalog_number=(row.get("catalog_number") or row.get("reference") or "").strip(),
                lot_number=row.get("lot_number", "").strip(),
                expires_on=(row.get("expires_on") or row.get("expiration_date") or None),
                quantity=quantity,
                unit=row.get("unit", "").strip() or "each",
                low_stock_threshold=Decimal(row.get("low_stock_threshold", "0").strip() or "0"),
                location=" / ".join(part.strip() for part in row.get("location", "").split("/") if part.strip()),
                notes=notes,
                custom_fields=custom_fields,
            )
        except (InvalidOperation, ValidationError, ValueError) as error:
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} has invalid resource fields: {error}") from error
        result.append((payload, tags))
    if not result:
        raise HTTPException(status_code=422, detail="CSV contains no non-empty resource records.")
    return result


def import_elabftw_samples(raw: bytes, project_id: int) -> list[ImportedSample]:
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="CSV import exceeds 20 MiB.")
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True))
    except (UnicodeDecodeError, csv.Error) as error:
        raise HTTPException(status_code=422, detail="CSV must be valid UTF-8 with well-formed quoting.") from error
    if not rows or not rows[0]:
        raise HTTPException(status_code=422, detail="CSV is empty.")
    headers = [header.strip() for header in rows[0]]
    normalized = [header.casefold() for header in headers]
    if any(not header for header in headers) or len(set(normalized)) != len(normalized):
        raise HTTPException(status_code=422, detail="CSV column names must be non-empty and unique.")
    if "title" not in normalized and "name" not in normalized:
        raise HTTPException(status_code=422, detail="Sample CSV requires a title or name column.")

    reserved = {
        "title", "name", "type", "sample_type", "category", "category_title",
        "external_id", "id", "reference", "catalog_number", "parent_external_id", "location",
        "storage_location", "description", "body", "content_type", "metadata",
        "project_id", "parent_sample_id", "tags",
    }
    result: list[ImportedSample] = []
    for row_number, values in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in values):
            continue
        if len(result) >= MAX_ROWS:
            raise HTTPException(status_code=413, detail="CSV contains more than 1,000 records.")
        if len(values) != len(headers):
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} does not match its header.")
        if any(len(value) > MAX_FIELD_CHARS for value in values):
            raise HTTPException(status_code=413, detail=f"CSV row {row_number} contains a field over 100,000 characters.")
        row = dict(zip(normalized, values, strict=True))
        name = (row.get("title") or row.get("name") or "").strip()
        if not name or len(name) > 160:
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} has an empty or overlong sample name.")
        sample_type = (row.get("sample_type") or row.get("type") or row.get("category_title") or row.get("category") or "imported").strip()
        if not sample_type or len(sample_type) > 80:
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} has an invalid sample type.")
        content_type = row.get("content_type", "1").strip() or "1"
        if content_type not in {"1", "2"}:
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} has an unsupported content_type.")
        description = row.get("description") or row.get("body", "")
        if "description" not in row and content_type == "1":
            description = _html_to_text(description)
        extra_fields = [
            f"{headers[index]}: {value.strip()}"
            for index, value in enumerate(values)
            if normalized[index] not in reserved and value.strip()
        ]
        metadata_json = row.get("metadata", "").strip()
        if metadata_json:
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError as error:
                raise HTTPException(status_code=422, detail=f"CSV row {row_number} metadata is invalid JSON.") from error
            if not isinstance(metadata, (dict, list)):
                raise HTTPException(status_code=422, detail=f"CSV row {row_number} metadata must be a JSON object or array.")
            extra_fields.append("Metadata JSON: " + json.dumps(metadata, ensure_ascii=False, sort_keys=True))
        if extra_fields:
            description = f"{description.rstrip()}\n\nImported CSV fields:\n" + "\n".join(extra_fields) if description.strip() else "Imported CSV fields:\n" + "\n".join(extra_fields)
        if len(description) > 5000:
            raise HTTPException(status_code=413, detail=f"CSV row {row_number} produces a sample description over 5,000 characters.")
        external_id = (row.get("external_id") or row.get("id") or row.get("reference") or row.get("catalog_number") or "").strip()
        if len(external_id) > 120:
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} external ID exceeds 120 characters.")
        parent_external_id = row.get("parent_external_id", "").strip()
        if len(parent_external_id) > 120:
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} parent external ID exceeds 120 characters.")
        storage_location = (row.get("storage_location") or row.get("location") or "").strip()
        if len(storage_location) > 200:
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} location exceeds 200 characters.")
        tags = list(dict.fromkeys(tag.strip() for tag in row.get("tags", "").split("|") if tag.strip()))
        if any(len(tag) > 80 for tag in tags):
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} contains a tag over 80 characters.")
        if len(tags) > 20:
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} contains more than 20 tags.")
        result.append(ImportedSample(
            payload=SampleCreate(
                name=name,
                sample_type=sample_type,
                external_id=external_id,
                project_id=project_id,
                storage_location=storage_location,
                description=description,
            ),
            tags=tags,
            parent_external_id=parent_external_id,
        ))
    if not result:
        raise HTTPException(status_code=422, detail="CSV contains no non-empty sample records.")
    return result
