const dataThemeMappings = {
    "http://publications.europa.eu/resource/authority/data-theme/AGRI": "Agriculture, fisheries, forestry and food",
    "http://publications.europa.eu/resource/authority/data-theme/ECON": "Economy and finance",
    "http://publications.europa.eu/resource/authority/data-theme/EDUC": "Education, culture and sport",
    "http://publications.europa.eu/resource/authority/data-theme/ENER": "Energy",
    "http://publications.europa.eu/resource/authority/data-theme/ENVI": "Environment",
    "http://publications.europa.eu/resource/authority/data-theme/GOVE": "Government and public sector",
    "http://publications.europa.eu/resource/authority/data-theme/INTR": "International issues",
    "http://publications.europa.eu/resource/authority/data-theme/HEAL": "Health",
    "http://publications.europa.eu/resource/authority/data-theme/JUST": "Justice, legal system and public safety",
    "http://publications.europa.eu/resource/authority/data-theme/REGI": "Regions and cities",
    "http://publications.europa.eu/resource/authority/data-theme/SOCI": "Population and society",
    "http://publications.europa.eu/resource/authority/data-theme/TECH": "Science and Technology",
    "http://publications.europa.eu/resource/authority/data-theme/TRAN": "Transport"
  };
  
  export function getDataThemeLabel(iri) {
    return dataThemeMappings[iri] || iri.split('/').pop();
  }
  
  export const allDataThemes = Object.entries(dataThemeMappings).map(([iri, label]) => ({
    iri,
    label
  }));