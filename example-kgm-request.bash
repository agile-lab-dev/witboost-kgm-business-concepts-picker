curl --location 'http://localhost:9980/v1/graph/sparql' \
--header 'Content-Type: application/sparql-query' \
--data 'PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT DISTINCT ?concept ?label ?definition ?scheme ?schemeLabel
WHERE {
  ?concept a skos:Concept ;
           skos:inScheme ?scheme .

  {
    ?child skos:broader ?concept .
  }
  UNION
  {
    ?concept skos:narrower ?child .
  }

  OPTIONAL {
    ?concept skos:prefLabel ?label .
    FILTER(LANG(?label) = "en" || LANG(?label) = "")
  }

  OPTIONAL {
    ?concept skos:definition ?definition .
    FILTER(LANG(?definition) = "en" || LANG(?definition) = "")
  }

  OPTIONAL {
    ?scheme skos:prefLabel ?schemeLabel .
    FILTER(LANG(?schemeLabel) = "en" || LANG(?schemeLabel) = "")
  }
}
ORDER BY ?schemeLabel ?label ?concept'