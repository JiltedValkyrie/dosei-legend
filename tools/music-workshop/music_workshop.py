"""Windows music workshop; launch with pythonw or the adjacent BAT."""
import argparse
import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from music_assets import (ROOT, WORKSPACE, CDDA_TARGET, GAME_TARGETS, bake,
                          catalog, cdda_tracks, find_source,
                          probe, summary, survey, game_songs,
                          assign_song, song_dictionary, publish_song)
from workshop_help import UserGuide


class Workshop:
    def __init__(self, root):
        self.root = root
        root.title('Dosei Legend - Music workshop')
        root.geometry('1000x730')
        root.minsize(900, 680)
        self.guide_window = None
        menu = tk.Menu(root)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label='User guide', accelerator='F1', command=self.show_help)
        menu.add_cascade(label='Help', menu=help_menu)
        root.configure(menu=menu)
        root.bind('<F1>', self.show_help)
        self.results = queue.Queue()
        self.busy = False
        self.entries = {}
        self.built = None
        self.checked = {}
        self.reasons = {}
        self.source, self.source_error = find_source()

        outer = ttk.Frame(root, padding=16)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Music workshop',
                  font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='Browse the US 1.2 sequences, listen, then bake a '
                  'Saturn bank into the workspace or an existing game music slot.').pack(anchor='w', pady=(3, 12))

        search = ttk.Frame(outer)
        search.pack(fill='x', pady=(0, 6))
        ttk.Label(search, text='Filter').pack(side='left', padx=(0, 6))
        self.filter = tk.StringVar()
        self.filter.trace_add('write', lambda *_: self.refresh())
        ttk.Entry(search, textvariable=self.filter).pack(side='left',
                                                         fill='x', expand=True)

        columns = [('sequence', 'Seq', 60), ('name', 'NA_BGM name', 250),
                   ('soundfont', 'Soundfont', 80), ('loop', 'Loop', 110),
                   ('bytes', 'Bytes', 80), ('in_game', 'Already in game', 170),
                   ('bakes', 'Bakes?', 150)]
        self.tree = ttk.Treeview(outer, columns=[c[0] for c in columns],
                                 show='headings', height=11)
        for key, title, width in columns:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=55)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', lambda _: self.select())

        options = ttk.Frame(outer)
        options.pack(fill='x', pady=(10, 4))
        self.fields = {}
        for key, label, width, value in [('name', 'Bank name', 14, ''),
                                         ('soundfont', 'Soundfont', 5, ''),
                                         ('loop', 'Loop label', 11, ''),
                                         ('budget', 'Sample budget', 8, ''),
                                         ('voices', 'Voices', 5, '')]:
            ttk.Label(options, text=label).pack(side='left', padx=(0, 4))
            variable = tk.StringVar(value=value)
            ttk.Entry(options, textvariable=variable,
                      width=width).pack(side='left', padx=(0, 12))
            self.fields[key] = variable
        self.preserve_intro = tk.BooleanVar(value=False)
        self.intro_option = ttk.Checkbutton(
            options, text='Keep the intro/loop point',
            variable=self.preserve_intro)
        self.intro_option.pack(side='left')
        ttk.Label(outer, text='Blank fields use what the sequence itself '
                  'declares. Overrides are for hand-tuning one bake.',
                  foreground='#555555').pack(anchor='w')

        export = ttk.Frame(outer)
        export.pack(fill='x', pady=(8, 0))
        ttk.Label(export, text='Generate to').pack(side='left', padx=(0, 8))
        self.destination = tk.StringVar(value='Workspace revision')
        self.destination_box = ttk.Combobox(export, textvariable=self.destination,
            values=['Workspace revision'] + list(GAME_TARGETS) + [CDDA_TARGET],
            state='readonly', width=25)
        self.destination_box.pack(side='left')
        self.destination_box.bind('<<ComboboxSelected>>', self.destination_changed)
        self.destination_info = tk.StringVar()
        ttk.Label(outer, textvariable=self.destination_info, wraplength=930).pack(anchor='w', pady=(3, 0))
        self.destination_changed()

        routes = ttk.LabelFrame(outer, text='Game song dictionary', padding=6)
        routes.pack(fill='x', pady=(8, 0))
        self.song = tk.StringVar()
        self.song_source = tk.StringVar()
        self.song_target = tk.StringVar()
        self.song_box = ttk.Combobox(routes, textvariable=self.song, state='readonly', width=29)
        self.song_box.pack(side='left', padx=(0, 5))
        self.song_source_box = ttk.Combobox(routes, textvariable=self.song_source,
                                          values=['BANK', 'CD'], state='readonly', width=6)
        self.song_source_box.pack(side='left', padx=5)
        self.song_target_box = ttk.Combobox(routes, textvariable=self.song_target, state='readonly', width=19)
        self.song_target_box.pack(side='left', padx=5)
        self.save_song_button = ttk.Button(routes, text='Save song mapping', command=self.save_song)
        self.save_song_button.pack(side='left', padx=5)
        self.song_box.bind('<<ComboboxSelected>>', self.song_changed)
        self.song_source_box.bind('<<ComboboxSelected>>', self.song_source_changed)
        self.refresh_songs()

        self.info = tk.StringVar()
        self.info_label = ttk.Label(outer, textvariable=self.info,
                                    wraplength=930, justify='left')
        self.info_label.pack(anchor='w', pady=(10, 6))

        buttons = ttk.Frame(outer)
        buttons.pack(fill='x', pady=8)
        self.controls = []
        for label, action in [('Inspect', self.inspect),
                              ('Preview WAV', self.preview),
                              ('Generate / Publish', self.generate),
                              ('Check all', self.check_all),
                              ('Open workspace', self.open_workspace),
                              ('Refresh', self.refresh)]:
            button = ttk.Button(buttons, text=label, command=action)
            button.pack(side='left', padx=(0, 8))
            self.controls.append(button)

        self.status = tk.StringVar(
            value='Ready. Inspecting or baking a sequence takes a few seconds.')
        ttk.Label(outer, textvariable=self.status,
                  wraplength=930).pack(anchor='w')
        self.refresh()
        root.after(100, self.poll)

    # -- selection ---------------------------------------------------------

    def refresh_songs(self):
        self.songs = {s['song']: s for s in game_songs()}
        self.song_box.configure(values=list(self.songs))
        if self.song.get() not in self.songs:
            self.song.set('NA_BGM_GAME_OVER')
        self.song_changed()

    def song_changed(self, _event=None):
        entry = self.songs[self.song.get()]
        self.song_source.set(entry['src'])
        self.song_source_box.configure(values=['BANK'] if self.song.get() in song_dictionary.BANK_ONLY else ['BANK', 'CD'])
        self.song_source_changed()
        self.song_target.set(entry.get('cd', entry.get('bank')))

    def song_source_changed(self, _event=None):
        values = ([e['name'].upper() for e in cdda_tracks()] if self.song_source.get() == 'CD'
                  else list(song_dictionary.BANKS))
        self.song_target_box.configure(values=values)
        if self.song_target.get() not in values:
            self.song_target.set(values[0] if values else '')

    def save_song(self):
        song, source, target = self.song.get(), self.song_source.get(), self.song_target.get()
        def action():
            path = assign_song(song, source, target)
            return ('installed', path, '%s -> %s: %s' % (song, source, target))
        self.task(action, 'Saving song mapping...')

    def destination_changed(self, _event=None):
        target = self.destination.get()
        if target in GAME_TARGETS:
            folder, prefix, raw = GAME_TARGETS[target]
            self.destination_info.set('Publishes %s bank files in %s and maps the selected Game song to %s. Rebuild Clean.'
                                      % (target, ROOT / folder, prefix))
        elif target == CDDA_TARGET:
            tracks = cdda_tracks()
            self.destination_info.set(
                'Adds a Red Book track to %s and renders every track. The disc '
                'has %d audio track(s); a new one becomes track %d and is '
                'assigned to the selected Game song when published. Name it, then rebuild Clean.'
                % (ROOT / 'game/assets/audio/cdda_tracks.json', len(tracks),
                   (tracks[-1]['track'] + 1) if tracks else 2))
        else:
            self.destination_info.set('Writes a new workspace revision. Preview WAV always uses the workspace.')

    def show_help(self, _event=None):
        if self.guide_window is None or not self.guide_window.winfo_exists():
            self.guide_window = UserGuide(self.root)
        else:
            self.guide_window.deiconify()
            self.guide_window.lift()
        return 'break'

    def selected(self):
        selection = self.tree.selection()
        if not selection:
            raise ValueError('Select a sequence first')
        entry = self.entries[selection[0]]
        if entry['error']:
            raise ValueError('Sequence %d: %s' % (entry['sequence'],
                                                  entry['error']))
        return entry

    def refresh(self):
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        if self.source is None:
            self.info.set(self.source_error)
            return
        needle = self.filter.get().strip().lower()
        try:
            entries = catalog(self.source)
        except ValueError as exc:
            self.info.set(str(exc))
            return
        self.entries = {e['id']: e for e in entries}
        for key, entry in self.entries.items():
            haystack = '%s %s %s' % (entry['sequence'], entry['name'],
                                     entry['in_game'] or '')
            if needle and needle not in haystack.lower():
                continue
            self.tree.insert('', 'end', iid=key,
                             values=(entry['sequence'], entry['name'],
                                     entry['error'] or entry['soundfont'],
                                     entry['loop'] or 'from the top',
                                     entry['bytes'], entry['in_game'] or '',
                                     self.checked.get(key, '')))
        visible = self.tree.get_children()
        if visible:
            key = selected[0] if selected and selected[0] in visible else visible[0]
            self.tree.selection_set(key)
        self.select()

    def select(self):
        self.built = None
        try:
            entry = self.selected()
        except ValueError as exc:
            self.info.set(str(exc))
            return
        self.info.set('%s (sequence %d), soundfont %s, loop %s.\n'
                      'Inspect to interpret and bake it on the host.'
                      % (entry['name'], entry['sequence'], entry['soundfont'],
                         entry['loop'] or 'from the top'))
        if not self.fields['name'].get().strip():
            self.fields['name'].set(entry['name'].replace('NA_BGM_', ''))

    # -- overrides ---------------------------------------------------------

    def number(self, key):
        text = self.fields[key].get().strip()
        if not text:
            return None
        if not text.isdigit():
            raise ValueError('%s must be a number' % key)
        return int(text)

    def overrides(self):
        return dict(soundfont=self.number('soundfont'),
                    loop=self.fields['loop'].get().strip() or None,
                    budget=self.number('budget'), voices=self.number('voices'))

    # -- background work ---------------------------------------------------

    def task(self, action, label):
        if self.busy:
            return
        self.busy = True
        self.destination_box.configure(state='disabled')
        for control in (self.song_box, self.song_source_box, self.song_target_box, self.save_song_button):
            control.configure(state='disabled')
        self.status.set(label)
        for control in self.controls + [self.intro_option]:
            control.configure(state='disabled')

        def worker():
            try:
                self.results.put((True, action()))
            except Exception as exc:
                self.results.put((False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            success, result = self.results.get_nowait()
            self.busy = False
            self.destination_box.configure(state='readonly')
            for control in (self.song_box, self.song_source_box, self.song_target_box):
                control.configure(state='readonly')
            self.save_song_button.configure(state='normal')
            for control in self.controls + [self.intro_option]:
                control.configure(state='normal')
            if not success:
                self.status.set('Failed: ' + str(result))
                messagebox.showerror('Music workshop', str(result),
                                     parent=self.root)
            elif isinstance(result, tuple) and result[0] == 'checked':
                _, rows, note = result
                self.checked = {r['id']: ('yes  %.0f s' % r['seconds']
                                          if r['bakes'] else 'no') for r in rows}
                self.reasons = {r['id']: r['reason'] for r in rows}
                self.status.set(note)
                self.refresh()
            elif isinstance(result, tuple) and result[0] == 'installed':
                _, folder, target = result
                self.refresh_songs()
                self.status.set('Installed %s: %s' % (target, folder))
                messagebox.showinfo('Music workshop',
                    '%s saved.\n%s\n\nRebuild Clean to update the game disc.'
                    % (target, folder), parent=self.root)
            elif isinstance(result, tuple):       # inspect / preview
                kind, built, extra = result
                self.built = built
                self.show(built)
                self.status.set(kind)
                if extra:
                    os.startfile(extra)
            else:                                 # a baked revision folder
                self.status.set('Saved: ' + str(result))
                messagebox.showinfo(
                    'Music workshop',
                    'Saved separately:\n%s\n\nCopy these files into the game '
                    'yourself when the bank sounds right. No game asset was '
                    'changed.' % result, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def show(self, built):
        text = summary(built)
        over = 'OVER BUDGET' in text or 'does not fit' in text
        self.info_label.configure(foreground='#9c3b13' if over else '')
        self.info.set(text)

    # -- actions -----------------------------------------------------------

    def build(self, sequence, overrides):
        """Render the selection, or fail with the reason rather than a traceback."""
        built, reason = probe(self.source, sequence, **overrides)
        if built is None:
            raise ValueError(reason)
        return built

    def inspect(self):
        try:
            sequence, overrides = self.selected()['sequence'], self.overrides()
        except ValueError as exc:
            messagebox.showerror('Inspect', str(exc), parent=self.root)
            return
        self.task(lambda: ('Inspected.', self.build(sequence, overrides), None),
                  'Interpreting and baking on the host...')

    def preview(self):
        try:
            sequence, overrides = self.selected()['sequence'], self.overrides()
            name = self.fields['name'].get() or 'PREVIEW'
            preserve_intro = self.preserve_intro.get()
        except ValueError as exc:
            messagebox.showerror('Preview', str(exc), parent=self.root)
            return

        def action():
            built = self.build(sequence, overrides)
            folder = bake(self.source, built['sequence'],
                          name, preserve_intro=preserve_intro, built=built)
            return ('Preview written beside the bank.', built,
                    folder / 'preview.wav')
        self.task(action, 'Baking and rendering the WAV preview...')

    def generate(self):
        try:
            entry = self.selected()
            overrides = self.overrides()
            preserve_intro = self.preserve_intro.get()
            target = self.destination.get()
            song = self.song.get()
            name = self.fields['name'].get().strip()
            if not name and target not in GAME_TARGETS:
                raise ValueError('Give the bank a name'
                                 if target != CDDA_TARGET else
                                 'Give the track a name; it becomes '
                                 'CDDA_TRACK_<NAME>')
        except ValueError as exc:
            messagebox.showerror('Generate', str(exc), parent=self.root)
            return
        def action():
            if target == CDDA_TARGET:
                # A CD track is plain PCM: it has no SCSP voice or sample
                # budget, so it is rendered by build_cdda.py rather than baked
                # against the player limits here.
                path = publish_song(self.source, song, target, entry['sequence'], name,
                                    soundfont=overrides.get('soundfont'))
                return ('installed', path, song + ' audio and CD mapping')
            built = self.build(entry['sequence'], overrides)
            if target in GAME_TARGETS:
                path = publish_song(self.source, song, target, entry['sequence'],
                                    built=built, preserve_intro=preserve_intro)
                return ('installed', path, song + ' audio and BANK mapping')
            return bake(self.source, entry['sequence'], name,
                        preserve_intro=preserve_intro, built=built)
        self.task(action, 'Baking the Saturn bank...')

    def check_all(self):
        if not messagebox.askokcancel(
                'Check all', 'Interpret and bake all %d sequences to see which '
                'ones this player supports. Takes a few minutes and writes '
                'nothing.' % len(self.entries), parent=self.root):
            return

        def action():
            rows = survey(self.source, list(self.entries.values()))
            playable = sum(1 for r in rows if r['bakes'])
            return ('checked', rows, '%d of %d sequences bake with the current '
                    'player.' % (playable, len(rows)))
        self.task(action, 'Checking every sequence...')

    def open_workspace(self):
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        os.startfile(WORKSPACE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--bake', nargs=2, metavar=('NAME', 'SEQUENCE'),
                        help='Bake one sequence without opening the GUI')
    parser.add_argument('--survey', action='store_true',
                        help='Report which sequences this player can bake')
    args = parser.parse_args()
    if args.bake:
        source, error = find_source()
        if source is None:
            raise ValueError(error)
        sequence = int(args.bake[1])
        built, reason = probe(source, sequence)
        if built is None:
            raise SystemExit(reason)
        print(bake(source, sequence, args.bake[0], built=built))
        return
    if args.survey:
        source, error = find_source()
        if source is None:
            raise ValueError(error)
        rows = survey(source)
        for row in rows:
            print('%3d  %-28s %s' % (row['sequence'], row['name'],
                                     '%.0f s' % row['seconds'] if row['bakes']
                                     else row['reason']))
        print('%d of %d bake.' % (sum(r['bakes'] for r in rows), len(rows)))
        return
    root = tk.Tk()
    if args.smoke_test:
        root.withdraw()
    app = Workshop(root)
    if args.smoke_test:
        root.update()
        assert app.tree.get_children(), 'No sequences listed'
        root.destroy()
        print('Music workshop GUI smoke test passed; no assets written.')
    else:
        root.mainloop()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # pythonw has no console: failures must be visible instead of vanishing.
        messagebox.showerror('Music workshop could not start', str(exc))
        raise
