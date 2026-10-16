# Shared contracts

Language-neutral JSON Schema contracts shared by the API, extraction pipeline and web client.

| File | Purpose |
|------|---------|
| `extractor-row.json` | Rows emitted by rule parser / OCR / optional Extractor plugin |
| `result.json` | Persisted Result object after normalization |

Pydantic mirrors live in `api/app/schemas/`. The HTTP contract is the OpenAPI schema (`make openapi`, or `/docs` on a running API).
