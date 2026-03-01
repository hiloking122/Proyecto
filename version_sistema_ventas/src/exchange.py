"""Módulo para obtener y cachear tasas de cambio.
Usamos open.er-api.com como fuente fiable y gratuita (sin key).
"""

import json
import time
import logging
from pathlib import Path
from typing import Optional

import requests

CACHE_FILE = Path("exchange_cache.json")
DEFAULT_TTL = 60 * 60  # 1 hora

logger = logging.getLogger(__name__)


class ExchangeRates:
    def __init__(self, ttl: int = DEFAULT_TTL, max_retries: int = 3, backoff_factor: float = 0.5):
        self.ttl = ttl
        self.cache = self._load_cache()
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def _load_cache(self):
        if CACHE_FILE.exists():
            try:
                return json.loads(CACHE_FILE.read_text())
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        CACHE_FILE.write_text(json.dumps(self.cache))

    def _is_stale(self, key: str) -> bool:
        entry = self.cache.get(key)
        if not entry:
            return True
        return time.time() - entry.get("ts", 0) > self.ttl

    def get_rate(self, base: str = "USD", target: str = "VES") -> float:
        """Devuelve la tasa base -> target.
        Usa open.er-api.com.
        """
        # Normalizamos la key de cache para evitar duplicados (USD:VES)
        key = f"{base}:{target}"
        
        # Check cache
        if not self._is_stale(key):
            try:
                return float(self.cache[key]["rate"])
            except:
                pass

        # URL recomendada por ser gratuita y estable
        url = f"https://open.er-api.com/v6/latest/{base}"
        
        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                
                # open.er-api returns rates in "rates" dict
                rates = data.get("rates", {})
                rate = rates.get(target)
                
                if rate is None:
                    raise ValueError(f"Rate for {target} not found in response.")
                
                # Update cache
                self.cache[key] = {"ts": time.time(), "rate": rate}
                try:
                    self._save_cache()
                except:
                    pass
                
                return float(rate)

            except Exception as e:
                last_exc = e
                time.sleep(self.backoff_factor * attempt)

        logger.warning(f"Failed to fetch exchange rate after {self.max_retries} attempts: {last_exc}")
        
        # Fallback to cache if exists (even if stale) or default
        if key in self.cache:
            return float(self.cache[key]["rate"])
        
        # Si fallamos completamente y es USD->VES, retornamos un valor seguro o lanzamos
        # El código legacy usaba 60.0 por defecto en la DB, así que aquí lanzamos para que la app use el de la DB
        raise ValueError(f"Could not fetch rate for {base} -> {target}")

if __name__ == "__main__":
    er = ExchangeRates()
    print("USD -> VES:", er.get_rate("USD", "VES"))
