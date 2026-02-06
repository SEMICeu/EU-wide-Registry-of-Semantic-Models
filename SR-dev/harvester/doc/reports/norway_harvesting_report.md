
# Harvesting Report Norway

...

## Transformation Report


TransformationExecution:
    Start Time: 2026-02-06 09:59:59.432399
    End Time: 2026-02-06 10:00:24.489391
    Duration: 25.056992s

Transformation:
    Input Access URL: https://sparql.fellesdatakatalog.digdir.no
    Output Access URL: http://localhost:7200/repositories/srm
    Extracted Assets: 13
    Transformed Assets: 13
    Validated Assets: 11
    Failed Validation Assets: 2
    Loaded Assets: 11

Provenance Report: 
    ProvenanceAccess URL: http://localhost:7200/repositories/norway_prov


## Failed entries


### Failed Entry 1

```
{
  "@graph": [
    {
      "@id": "_:b0",
      "sh:resultMessage": "Property needs to have at least 1 value",
      "sh:resultPath": {
        "@id": "dct:title"
      },
      "sh:focusNode": {
        "@id": "_:b1"
      },
      "sh:sourceShape": {
        "@id": "https://semiceu.github.io/SRM/releases/1.0.1#AssetDistributionShape/96cdcbb0489a41ab01fc39c521f5ed607a0b2c41"
      },
      "sh:sourceConstraintComponent": {
        "@id": "sh:MinCountConstraintComponent"
      },
      "sh:resultSeverity": {
        "@id": "sh:Violation"
      },
      "@type": "sh:ValidationResult"
    },
    {
      "@id": "_:b2",
      "sh:resultMessage": "The theme must be in the EU Publications Office data theme authority table",
      "sh:resultPath": {
        "@id": "dcat:theme"
      },
      "sh:value": {
        "@id": "https://psi.norge.no/los/tema/eiendom"
      },
      "sh:focusNode": {
        "@id": "https://raw.githubusercontent.com/Informasjonsforvaltning/model-publisher/master/src/model/model-catalog.ttl#AdresseModell"
      },
      "sh:sourceShape": {
        "@id": "_:b3"
      },
      "sh:sourceConstraintComponent": {
        "@id": "sh:NodeConstraintComponent"
      },
      "sh:resultSeverity": {
        "@id": "sh:Violation"
      },
      "@type": "sh:ValidationResult"
    },
    {
      "@id": "_:b4",
      "sh:conforms": {
        "@value": "false",
        "@type": "xsd:boolean"
      },
      "sh:result": [
        {
          "@id": "_:b0"
        },
        {
          "@id": "_:b2"
        }
      ],
      "@type": "sh:ValidationReport"
    }
  ],
  "@context": {
    "schema": "http://schema.org/",
    "owl": "http://www.w3.org/2002/07/owl#",
    "xhv": "http://www.w3.org/1999/xhtml/vocab#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "shacl": "http://www.w3.org/ns/shacl#",
    "ns6": "http://www.w3.org/2008/05/skos-xl#",
    "ns5": "http://publications.europa.eu/ontology/euvoc#",
    "ns7": "http://publications.europa.eu/ontology/authority/",
    "dct": "http://purl.org/dc/terms/",
    "sh": "http://www.w3.org/ns/shacl#",
    "xml": "http://www.w3.org/XML/1998/namespace",
    "dcterms": "http://purl.org/dc/terms/",
    "dcat": "http://www.w3.org/ns/dcat#",
    "vann": "http://purl.org/vocab/vann/",
    "graphql": "http://datashapes.org/graphql#",
    "prov": "http://www.w3.org/ns/prov#",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "cc": "http://creativecommons.org/ns#",
    "adms": "http://www.w3.org/ns/adms#",
    "tosh": "http://topbraid.org/tosh#",
    "vcard": "http://www.w3.org/2006/vcard/ns#",
    "prof": "http://www.w3.org/ns/dx/prof/",
    "srm": "https://semiceu.github.io/SRM/releases/1.0.0/codelist/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "wdrs": "http://www.w3.org/2007/05/powder-s#",
    "dash": "http://datashapes.org/dash#",
    "swa": "http://topbraid.org/swa#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "sdo": "https://schema.org/",
    "@vocab": "http://www.w3.org/ns/dx/prof/role/"
  }
}
```

### Failed Entry 2

