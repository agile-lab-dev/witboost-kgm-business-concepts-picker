# KGM Custom URL Picker

A [Witboost](https://www.witboost.com/) **Custom URL Picker** microservice that serves drop-down options to templates by querying a **Knowledge Graph Manager (KGM)** SPARQL endpoint.

## Overview

The Custom URL Picker is an extension point in Witboost. When a template form contains a Custom URL Picker field, Witboost calls this microservice to fetch the available options for the drop-down menu. Users can filter, paginate, and validate their selections.

This service queries a KGM instance via its SPARQL endpoint, extracts SKOS concepts, and maps them to the drop-down items expected by the [Custom URL Picker OpenAPI contract](custom-url-picker-openapi.yaml).

### Architecture

```
Witboost UI  ──▶  POST /v1/resources?offset=0&limit=5&filter=…
                  Body: { "sparql": "business-term-query", "sparql-params": "A|B" }
                        │
                        ▼
                  ┌─────────────┐     _resolve_query()
                  │   FastAPI    │───▶  look up named query
                  │   Router     │      + replace $1, ${1*}, …
                  └──────┬──────┘
                         │  Depends()
                         ▼
                  ┌─────────────┐        SPARQL query        ┌─────────┐
                  │  KgmService │  ─────────────────────▶    │   KGM   │
                  └─────────────┘                            └─────────┘
```

### Item Mapping

The SPARQL query results are mapped to Custom URL Picker items as follows:

| Custom URL Picker field | SPARQL binding    | Description                              |
|-------------------------|-------------------|------------------------------------------|
| `id`                    | `?label`          | The concept label (used as identifier)   |
| `value`                 | `?label`          | The concept label (displayed to user)    |
| `description`           | `?definition`     | The concept definition                   |
| `referenceGlossary`     | `?schemeLabel`    | The vocabulary/scheme the concept belongs to |

## Named SPARQL Queries

The platform team can configure **multiple named SPARQL queries** in `application.yaml`. Each query is identified by a unique key (e.g. `business-concept-query`, `business-term-query`).

When calling the Custom URL Picker, the **template author** specifies which query to run via the `?sparql=<key>` query parameter. This allows the same microservice instance to serve different drop-downs in different parts of the UI.

### Positional Placeholders

Queries can contain **scalar** and **list** placeholders that are replaced at runtime with values from the `sparql-params` field in the POST body (comma-separated positional params):

| Placeholder | Type   | Description                                                        |
|-------------|--------|--------------------------------------------------------------------|
| `$1`, `$2`  | Scalar | Replaced with the corresponding comma-separated value as-is       |
| `${1*}`, `${2*}` | List | Pipe-separated values expanded into SPARQL `VALUES` quoted strings |

**List placeholder example:** if `sparql-params` = `"Customer Metric|Investment"`, then `${1*}` is expanded to `"Customer Metric" "Investment"` — ready to use inside a SPARQL `VALUES` clause.

### Example Configuration

```yaml
kgm:
  base_url: "http://kgm:8080"
  sparql_queries:
    # Fetch top-level business concepts (parents)
    business-concept-query: |
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      SELECT DISTINCT ?label ?definition ?schemeLabel
      WHERE {
        ?concept a skos:Concept ;
                 skos:inScheme ?scheme .
        { ?child skos:broader ?concept . }
        UNION
        { ?concept skos:narrower ?child . }
        OPTIONAL { ?concept skos:prefLabel ?label . FILTER(LANG(?label) = "en" || LANG(?label) = "") }
        OPTIONAL { ?concept skos:definition ?definition . FILTER(LANG(?definition) = "en" || LANG(?definition) = "") }
        OPTIONAL { ?scheme skos:prefLabel ?schemeLabel . FILTER(LANG(?schemeLabel) = "en" || LANG(?schemeLabel) = "") }
      }
      ORDER BY ?schemeLabel ?label

    # Fetch business terms narrower than one or more parent concepts.
    # ${1*} is replaced with pipe-separated concept labels.
    # e.g. sparql-params = "Customer Metric|Investment"
    #   → VALUES ?parentLabel { "Customer Metric" "Investment" }
    business-term-query: |
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      SELECT DISTINCT ?label ?definition ?schemeLabel
      WHERE {
        VALUES ?parentLabel { ${1*} }
        ?parent skos:prefLabel ?parentLabel .
        ?term a skos:Concept ;
              skos:broader ?parent ;
              skos:inScheme ?scheme .
        OPTIONAL { ?term skos:prefLabel ?label . FILTER(LANG(?label) = "en" || LANG(?label) = "") }
        OPTIONAL { ?term skos:definition ?definition . FILTER(LANG(?definition) = "en" || LANG(?definition) = "") }
        OPTIONAL { ?scheme skos:prefLabel ?schemeLabel . FILTER(LANG(?schemeLabel) = "en" || LANG(?schemeLabel) = "") }
      }
      ORDER BY ?label
```

### Query Resolution Rules

| `?sparql` param | `"default"` key in config | Behaviour                                |
|-----------------|---------------------------|------------------------------------------|
| Not provided    | Present                   | Uses the `"default"` query               |
| Not provided    | Absent                    | Uses the built-in default query           |
| `my-query`      | —                         | Uses the `"my-query"` query from config   |
| `unknown-key`   | —                         | Returns **400 Bad Request**               |

### SPARQL Query Requirements

Each query **must return bindings** with at least:

| Variable       | Required | Description                          |
|----------------|----------|--------------------------------------|
| `?label`       | Yes      | Concept label — mapped to `id` and `value` |
| `?definition`  | No       | Concept definition — mapped to `description` |
| `?schemeLabel` | No       | Vocabulary name — mapped to `referenceGlossary` |

Any additional variables (e.g. `?concept`, `?scheme`) are allowed but ignored.

## Configuration

The service is configured via `application.yaml`, which supports `${ENV_VAR}` placeholder resolution from environment variables.

### Configuration Parameters

| Parameter                        | Env Variable   | Default            | Description                              |
|----------------------------------|----------------|--------------------|------------------------------------------|
| `kgm.base_url`                  | `KGM_BASE_URL` | `http://kgm:8080`  | Base URL of the Knowledge Graph Manager  |
| `kgm.sparql_queries`            | —              | `{}`               | Map of named SPARQL queries (see above)  |
| `custom_url_picker.cors.origin`  | —              | `*`                | Allowed CORS origin                      |

## Running Locally

### Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/)
- A running KGM instance

### Install dependencies

```bash
poetry install
```

### Run tests

```bash
poetry run pytest -v
```

### Start the server

```bash
# Point to your local KGM instance
export KGM_BASE_URL="http://localhost:9980"

poetry run uvicorn src.main:app --host 0.0.0.0 --port 5002
```

The service will be available at `http://localhost:5002`.

### API Endpoints

| Method | Path                       | Description                          |
|--------|----------------------------|--------------------------------------|
| POST   | `/v1/resources`            | Retrieve paginated drop-down options |
| POST   | `/v1/resources/validate`   | Validate previously selected values  |
| GET    | `/health`                  | Health check                         |

### Query Parameters

| Parameter       | In         | Required | Description                                                     |
|-----------------|------------|----------|-----------------------------------------------------------------|
| `offset`        | URL query  | Yes      | Number of items to skip (pagination)                            |
| `limit`         | URL query  | Yes      | Number of items to return (min 5)                               |
| `filter`        | URL query  | No       | Free-text filter on value, description, referenceGlossary       |
| `sparql`        | POST body  | No       | Key of the named SPARQL query to execute                        |
| `sparql-params` | POST body  | No       | Comma-separated positional params; use `|` inside a param for list placeholders |

#### Example: retrieve business concepts

```bash
curl -X POST 'http://localhost:5002/v1/resources?offset=0&limit=10' \
  -H 'Content-Type: application/json' \
  -d '{"sparql": "business-concept-query"}'
```

#### Example: retrieve business terms for multiple parent concepts

```bash
curl -X POST 'http://localhost:5002/v1/resources?offset=0&limit=10&filter=customer' \
  -H 'Content-Type: application/json' \
  -d '{"sparql": "business-term-query", "sparql-params": "Customer Metric|Investment"}'
```

#### Example: validate selections

```bash
curl -X POST 'http://localhost:5002/v1/resources/validate' \
  -H 'Content-Type: application/json' \
  -d '{
    "selectedObjects": [{"id": "Banking Channels"}],
    "queryParameters": {"sparql": "business-concept-query"}
  }'
```

## Docker

### Build

```bash
docker build -t kgm-custom-url-picker:latest .
```

### Run

```bash
docker run -d --rm --name kgm-custom-url-picker \
  -p 5002:5002 \
  -e KGM_BASE_URL="http://host.docker.internal:9980" \
  kgm-custom-url-picker:latest
```

> **Note:** Use `host.docker.internal` to reach services running on the Docker host (macOS/Windows). On Linux, use `--network host` or the host IP.

To configure custom SPARQL queries via Docker, mount a custom `application.yaml`:

```bash
docker run -d --rm --name kgm-custom-url-picker \
  -p 5002:5002 \
  -v $(pwd)/application.yaml:/app/application.yaml \
  kgm-custom-url-picker:latest
```

To stop:

```bash
docker stop kgm-custom-url-picker
```

## Kubernetes (Helm)

### Install

```bash
helm install kgm-custom-url-picker ./helm
```

### Helm Values

| Key                        | Type   | Default            | Description                                                   |
|----------------------------|--------|--------------------|---------------------------------------------------------------|
| `image.registry`           | string | `registry.example.com/kgm-custom-url-picker` | Docker image registry                      |
| `image.tag`                | string | `latest`           | Docker image tag                                              |
| `image.pullPolicy`         | string | `Always`           | Image pull policy                                             |
| `kgm.baseUrl`              | string | `http://kgm:8080`  | Base URL of the KGM service                                   |
| `kgm.sparqlQueries`        | object | `{}`               | Map of named SPARQL queries (rendered into the ConfigMap)      |
| `dockerRegistrySecretName`  | string | `regcred`          | Name of the image pull secret                                 |
| `extraEnvVars`             | list   | `[]`               | Additional environment variables                              |
| `configOverride`           | string | `nil`              | Override the full `application.yaml` content                  |
| `securityContext`           | object | `{runAsUser: 1001, ...}` | Pod security context                                   |
| `readinessProbe`           | object | `{}`               | Readiness probe configuration                                 |
| `livenessProbe`            | object | `{}`               | Liveness probe configuration                                  |
| `resources`                | object | `{}`               | CPU/memory resource limits                                    |
| `labels`                   | object | `{}`               | Additional labels to apply                                    |

### Deploy with custom queries

Create a `custom-values.yaml`:

```yaml
kgm:
  baseUrl: "http://my-kgm:9090"
  sparqlQueries:
    business-concept-query: |
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      SELECT DISTINCT ?label ?definition ?schemeLabel
      WHERE {
        ?concept a skos:Concept ;
                 skos:inScheme ?scheme .
        { ?child skos:broader ?concept . }
        UNION
        { ?concept skos:narrower ?child . }
        OPTIONAL { ?concept skos:prefLabel ?label . FILTER(LANG(?label) = "en" || LANG(?label) = "") }
        OPTIONAL { ?concept skos:definition ?definition . FILTER(LANG(?definition) = "en" || LANG(?definition) = "") }
        OPTIONAL { ?scheme skos:prefLabel ?schemeLabel . FILTER(LANG(?schemeLabel) = "en" || LANG(?schemeLabel) = "") }
      }
      ORDER BY ?schemeLabel ?label
    business-term-query: |
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      SELECT DISTINCT ?label ?definition ?schemeLabel
      WHERE {
        VALUES ?parentLabel { ${1*} }
        ?parent skos:prefLabel ?parentLabel .
        ?term a skos:Concept ;
              skos:broader ?parent ;
              skos:inScheme ?scheme .
        OPTIONAL { ?term skos:prefLabel ?label . FILTER(LANG(?label) = "en" || LANG(?label) = "") }
        OPTIONAL { ?term skos:definition ?definition . FILTER(LANG(?definition) = "en" || LANG(?definition) = "") }
        OPTIONAL { ?scheme skos:prefLabel ?schemeLabel . FILTER(LANG(?schemeLabel) = "en" || LANG(?schemeLabel) = "") }
      }
      ORDER BY ?label

image:
  registry: "my-registry.com/kgm-custom-url-picker"
  tag: "1.0.0"
```

```bash
helm install kgm-custom-url-picker ./helm -f custom-values.yaml
```

### Using in a Witboost Template

Configure `EntitySearchPicker` fields in your template. The `params` map is sent as the POST body, where `sparql` and `sparql-params` select and parameterise the named query.

#### Business Concept Selector

```yaml
properties:
  businessConcept:
    title: Business Concept
    ui:field: EntitySearchPicker
    ui:options:
      entities:
        - type: Remote
          displayName: Business Concepts
          fieldsToSave:
            - id
            - value
            - description
            - referenceGlossary
          columns:
            - name: 'Name'
              path: '{{value}}'
            - name: 'Description'
              path: '{{description}}'
            - name: 'Glossary'
              path: '{{referenceGlossary}}'
          displayField: '{{value}}'
          userFilters: ['search']
          apiSpec:
            retrieval:
              baseUrl: 'http://kgm-custom-url-picker:5002'
              path: '/v1/resources'
              method: 'POST'
              params:
                sparql: 'business-concept-query'
```

#### Business Term Selector (filtered by selected concepts)

Assumes `businessConcept` is a multi-select field whose selected `id` values
are joined with `|` and passed via `sparql-params`. The `${1*}` placeholder
in the query expands them into a SPARQL `VALUES` clause.

```yaml
  businessTerm:
    title: Business Term
    ui:field: EntitySearchPicker
    ui:options:
      entities:
        - type: Remote
          displayName: Business Terms
          fieldsToSave:
            - id
            - value
            - description
          columns:
            - name: 'Name'
              path: '{{value}}'
            - name: 'Description'
              path: '{{description}}'
          displayField: '{{value}}'
          userFilters: ['search']
          apiSpec:
            retrieval:
              baseUrl: 'http://kgm-custom-url-picker:5002'
              path: '/v1/resources'
              method: 'POST'
              params:
                sparql: 'business-term-query'
                sparql-params: '{{businessConcept.id}}'
```

> **Note:** If `businessConcept` is a single-select, `{{businessConcept.id}}` is a single label
> like `"Customer Metric"`. If multi-select, join the selected IDs with `|` pipes,
> e.g. `"Customer Metric|Investment"`, so `${1*}` expands to
> `"Customer Metric" "Investment"` in the SPARQL `VALUES` clause.

## Project Structure

```
├── application.yaml              # App config (env-var placeholders + named queries)
├── pyproject.toml                # Poetry dependencies
├── server_start.sh               # Uvicorn startup script
├── Dockerfile                    # Container image
├── custom-url-picker-openapi.yaml# OpenAPI specification
├── example-kgm-response.yaml     # Example KGM SPARQL response
│
├── src/
│   ├── main.py                   # FastAPI app, middleware, health check
│   ├── dependencies.py           # Dependency injection wiring
│   ├── settings.py               # YAML config loader with ${ENV_VAR} resolution
│   ├── models/
│   │   └── api_models.py         # Pydantic models (Item, ValidationRequest, etc.)
│   ├── routers/
│   │   └── custom_url_picker_router.py   # POST /v1/resources, POST /v1/resources/validate
│   └── services/
│       ├── external_service.py           # Abstract interface
│       └── kgm_service.py                # KGM SPARQL implementation (named queries)
│
├── tests/
│   ├── conftest.py               # Shared fixtures + in-memory mock service
│   ├── test_health.py            # Health endpoint tests
│   ├── test_resources.py         # /v1/resources route tests
│   ├── test_validate.py          # /v1/resources/validate route tests
│   └── test_kgm_service.py      # KgmService unit tests (queries, params, mapping)
│
└── helm/                         # Helm chart for Kubernetes deployment
    ├── Chart.yaml
    ├── values.yaml
    └── templates/
        ├── _helpers.tpl
        ├── configmap.yaml        # Renders named queries from values
        ├── deployment.yaml
        └── service.yaml
```
