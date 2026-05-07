# Low Level Design

## Module Details

### `src/main.py` — Entry Point

Creates the FastAPI instance and configures:

1. **CORS Middleware**: origin read from `settings.custom_url_picker.cors.origin` (default `"*"`).
2. **Logging Middleware**: logs method/URL for every request and the response status (loguru).
3. **Router**: includes `custom_url_picker_router.router`.
4. **Health Check**: `GET /health` → `{"status": "ok"}`.

Log level is configurable via the `LOG_LEVEL` environment variable (default: `DEBUG`).

---

### `src/settings.py` — Configuration

**Loading flow:**

```
application.yaml  →  YAML parse  →  resolve ${ENV_VAR}  →  convert keys to snake_case  →  AppSettings (Pydantic)
```

**Config file lookup:**
1. Explicit `config_path` argument
2. `CONFIG_PATH` environment variable
3. Fallback: `application.yaml` in the project root

**Pydantic Models:**

```python
class SparqlQueryConfig(BaseModel):
    query: str
    field_mapping: dict[str, str] = {}

class KgmConfig(BaseModel):
    base_url: str = "http://kgm:8080"
    sparql_queries: dict[str, str | SparqlQueryConfig] = {}

class CorsConfig(BaseModel):
    origin: str = "*"

class CustomUrlPickerConfig(BaseModel):
    cors: CorsConfig = CorsConfig()

class AppSettings(BaseModel):
    kgm: KgmConfig = KgmConfig()
    custom_url_picker: CustomUrlPickerConfig = CustomUrlPickerConfig()
```

**Key conversion:** both `camelCase` and `kebab-case` in YAML are converted to `snake_case` for Pydantic models. Keys inside `sparql_queries` and `field_mapping` are preserved (they are user-defined).

---

### `src/dependencies.py` — Dependency Injection

```python
@lru_cache
def get_settings() -> AppSettings:
    return load_settings()

def get_external_service(settings) -> ExternalService:
    return KgmService(settings)

ExternalServiceDep = Annotated[ExternalService, Depends(get_external_service)]
```

The pattern is straightforward: each route receives `service: ExternalServiceDep` and FastAPI instantiates `KgmService` automatically.

**To swap implementations:** modify `get_external_service()` to return a different class that implements `ExternalService`.

---

### `src/models/api_models.py` — API Models

| Model | Usage |
|---|---|
| `Item` | A single dropdown option (id, value, description + extra fields via `extra="allow"`) |
| `ValidationRequest` | Body of `/v1/resources/validate` |
| `SelectedObject` | A user-selected element (contains `id`) |
| `ValidationErrorResponse` | List of validation errors |
| `ErrorResponse` | Generic error |

---

### `src/routers/custom_url_picker_router.py` — Endpoints

#### `POST /v1/resources`

| Parameter | Type | Description |
|---|---|---|
| `offset` | query (int) | Number of results to skip |
| `limit` | query (int, ≥5) | Number of results to return |
| `filter` | query (str, optional) | Text typed by the user to filter results |
| `body` | JSON body (optional) | Contains `sparql` (query name) and `sparql-params` (parameters) |

**Logic:**
1. Extracts `sparql` and `sparql-params` from the body.
2. Calls `service.search(...)`.
3. Returns the list of `Item` as JSON.

#### `POST /v1/resources/validate`

| Parameter | Type | Description |
|---|---|---|
| `body` | `ValidationRequest` | List of `selectedObjects` + `queryParameters` |

**Logic:**
1. Extracts `sparql` and `sparql-params` from `queryParameters`.
2. Calls `service.validate(...)`.
3. If errors exist → 400 with `ValidationErrorResponse`.
4. If all ok → 200.

---

### `src/services/external_service.py` — Interface

```python
class ExternalService(ABC):
    @abstractmethod
    def search(self, *, offset, limit, filter, body, sparql_key, sparql_params) -> list[Item]: ...

    @abstractmethod
    def validate(self, selected_objects, query_parameters, sparql_key, sparql_params) -> list[str]: ...
```

This is the project's **extension point**. To integrate a service other than KGM:
1. Create a new class in `src/services/` inheriting from `ExternalService`.
2. Implement `search()` and `validate()`.
3. Update `src/dependencies.py` to instantiate the new class.

---

### `src/services/kgm_service.py` — KGM Implementation

#### Initialization

Reads `settings.kgm.base_url` and `settings.kgm.sparql_queries`, building a dictionary of `SparqlQueryConfig`.

