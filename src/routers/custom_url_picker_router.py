"""
Routes for the Custom URL Picker contract.

- POST /v1/resources          → paginated drop-down options
- POST /v1/resources/validate → validate previously selected values
"""

from fastapi import APIRouter, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger

from src.dependencies import ExternalServiceDep
from src.models.api_models import ErrorResponse, ValidationErrorDetail, ValidationErrorResponse, ValidationRequest

router = APIRouter()


@router.post("/v1/resources")
def retrieve_values(
    service: ExternalServiceDep,
    offset: int = Query(..., description="Number of values to skip"),
    limit: int = Query(..., ge=5, description="Number of values to return"),
    filter: str | None = Query(None, description="Free-text filter typed by the user"),
    body: dict | None = None,
) -> Response:
    """Return a page of drop-down options from the external service."""
    try:
        sparql_key = body.get("sparql") if body else None
        raw_params = body.get("sparql-params") if body else None
        params_list = [p.strip() for p in raw_params.split(",")] if raw_params else None

        items = service.search(
            offset=offset,
            limit=limit,
            filter=filter,
            body=body,
            sparql_key=sparql_key,
            sparql_params=params_list,
        )
        return JSONResponse(content=jsonable_encoder(items), status_code=200)
    except KeyError as exc:
        logger.warning("Bad SPARQL query key: {}", exc)
        return JSONResponse(
            content=jsonable_encoder(ErrorResponse(errors=[str(exc)])),
            status_code=400,
        )
    except Exception as exc:
        logger.exception("Error retrieving values from external service")
        return JSONResponse(
            content=jsonable_encoder(ErrorResponse(errors=[str(exc)])),
            status_code=500,
        )


@router.post("/v1/resources/validate")
def validate(
    service: ExternalServiceDep,
    validation_request: ValidationRequest,
) -> Response:
    """Validate that selected options still exist in the external glossary."""
    try:
        qp = validation_request.queryParameters or {}
        sparql_key = qp.get("sparql")
        raw_params = qp.get("sparql-params")
        params_list = [p.strip() for p in raw_params.split(",")] if raw_params else None

        errors = service.validate(
            selected_objects=validation_request.selectedObjects,
            query_parameters=validation_request.queryParameters,
            sparql_key=sparql_key,
            sparql_params=params_list,
        )

        if errors:
            detail = [ValidationErrorDetail(error=e) for e in errors]
            return JSONResponse(
                content=jsonable_encoder(ValidationErrorResponse(errors=detail)),
                status_code=400,
            )

        return JSONResponse(content="Validation succeeded", status_code=200)

    except KeyError as exc:
        logger.warning("Bad SPARQL query key: {}", exc)
        return JSONResponse(
            content=jsonable_encoder(ErrorResponse(errors=[str(exc)])),
            status_code=400,
        )
    except Exception as exc:
        logger.exception("Error validating selected values")
        return JSONResponse(
            content=jsonable_encoder(ErrorResponse(errors=[str(exc)])),
            status_code=500,
        )
