"""Eigenständige Desktop-Anwendung für den klassifizierten Datencheck."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from datencheck_output import ROOT, run_check


class OutputDatencheckApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AgroTechNova Datencheck – Klassifizierung")
        self.geometry("650x210")
        self.resizable(False, False)
        self.folder = tk.StringVar(value=str(ROOT))
        tk.Label(self, text="Ordner mit den Excel-Eingabedateien:").pack(
            anchor="w", padx=20, pady=(20, 4)
        )
        row = tk.Frame(self)
        row.pack(fill="x", padx=20)
        tk.Entry(row, textvariable=self.folder).pack(side="left", fill="x", expand=True)
        tk.Button(row, text="Auswählen", command=self.choose_folder).pack(
            side="left", padx=(8, 0)
        )
        tk.Button(self, text="Klassifizierten Datencheck starten",
                  command=self.start_check).pack(pady=25)

    def choose_folder(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.folder.get())
        if selected:
            self.folder.set(selected)

    def start_check(self) -> None:
        try:
            folder = Path(self.folder.get()).resolve()
            output = run_check(
                folder,
                rules_file=folder / "datencheck_regeln.json",
                catalog_file=folder / "FEHLERKLASSIFIZIERUNG.csv",
            )
        except Exception as error:
            messagebox.showerror("Datencheck fehlgeschlagen", str(error))
            return
        messagebox.showinfo("Datencheck abgeschlossen", f"Bericht erstellt:\n{output}")


if __name__ == "__main__":
    OutputDatencheckApp().mainloop()
