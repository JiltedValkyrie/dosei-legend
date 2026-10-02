"""Windows mesh workshop; launch with pythonw or the adjacent BAT."""
import argparse
import hashlib
import json
import os
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from mesh_assets import PROJECT, WORKSPACE, catalog, export_obj, import_obj
import asset_catalog
from game_install import GAME_TARGETS, install_mesh
import actor_meshes  # game/tools, on sys.path via game_install


class Workshop:
    def __init__(self, root):
        self.root = root
        root.title('Dosei Legend - Mesh workshop')
        root.geometry('1180x720')
        root.minsize(1040, 680)
        self.results = queue.Queue()
        self.busy = False
        self.entries = {}
        self.viewport_window = None
        outer = ttk.Frame(root, padding=16)
        outer.pack(fill='both', expand=True)
        heading = ttk.Frame(outer)
        heading.pack(fill='x')
        ttk.Label(heading, text='Mesh workshop', font=('Segoe UI', 17, 'bold')).pack(side='left')
        ttk.Button(heading, text='Map Workshop', command=self.open_viewport).pack(side='right')
        ttk.Label(outer, text='Export, edit, then choose a game room and use your OBJ in the next Clean build.').pack(anchor='w', pady=(3, 12))
        filters = ttk.Frame(outer)
        filters.pack(fill='x', pady=(0, 8))
        ttk.Label(filters, text='Search assets').pack(side='left')
        self.query = tk.StringVar()
        ttk.Entry(filters, textvariable=self.query, width=30).pack(side='left', padx=8)
        self.kind = tk.StringVar(value='All types')
        self.kind_box = ttk.Combobox(filters, textvariable=self.kind, state='readonly', width=18)
        self.kind_box.pack(side='left', padx=4)
        self.pub_state = tk.StringVar(value='All states')
        self.state_box = ttk.Combobox(filters, textvariable=self.pub_state, state='readonly', width=18,
            values=['All states', 'Published', 'Modified', 'Missing', 'Assigned', 'Not published', 'Not tracked', 'Staged'])
        self.state_box.pack(side='left', padx=4)
        self.count = tk.StringVar()
        ttk.Label(filters, textvariable=self.count).pack(side='left', padx=8)
        self.sort_key, self.sort_reverse = 'source', False
        self.rows = []
        grid = ttk.Frame(outer)
        grid.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(grid, columns=('source', 'type', 'origin', 'publication', 'published_at', 'size'), show='headings', height=12)
        self.column_titles = {}
        for key, title, width in [('source', 'Asset path', 410), ('type', 'Type', 115),
                                  ('origin', 'Location', 90), ('publication', 'Mesh publish state', 135),
                                  ('published_at', 'Last publish (UTC)', 185), ('size', 'Bytes', 85)]:
            self.column_titles[key] = title
            self.tree.heading(key, text=title, command=lambda k=key: self.sort(k))
            self.tree.column(key, width=width, minwidth=65)
        vertical = ttk.Scrollbar(grid, orient='vertical', command=self.tree.yview)
        horizontal = ttk.Scrollbar(grid, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        vertical.pack(side='right', fill='y')
        horizontal.pack(side='bottom', fill='x')
        self.tree.pack(fill='both', expand=True)
        for variable in (self.query, self.kind, self.pub_state):
            variable.trace_add('write', lambda *_: self.render_rows())
        self.tree.bind('<<TreeviewSelect>>', lambda _: self.select())
        targets = ttk.Frame(outer)
        targets.pack(fill='x', pady=(12, 6))
        ttk.Label(targets, text='Game room:').pack(side='left', padx=(0, 8))
        self.target = tk.StringVar(value=next(iter(GAME_TARGETS)))
        self.target_picker = ttk.Combobox(targets, textvariable=self.target,
                                        values=list(GAME_TARGETS), state='readonly', width=36)
        self.target_picker.pack(side='left')
        self.split_incompatible = tk.BooleanVar(value=False)
        self.split_option = ttk.Checkbutton(outer,
            text='Split incompatible quads on import (keep valid quads; report splits)',
            variable=self.split_incompatible)
        self.split_option.pack(anchor='w', pady=(0, 8))
        self.info = tk.StringVar()
        ttk.Label(outer, textvariable=self.info, wraplength=860).pack(anchor='w', pady=(0, 8))
        ttk.Label(outer, text='Use in game overwrites the selected room visual. Collision stays unchanged. Rebuild Clean to play.',
                  foreground='#9c3b13').pack(anchor='w')
        buttons = ttk.Frame(outer)
        buttons.pack(fill='x', pady=12)
        self.controls = []
        for label, action in [('Export OBJ...', self.export), ('Store edited OBJ...', self.import_mesh),
                              ('Publish mesh...', self.install), ('Open asset folder', self.open_asset_folder),
                              ('Open workspace', self.open_workspace), ('Refresh', self.refresh)]:
            button = ttk.Button(buttons, text=label, command=action)
            button.pack(side='left', padx=(0, 8))
            self.controls.append(button)
        characters = ttk.LabelFrame(outer, text='Character mesh (skinned; animation follows edits)', padding=8)
        characters.pack(fill='x', pady=(0, 10))
        self.actor = tk.StringVar(value=actor_meshes.ACTORS[0])
        ttk.Combobox(characters, textvariable=self.actor, values=list(actor_meshes.ACTORS),
                     state='readonly', width=10).pack(side='left', padx=(0, 8))
        self.actor.trace_add('write', lambda *_: self.actor_state())
        for label, action in [('Export character OBJ...', self.export_actor),
                              ('Use character OBJ...', self.install_actor),
                              ('Restore original', self.restore_actor)]:
            button = ttk.Button(characters, text=label, command=action)
            button.pack(side='left', padx=(0, 8))
            self.controls.append(button)
        self.actor_info = tk.StringVar()
        ttk.Label(characters, textvariable=self.actor_info).pack(side='left', padx=8)
        self.actor_state()
        self.status = tk.StringVar(value='Ready. Use matching Blender axes on import and export: Forward -Z, Up Y, scale 1.')
        ttk.Label(outer, textvariable=self.status, wraplength=860).pack(anchor='w')
        menu = tk.Menu(root)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label='Mesh Workshop guide (F1)', command=self.help)
        menu.add_cascade(label='Help', menu=help_menu)
        root.configure(menu=menu)
        root.bind('<F1>', lambda _: self.help())
        self.refresh()
        root.after(100, self.poll)

    def selected(self):
        selection = self.tree.selection()
        if not selection:
            raise ValueError('Select an asset first')
        entry = self.entries[selection[0]]
        return entry

    def refresh(self):
        self.rows = asset_catalog.catalog()
        self.entries = {e['id']: e for e in self.rows}
        self.kind_box.configure(values=['All types'] + sorted({e['type'] for e in self.rows}))
        self.render_rows()

    def sort(self, key):
        self.sort_reverse = not self.sort_reverse if self.sort_key == key else False
        self.sort_key = key
        for column, title in self.column_titles.items():
            self.tree.heading(column, text=title + ((' ▼' if self.sort_reverse else ' ▲') if column == key else ''))
        self.render_rows()

    def render_rows(self):
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        rows = asset_catalog.select_rows(self.rows, self.query.get(), self.kind.get(), self.pub_state.get(), self.sort_key, self.sort_reverse)
        for e in rows:
            self.tree.insert('', 'end', iid=e['id'], values=(e['source'], e['type'], e['origin'],
                e['publication'], e['published_at'].replace('T', ' ').replace('+00:00', '') or 'Unknown / never', e['size']))
        self.count.set(f'{len(rows)} / {len(self.rows)} assets')
        if rows:
            visible = {e['id'] for e in rows}
            key = selected[0] if selected and selected[0] in visible else rows[0]['id']
            self.tree.selection_set(key)
        self.select()

    def select(self):
        try:
            entry = self.selected()
            for label, room in GAME_TARGETS.items():
                if entry['targets'] == room:
                    self.target.set(label)
                    break
            detail = entry['error'] or (f"{entry['vertices']} vertices, {entry['triangles']} triangles" if entry['exportable'] else 'Browse only; OBJ publishing accepts room visual meshes.')
            self.info.set(entry['source'] + '\n' + detail + (' | Rooms: ' + entry['targets'] if entry['targets'] else '') +
                          (' | Combined forest: publish only intended room geometry.' if entry['name'] == 'FOREST.BIN' else ''))
            if not self.busy:
                self.controls[0].configure(state='normal' if entry['exportable'] else 'disabled')
                self.controls[1].configure(state='normal' if entry['type'] == 'Mesh' and entry['path'].is_file() else 'disabled')
        except ValueError as exc:
            self.info.set(str(exc))
            if not self.busy:
                for control in self.controls[:2]: control.configure(state='disabled')

    def mesh_entry(self, entry):
        path = entry['path']
        source = path.relative_to(PROJECT).as_posix() if path.is_relative_to(PROJECT) else str(path)
        identity = 'cd/FOREST.BIN' if source == 'levels/kokiri/assets/static/FOREST.BIN' else source
        return dict(id=hashlib.sha256(identity.encode()).hexdigest()[:12], source=source, name=path.stem)

    def task(self, action, label):
        if self.busy: return
        self.busy = True
        self.status.set(label)
        for control in self.controls + [self.target_picker, self.split_option]: control.configure(state='disabled')
        def worker():
            try: self.results.put((True, action()))
            except Exception as exc: self.results.put((False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            success, result = self.results.get_nowait()
            self.busy = False
            for control in self.controls + [self.split_option]: control.configure(state='normal')
            self.target_picker.configure(state='readonly')
            self.status.set(('Saved: ' if success else 'Failed: ') + str(result))
            self.refresh()
            self.actor_state()
            if success:
                summary = ''
                if isinstance(result, dict):
                    self.status.set(result['message'])
                    messagebox.showinfo('Mesh installed', result['message'], parent=self.root)
                elif result.is_dir() and (result / 'mesh.json').exists():
                    meta = json.loads((result / 'mesh.json').read_text())
                    summary = (f"\n\nKept {meta['quads']} quads; split {meta.get('split_quads', 0)} incompatible quads."
                               f"\nOutput: {meta['triangles']} triangles, {meta['quads']} quads.")
                if not isinstance(result, dict):
                    messagebox.showinfo('Mesh workshop', 'Saved separately:\n' + str(result) + summary + '\n\nUse OBJ in game to install it for a room.', parent=self.root)
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
        if not entry['exportable']:
            messagebox.showerror('Export', 'Select a supported KFR1 mesh to export.', parent=self.root)
            return
        entry = self.mesh_entry(entry)
        self.task(lambda: export_obj(entry), 'Exporting OBJ and preview atlas...')

    def import_mesh(self):
        try: entry = self.selected()
        except ValueError as exc:
            messagebox.showerror('Import', str(exc), parent=self.root)
            return
        entry = self.mesh_entry(entry)
        path = filedialog.askopenfilename(parent=self.root, title='Import edited OBJ for ' + entry['name'],
                                          filetypes=[('Wavefront OBJ', '*.obj')])
        split = self.split_incompatible.get()
        if path:
            self.task(lambda: import_obj(entry, path, split_incompatible=split, require_quads=False), 'Validating and storing edited OBJ...')

    def install(self):
        target = self.target.get()
        selected = self.tree.selection()
        entry = self.entries[selected[0]] if selected else None
        path = str(entry['path']) if entry and entry['path'].suffix.lower() == '.obj' and entry['path'].is_file() else filedialog.askopenfilename(parent=self.root, title='Publish OBJ to ' + target,
                                         filetypes=[('Wavefront OBJ', '*.obj')])
        if not path:
            return
        split = self.split_incompatible.get()
        def work():
            folder = install_mesh(path, target, split_incompatible=split)
            import layout_variants
            choice=layout_variants.selection()
            next_step=('Map Workshop: choose Current baked, then Use for next build, then Clean.'
                       if choice is not None else 'Rebuild Clean to play.')
            return dict(message=f'Installed {target}:\n{folder}\n\n{next_step} Collision stays unchanged.')
        self.task(work, 'Checking geometry and memory budget, then installing ' + target + '...')

    def actor_state(self):
        mesh = actor_meshes.override(self.actor.get())
        self.actor_info.set('Using edited: ' + str(mesh.relative_to(PROJECT)) if mesh else 'Using original ROM mesh')

    def export_actor(self):
        actor = self.actor.get()
        default = actor_meshes.default_export(actor)
        default.parent.mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(parent=self.root, title='Export ' + actor + ' character OBJ',
            initialdir=str(default.parent), initialfile=default.name, defaultextension='.obj',
            filetypes=[('Wavefront OBJ', '*.obj')])
        if not any(default.parent.iterdir()): default.parent.rmdir()   # cancelled or saved elsewhere
        if path:
            self.task(lambda: dict(message=f'Exported {actor}:\n{actor_meshes.export_actor(actor, path)}\n\n'
                'Keep MTL, PNGs and .actor.json beside it. Keep material names; '
                'decimate/edit freely, then Use character OBJ.'), 'Exporting ' + actor + ' from ROM...')

    def install_actor(self):
        actor = self.actor.get()
        path = filedialog.askopenfilename(parent=self.root, title='Use edited OBJ for ' + actor,
            initialdir=str(actor_meshes.default_export(actor).parent), filetypes=[('Wavefront OBJ', '*.obj')])
        if path:
            self.task(lambda: dict(message=f'{actor}: {actor_meshes.install(actor, path)}\n\nRebuild Clean to play.'),
                      'Checking ' + actor + ' OBJ with the real builder...')

    def restore_actor(self):
        actor = self.actor.get()
        done = actor_meshes.restore(actor)
        self.actor_state()
        self.status.set(f'{actor}: original ROM mesh restored. Rebuild Clean.' if done else f'{actor}: already original.')

    def help(self):
        window = tk.Toplevel(self.root)
        window.title('Mesh Workshop guide')
        window.geometry('840x600')
        text = tk.Text(window, wrap='word', padx=16, pady=16)
        scrollbar = ttk.Scrollbar(window, command=text.yview)
        scrollbar.pack(side='right', fill='y')
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(fill='both', expand=True)
        text.insert('1.0', Path(__file__).with_name('README.md').read_text(encoding='utf-8'))
        text.configure(state='disabled')
        window.bind('<Escape>', lambda _: window.destroy())

    def open_workspace(self):
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        os.startfile(WORKSPACE)

    def open_viewport(self):
        from level_viewport import RoomViewport
        if self.viewport_window is None or not self.viewport_window.winfo_exists():
            self.viewport_window = RoomViewport(self.root, GAME_TARGETS[self.target.get()])
        else:
            self.viewport_window.deiconify()
            self.viewport_window.lift()

    def open_asset_folder(self):
        try:
            folder = self.selected()['path'].parent
            if not folder.is_dir(): raise ValueError('Asset folder is missing')
            os.startfile(folder)
        except ValueError as exc:
            messagebox.showerror('Open asset folder', str(exc), parent=self.root)


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
        assert len(app.tree.get_children()) == len(app.rows)
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
