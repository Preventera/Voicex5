"""SafeTalkX5 — Generateur de causeries SST vocales a partir de donnees CNESST + OSHA."""

from safetalk.cnesst_parser import CNESSTParser
from safetalk.osha_scraper import OSHAScraper

__all__ = ["CNESSTParser", "OSHAScraper"]
