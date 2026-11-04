"""Optionaler Direktstart der Prüfengine ohne Web-UI.

Die empfohlene Standalone-Oberfläche ist app.py / start_datencheck.bat.
Dieses Skript bleibt als schlanke Alternative für den reinen SQLite-Check.
"""

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from datencheck_output_sqlite import DB_PATH, OUTPUT_FILE, run_check


class SqliteDatencheckApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AgroTechNova Datencheck – SQLite")
        self.geometry("680x260")
        self.resizable(False, False)
        self._running = False

        tk.Label(self, text="Datenquelle (fest):").pack(anchor="w", padx=20, pady=(20, 4))
        tk.Label(self, text=str(DB_PATH), fg="#333").pack(anchor="w", padx=20)

        tk.Label(
            self,
            text=f"Bericht: {OUTPUT_FILE.name}",
            fg="#555",
        ).pack(anchor="w", padx=20, pady=(8, 0))

        tk.Label(
            self,
            text="Tipp: Für Dashboard + Fehlerliste start_datencheck.bat nutzen.",
            fg="#666",
        ).pack(anchor="w", padx=20, pady=(12, 0))

        self.status = tk.StringVar(value="Bereit.")
        tk.Label(self, textvariable=self.status, fg="#333").pack(
            anchor="w", padx=20, pady=(14, 4)
        )

        self.progress = ttk.Progressbar(self, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill="x", padx=20, pady=(0, 8))

        self.button = tk.Button(
            self,
            text="Klassifizierten Datencheck starten",
            command=self.start_check,
        )
        self.button.pack(pady=10)

    def start_check(self) -> None:
        if self._running:
            return
        self._running = True
        self.button.configure(state="disabled")
        self.progress["value"] = 0
        self.status.set("Starte Datencheck …")
        threading.Thread(target=self._run_worker, daemon=True).start()

    def _on_progress(self, info: dict) -> None:
        percent = float(info.get("percent") or 0)
        message = str(info.get("message") or "")
        self.after(0, lambda: self._apply_progress(percent, message))

    def _apply_progress(self, percent: float, message: str) -> None:
        self.progress["value"] = percent
        self.status.set(f"{percent:.0f} % – {message}")

    def _run_worker(self) -> None:
        try:
            output = run_check(on_progress=self._on_progress)
        except Exception as error:
            self.after(0, lambda: self._finish_error(error))
            return
        self.after(0, lambda: self._finish_ok(output))

    def _finish_ok(self, output) -> None:
        self._running = False
        self.button.configure(state="normal")
        self.progress["value"] = 100
        self.status.set("Fertig.")
        messagebox.showinfo(
            "Datencheck abgeschlossen",
            f"Bericht erstellt:\n{output}\n\n"
            "Relevante Befunde zusätzlich in Tabelle Fehlerliste geschrieben "
            "(ohne Priorität „ignorieren“).",
        )

    def _finish_error(self, error: Exception) -> None:
        self._running = False
        self.button.configure(state="normal")
        self.status.set("Fehlgeschlagen.")
        messagebox.showerror("Datencheck fehlgeschlagen", str(error))


if __name__ == "__main__":
    SqliteDatencheckApp().mainloop()
