const formatMappings = {
    "http://publications.europa.eu/resource/authority/file-type/JSON_LD": "JSON-LD",
    "http://publications.europa.eu/resource/authority/file-type/RDF_XML": "XML",
    "http://publications.europa.eu/resource/authority/file-type/RDF_TURTLE": "Turtle",
    "http://publications.europa.eu/resource/authority/file-type/CSV": "CSV",
    "http://publications.europa.eu/resource/authority/file-type/JSON": "JSON",
  };
  
  export function getFormatLabel(iri) {
    return formatMappings[iri] || iri.split('/').pop(); // fallback: show last part of IRI if not mapped
  }  