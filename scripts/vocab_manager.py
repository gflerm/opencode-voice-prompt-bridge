"""Vocabulary manager: inspect, edit, enable/disable and delete learned rules.

Usage:
  .venv\\Scripts\\python.exe scripts\\vocab_manager.py
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from config import REPO_ROOT, load_config
from storage import AdaptationStore, seed_glossary


class VocabManager:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.config = load_config()
        db_path = Path(self.config.adaptation.db_path)
        if not db_path.is_absolute():
            db_path = REPO_ROOT / db_path
        self.store = AdaptationStore(db_path)
        seed_glossary(self.store)

        root.title("OpenCode Whisper - Vocabulary Manager")
        root.geometry("880x500")

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=6, pady=6)
        corrections_tab = ttk.Frame(notebook)
        terms_tab = ttk.Frame(notebook)
        notebook.add(corrections_tab, text="Learned corrections")
        notebook.add(terms_tab, text="Glossary terms")

        self._build_corrections_tab(corrections_tab)
        self._build_terms_tab(terms_tab)

        self.status = tk.Label(root, text="", anchor="w", fg="#555")
        self.status.pack(fill="x", padx=8, pady=(0, 6))

    def _set_status(self, text: str) -> None:
        self.status.config(text=text)

    def _build_search_row(self, parent: ttk.Frame) -> tuple[ttk.Frame, tk.StringVar, callable]:
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=6, pady=(6, 2))
        tk.Label(row, text="Search:").pack(side="left")
        query = tk.StringVar()
        return row, query

    def _build_corrections_tab(self, tab: ttk.Frame) -> None:
        _row, self.corr_query = self._build_search_row(tab)
        entry = ttk.Entry(_row, textvariable=self.corr_query)
        entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.corr_query.trace_add("write", lambda *_: self.refresh_corrections())

        columns = ("source", "replacement", "count", "context", "enabled", "last_used")
        self.corr_tree = ttk.Treeview(tab, columns=columns, show="headings", height=14)
        widths = (220, 220, 50, 110, 70, 150)
        for col, width in zip(columns, widths):
            self.corr_tree.heading(col, text=col.replace("_", " ").capitalize())
            self.corr_tree.column(col, width=width, anchor="w")
        self.corr_tree.pack(fill="both", expand=True, padx=6, pady=4)

        buttons = ttk.Frame(tab)
        buttons.pack(fill="x", padx=6, pady=(0, 6))
        for label, command in (
            ("Toggle enable/disable", self.toggle_correction),
            ("Edit", self.edit_correction),
            ("Delete", self.delete_correction),
            ("Refresh", self.refresh_corrections),
        ):
            ttk.Button(buttons, text=label, command=command).pack(side="left", padx=(0, 6))

    def _build_terms_tab(self, tab: ttk.Frame) -> None:
        _row, self.term_query = self._build_search_row(tab)
        entry = ttk.Entry(_row, textvariable=self.term_query)
        entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.term_query.trace_add("write", lambda *_: self.refresh_terms())

        columns = ("canonical", "aliases", "category")
        self.term_tree = ttk.Treeview(tab, columns=columns, show="headings", height=14)
        for col, width in zip(columns, (200, 420, 160)):
            self.term_tree.heading(col, text=col.capitalize())
            self.term_tree.column(col, width=width, anchor="w")
        self.term_tree.pack(fill="both", expand=True, padx=6, pady=4)

        buttons = ttk.Frame(tab)
        buttons.pack(fill="x", padx=6, pady=(0, 6))
        for label, command in (
            ("Add term", self.add_term),
            ("Edit", self.edit_term),
            ("Delete", self.delete_term),
            ("Refresh", self.refresh_terms),
        ):
            ttk.Button(buttons, text=label, command=command).pack(side="left", padx=(0, 6))

    def _selected_id(self, tree) -> int | None:  # noqa: ANN001
        selection = tree.selection()
        if not selection:
            self._set_status("select a row first")
            return None
        return int(selection[0])

    def refresh_corrections(self) -> None:
        query = self.corr_query.get().lower()
        self.corr_tree.delete(*self.corr_tree.get_children())
        for corr in self.store.list_corrections():
            hay = f"{corr.source} {corr.replacement} {corr.context}".lower()
            if query and query not in hay:
                continue
            self.corr_tree.insert(
                "", "end", iid=str(corr.id),
                values=(corr.source, corr.replacement, corr.count, corr.context,
                        "yes" if corr.enabled else "no", corr.last_used),
            )

    def toggle_correction(self) -> None:
        correction_id = self._selected_id(self.corr_tree)
        if correction_id is None:
            return
        corr = next((c for c in self.store.list_corrections() if c.id == correction_id), None)
        if corr is None:
            return
        self.store.set_correction_enabled(correction_id, not corr.enabled)
        self._set_status(f"correction #{correction_id} {'enabled' if not corr.enabled else 'disabled'}")
        self.refresh_corrections()

    def edit_correction(self) -> None:
        correction_id = self._selected_id(self.corr_tree)
        if correction_id is None:
            return
        corr = next((c for c in self.store.list_corrections() if c.id == correction_id), None)
        if corr is None:
            return
        source = simpledialog.askstring("Edit correction", "Source (as Whisper hears it):", initialvalue=corr.source, parent=self.root)
        if not source:
            return
        replacement = simpledialog.askstring("Edit correction", "Replacement:", initialvalue=corr.replacement, parent=self.root)
        if replacement is None:
            return
        context = simpledialog.askstring("Edit correction", "Context (empty = always apply):", initialvalue=corr.context, parent=self.root) or ""
        self.store.update_correction(correction_id, source, replacement, context)
        self._set_status(f"correction #{correction_id} updated")
        self.refresh_corrections()

    def delete_correction(self) -> None:
        correction_id = self._selected_id(self.corr_tree)
        if correction_id is None:
            return
        if not messagebox.askyesno("Delete", f"Delete correction #{correction_id}?"):
            return
        self.store.delete_correction(correction_id)
        self._set_status(f"correction #{correction_id} deleted")
        self.refresh_corrections()

    def refresh_terms(self) -> None:
        query = self.term_query.get().lower()
        self.term_tree.delete(*self.term_tree.get_children())
        for term in self.store.list_terms():
            hay = f"{term.canonical} {term.aliases} {term.category}".lower()
            if query and query not in hay:
                continue
            self.term_tree.insert(
                "", "end", iid=str(term.id),
                values=(term.canonical, term.aliases, term.category),
            )

    def add_term(self) -> None:
        canonical = simpledialog.askstring("Add term", "Canonical term:", parent=self.root)
        if not canonical:
            return
        aliases = simpledialog.askstring("Add term", "Aliases (comma-separated):", parent=self.root) or ""
        category = simpledialog.askstring("Add term", "Category (optional):", parent=self.root) or ""
        self.store.upsert_term(canonical, aliases, category)
        self._set_status(f"term '{canonical}' saved")
        self.refresh_terms()

    def edit_term(self) -> None:
        term_id = self._selected_id(self.term_tree)
        if term_id is None:
            return
        term = next((t for t in self.store.list_terms() if t.id == term_id), None)
        if term is None:
            return
        canonical = simpledialog.askstring("Edit term", "Canonical term:", initialvalue=term.canonical, parent=self.root)
        if not canonical:
            return
        aliases = simpledialog.askstring("Edit term", "Aliases (comma-separated):", initialvalue=term.aliases, parent=self.root) or ""
        category = simpledialog.askstring("Edit term", "Category:", initialvalue=term.category, parent=self.root) or ""
        self.store.upsert_term(canonical, aliases, category)
        if canonical != term.canonical:
            self.store.delete_term(term_id)
        self._set_status(f"term '{canonical}' saved")
        self.refresh_terms()

    def delete_term(self) -> None:
        term_id = self._selected_id(self.term_tree)
        if term_id is None:
            return
        if not messagebox.askyesno("Delete", f"Delete term #{term_id}?"):
            return
        self.store.delete_term(term_id)
        self._set_status(f"term #{term_id} deleted")
        self.refresh_terms()


def main() -> int:
    root = tk.Tk()
    VocabManager(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
