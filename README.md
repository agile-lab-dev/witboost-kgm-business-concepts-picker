<p align="center">
    <a href="https://www.witboost.com/">
        <img src="docs/img/witboost_logo.svg" alt="witboost" width=600 >
    </a>
</p>

Designed by [Agile Lab](https://www.agilelab.it/), Witboost is a versatile platform that addresses a wide range of sophisticated data engineering challenges. It enables businesses to discover, enhance, and productize their data, fostering the creation of automated data platforms that adhere to the highest standards of data governance. Want to know more about Witboost? Check it out [here](https://www.witboost.com/) or [contact us!](https://witboost.com/contact-us)

This repository is part of our [Starter Kit](https://github.com/agile-lab-dev/witboost-starter-kit) meant to showcase Witboost integration capabilities and provide a "batteries-included" product.

# KGM Custom URL Picker

A [Witboost](https://www.witboost.com/) **Custom URL Picker** microservice that serves drop-down options to templates by querying the **Witboost Knowledge Graph Manager (KGM)** [SPARQL endpoint](https://docs.witboost.com/docs/apis/witboost/knowledge-graph-manager#tag/Graph/operation/queryWithSparql).

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

### Item Mapping — `fieldMapping`

Each SPARQL query can define a **`fieldMapping`** that controls how SPARQL result variables are mapped to the JSON fields of each picker item. The mapping is a flat `{ itemField: sparqlVariable }` dict:

- **`id`** is mandatory — bindings where the mapped variable has no value are skipped.
- **`value`**, **`description`** are optional core fields.
- **Any other key** becomes an extra flat field on the item JSON (the model uses `additionalProperties: true`).

You can map **as many fields as you want**. Only the variables listed in `fieldMapping` end up in the item; unmapped SPARQL variables are ignored.

#### Default mapping

When no `fieldMapping` is provided (or the query is a plain string), the built-in default mapping is used:

| Item field          | SPARQL variable | Description                              |
|---------------------|-----------------|------------------------------------------|
| `id`                | `?label`        | The concept label (used as identifier)   |
| `value`             | `?label`        | The concept label (displayed to user)    |
| `description`       | `?definition`   | The concept definition                   |
| `referenceGlossary` | `?schemeLabel`  | The vocabulary/scheme the concept belongs to |

The default mapping is applied automatically in the following cases:

1. **Plain string query** — no `fieldMapping` specified:
   ```yaml
   sparql_queries:
     my-query: |
       SELECT ?label ?definition ?schemeLabel WHERE { ... }
   ```
2. **Structured query without `fieldMapping`** — only `query` is provided:
   ```yaml
   sparql_queries:
     my-query:
       query: |
         SELECT ?label ?definition ?schemeLabel WHERE { ... }
   ```
3. **No query configured at all** — the built-in default SPARQL query runs (fetches SKOS concepts with `?label`, `?definition`, `?schemeLabel`).

In all three cases the resulting items will have `id`, `value`, `description`, and `referenceGlossary` fields.

#### Custom mapping example

```yaml
sparql_queries:
  data-products:
    query: |
      SELECT ?dpName ?dpDomain ?dpOwner ?dpStatus WHERE { ... }
    fieldMapping:
      id: dpName
      value: dpName
      description: dpDomain
      owner: dpOwner
      status: dpStatus
```

Produces items like:

```json
{
  "id": "MyDataProduct",
  "value": "MyDataProduct",
  "description": "Finance",
  "owner": "Alice",
  "status": "Active"
}
```

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

Each named query can be either a **plain SPARQL string** (backward-compatible, uses the default field mapping) or a **structured object** with `query` and `fieldMapping`:

```yaml
kgm:
  base_url: "http://kgm:8080"
  sparql_queries:
    # ── Structured format with explicit fieldMapping ─────────────────
    business-concept-query:
      query: |
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
      fieldMapping:
        id: label
        value: label
        description: definition
        referenceGlossary: schemeLabel

    # ── Plain string format (uses default mapping) ───────────────────
    business-term-query: |
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      SELECT DISTINCT ?label ?definition (?parentLabel AS ?schemeLabel)
      WHERE {
        VALUES ?parentLabel { ${1*} }
        ?parent skos:prefLabel ?parentLabel .
        ?term a skos:Concept ;
              skos:broader ?parent ;
              skos:inScheme ?scheme .
        OPTIONAL { ?term skos:prefLabel ?label . FILTER(LANG(?label) = "en" || LANG(?label) = "") }
        OPTIONAL { ?term skos:definition ?definition . FILTER(LANG(?definition) = "en" || LANG(?definition) = "") }
      }
      ORDER BY ?label

    # ── Custom domain with extra fields ──────────────────────────────
    data-product-query:
      query: |
        SELECT ?dpName ?dpDomain ?dpOwner ?dpStatus
        WHERE { ?dp a :DataProduct . ... }
      fieldMapping:
        id: dpName
        value: dpName
        description: dpDomain
        owner: dpOwner
        status: dpStatus
```

### Query Resolution Rules

| `?sparql` param | `"default"` key in config | Behaviour                                |
|-----------------|---------------------------|------------------------------------------|
| Not provided    | Present                   | Uses the `"default"` query               |
| Not provided    | Absent                    | Uses the built-in default query           |
| `my-query`      | —                         | Uses the `"my-query"` query from config   |
| `unknown-key`   | —                         | Returns **400 Bad Request**               |

### SPARQL Query Requirements

When using the **default field mapping** (no `fieldMapping` specified), the query must return:

| Variable       | Required | Description                          |
|----------------|----------|--------------------------------------|
| `?label`       | Yes      | Concept label — mapped to `id` and `value` |
| `?definition`  | No       | Concept definition — mapped to `description` |
| `?schemeLabel` | No       | Vocabulary name — mapped to `referenceGlossary` |

When using a **custom `fieldMapping`**, the query must return at least the SPARQL variable mapped to `id`. All other mapped variables are optional — missing values become `null` in the item JSON. Unmapped SPARQL variables are ignored.

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
| `filter`        | URL query  | No       | Free-text filter across all mapped item fields              |
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
    # Structured format with explicit fieldMapping
    business-concept-query:
      query: |
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
      fieldMapping:
        id: label
        value: label
        description: definition
        referenceGlossary: schemeLabel

    # Plain string format (backward-compatible, uses default mapping)
    business-term-query: |
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      SELECT DISTINCT ?label ?definition (?parentLabel AS ?schemeLabel)
      WHERE {
        VALUES ?parentLabel { ${1*} }
        ?parent skos:prefLabel ?parentLabel .
        ?term a skos:Concept ;
              skos:broader ?parent ;
              skos:inScheme ?scheme .
        OPTIONAL { ?term skos:prefLabel ?label . FILTER(LANG(?label) = "en" || LANG(?label) = "") }
        OPTIONAL { ?term skos:definition ?definition . FILTER(LANG(?definition) = "en" || LANG(?definition) = "") }
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

#### Custom Domain Selector (with extra fields)

When using a custom `fieldMapping`, include the extra fields in `fieldsToSave` and `columns`:

```yaml
  dataProduct:
    title: Data Product
    ui:field: EntitySearchPicker
    ui:options:
      entities:
        - type: Remote
          displayName: Data Products
          fieldsToSave:
            - id
            - value
            - description
            - owner
            - status
          columns:
            - name: 'Name'
              path: '{{value}}'
            - name: 'Domain'
              path: '{{description}}'
            - name: 'Owner'
              path: '{{owner}}'
            - name: 'Status'
              path: '{{status}}'
          displayField: '{{value}}'
          userFilters: ['search']
          apiSpec:
            retrieval:
              baseUrl: 'http://kgm-custom-url-picker:5002'
              path: '/v1/resources'
              method: 'POST'
              params:
                sparql: 'data-product-query'
```