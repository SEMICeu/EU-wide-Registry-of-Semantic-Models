from enum import Enum

class Source(str, Enum):
    nltk="nltk"
    altervista="altervista"
    datamuse="datamuse"
    all="all"


