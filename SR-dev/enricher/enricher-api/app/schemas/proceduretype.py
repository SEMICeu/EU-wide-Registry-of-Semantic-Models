from enum import Enum

class Proceduretype(str, Enum):
    comp_dial="comp-dial"
    neg_w_call="neg-w-call"
    neg_wo_call="neg-wo-call"
    open="open"
    restricted="restricted"
    innovation="innovation"
    oth_single="oth-single"
    oth_mult="oth-mult"
    comp_tend="comp-tend"