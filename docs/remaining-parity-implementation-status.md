# Remaining ELN Parity Work: Handoff Status

This note records the state reached when implementation was paused at the user's request. The work below is partial and has not been validated; it is not a feature-completion or regulatory-compliance claim.

## Scope clarification

Interactive ELN is intended to be a compatible product with general ELN capabilities, not an exact SciNote or eLabFTW replacement. Implement general needs first. Track vendor-specific formats and behavior as future work rather than guessing at undocumented proprietary formats. In particular, SciNote's public material mentions `.eln` protocol-template files, but this work did not establish their schema. The ELN Consortium/eLabFTW `.eln` RO-Crate is a documented interchange format and was selected as the standards-based import target.

Regulatory controls and certification remain out of scope.

## Work started in the working tree

- `backend/services/notebook/app/models.py`
  - Added models for hierarchical storage locations, workflow rules/executions, and RFC 3161 entry timestamp records.
  - Added nullable structured-location foreign keys to inventory, sample, and equipment records.
- `backend/eln_common/contracts.py`
  - Added contracts for locations, workflow rules, and entry timestamps.
  - Added optional structured-location IDs to inventory, sample, and equipment payloads.
- `backend/services/notebook/app/service.py`
  - Began creating a task when an experiment status transition matches a configured project workflow rule.
  - Began validating structured locations on inventory, sample, and equipment creation.
  - Began RFC 3161 timestamp creation and timestamp record retrieval using a configured endpoint and pinned signer certificate.
- `backend/services/notebook/app/router.py`
  - Added internal notebook-service routes for workflow rules, storage locations, timestamp records, and timestamp proof ZIP downloads.
- `backend/gateway/app/router.py`
  - Added gateway proxy routes for workflow rules, storage locations, and timestamp records/proofs.
- `backend/gateway/app/eln_import.py`
  - Added an initial RO-Crate parsing helper that attempts to map text records, keywords, and referenced files into the existing project import contracts.
  - This helper is **not yet connected** to the existing project import endpoint.
- `docs/remaining-parity-implementation-status.md`
  - This handoff note.

## Not implemented or not finished

- The RO-Crate importer is not wired into the import endpoint. Vendor-specific SciNote `.eln` parsing is not implemented.
- No Alembic migration has been added for the new notebook tables and columns. Do not deploy the new model code until a migration is created and applied.
- `rfc3161ng` is imported by the notebook service but has not been added to the Python dependency manifest or installed. Its runtime APIs and proof verification flow have not been tested.
- The TSA environment variables and operational setup have not been added to `.env.example`, Compose, or the migration/design documentation.
- Structured locations do not yet have frontend management/selection UI; legacy free-text locations remain in the existing UI.
- Workflow rules do not yet have frontend management UI.
- Timestamp creation/list/download controls do not yet have frontend UI.
- Scientific document authoring/rendering tools (for example, math notation and chemical structures) have not been implemented.
- README parity claims and vendor-specific follow-up documentation have not been updated for these partial changes.
- No tests, builds, migration rendering, or type checks have been run after these edits. Treat all new code as unverified.

## Suggested resume sequence

1. Inspect the current working tree and resolve any type, import, or model issues in the partial changes.
2. Add and validate a notebook Alembic migration before running services.
3. Finish and test the RO-Crate importer, including hostile ZIP paths, archive size limits, attachment mapping, and malformed metadata; connect it to the existing import endpoint.
4. Add the RFC 3161 dependency/configuration, verify the library's exact token and timestamp APIs, and test failure paths and offline proof contents before documenting operational trust assumptions.
5. Complete the frontend surfaces for locations, workflow rules, timestamps, and scientific writing tools.
6. Update the README/design documentation to distinguish implemented general capabilities from vendor-specific follow-up and run focused backend/frontend validation.

No regulated certification or compliance claim should be made based on this work.
