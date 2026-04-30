# Semantic Registry Model (SRM) 1.0.1

Source: [https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.1/](https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.1/)

## Abstract

SRM (Semantic Registry Model) is designed to accomodate metadata to be used by the Semantic Registry.

## Introduction

SRM has been conceived to find and search semantic models withing the Semantic Registry.

SRM is designed to meet the following use cases:

- facilitating the access to semantic models;
- building user-centric registry of semantic models so end users are able to find them quickly; and
- incentive communities to collaborate on semantic models.

## Status

This Application Profile has the status Draft published at 2025-12-12.

## License

Copyright © 2024 European Union. All material in the SRM repository is published under CC-BY 4.0 unless explicitly stated otherwise.

## Terminology

- **Application Profile (AP)**: specification reusing terms from base standards with additional constraints and vocabulary recommendations.
- **Core Vocabulary (CV)**: reusable, extensible, context-neutral data specification.

## Used Prefixes

| Prefix | Namespace IRI |
| --- | --- |
| `adms` | `http://www.w3.org/ns/adms#` |
| `cv` | `http://data.europa.eu/m8g/` |
| `dcat` | `http://www.w3.org/ns/dcat#` |
| `dct` | `http://purl.org/dc/terms/` |
| `foaf` | `http://xmlns.com/foaf/0.1/` |
| `owl` | `http://www.w3.org/2002/07/owl#` |
| `prof` | `http://www.w3.org/ns/dx/prof/` |
| `rdf` | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` |
| `rdfs` | `http://www.w3.org/2000/01/rdf-schema#` |
| `skos` | `http://www.w3.org/2004/02/skos/core#` |
| `vann` | `http://purl.org/vocab/vann/` |
| `vcard` | `http://www.w3.org/2006/vcard/ns#` |
| `xsd` | `http://www.w3.org/2001/XMLSchema#` |

## Overview

Main entity:

- `Asset`

Supportive entities:

- `Agent`
- `Asset Distribution`
- `Class`
- `Document`
- `Email`
- `Kind`
- `Licence Document`
- `Location`
- `Media Type or Extent`

Datatypes:

- `Code`
- `DateTime`
- `NonNegativeInteger`
- `String`
- `Text`
- `URI`

## Main Entity: Asset

Definition: An abstract entity that reflects the intellectual content of the asset and the characteristics independent of physical embodiment.

### Asset property descriptions

- `contact point` (`dcat:contactPoint`, 0..*): contact information for comments/questions about the standard.
- `contributor` (`dct:contributor`, 0..*): agent contributing to the resource.
- `creator` (`dct:creator`, 1..*): agent that created the resource.
- `date created` (`dct:created`, 0..1): creation date/time.
- `date issued` (`dct:issued`, 0..1): formal publication/issuance date/time.
- `date modified` (`dct:modified`, 0..1): last modification date/time.
- `description` (`dct:description`, 0..*): free-text description (can be multilingual/repeated).
- `distribution` (`dcat:distribution`, 0..*): links asset to one or more `Asset Distribution` entries.
- `has implementation` (`cv:hasImplementation`, 0..*): URI of portal/repository implementing the standard.
- `homepage` (`foaf:homepage`, 0..1): homepage document.
- `identifier` (`dct:identifier`, 1): unique identifier in context.
- `is reused by` (`cv:isReusedBy`, 0..*): URI of portal/repository reusing the standard.
- `keyword` (`dcat:keyword`, 0..*): tags/keywords.
- `language` (`dct:language`, 0..*): language code URI (Publications Office language codelist).
- `licence` (`dct:license`, 0..*): license document/code URI.
- `lov rank` (`cv:lovRank`, 0..1): numeric reuse ranking score.
- `preferred namespace URI` (`vann:preferredNamespaceUri`, 0..1): preferred namespace URI for the standard.
- `publisher` (`dct:publisher`, 0..*): publishing agent.
- `requires` (`dct:requires`, 0..*): dependency relation to another asset.
- `status` (`adms:status`, 0..1): status code URI (ADMS status codelist).
- `theme` (`dcat:theme`, 0..*): theme code URI (EU data-theme codelist).
- `title` (`dct:title`, 1..*): asset title/name (can be multilingual/repeated).
- `type` (`dct:type`, 0..1): nature/genre (typically `voaf:Vocabulary` or `prof:Profile`).
- `version info` (`owl:versionInfo`, 0..1): version string.

## Supportive Entities

### Agent

Definition: Any resource that acts or has the power to act (people, organizations, groups).

Property descriptions:

- `name` (`foaf:name`, 1..*): human-readable agent name (multilingual possible).
- `spatial` (`dct:spatial`, 0..*): country/location of the agent (country codelist URI).
- `type` (`dct:type`, 0..1): organization/publisher type code URI.

### Asset Distribution

Definition: A concrete/physical embodiment of an `Asset`.

Property descriptions:

- `download URL` (`dcat:downloadURL`, 1): URL to downloadable artifact.
- `format` (`dct:format`, 1): media type/extent.
- `has role` (`prof:hasRole`, 0..1): role code for distribution artifact in the profile.
- `name` (`dct:title`, 1..*): distribution title/name.

### Class

Definition: RDF class resource represented in the registry.

Property descriptions:

- `name` (`rdfs:label`, 1..*): class name/label.
- `alternative label` (`skos:altLabel`, 0..*): alternate class labels.
- `is defined by` (`rdfs:isDefinedBy`, 1..*): distribution(s) that define the class.

### Document, Email, Licence Document, Location, Media Type or Extent

Definitions:

- `Document`: generic document resource.
- `Email`: email resource (vCard).
- `Licence Document`: legal license document.
- `Location`: spatial region/place.
- `Media Type or Extent`: media type or extent descriptor.

No additional SRM-specific mandatory constraints are imposed beyond reused base standards.

### Kind

Definition: vCard-based contact description object.

Property description:

- `has email` (`vcard:hasEmail`, 0..*): associated email resource.

## Datatypes

- `Code` (`skos:Concept`)
- `DateTime` (`xsd:dateTime`)
- `NonNegativeInteger` (`xsd:nonNegativeInteger`)
- `String` (`xsd:string`)
- `Text` (`rdf:langString`)
- `URI` (`xsd:anyURI`)

## Implementation Support

- JSON-LD context:
  - [https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.1/context/srm.jsonld](https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.1/context/srm.jsonld)
- SHACL shapes:
  - [https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.1/shacl/srm-SHACL.ttl](https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.1/shacl/srm-SHACL.ttl)
- UML:
  - [https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.1/UML](https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.1/UML)

## Governance

- Versioning follows SEMIC Style Guide rule PC-R3.
- Deprecated assets remain available via PURI and should include replacement/status metadata.
- Reused assets should meet governance and maintenance quality expectations.

## Quick Reference (condensed)

- **Asset** mandatory: creator, description, identifier, title
- **Agent** mandatory: name
- **Asset Distribution** mandatory: download URL, format, has role, name
- **Class** mandatory: name

---

For the complete canonical specification tables, examples, and full property-level constraints, refer to the official SRM 1.0.1 page:

[https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.1/](https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.1/)
