export const countryLabels = {
    "http://publications.europa.eu/resource/authority/country/EUR": "🇪🇺 Europe",
    "http://publications.europa.eu/resource/authority/country/GBR": "🇬🇧 United Kingdom",
    "http://publications.europa.eu/resource/authority/country/IRL": "🇮🇪 Ireland",
    "http://publications.europa.eu/resource/authority/country/ITA": "🇮🇹 Italy",
    "http://publications.europa.eu/resource/authority/country/USA": "🇺🇸 United States",
    "http://publications.europa.eu/resource/authority/country/NOR": "🇳🇴 Norway"
  };
  
  export function getCountryLabel(iri) {
    return countryLabels[iri] || iri.split('/').pop(); // fallback to IRI if not mapped
  }  

  export const allCountries = Object.entries(countryLabels).map(([iri, label]) => ({
    iri,
    label
  }));