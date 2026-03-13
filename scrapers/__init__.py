from importlib import import_module

from .coupang import scrape_coupang
from .kream import scrape_kream
from .musinsa import scrape_musinsa
from .ohouse import scrape_ohouse
from .oliveyoung import scrape_oliveyoung
from .ssg import scrape_ssg
from .wconcept import scrape_wconcept

scrape_29cm = import_module(".29cm", __name__).scrape_29cm

__all__ = [
    "scrape_coupang",
    "scrape_kream",
    "scrape_musinsa",
    "scrape_ohouse",
    "scrape_oliveyoung",
    "scrape_29cm",
    "scrape_ssg",
    "scrape_wconcept",
]
