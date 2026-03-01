"""Búsqueda global inteligente usando fuzzy matching (rapidfuzz).

Prototipo: index simple en memoria que admite búsquedas sobre varios tipos de entidades.
"""

from typing import List, Dict, Any
from rapidfuzz import process, fuzz


class GlobalSearch:
    def __init__(self):
        # items: dict id -> {"type": "product"|..., "text": str, "meta": {...}}
        self.items = {}

    def index_items(self, items: List[Dict[str, Any]]):
        for it in items:
            _id = it.get("id")
            text_fields = [str(it.get(k, "")) for k in ("name", "description", "sku")]
            text = " ".join([t for t in text_fields if t])
            self.items[_id] = {"type": it.get("type"), "text": text, "meta": it}

    def search(self, query: str, limit: int = 10):
        choices = {k: v["text"] for k, v in self.items.items()}
        results = process.extract(query, choices, scorer=fuzz.WRatio, limit=limit)
        # results: list of tuples (matched_text, score, _id)
        out = []
        for match_text, score, _id in results:
            entry = self.items[_id]
            out.append({"id": _id, "type": entry["type"], "score": score, "meta": entry["meta"]})
        return out


if __name__ == "__main__":
    gs = GlobalSearch()
    sample = [
        {"id": "p1", "type": "product", "name": "iPhone 12", "description": "Used, good condition", "sku": "IP12"},
        {"id": "c1", "type": "customer", "name": "Carlos Pérez", "description": "Cliente mayorista"},
    ]
    gs.index_items(sample)
    print(gs.search("iphone"))
