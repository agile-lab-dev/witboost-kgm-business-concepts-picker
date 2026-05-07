# High Level Design

## Overview

The **KGM Business Concepts Picker** is a Python (FastAPI) microservice implementing the **Custom URL Picker** contract of Witboost. Its purpose is to expose business concepts (SKOS Concepts) from a Knowledge Graph Manager (KGM) as selectable options in Witboost template dropdowns.

## System Architecture

```
┌────────────────────────┐         ┌─────────────────────────┐         ┌──────────────┐
│   Witboost UI          │         │  KGM Business Concepts  │         │   Knowledge  │
│   (Template Form)      │────────▶│  Picker (FastAPI)       │────────▶│   Graph      │
│                        │  HTTP   │  :5002                  │  HTTP   │   Manager    │
│   EntitySearchPicker   │◀────────│                         │◀────────│   (SPARQL)   │
└────────────────────────┘         └─────────────────────────┘         └──────────────┘
```

### Main Flow

1. The user opens a Witboost template containing an `EntitySearchPicker` field of type `Remote`.
2. The Witboost UI calls `POST /v1/resources` on the picker with pagination parameters (`offset`, `limit`) and an optional text `filter`.
3. The picker builds a configurable SPARQL query and executes it against the KGM's `/v1/graph/sparql` endpoint.
4. The SPARQL results are mapped to `Item` objects (id, value, description, + extra fields) and returned to the UI.
5. During template validation, Witboost calls `POST /v1/resources/validate` to verify that the user's selected values still exist in the glossary.

## Main Components

| Component | Responsibility |
|---|---|
| **FastAPI App** (`src/main.py`) | Entry-point, CORS, logging middleware, health check |
| **Router** (`src/routers/custom_url_picker_router.py`) | Exposes `/v1/resources` and `/v1/resources/validate` endpoints |
| **ExternalService** (`src/services/external_service.py`) | Abstract interface for the external service (Strategy Pattern) |
| **KgmService** (`src/services/kgm_service.py`) | Concrete implementation: calls KGM via SPARQL |
| **Settings** (`src/settings.py`) | Loads configuration from `application.yaml` with env var resolution |
| **Dependencies** (`src/dependencies.py`) | Dependency Injection via FastAPI `Depends` |
| **Helm Chart** (`helm/`) | Kubernetes deployment with ConfigMap for configuration |

## Technology Stack

- **Language**: Python 3.11
- **Framework**: FastAPI + Uvicorn
- **HTTP Client**: httpx (calls to KGM)
- **Configuration**: YAML + Pydantic
- **Containerization**: Docker
- **Orchestration**: Kubernetes via Helm
- **Testing**: pytest + respx (HTTP mocking)

## Non-Functional Requirements

- **Stateless**: no persistent state, each request is independent.
- **Configurable**: SPARQL queries are defined in the configuration file, not hardcoded.
- **Extensible**: to integrate a service other than KGM, just implement `ExternalService`.
- **Security**: configurable CORS, no credentials in code.

## Deployment Target

The microservice is deployed as a Kubernetes Pod in the same cluster/namespace as Witboost, exposed as a `ClusterIP` Service on port `5002`. The Witboost UI reaches it via internal service discovery (`http://<service-name>:5002`).
