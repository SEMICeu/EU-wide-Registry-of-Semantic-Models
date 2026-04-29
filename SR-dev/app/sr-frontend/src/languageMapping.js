export const languageLabels = {
    "http://publications.europa.eu/resource/authority/language/ENG": "English",
    "http://publications.europa.eu/resource/authority/language/ITA": "Italian",
    "http://publications.europa.eu/resource/authority/language/NOB": "Norwegian Bokmål",
    "http://publications.europa.eu/resource/authority/language/NLD": "Dutch"
  };
  
  export function getLanguageLabel(iri) {
    return languageLabels[iri] || iri.split('/').pop(); // fallback to IRI if not mapped
  }  