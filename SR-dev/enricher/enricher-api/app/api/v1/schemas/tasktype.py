from enum import Enum

class TaskType(str, Enum):
    all="all"
    classify="classify"
    synonyms="synonyms"
    translate="translate"


