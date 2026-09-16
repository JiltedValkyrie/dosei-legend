"""Windows mesh workshop; launch with pythonw or the adjacent BAT."""
import argparse
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from mesh_assets import (PROJECT, WORKSPACE, build_selection, catalog, export_obj,
                         import_obj, load_settings, save_settings)


class Workshop:
    def __init__(self, root):
        self.root = root
        root.title('Dosei Legend - Mesh workshop')
        root.geometry('930x570')
        root.minsize(780, 550)
        self.results = queue.Queue()
        self.busy = False
        self.entries = {}
        outer = ttk.Frame(root, padding=16)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Mesh workshop', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='OBJ export / quad candidates - originals and collision remain unchanged.').pack(anchor='w', pady=(3, 12))
        self.tree = ttk.Treeview(outer, columns=('mesh', 'verts', 'tris', 'candidate'), show='headings', height=7)
        for key, title, width in [('mesh', 'Source mesh', 250), ('verts', 'Vertices', 80),
                                  ('tris', 'Triangles', 80), ('candidate', 'Quad import', 370)]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=65)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', lambda _: self.select())
        self.prefer = tk.BooleanVar(value=load_settings().get('prefer_quads', True))
        self.preference = ttk.Checkbutton(outer, text='Prefer quads when build support is available (saved preference)',
                                         variable=self.prefer, command=self.save_preference)
        self.preference.pack(anchor='w', pady=(12, 6))
        self.split_incompatible = tk.BooleanVar(value=False)
        self.split_option = ttk.Checkbutton(outer,
            text='Split incompatible quads on import (keep valid quads; report splits)',
            variable=self.split_incompatible)
        self.split_option.pack(anchor='w', pady=(0, 8))
        self.info = tk.StringVar()
        ttk.Label(outer, textvariable=self.info, wraplength=860).pack(anchor='w', pady=(0, 8))
        ttk.Label(outer, text='Current ISO builds still use triangles. Imported quads are NOT active runtime assets.',
                  foreground='#9c3b13').pack(anchor='w')
        buttons = ttk.Frame(outer)
        buttons.pack(fill='x', pady=12)
        self.controls = []
        for label, action in [('Export OBJ...', self.export), ('Import edited OBJ...', self.import_mesh),
                              ('Open workspace', self.open_workspace), ('Refresh', self.refresh)]:
            button = ttk.Button(buttons, text=label, command=action)
            button.pack(side='left', padx=(0, 8))
            self.controls.append(button)
        self.status = tk.StringVar(value='Ready. Use matching Blender axes on import and export: Forward -Z, Up Y, scale 1.')
        ttk.Label(outer, textvariable=self.status, wraplength=860).pack(anchor='w')
        self.refresh()
        root.after(100, self.poll)

    def selected(self):
        selection = self.tree.selection()
        if not selection:
            raise ValueError('Select a source mesh first')
        entry = self.entries[selection[0]]
        if entry['error']:
            raise ValueError(entry['error'])
        return entry

    def refresh(self):
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        settings = load_settings()
        self.entries = {e['id']: e for e in catalog()}
        for key, entry in self.entries.items():
            candidate = settings.get('meshes', {}).get(key, {}).get('candidate')
            state = entry['error'] or ('Stored; runtime support pending' if candidate else 'None')
            self.tree.insert('', 'end', iid=key, values=(entry['source'], entry['vertices'], entry['triangles'], state))
        if self.entries:
            key = selected[0] if selected and selected[0] in self.entries else next(iter(self.entries))
            self.tree.selection_set(key)
        self.select()

    def select(self):
        try:
            entry = self.selected()
            self.info.set(build_selection(entry)['reason'] + '.\nKokiri is exported as one combined visual mesh; collision is excluded.')
        except ValueError as exc:
            self.info.set(str(exc))

    def save_preference(self):
        try:
            settings = load_settings()
            settings['prefer_quads'] = self.prefer.get()
            save_settings(settings)
            self.select()
        except Exception as exc:
            messagebox.showerror('Preference not saved', str(exc), parent=self.root)

    def task(self, action, label):
        if self.busy: return
        self.busy = True
        self.status.set(label)
        for control in self.controls + [self.preference, self.split_option]: control.configure(state='disabled')
        def worker():
            try: self.results.put((True, action()))
            except Exception as exc: self.results.put((False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            success, result = self.results.get_nowait()
            self.busy = False
            for control in self.controls + [self.preference, self.split_option]: control.configure(state='normal')
            self.status.set(('Saved: ' if success else 'Failed: ') + str(result))
            self.refresh()
            if success:
                summary = ''
                if result.is_dir() and (result / 'mesh.json').exists():
                    meta = json.loads((result / 'mesh.json').read_text())
                    summary = (f"\n\nKept {meta['quads']} quads; split {meta.get('split_quads', 0)} incompatible quads."
                               f"\nOutput: {meta['triangles']} triangles, {meta['quads']} quads.")
                messagebox.showinfo('Mesh workshop', 'Saved separately:\n' + str(result) + summary + '\n\nOriginal assets were not changed.', parent=self.root)
            else:
                messagebox.showerror('Mesh operation failed', result, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def export(self):
        try: entry = self.selected()
        except ValueError as exc:
            messagebox.showerror('Export', str(exc), parent=self.root)
            return
        self.task(lambda: export_obj(entry), 'Exporting OBJ and preview atlas...')

    def import_mesh(self):
        try: entry = self.selected()
        except ValueError as exc:
            messagebox.showerror('Import', str(exc), parent=self.root)
            return
        path = filedialog.askopenfilename(parent=self.root, title='Import edited OBJ for ' + entry['name'],
                                          filetypes=[('Wavefront OBJ', '*.obj')])
        split = self.split_incompatible.get()
        policy = ('Recoverable incompatible quads will be split into triangles; valid quads stay intact.\n\n'
                  if split else 'Incompatible quads will be rejected.\n\n')
        if path and messagebox.askokcancel('Store quad candidate',
            'Keep original scale/axes, UVs and flags_* materials.\n\n' + policy +
            'Collision will NOT follow geometry edits. This stores a candidate only; runtime quad support is pending.', parent=self.root):
            self.task(lambda: import_obj(entry, path, split_incompatible=split), 'Validating and storing quad candidate...')

    def open_workspace(self):
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        os.startfile(WORKSPACE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--export-all', action='store_true', help='Export all supported source meshes without opening the GUI')
    args = parser.parse_args()
    if args.export_all:
        for entry in catalog():
            if entry['error']: raise ValueError(entry['error'])
            print(export_obj(entry))
        return
    root = tk.Tk()
    if args.smoke_test: root.withdraw()
    app = Workshop(root)
    if args.smoke_test:
        root.update()
        assert len(app.tree.get_children()) == len(catalog())
        root.destroy()
        print('Mesh workshop GUI smoke test passed; no assets written.')
    else:
        root.mainloop()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # pythonw has no console: failures must be visible instead of disappearing.
        messagebox.showerror('Mesh workshop could not start', str(exc))
        raise
