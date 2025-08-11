export const countryLabels = {
    "http://publications.europa.eu/resource/authority/country/EUR": { code: "eu", name: "Europe" },
    "http://publications.europa.eu/resource/authority/country/GBR": { code: "gb", name: "United Kingdom" },
    "http://publications.europa.eu/resource/authority/country/IRL": { code: "ie", name: "Ireland" },
    "http://publications.europa.eu/resource/authority/country/ITA": { code: "it", name: "Italy" },
    "http://publications.europa.eu/resource/authority/country/USA": { code: "us", name: "United States" },
    "http://publications.europa.eu/resource/authority/country/NOR": { code: "no", name: "Norway" }
  };
  
  export function getCountryLabel(iri) {
    const entry = countryLabels[iri];
    if (entry) {
      return entry.name;
    }
    return iri.split('/').pop(); // fallback to IRI if not mapped
  }
  
  export function getCountryCode(iri) {
    const entry = countryLabels[iri];
    if (entry) {
      return entry.code;
    }
    return null;
  }
  
  export const allCountries = Object.entries(countryLabels).map(([iri, entry]) => ({
    iri,
    code: entry.code,
    name: entry.name
  }));