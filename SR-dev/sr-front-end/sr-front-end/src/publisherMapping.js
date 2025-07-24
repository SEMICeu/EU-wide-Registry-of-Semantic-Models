export const publisherLabels = {
    "http://www.w3.org/data#W3C": "W3C",
    "http://publications.europa.eu/resource/authority/corporate-body/DIGIT": "DIGIT",
    "http://spcdata.digitpa.gov.it/Amministrazione/agid": "Italian Digital Agency",
    "https://w3id.org/italia/data/organization/support-unit/pcm-AA1D3A2": "Italian Department of Digital Transformation",
    "https://w3id.org/italia/data/public-organization/PCM-1RSIZZ": "Italian Digital Transformation department of the Presidency of the Council of Ministers",
    "https://w3id.org/italia/data/support-unit/cnr-Z6HZEH/stlab": "Institute of Cognitive Sciences and Technologies of the Italian Research Council (CNR) - Semantic Technology Laboratory (STLab)",
    "http://purl.org/dc/aboutdcmi#DCMI": "DCMI Usage Board",
    "http://data.semanticweb.org/person/libby-miller": "Libby Miller",
    "https://danbri.org/foaf.rdf#danbri": "Dan Brickley",
    "https://organization-catalogue.fellesdatakatalog.digdir.no/organizations/991825827": "Norwegian Digitalisation Agency"
  };
  
  export function getPublisherLabel(iri) {
    return publisherLabels[iri] || iri.split('/').pop(); // fallback to IRI if not mapped
  }  

  export const allPublishers = Object.entries(publisherLabels).map(([iri, label]) => ({
    iri,
    label
  }));