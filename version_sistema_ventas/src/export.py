"""Exportar datos a CSV/JSON para cuentas Premium.
"""
from typing import List, Dict, Optional
import csv
import io
import json


def export_to_csv(items: List[Dict], fields: Optional[List[str]] = None) -> str:
    if not items:
        return ""
    if fields is None:
        # infer fields from first item
        fields = list(items[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for it in items:
        row = {k: it.get(k, "") for k in fields}
        writer.writerow(row)
    return output.getvalue()


def export_to_json(items: List[Dict]) -> str:
    return json.dumps(items)
