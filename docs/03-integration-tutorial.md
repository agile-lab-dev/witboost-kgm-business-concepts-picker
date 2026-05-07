# Tutorial: Integrating the Picker into a Witboost Template

This guide explains how to deploy the KGM Business Concepts Picker and configure it as a data source for an `EntitySearchPicker` field in a Witboost template.

---

## Prerequisites

- Kubernetes cluster with Witboost installed
- Helm 3 installed
- Access to a Knowledge Graph Manager (KGM) with a SPARQL endpoint
- A container registry to push the Docker image

---

## Step 1: Build and Push the Docker Image

```bash
# Build
docker build -t <registry>/kgm-custom-url-picker:latest .

# Push
docker push <registry>/kgm-custom-url-picker:latest
```

---

## Step 2: Configure the SPARQL Queries

Edit `helm/values.yaml` (or create an override file) with the desired SPARQL queries:

```yaml
kgm:
  baseUrl: "http://kgm-service:8080"   # KGM URL inside the cluster
  sparqlQueries:
    # Query for Business Concepts (parent categories)
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

    # Query for Business Terms (with dynamic parameter)
    business-term-query:
      query: |
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT DISTINCT ?label ?definition (?parentLabel AS ?schemeLabel)
        WHERE {
          VALUES ?parentLabel { ${1*} }
          ?parent skos:prefLabel ?parentLabel .
          ?term a skos:Concept ;
                skos:broader ?parent .
          OPTIONAL { ?term skos:prefLabel ?label . FILTER(LANG(?label) = "en" || LANG(?label) = "") }
          OPTIONAL { ?term skos:definition ?definition . FILTER(LANG(?definition) = "en" || LANG(?definition) = "") }
        }
      fieldMapping:
        id: label
        value: label
        description: definition
        parentBusinessConcept: schemeLabel
```

---

## Step 3: Deploy with Helm

```bash
# From the project root
helm dependency update helm/

helm install kgm-picker helm/ \
  --namespace <witboost-namespace> \
  --set image.registry=<registry>/kgm-custom-url-picker \
  --set image.tag=latest \
  --set kgm.baseUrl=http://<kgm-service>:8080
```

Or with an override file:

```bash
helm install kgm-picker helm/ \
  --namespace <witboost-namespace> \
  -f my-values.yaml
```

### Verify the deployment

```bash
# Check that the pod is running
kubectl get pods -n <witboost-namespace> -l app=kgm-custom-url-picker

# Test the health check
kubectl port-forward svc/kgm-custom-url-picker 5002:5002 -n <witboost-namespace>
curl http://localhost:5002/health
# → {"status": "ok"}
```

---

## Step 4: Configure the Witboost Template

In your template's `template.yaml` file, add a field using `EntitySearchPicker` with `type: Remote`.

### Example: Business Concept Field (multi-select)

```yaml
parameters:
  - title: Data Product metadata
    properties:
      businessConcept:
        title: Business Concept
        ui:field: EntitySearchPicker
        ui:options:
          multiSelection: true
          entities:
            - type: Remote
              displayName: Business Concepts
              fieldsToSave:           # Fields saved in the descriptor
                - id
                - value
                - description
                - referenceGlossary
              columns:                # Columns visible in the dropdown table
                - name: 'Name'
                  path: '{{value}}'
                - name: 'Description'
                  path: '{{description}}'
                - name: 'Glossary'
                  path: '{{referenceGlossary}}'
              displayField: '{{value}}'     # What to show in the selected chip
              userFilters: ['search']       # Enables text search
              apiSpec:
                retrieval:
                  baseUrl: 'http://kgm-custom-url-picker:5002'  # ← K8s Service name
                  path: '/v1/resources'
                  method: 'POST'
                  params:
                    sparql: 'business-concept-query'   # ← Name of the configured query
```

### Example: Business Term Field (with dynamic parameters)

```yaml
      businessTerm:
        title: Business Term
        ui:field: EntitySearchPicker
        ui:options:
          multiSelection: true
          entities:
            - type: Remote
              displayName: Business Terms
              fieldsToSave:
                - id
                - value
                - description
                - parentBusinessConcept
              columns:
                - name: 'Name'
                  path: '{{value}}'
                - name: 'Description'
                  path: '{{description}}'
                - name: 'Business Concept'
                  path: '{{parentBusinessConcept}}'
              displayField: '{{value}}'
              userFilters: ['search']
              apiSpec:
                retrieval:
                  baseUrl: 'http://kgm-custom-url-picker:5002'
                  path: '/v1/resources'
                  method: 'POST'
                  params:
                    sparql: 'business-term-query'
                    sparql-params: 'Customer Metric|Investment Services'  # ← pipe-separated values
```

> **Note**: the `sparql-params` value uses `|` as a separator. In the picker, it will be expanded into the `${1*}` placeholder of the SPARQL query as `"Customer Metric" "Investment Services"` (SPARQL VALUES format).

---

## Step 5: End-to-End Verification

1. Access the Witboost UI.
2. Create a new component using the configured template.
3. The `Business Concept` (or `Business Term`) field should show a dropdown with values from the KGM.
4. Typing in the field filters results (server-side filtering).
5. On submission, Witboost calls `/v1/resources/validate` to verify the validity of selected values.

---

## API Response Structure

The picker returns a list of JSON objects:

```json
[
  {
    "id": "Customer",
    "value": "Customer",
    "description": "A person or organization that buys goods or services",
    "referenceGlossary": "Business Glossary"
  },
  {
    "id": "Investment",
    "value": "Investment",
    "description": "An asset acquired for income or appreciation",
    "referenceGlossary": "Finance Glossary"
  }
]
```

The fields depend on the configured `fieldMapping`. The `id` field is always mandatory.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Empty dropdown | Verify that `kgm.baseUrl` in Helm is correct and reachable from the pod. Check logs: `kubectl logs -l app=kgm-custom-url-picker` |
| Error 400 "SPARQL query 'xxx' is not configured" | The name in `params.sparql` of the template doesn't match any key in `sparqlQueries` |
| Error 500 | KGM is not responding or the SPARQL query has a syntax error. Check the picker logs. |
| CORS error in browser console | Verify that `custom_url_picker.cors.origin` includes the Witboost UI origin (default is `"*"`) |
| Validation fails for valid items | Ensure the validation query (same query used for retrieval) returns the same mapped `id` |

---

## Quick Recipe: Adding a New Picker to an Existing Template

1. **Define the SPARQL query** in `helm/values.yaml` under `kgm.sparqlQueries.<query-name>`.
2. **Re-deploy** with `helm upgrade kgm-picker helm/ -n <namespace>`.
3. **Add the field** in `template.yaml` with `apiSpec.retrieval.params.sparql: '<query-name>'`.
4. **Test** by opening the template in the UI.

No Python code changes are needed to add new queries — it's all configuration.
