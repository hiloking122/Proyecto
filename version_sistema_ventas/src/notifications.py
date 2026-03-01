"""Recordatorios y notificaciones usando APScheduler, win10toast y Telegram.
"""

from datetime import datetime
from typing import Optional
import requests
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from win10toast import ToastNotifier


class ReminderManager:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.notifier = ToastNotifier()
        self.telegram_token = None
        self.telegram_chat_id = None

    def set_telegram_config(self, token, chat_id):
        self.telegram_token = token
        self.telegram_chat_id = chat_id

    def _send_telegram(self, title, message):
        if not self.telegram_token or not self.telegram_chat_id:
            return
        
        def run():
            try:
                url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                payload = {
                    "chat_id": self.telegram_chat_id,
                    "text": f"🔔 *{title}*\n\n{message}",
                    "parse_mode": "Markdown"
                }
                requests.post(url, json=payload, timeout=10)
            except Exception as e:
                print(f"Error enviando Telegram: {e}")
        
        # Ejecutar en hilo separado para no bloquear
        threading.Thread(target=run).start()

    def _notify(self, title: str, message: str):
        # 1. Notificación Desktop Windows
        try:
            self.notifier.show_toast(title, message, threaded=True)
        except Exception:
            print(f"NOTIFICATION: {title} - {message}")
        
        # 2. Notificación Telegram (si configurado)
        self._send_telegram(title, message)

    def schedule_once(self, run_at: datetime, title: str, message: str):
        trigger = DateTrigger(run_date=run_at)
        self.scheduler.add_job(self._notify, trigger=trigger, args=[title, message])

    def schedule_repeat(self, interval_seconds: int, title: str, message: str):
        trigger = IntervalTrigger(seconds=interval_seconds)
        self.scheduler.add_job(self._notify, trigger=trigger, args=[title, message])

    def shutdown(self):
        self.scheduler.shutdown(wait=False)

if __name__ == "__main__":
    rm = ReminderManager()
    rm._notify("Test", "Hola mundo")
