"""Offline, searchable user guide. Opening help never loads or bakes audio."""
from pathlib import Path
import re
import tkinter as tk
from tkinter import ttk

GUIDE_PATH = Path(__file__).with_name('USER_GUIDE.md')


class UserGuide(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Music workshop - User guide')
        self.geometry('980x720')
        self.minsize(680, 440)
        self.search_from = '1.0'
        self.query = tk.StringVar()
        self.notice = tk.StringVar(value='Choose a topic, or search. Ctrl+F focuses search; Esc closes help.')
        bar = ttk.Frame(self, padding=10)
        bar.pack(fill='x')
        ttk.Label(bar, text='Find').pack(side='left', padx=(0, 6))
        self.find_entry = ttk.Entry(bar, textvariable=self.query)
        self.find_entry.pack(side='left', fill='x', expand=True)
        self.find_entry.bind('<Return>', self.find_next)
        self.query.trace_add('write', lambda *_: self.reset_search())
        ttk.Button(bar, text='Find next', command=self.find_next).pack(side='left', padx=6)
        ttk.Button(bar, text='Copy guide', command=self.copy_guide).pack(side='left')
        panes = ttk.Panedwindow(self, orient='horizontal')
        panes.pack(fill='both', expand=True, padx=10)
        topics = ttk.Frame(panes)
        content = ttk.Frame(panes)
        panes.add(topics, weight=1)
        panes.add(content, weight=4)
        self.topics = tk.Listbox(topics, width=26, exportselection=False,
                                 activestyle='dotbox')
        topic_scroll = ttk.Scrollbar(topics, command=self.topics.yview)
        self.topics.configure(yscrollcommand=topic_scroll.set)
        topic_scroll.pack(side='right', fill='y')
        self.topics.pack(fill='both', expand=True)
        self.text = tk.Text(content, wrap='word', padx=16, pady=12,
                            font=('Segoe UI', 10), spacing3=5, undo=False)
        scroll = ttk.Scrollbar(content, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.text.pack(fill='both', expand=True)
        self.text.tag_configure('heading', font=('Segoe UI', 13, 'bold'), spacing1=14)
        self.text.tag_configure('title', font=('Segoe UI', 17, 'bold'), spacing1=8)
        self.text.tag_configure('match', background='#ffe58a', foreground='#111111')
        self.marks = []
        try:
            self.guide = GUIDE_PATH.read_text(encoding='utf-8')
        except OSError as exc:
            self.guide = '# Guide unavailable\n\nRestore USER_GUIDE.md beside music_workshop.py.\n\n' + str(exc)
        for line in self.guide.splitlines():
            heading = re.match(r'^(#{1,2}) (.+)$', line)
            if heading:
                start = self.text.index('end-1c')
                self.text.insert('end', heading[2] + '\n',
                                 'title' if len(heading[1]) == 1 else 'heading')
                self.topics.insert('end', heading[2])
                self.marks.append(start)
            else:
                self.text.insert('end', line + '\n')
        self.text.configure(state='disabled')
        self.topics.bind('<<ListboxSelect>>', self.select_topic)
        ttk.Label(self, textvariable=self.notice, wraplength=900,
                  padding=10).pack(fill='x')
        self.bind('<Control-f>', self.focus_search)
        self.bind('<Escape>', lambda _: self.destroy())

    def select_topic(self, _event=None):
        selected = self.topics.curselection()
        if selected:
            self.text.yview(self.marks[selected[0]])

    def focus_search(self, _event=None):
        self.find_entry.focus_set()
        self.find_entry.selection_range(0, 'end')
        return 'break'

    def reset_search(self):
        self.search_from = '1.0'
        self.text.tag_remove('match', '1.0', 'end')

    def find_next(self, _event=None):
        needle = self.query.get().strip()
        self.text.tag_remove('match', '1.0', 'end')
        if not needle:
            self.notice.set('Type a word or phrase to find.')
            return 'break'
        found = self.text.search(needle, self.search_from, stopindex='end', nocase=True)
        if not found:
            found = self.text.search(needle, '1.0', stopindex=self.search_from, nocase=True)
        if found:
            end = '%s+%dc' % (found, len(needle))
            self.text.tag_add('match', found, end)
            self.text.see(found)
            self.search_from = self.text.index(end)
            self.notice.set('Found: %s. Find next wraps to the beginning.' % needle)
        else:
            self.notice.set('No match: ' + needle)
        return 'break'

    def copy_guide(self):
        self.clipboard_clear()
        self.clipboard_append(self.guide)
        self.notice.set('Guide copied. Paste into a text editor to keep or print it.')
