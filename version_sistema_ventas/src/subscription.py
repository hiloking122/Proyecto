"""Gestión simple de suscripciones Premium (mock).

Implementación en memoria: permite marcar usuarios como Premium y comprobar permisos.
"""
from typing import Dict


class SubscriptionManager:
    def __init__(self):
        # almacenamos user_id -> bool
        self._users: Dict[str, bool] = {}

    def set_premium(self, user_id: str, is_premium: bool = True):
        self._users[user_id] = bool(is_premium)

    def is_premium(self, user_id: str) -> bool:
        return bool(self._users.get(user_id, False))


# singleton útil para tests y uso simple
_default_manager = SubscriptionManager()


def get_subscription_manager():
    return _default_manager
