from enum import Enum

class Language(str, Enum):
  en="en"   # English (~370M)
  de="de"   # German (~95M)
  fr="fr"   # French (~80M)
  it="it"   # Italian (~65M)
  es="es"   # Spanish (~45M)
  pl="pl"   # Polish (~38M)
  ro="ro"   # Romanian (~24M)
  nl="nl"   # Dutch (~23M)
  hu="hu"   # Hungarian (~13M)
  el="el"   # Greek (~13M)