```
{
  "@graph": [
    {
      "@id": "_:b0",
      "sh:resultMessage": "Property needs to have at least 1 value",
      "sh:resultPath": {
        "@id": "dct:title"
      },
      "sh:focusNode": {
        "@id": "_:b1"
      },
      "sh:sourceShape": {
        "@id": "https://semiceu.github.io/SRM/releases/1.0.1#AssetDistributionShape/96cdcbb0489a41ab01fc39c521f5ed607a0b2c41"
      },
      "sh:sourceConstraintComponent": {
        "@id": "sh:MinCountConstraintComponent"
      },
      "sh:resultSeverity": {
        "@id": "sh:Violation"
      },
      "@type": "sh:ValidationResult"
    },
    {
      "@id": "_:b2",
      "sh:resultMessage": "The theme must be in the EU Publications Office data theme authority table",
      "sh:resultPath": {
        "@id": "dcat:theme"
      },
      "sh:value": {
        "@id": "https://psi.norge.no/los/tema/naringsliv"
      },
      "sh:focusNode": {
        "@id": "https://raw.githubusercontent.com/Informasjonsforvaltning/model-publisher/master/src/model/model-catalog.ttl#PersonOgEnhet"
      },
      "sh:sourceShape": {
        "@id": "_:b3"
      },
      "sh:sourceConstraintComponent": {
        "@id": "sh:NodeConstraintComponent"
      },
      "sh:resultSeverity": {
        "@id": "sh:Violation"
      },
      "@type": "sh:ValidationResult"
    },
    {
      "@id": "_:b4",
      "sh:resultMessage": "The theme must be in the EU Publications Office data theme authority table",
      "sh:resultPath": {
        "@id": "dcat:theme"
      },
      "sh:value": {
        "@id": "https://psi.norge.no/los/tema/personopplysninger"
      },
      "sh:focusNode": {
        "@id": "https://raw.githubusercontent.com/Informasjonsforvaltning/model-publisher/master/src/model/model-catalog.ttl#PersonOgEnhet"
      },
      "sh:sourceShape": {
        "@id": "_:b3"
      },
      "sh:sourceConstraintComponent": {
        "@id": "sh:NodeConstraintComponent"
      },
      "sh:resultSeverity": {
        "@id": "sh:Violation"
      },
      "@type": "sh:ValidationResult"
    },
    {
      "@id": "_:b5",
      "sh:conforms": {
        "@value": "false",
        "@type": "xsd:boolean"
      },
      "sh:result": [
        {
          "@id": "_:b0"
        },
        {
          "@id": "_:b2"
        },
        {
          "@id": "_:b4"
        }
      ],
      "@type": "sh:ValidationReport"
    }
  ],
  "@context": {
    "schema": "http://schema.org/",
    "owl": "http://www.w3.org/2002/07/owl#",
    "xhv": "http://www.w3.org/1999/xhtml/vocab#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "shacl": "http://www.w3.org/ns/shacl#",
    "ns6": "http://www.w3.org/2008/05/skos-xl#",
    "ns5": "http://publications.europa.eu/ontology/euvoc#",
    "ns7": "http://publications.europa.eu/ontology/authority/",
    "dct": "http://purl.org/dc/terms/",
    "sh": "http://www.w3.org/ns/shacl#",
    "xml": "http://www.w3.org/XML/1998/namespace",
    "dcterms": "http://purl.org/dc/terms/",
    "dcat": "http://www.w3.org/ns/dcat#",
    "vann": "http://purl.org/vocab/vann/",
    "graphql": "http://datashapes.org/graphql#",
    "prov": "http://www.w3.org/ns/prov#",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "cc": "http://creativecommons.org/ns#",
    "adms": "http://www.w3.org/ns/adms#",
    "tosh": "http://topbraid.org/tosh#",
    "vcard": "http://www.w3.org/2006/vcard/ns#",
    "prof": "http://www.w3.org/ns/dx/prof/",
    "srm": "https://semiceu.github.io/SRM/releases/1.0.0/codelist/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "wdrs": "http://www.w3.org/2007/05/powder-s#",
    "dash": "http://datashapes.org/dash#",
    "swa": "http://topbraid.org/swa#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "sdo": "https://schema.org/",
    "@vocab": "http://www.w3.org/ns/dx/prof/role/"
  }
}
```
