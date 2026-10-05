#!/usr/bin/env python3
"""Your vault, as a window. Double-click, type your password, read and edit.

WHY THIS EXISTS AND THE COMMAND LINE WAS NOT ENOUGH: "how would I open my own vault
without you" is the question that decides whether this is really yours. A terminal is
still a thing you have to know how to drive. A window you double-click is not.

Built on tkinter, which comes with Python. No extra install, nothing to build, and it
opens on Windows, macOS and Linux from the same file.

    python vault_ui.py          (or double-click Open Vault.bat on Windows)

Nothing here talks to the network, and the password stays in memory for as long as the
window is open. Close it and it is gone.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import tkinter as tk
    from tkinter import messagebox, simpledialog, ttk
except ImportError:
    sys.exit("This needs tkinter. On Debian/Ubuntu: sudo apt install python3-tk")

import vault_core as V


class VaultWindow:
    def __init__(self, root: tk.Tk, data: dict, password: str):
        self.root, self.data, self.password = root, data, password
        self.current: str | None = None
        self.dirty = False

        root.title(f"Vault  ·  {V.VAULT}")
        root.geometry("900x560")
        root.configure(bg="#0b1020")

        # left: the names. right: the fields of whichever is selected.
        panes = tk.PanedWindow(root, orient="horizontal", bg="#0b1020", sashwidth=4, bd=0)
        panes.pack(fill="both", expand=True, padx=10, pady=10)

        left = tk.Frame(panes, bg="#0b1020")
        tk.Label(left, text="ENTRIES", bg="#0b1020", fg="#64748b",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 6))
        self.search = tk.Entry(left, bg="#111a33", fg="#f1f5f9", insertbackground="#f1f5f9",
                               relief="flat", font=("Segoe UI", 10))
        self.search.pack(fill="x", pady=(0, 6), ipady=4)
        self.search.bind("<KeyRelease>", lambda _e: self.refresh_list())

        self.listbox = tk.Listbox(left, bg="#111a33", fg="#f1f5f9", relief="flat",
                                  selectbackground="#22d3ee", selectforeground="#02040f",
                                  font=("Segoe UI", 10), activestyle="none", highlightthickness=0)
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_pick)
        panes.add(left, width=260)

        right = tk.Frame(panes, bg="#0b1020")
        self.title = tk.Label(right, text="pick one on the left", bg="#0b1020", fg="#f1f5f9",
                              font=("Segoe UI", 13, "bold"), anchor="w")
        self.title.pack(fill="x", pady=(0, 2))
        self.hint = tk.Label(right, text="one KEY=value per line", bg="#0b1020", fg="#64748b",
                             font=("Segoe UI", 8), anchor="w")
        self.hint.pack(fill="x", pady=(0, 6))

        self.text = tk.Text(right, bg="#111a33", fg="#f1f5f9", insertbackground="#f1f5f9",
                            relief="flat", font=("Consolas", 11), wrap="none", padx=10, pady=10)
        self.text.pack(fill="both", expand=True)
        self.text.bind("<<Modified>>", self.on_edit)

        bar = tk.Frame(right, bg="#0b1020")
        bar.pack(fill="x", pady=(8, 0))
        for label, fn, main in [("Save", self.save_entry, True), ("Copy all", self.copy_all, False),
                                ("New", self.new_entry, False), ("Delete", self.delete_entry, False)]:
            tk.Button(bar, text=label, command=fn, relief="flat", cursor="hand2",
                      bg="#22d3ee" if main else "#1a2440", fg="#02040f" if main else "#f1f5f9",
                      font=("Segoe UI", 9, "bold"), padx=16, pady=6,
                      activebackground="#22d3ee" if main else "#243057").pack(side="left", padx=(0, 8))
        self.status = tk.Label(bar, text="", bg="#0b1020", fg="#34d399", font=("Segoe UI", 9))
        self.status.pack(side="right")
        panes.add(right)

        self.refresh_list()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ── data ───────────────────────────────────────────────────────────────
    @property
    def entries(self) -> dict:
        return self.data.setdefault("entries", {})

    def refresh_list(self):
        q = self.search.get().strip().lower()
        self.listbox.delete(0, "end")
        for name in sorted(self.entries):
            if q and q not in name.lower():
                continue
            self.listbox.insert("end", name)

    def on_pick(self, _e=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        name = self.listbox.get(sel[0])
        self.show(name)

    def show(self, name: str):
        self.current = name
        e = self.entries.get(name, {})
        lines = [f"{k}={v}" for k, v in (e.get("fields") or {}).items()]
        if e.get("notes"):
            lines += ["", f"# {e['notes']}"]
        self.title.config(text=f"{name}   [{e.get('category', 'note')}]")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.edit_modified(False)
        self.set_status("")

    def on_edit(self, _e=None):
        if self.text.edit_modified():
            self.dirty = True
            self.set_status("unsaved", "#fbbf24")
            self.text.edit_modified(False)

    # ── actions ────────────────────────────────────────────────────────────
    def save_entry(self):
        if not self.current:
            return
        fields, notes = {}, []
        for line in self.text.get("1.0", "end").splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                notes.append(line.lstrip("# ").strip())
            elif "=" in line:
                k, v = line.split("=", 1)
                fields[k.strip()] = v.strip()
        e = self.entries.setdefault(self.current, {"category": "api"})
        e["fields"] = fields
        e["notes"] = " ".join(notes)
        try:
            V.save(self.data, self.password)
        except Exception as ex:
            messagebox.showerror("Could not save", str(ex))
            return
        self.dirty = False
        self.set_status(f"saved · {len(fields)} field(s)")

    def copy_all(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.text.get("1.0", "end").strip())
        self.set_status("copied")

    def new_entry(self):
        name = simpledialog.askstring("New entry", "Name it after the service:", parent=self.root)
        if not name:
            return
        name = name.strip()
        if name in self.entries:
            messagebox.showinfo("Already there", f"{name} exists already.")
            return
        self.entries[name] = {"category": "api", "fields": {}, "notes": ""}
        V.save(self.data, self.password)
        self.refresh_list()
        self.show(name)

    def delete_entry(self):
        if not self.current:
            return
        if not messagebox.askyesno("Delete", f"Delete {self.current}? This cannot be undone."):
            return
        self.entries.pop(self.current, None)
        V.save(self.data, self.password)
        self.current = None
        self.text.delete("1.0", "end")
        self.title.config(text="pick one on the left")
        self.refresh_list()
        self.set_status("deleted")

    def set_status(self, msg: str, colour: str = "#34d399"):
        self.status.config(text=msg, fg=colour)

    def on_close(self):
        if self.dirty and not messagebox.askyesno("Unsaved", "You have unsaved edits. Close anyway?"):
            return
        self.root.destroy()


def main():
    root = tk.Tk()
    root.withdraw()

    if not V.VAULT.exists():
        if not messagebox.askyesno("No vault yet", f"There is no vault at\n{V.VAULT}\n\nCreate one now?"):
            return
        pw = simpledialog.askstring("New vault", "Choose a master password:", show="*", parent=root)
        if not pw or len(pw) < 8:
            messagebox.showerror("Too short", "Use at least 8 characters.")
            return
        if pw != simpledialog.askstring("New vault", "Repeat it:", show="*", parent=root):
            messagebox.showerror("No match", "They do not match.")
            return
        V.save(V.empty(), pw)
        messagebox.showinfo("Created", f"Vault created at\n{V.VAULT}\n\nBack that file up. It is encrypted.")
        data = V.load(pw)
    else:
        # Three tries, then the window closes. There is no reset: that is what the
        # encryption is for, and pretending otherwise would be the lie.
        data = pw = None
        for _ in range(3):
            pw = simpledialog.askstring("Vault", "Master password:", show="*", parent=root)
            if pw is None:
                return
            try:
                data = V.load(pw)
                break
            except ValueError:
                messagebox.showerror("Wrong password", "That is not it. Try again.")
        if data is None:
            return

    root.deiconify()
    VaultWindow(root, data, pw)
    root.mainloop()


if __name__ == "__main__":
    main()
