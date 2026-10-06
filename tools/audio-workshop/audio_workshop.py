"""Windows audio workshop. Play any US 1.2 SFX or sequence. No export."""
import argparse
import queue
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk
import winsound

import audio_assets as audio


class Workshop:
    def __init__(self, root):
        self.root = root
        root.title('Dosei Legend - Audio workshop')
        root.geometry('860x640')
        root.minsize(720, 480)
        self.results = queue.Queue()
        self.play_token = 0
        self.rows = []
        self.error = None
        try:
            self.oot = audio.decomp_root()
            self.source = audio.audio_source()
            self.seq = (self.oot / 'assets/audio/sequences/seq_0.prg.seq').read_text()
            self.cache = audio.SampleCache(self.source)
            self.rows = audio.catalog(self.oot)
        except Exception as exc:
            self.error = str(exc)

        outer = ttk.Frame(root, padding=16)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Audio workshop',
                  font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='Play SFX or music from the US 1.2 extraction. '
                  'Search by name. No export.').pack(anchor='w', pady=(3, 10))

        bar = ttk.Frame(outer)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text='Search').pack(side='left', padx=(0, 6))
        self.query = tk.StringVar()
        self.query.trace_add('write', lambda *_: self.refresh())
        ttk.Entry(bar, textvariable=self.query).pack(side='left', fill='x', expand=True)
        ttk.Label(bar, text='Type').pack(side='left', padx=(12, 6))
        self.kind = tk.StringVar(value='All')
        kinds = ['All'] + list(audio.TYPE_ORDER)
        box = ttk.Combobox(bar, textvariable=self.kind, values=kinds,
                           state='readonly', width=14)
        box.pack(side='left')
        box.bind('<<ComboboxSelected>>', lambda _: self.refresh())

        listing = ttk.Frame(outer)
        listing.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(listing, columns=('type', 'name', 'id'),
                                 show='headings')
        self.tree.heading('type', text='Type')
        self.tree.heading('name', text='Name')
        self.tree.heading('id', text='Id')
        self.tree.column('type', width=120, minwidth=80)
        self.tree.column('name', width=520, minwidth=200)
        self.tree.column('id', width=90, minwidth=60)
        scroll = ttk.Scrollbar(listing, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.tree.bind('<Double-1>', lambda _: self.play())

        buttons = ttk.Frame(outer)
        buttons.pack(fill='x', pady=8)
        ttk.Button(buttons, text='Play', command=self.play).pack(side='left', padx=(0, 8))
        ttk.Button(buttons, text='Stop', command=self.stop).pack(side='left')

        self.status = tk.StringVar(value='Ready.' if self.rows else self.error or 'No audio.')
        ttk.Label(outer, textvariable=self.status, wraplength=800).pack(anchor='w')
        self.refresh()
        root.after(100, self.poll)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def shown(self):
        text = self.query.get().strip().upper()
        kind = self.kind.get()
        for row in self.rows:
            if kind != 'All' and row['kind'] != kind:
                continue
            blob = '%s %s %s' % (row['name'], row['channel'], row['sfx_id'] or row['sequence'])
            if text and text not in blob.upper():
                continue
            yield row

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for index, row in enumerate(self.shown()):
            ident = row['sfx_id'] if row['sfx_id'] is not None else row['sequence']
            label = ('0x%X' % ident) if row['sfx_id'] is not None else 'seq %d' % ident
            self.tree.insert('', 'end', iid=str(index),
                             values=(row['kind'], row['name'], label))
        self.index = list(self.shown())

    def selected(self):
        picked = self.tree.selection()
        if not picked:
            return None
        return self.index[int(picked[0])]

    def play(self):
        row = self.selected()
        if row is None:
            self.status.set('Pick a sound first.')
            return
        self.play_token += 1
        token = self.play_token
        self.status.set('Loading %s...' % row['name'])
        threading.Thread(target=self._render, args=(row, token), daemon=True).start()

    def _render(self, row, token):
        try:
            if row['kind'] == 'Music':
                data = audio.render_music(row['sequence'], self.source)
            else:
                data = audio.render_sfx(row['channel'], self.source, self.seq, self.cache)
            self.results.put((token, row['name'], data, None))
        except Exception as exc:
            self.results.put((token, row['name'], None, str(exc)))

    def poll(self):
        try:
            while True:
                token, name, data, error = self.results.get_nowait()
                if token != self.play_token:
                    continue
                if error:
                    self.status.set('%s: %s' % (name, error))
                    continue
                path = Path(tempfile.gettempdir()) / 'dosei-audio-workshop.wav'
                path.write_bytes(data)
                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                self.status.set('Playing %s. Stop cuts it.' % name)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def stop(self):
        self.play_token += 1
        winsound.PlaySound(None, winsound.SND_PURGE)
        self.status.set('Stopped.')

    def close(self):
        self.stop()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test', action='store_true')
    args = parser.parse_args()
    if args.smoke_test:
        rows = audio.catalog()
        assert any(r['name'] == 'NA_SE_PL_WALK_GROUND' for r in rows)
        assert any(r['kind'] == 'Music' for r in rows)
        print('audio workshop smoke ok', len(rows))
        return
    root = tk.Tk()
    Workshop(root)
    root.mainloop()


if __name__ == '__main__':
    main()