#### `_resolve_query(sparql_key, sparql_params)`

1. If `sparql_key` is `None`, uses the `"default"` key.
2. If the key exists in config → uses that query + field mapping.
3. If the key is `"default"` and not in config → uses `DEFAULT_SPARQL_QUERY`.
4. Otherwise → `KeyError`.
5. Replaces positional placeholders:
   - `$1`, `$2`, ... → scalar value from the corresponding `sparql_params[i-1]`
   - `${1*}`, `${2*}`, ... → expands pipe-separated values into SPARQL VALUES format (`"val1" "val2"`)

#### `_fetch_concepts(query)`

Executes the SPARQL query against `{base_url}/v1/graph/sparql` via `httpx.post()` with `Content-Type: application/sparql-query`. Timeout: 30s.

#### `_map_to_items(bindings, field_mapping)`

Maps each SPARQL binding to an `Item`:
- The field mapping defines `{item_field: sparql_variable}`.
- `id` is mandatory; bindings without a value for the variable mapped to `id` are skipped.
- Extra fields (beyond id/value/description) are added flat thanks to `ConfigDict(extra="allow")`.

#### `search(...)`

1. Resolves the query → `_resolve_query()`
2. Executes → `_fetch_concepts()`
3. Maps → `_map_to_items()`
4. Filters in-memory if `filter` is present (case-insensitive across all fields)
5. Pagination: `items[offset : offset + limit]`

#### `validate(...)`

1. Resolves and executes the query like `search`.
2. Compares selected `id`s against available `id`s.
3. Returns a list of errors for each id not found.

---

## SPARQL Configuration — `application.yaml`

```yaml
kgm:
  base_url: "${KGM_BASE_URL}"
  sparql_queries:
    business-concept-query:
      query: |
        PREFIX skos: ...
        SELECT DISTINCT ?label ?definition ?schemeLabel
        WHERE { ... }
      fieldMapping:
        id: label
        value: label
        description: definition
        referenceGlossary: schemeLabel

    business-term-query:
      query: |
        PREFIX skos: ...
        SELECT DISTINCT ?label ?definition ?parentLabel
        WHERE {
          VALUES ?parentLabel { ${1*} }   # ← list placeholder
          ...
        }
      fieldMapping:
        id: label
        value: label
        description: definition
        parentBusinessConcept: parentLabel
```

**Placeholder rules:**
- `$N` → replaced with the value `sparql_params[N-1]` (1-based).
- `${N*}` → the value is split on `|` and rendered as `"val1" "val2"` for use in SPARQL `VALUES`.

---

## Helm Chart

### `values.yaml` — Main Configuration

| Field | Description |
|---|---|
| `image.registry` | Container registry |
| `image.tag` | Image tag |
| `kgm.baseUrl` | KGM URL (injected as env var `KGM_BASE_URL`) |
| `kgm.sparqlQueries` | Map of SPARQL queries (injected into ConfigMap) |
| `configOverride` | Allows fully overriding `application.yaml` |
| `extraEnvVars` | Additional environment variables |

### ConfigMap

Generates `application.yaml` inside the pod from Helm values. Mounted at `/app/application.yaml`.

### Deployment

- Single replica (stateless, horizontally scalable).
- `CONFIG_PATH=/app/application.yaml` and `KGM_BASE_URL` passed as env vars.
- SecurityContext: `runAsUser: 1001`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`.

### Service

Type `ClusterIP`, port `5002`. The service name is what goes into the Witboost template as `baseUrl`.

---

## Testing

Tests are in `tests/` and use:
- **pytest** as the framework
- **respx** to mock HTTP calls to KGM
- **FastAPI TestClient** to test endpoints

To run:
```bash
poetry install
poetry run pytest
```

---

## How to Extend the Project

### Adding a new SPARQL query

1. Add the entry in `application.yaml` under `sparql_queries`.
2. Define the appropriate `fieldMapping`.
3. In the Witboost template, reference the query name with `params.sparql: "query-name"`.

### Integrating a service other than KGM

1. Create `src/services/my_service.py` with a class inheriting from `ExternalService`.
2. Implement `search()` and `validate()`.
3. In `src/dependencies.py`, change `get_external_service()` to return the new class.
4. Update `src/settings.py` if additional configuration is needed.

### Adding extra fields to Item

Thanks to `ConfigDict(extra="allow")` on `Item`, just add the key to `fieldMapping` and the corresponding SPARQL variable. The field will be serialized in the JSON response without any code changes.
