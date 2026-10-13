import json
import mimetypes
import posixpath
import re
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from eln_common.contracts import (
    ProjectImportAttachment,
    ProjectImportEntry,
    ProjectImportExperiment,
    ProjectImportExperimentInfo,
    ProjectImportPayload,
)
from fastapi import HTTPException


MAX_METADATA_BYTES = 20 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
MAX_IMPORT_FILES = 5000


def _safe_member_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    parsed = PurePosixPath(normalized)
    return (
        bool(normalized)
        and not parsed.is_absolute()
        and not any(part in {"", ".", ".."} for part in parsed.parts)
        and not re.match(r"^[A-Za-z]:", normalized)
    )


def _entity_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        text = value.get("@value")
        if isinstance(text, str):
            return text
    return ""


def _references(value: object) -> list[str]:
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in values:
        reference = item.get("@id") if isinstance(item, dict) else item
        if isinstance(reference, str):
            result.append(reference)
    return result


def _crate_member(reference: str, members: dict[str, object]) -> str | None:
    path = reference.removeprefix("./")
    if not _safe_member_path(path):
        return None
    normalized = posixpath.normpath(path)
    if normalized in members:
        return normalized
    matches = [name for name in members if name.endswith(f"/{normalized}")]
    return matches[0] if len(matches) == 1 else None


def _node_keywords(node: dict) -> list[str]:
    values = node.get("keywords", [])
    values = values if isinstance(values, list) else [values]
    return [
        item.strip()
        for item in values
        if isinstance(item, str) and item.strip()
    ][:20]


def import_eln_crate(
    archive: ZipFile, members: dict[str, object], target_project_name: str
) -> tuple[ProjectImportPayload, dict[str, bytes]]:
    metadata_paths = [
        name for name in members if PurePosixPath(name).name == "ro-crate-metadata.json"
    ]
    if len(metadata_paths) != 1:
        raise HTTPException(
            status_code=422,
            detail="ELN Consortium ZIP must contain exactly one ro-crate-metadata.json.",
        )
    metadata_path = metadata_paths[0]
    metadata_info = members[metadata_path]
    if metadata_info.file_size > MAX_METADATA_BYTES:
        raise HTTPException(status_code=413, detail="RO-Crate metadata exceeds 20 MiB.")
    try:
        crate = json.loads(archive.read(metadata_path))
    except (BadZipFile, OSError, RuntimeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=422, detail="RO-Crate metadata is unreadable JSON."
        ) from error
    graph = crate.get("@graph") if isinstance(crate, dict) else None
    if not isinstance(graph, list) or len(graph) > MAX_IMPORT_FILES:
        raise HTTPException(status_code=422, detail="RO-Crate graph is invalid or too large.")
    nodes = {
        node["@id"]: node
        for node in graph
        if isinstance(node, dict) and isinstance(node.get("@id"), str)
    }
    if len(nodes) != sum(isinstance(node, dict) and isinstance(node.get("@id"), str) for node in graph):
        raise HTTPException(status_code=422, detail="RO-Crate contains duplicate entity IDs.")
    root = nodes.get("./")
    root_references = _references(root.get("hasPart")) if isinstance(root, dict) else []
    candidates = [
        nodes[reference]
        for reference in root_references
        if reference in nodes and isinstance(nodes[reference], dict)
    ]
    if not candidates:
        candidates = [
            node
            for node in nodes.values()
            if node.get("@id") != "./"
            and (
                "Dataset" in _references(node.get("@type"))
                or node.get("@type") == "Dataset"
            )
            and ("text" in node or "hasPart" in node)
        ]
    importable = [
        node
        for node in candidates
        if not any(word in str(node.get("genre", "")).casefold() for word in ("file", "attachment"))
    ]
    if not importable:
        raise HTTPException(status_code=422, detail="RO-Crate contains no importable records.")

    imported_files: dict[str, bytes] = {}
    file_path_to_virtual_path: dict[str, str] = {}
    experiments: list[ProjectImportExperiment] = []

    def make_entry(node: dict, fallback_title: str) -> ProjectImportEntry:
        content = _entity_text(node.get("text"))
        attachments: list[ProjectImportAttachment] = []
        references = _references(node.get("hasPart"))
        html_paths = re.findall(
            r"""(?:src|href)\s*=\s*["']([^"'#?]+)["']""", content, flags=re.IGNORECASE
        )
        entry_paths: set[str] = set()
        for reference in [*references, *html_paths]:
            file_path = _crate_member(reference, members)
            if file_path is None or file_path in entry_paths:
                continue
            info = members[file_path]
            if info.is_dir() or info.file_size > MAX_ATTACHMENT_BYTES:
                if info.file_size > MAX_ATTACHMENT_BYTES:
                    raise HTTPException(
                        status_code=413, detail="An imported attachment exceeds 25 MiB."
                    )
                continue
            if file_path == metadata_path:
                continue
            virtual_path = file_path_to_virtual_path.get(file_path)
            if virtual_path is None:
                if len(imported_files) >= 10000:
                    raise HTTPException(status_code=413, detail="ELN archive has too many attachments.")
                try:
                    attachment_data = archive.read(file_path)
                except (BadZipFile, OSError, RuntimeError) as error:
                    raise HTTPException(
                        status_code=422, detail="ELN archive contains an unreadable attachment."
                    ) from error
                if len(attachment_data) != info.file_size:
                    raise HTTPException(
                        status_code=422, detail="Imported attachment size is inconsistent."
                    )
                virtual_path = f"attachments/entry-{len(imported_files) + 1}"
                imported_files[virtual_path] = attachment_data
                file_path_to_virtual_path[file_path] = virtual_path
            entry_paths.add(file_path)
            attachments.append(
                ProjectImportAttachment(
                    archive_path=virtual_path,
                    original_filename=PurePosixPath(file_path).name or "attachment",
                    media_type=mimetypes.guess_type(file_path)[0] or "application/octet-stream",
                )
            )
        return ProjectImportEntry(
            title=str(node.get("name") or fallback_title)[:200],
            content=content[:100_000],
            tags=_node_keywords(node),
            attachments=attachments,
        )

    for index, record in enumerate(importable[:1000], start=1):
        children = [
            nodes[reference]
            for reference in _references(record.get("hasPart"))
            if reference in nodes
            and isinstance(nodes[reference], dict)
            and reference != record.get("@id")
            and "text" in nodes[reference]
        ]
        entries = [
            make_entry(child, f"Entry {entry_index}")
            for entry_index, child in enumerate(children, start=1)
        ]
        if not entries and ("text" in record or record.get("hasPart")):
            entries = [make_entry(record, "Imported record")]
        if not entries:
            continue
        experiments.append(
            ProjectImportExperiment(
                experiment=ProjectImportExperimentInfo(
                    name=str(record.get("name") or f"Imported record {index}")[:160],
                    description="Imported from an ELN Consortium RO-Crate.",
                ),
                tags=_node_keywords(record),
                entries=entries,
            )
        )
    if not experiments:
        raise HTTPException(
            status_code=422,
            detail="RO-Crate contained no supported experiment or text records.",
        )
    payload = ProjectImportPayload(
        project={"name": target_project_name, "description": "Imported RO-Crate records."},
        experiments=experiments,
        tasks=[],
    )
    return payload, imported_files
