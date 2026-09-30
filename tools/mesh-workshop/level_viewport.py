"""ROM room inspector and named placement variants with UE-style navigation."""
import json
import copy
import math
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import viewport_scene as scene_data
from viewport_math import Camera, add, mul, sub, dot, bounds, clip_near, project, contains

COLOURS = {'Actor':'#67d8ff','Enemy':'#ff6464','Spawn':'#75ef9c','Transition':'#d5a0ff'}


class RoomViewport(tk.Toplevel):
    def __init__(self, parent, initial='spot04_room_0', autoload=True):
        super().__init__(parent)
        self.title('Dosei Legend - Map Workshop')
        self.document = scene_data.layouts.empty()
        self.layout_name = 'original'
        self.unsaved = False
        self.saved_document = copy.deepcopy(self.document)
        self.undo_stack, self.redo_stack = [], []
        self.reimport_paths = {}
        self.restore_view = None
        self.pending_selection = None
        self.bake_results = queue.Queue()
        self.baking = False
        self.build_process=None
        self.last_workflow_check=0
        self.geometry('1280x800')
        self.minsize(960,620)
        self.camera = Camera()
        self.scene = None
        self.entities = {}
        self.selected = None
        self.results = queue.Queue()
        self.request_id = 0
        self.keys = set()
        self.drag = None
        self.last_mouse = None
        self.dragged = False
        self.pick_faces, self.pick_markers = [], []
        self.dirty = True
        self.game_view = self.immersive = False
        self.last_tick = time.perf_counter()
        self.after_id = None
        self.top = ttk.Frame(self,padding=8)
        self.top.pack(fill='x')
        bar = ttk.Frame(self.top)
        bar.pack(fill='x')
        self.room_choices = {label:(prefix,index,room) for label,prefix,index,room in scene_data.rooms()}
        self.room_name = tk.StringVar(value=next(iter(self.room_choices)))
        for label,(prefix,index,room) in self.room_choices.items():
            if f'{prefix}_room_{room}' == initial: self.room_name.set(label)
        picker = ttk.Combobox(bar,textvariable=self.room_name,values=list(self.room_choices),state='readonly',width=37)
        picker.pack(side='left',padx=(0,8))
        picker.bind('<<ComboboxSelected>>',lambda _:self.load())
        ttk.Button(bar,text='Reload',command=self.reload).pack(side='left')
        ttk.Button(bar,text='Frame room',command=self.frame_room).pack(side='left',padx=6)
        self.mode = tk.StringVar(value='Solid')
        mode = ttk.Combobox(bar,textvariable=self.mode,values=['Solid','Textured','Wireframe'],state='readonly',width=12)
        mode.pack(side='left',padx=6)
        mode.bind('<<ComboboxSelected>>',lambda _:self.redraw())
        self.speed_label = tk.StringVar(value='Speed: 700')
        ttk.Label(bar,textvariable=self.speed_label).pack(side='left',padx=8)
        ttk.Button(bar,text='Controls / Help',command=self.help).pack(side='right')
        actions=ttk.Frame(self.top); actions.pack(fill='x',pady=(5,0))
        ttk.Button(actions,text='Selected object / Materials / Code',command=self.inspect_object).pack(side='left')
        ttk.Button(actions,text='Camera...',command=self.camera_settings).pack(side='left',padx=5)
        ttk.Button(actions,text='Validate room / rebake UV',command=self.check_bake).pack(side='left')

        self.undo_button=ttk.Button(actions,text='Undo',command=self.undo,state='disabled')
        self.undo_button.pack(side='left',padx=3)
        self.redo_button=ttk.Button(actions,text='Redo',command=self.redo,state='disabled')
        self.redo_button.pack(side='left')
        versions = ttk.Frame(self.top)
        versions.pack(fill='x',pady=(6,0))
        ttk.Label(versions,text='Preview layout:').pack(side='left')
        self.layout_var = tk.StringVar(value='original')
        self.layout_picker = ttk.Combobox(versions,textvariable=self.layout_var,state='readonly',width=23)
        self.layout_picker.pack(side='left',padx=5)
        self.layout_picker.bind('<<ComboboxSelected>>',self.switch_layout)
        ttk.Button(versions,text='Reset to original',command=self.reset_original).pack(side='left')
        ttk.Button(versions,text='Save map',command=self.save_layout).pack(side='left',padx=4)
        ttk.Button(versions,text='Save as...',command=lambda:self.save_layout(True)).pack(side='left')
        self.layout_status = tk.StringVar()
        ttk.Label(versions,textvariable=self.layout_status).pack(side='left')
        workflow=ttk.LabelFrame(self.top,text='PREVIEW THIS MAP IN GAME',padding=8)
        workflow.pack(fill='x',pady=(8,4))
        self.build_button=ttk.Button(workflow,text='1. Save + build this map...',command=self.build_clean)
        self.build_button.pack(side='left',padx=(0,8))
        self.play_button=ttk.Button(workflow,text='2. Play in Kronos',command=self.play_map,state='disabled')
        self.play_button.pack(side='left',padx=(0,10))
        self.workflow_status=tk.StringVar()
        ttk.Label(workflow,textvariable=self.workflow_status,wraplength=650).pack(side='left',fill='x',expand=True)
        self.refresh_layouts()
        layer_bar = ttk.Frame(self.top)
        layer_bar.pack(fill='x',pady=(7,0))
        self.layers = {}
        for name in ('Mesh','Actor','Enemy','Collision','Exit','Spawn','Transition','Labels'):
            var = tk.BooleanVar(value=name not in ('Collision','Labels'))
            self.layers[name] = var
            ttk.Checkbutton(layer_bar,text=name,variable=var,command=self.redraw).pack(side='left',padx=3)
        self.notice = tk.StringVar(value='Choose a room. Preview never writes assets.')
        ttk.Label(self.top,textvariable=self.notice,wraplength=1180).pack(anchor='w',pady=(5,0))
        self.panes = ttk.Panedwindow(self,orient='horizontal')
        self.panes.pack(fill='both',expand=True,padx=8)
        self.canvas = tk.Canvas(self.panes,background='#20262d',highlightthickness=0,takefocus=True)
        self.panes.add(self.canvas,weight=4)
        self.sidebar = ttk.Frame(self.panes,width=310)
        self.panes.add(self.sidebar,weight=1)
        ttk.Label(self.sidebar,text='World Outliner',font=('Segoe UI',11,'bold')).pack(anchor='w',padx=8,pady=6)
        self.search = tk.StringVar()
        entry = ttk.Entry(self.sidebar,textvariable=self.search)
        entry.pack(fill='x',padx=8)
        self.search.trace_add('write',lambda *_:self.fill_outliner())
        tree_frame = ttk.Frame(self.sidebar)
        tree_frame.pack(fill='both',expand=True,padx=8,pady=6)
        self.outliner = ttk.Treeview(tree_frame,columns=('kind',),show='tree headings',height=12,selectmode='browse')
        self.outliner.heading('#0',text='Object / original actor')
        self.outliner.heading('kind',text='Type')
        self.outliner.column('#0',width=200)
        self.outliner.column('kind',width=80)
        scroll = ttk.Scrollbar(tree_frame,command=self.outliner.yview)
        self.outliner.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y')
        self.outliner.pack(fill='both',expand=True)
        self.outliner.bind('<<TreeviewSelect>>',self.outliner_select)
        self.outliner.bind('<Double-1>',lambda _:self.frame_selection())
        self.outliner.bind('<KeyPress-f>',lambda _:self.frame_selection())
        self.outliner.bind('<Button-3>',self.outliner_menu)
        self.outliner.bind('<F2>',lambda _:self.rename_selected())
        self.mesh_menu=tk.Menu(self,tearoff=False)
        edit = ttk.LabelFrame(self.sidebar,text='Placement: grass / sign / chest',padding=5)
        edit.pack(fill='x',padx=8,pady=4)
        self.fields = {}
        self.field_entries = {}
        for column,name in enumerate(('X','Y','Z','Yaw')):
            ttk.Label(edit,text=name).grid(row=0,column=column)
            var = tk.StringVar()
            field = ttk.Entry(edit,textvariable=var,width=8)
            field.grid(row=1,column=column,padx=2)
            self.field_entries[name] = field
            self.fields[name] = var
        self.apply_button = ttk.Button(edit,text='Apply to draft',command=self.edit_actor,state='disabled')
        self.apply_button.grid(row=2,column=0,columnspan=4,sticky='ew',pady=4)
        ttk.Label(self.sidebar,text='Details - native coordinates',font=('Segoe UI',10,'bold')).pack(anchor='w',padx=8)
        detail_frame = ttk.Frame(self.sidebar)
        detail_frame.pack(fill='both',expand=True,padx=8,pady=6)
        self.details = tk.Text(detail_frame,height=13,width=38,wrap='word',state='disabled')
        detail_scroll = ttk.Scrollbar(detail_frame,command=self.details.yview)
        self.details.configure(yscrollcommand=detail_scroll.set)
        detail_scroll.pack(side='right',fill='y')
        self.details.pack(fill='both',expand=True)
        self.footer = ttk.Frame(self,padding=8)
        self.footer.pack(fill='x')
        ttk.Label(self.footer,text='RMB + WASD/QE fly | RMB look | RMB + wheel speed | Alt+LMB orbit | MMB pan | F frame | G overlays | F11 immersive | Esc release').pack(anchor='w')
        self.stats = tk.StringVar()
        ttk.Label(self.footer,textvariable=self.stats).pack(anchor='w')
        for button,drag in ((1,'navigate'),(2,'pan'),(3,'look')):
            self.canvas.bind(f'<ButtonPress-{button}>',lambda event,d=drag:self.mouse_down(event,d))
            self.canvas.bind(f'<ButtonRelease-{button}>',self.mouse_up)
        self.canvas.bind('<Alt-ButtonPress-1>',lambda e:self.mouse_down(e,'orbit'))
        self.canvas.bind('<Alt-ButtonPress-3>',lambda e:self.mouse_down(e,'dolly'))
        self.canvas.bind('<Motion>',self.mouse_move)
        self.canvas.bind('<MouseWheel>',self.wheel)
        self.canvas.bind('<Button-4>',lambda e:self.wheel(e,1))
        self.canvas.bind('<Button-5>',lambda e:self.wheel(e,-1))
        self.canvas.bind('<KeyPress>',self.key_down)
        self.canvas.bind('<KeyRelease>',lambda e:self.keys.discard(e.keysym.lower()))
        self.canvas.bind('<FocusOut>',lambda _:self.release_input())
        self.canvas.bind('<Configure>',lambda _:self.redraw())
        self.bind('<Unmap>',lambda _:self.release_input())
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.bind('<F1>',lambda _:self.help())
        for widget in (self,self.canvas):
            widget.bind('<Control-z>',lambda _:self.undo())
            widget.bind('<Control-y>',lambda _:self.redo())
            widget.bind('<Control-Shift-Z>',lambda _:self.redo())
        self.after_id = self.after(16,self.tick)
        if autoload: self.load()

    def redraw(self): self.dirty = True

    def history_state(self):
        return (copy.deepcopy(self.document),self.room_name.get(),self.selected or self.pending_selection)

    def history_buttons(self):
        self.undo_button.configure(state='normal' if self.undo_stack else 'disabled')
        self.redo_button.configure(state='normal' if self.redo_stack else 'disabled')

    def apply_document(self,document):
        if self.document is None or self.layout_name=='original':
            raise ValueError('Save as a named alternate before editing. Original is read-only.')
        scene_data.layouts.validate(document)
        if document==self.document: return
        self.undo_stack.append(self.history_state())
        self.redo_stack.clear()
        self.document=copy.deepcopy(document)
        self.unsaved=self.document!=self.saved_document
        self.history_buttons(); self.refresh_layouts()

    def restore_history(self,source,destination):
        if not source: return 'break'
        destination.append(self.history_state())
        document,room,selected=source.pop()
        same_room=room==self.room_name.get()
        self.document=document
        self.room_name.set(room)
        self.selected=selected
        self.unsaved=document!=self.saved_document
        self.history_buttons(); self.refresh_layouts()
        self.load(preserve=same_room,selection_after_load=selected)
        return 'break'

    def undo(self): return self.restore_history(self.undo_stack,self.redo_stack)
    def redo(self): return self.restore_history(self.redo_stack,self.undo_stack)

    def outliner_menu(self,event):
        row=self.outliner.identify_row(event.y)
        if not row or self.entities[row]['kind']!='Mesh': return
        self.outliner.focus(row)
        self.select(row)
        source=bool(self.entities[row].get('details',{}).get('mesh_key'))
        editable=source and self.document is not None and self.layout_name!='original'
        self.mesh_menu.delete(0,'end')
        self.mesh_menu.add_command(label='Export mesh (OBJ / MTL / textures)...',
            state='normal' if source else 'disabled',command=lambda:self.mesh_exchange('export'))
        self.mesh_menu.add_command(label='Import / replace this mesh...',
            state='normal' if editable else 'disabled',command=lambda:self.mesh_exchange('replace'))
        self.mesh_menu.add_command(label='Rename... (F2)',state='normal' if editable else 'disabled',command=self.rename_selected)
        self.mesh_menu.add_command(label='Re-import last OBJ',
            state='normal' if editable else 'disabled',command=lambda:self.mesh_exchange('reimport'))
        if self.layout_name=='original':
            self.mesh_menu.add_separator()
            self.mesh_menu.add_command(label='Save as alternate to enable editing...',command=lambda:self.save_layout(True))
        self.mesh_menu.add_separator()
        self.mesh_menu.add_command(label='Frame mesh',command=self.frame_selection)
        try: self.mesh_menu.tk_popup(event.x_root,event.y_root)
        finally: self.mesh_menu.grab_release()
        return 'break'

    def rename_selected(self):
        entity=self.entities.get(self.selected)
        if not entity or entity['kind'] not in ('Mesh','Actor','Enemy') or self.document is None or self.layout_name=='original':
            return 'break'
        name=simpledialog.askstring('Rename Outliner object','Display name (blank restores source name):',initialvalue=entity['label'],parent=self)
        if name is None: return 'break'
        document=copy.deepcopy(self.document)
        labels=document.setdefault('labels',{})
        if name.strip(): labels[entity['id']]=name.strip()
        else: labels.pop(entity['id'],None)
        if not labels: document.pop('labels',None)
        try: self.apply_document(document)
        except ValueError as exc:
            messagebox.showerror('Object name',str(exc),parent=self)
            return 'break'
        self.load(preserve=True)
        return 'break'

    def mesh_exchange(self,action):
        from map_inspector import ObjectInspector
        if self.selected not in self.entities: return
        inspector=ObjectInspector(self,show=False)
        try: inspector.run(getattr(inspector,action))
        finally:
            if inspector.winfo_exists(): inspector.destroy()

    def inspect_object(self):
        if self.selected not in self.entities:
            messagebox.showinfo('Map Workshop','Select an object in the viewport or Outliner first.',parent=self)
            return
        from map_inspector import ObjectInspector
        ObjectInspector(self)

    def camera_settings(self):
        from map_inspector import camera_dialog
        camera_dialog(self)

    def update_workflow(self):
        import map_build_status
        running=self.build_process is not None and self.build_process.poll() is None
        ready=not self.unsaved and map_build_status.matches(scene_data.PROJECT,
            None if self.document is None else self.layout_name,self.document)
        self.build_button.configure(state='disabled' if running else 'normal')
        self.play_button.configure(state='normal' if ready and not running else 'disabled')
        if running: text='Build window: leave Clean selected, click Build, then close window when finished.'
        elif self.unsaved: text='Edits visible here only. Step 1 saves them and builds the game image.'
        elif ready: text='This saved map is in the last successful Clean image. Step 2 opens it in Kronos.'
        else: text='Game image not yet verified for this map. Close Kronos, then use Step 1.'
        self.workflow_status.set(text)

    def build_clean(self):
        import subprocess
        if self.build_process is not None and self.build_process.poll() is None: return
        if not self.choose_build(): return
        try:
            self.build_process=subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
                str(scene_data.ROOT/'tools/map-workshop/open-build.ps1')],creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as exc: messagebox.showerror('Could not open build window',str(exc),parent=self)
        self.update_workflow()

    def play_map(self):
        import subprocess
        import map_build_status
        if self.unsaved or not map_build_status.matches(scene_data.PROJECT,None if self.document is None else self.layout_name,self.document):
            self.update_workflow()
            return
        try:
            subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
                str(scene_data.ROOT/'tools/launcher/kronos-launcher.ps1'),'-Variant','clean'],creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as exc: messagebox.showerror('Could not start Kronos',str(exc),parent=self)

    def check_bake(self):
        if self.baking or self.document is None or not self.scene: return
        document=copy.deepcopy(self.document); prefix,room=self.scene['prefix'],self.scene['room']
        self.baking=True; self.notice.set('Validating '+prefix+f' room {room}: production UV bake and memory budgets...')
        def work():
            try:
                paths=scene_data.project_config.read_paths(scene_data.ROOT)
                result=scene_data.map_meshes.check_room(document,prefix,room,paths['oot_decomp'],paths['oot_roms'])
                self.bake_results.put((True,prefix,room,result['budget']))
            except Exception as exc: self.bake_results.put((False,prefix,room,str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def refresh_layouts(self):
        self.layout_picker.configure(values=['original',*scene_data.layouts.names(),'Current baked'])
        try: chosen = scene_data.layouts.selection() or 'legacy meshes'
        except (ValueError,OSError) as exc: chosen = 'invalid: '+str(exc)
        self.layout_status.set(('Unsaved draft | ' if self.unsaved else '')+'Build source: '+chosen)
        self.update_workflow()

    def save_layout(self, save_as=False):
        if self.document is None: return False
        name = self.layout_name
        if save_as or name=='original':
            name = simpledialog.askstring('Save alternate layout','Alternate name (lowercase letters, numbers, hyphens):',parent=self)
            if name is None: return False
        try: scene_data.layouts.save(name,self.document)
        except (ValueError,OSError) as exc:
            messagebox.showerror('Layout not saved',str(exc),parent=self)
            return False
        self.layout_name = name
        self.layout_var.set(name)
        self.unsaved = False
        self.saved_document=copy.deepcopy(self.document)
        self.refresh_layouts()
        self.show_details(self.entities.get(self.selected))
        return True

    def keep_draft(self):
        if not self.unsaved: return True
        answer = messagebox.askyesnocancel('Unsaved layout','Save your draft before leaving it?',parent=self)
        if answer is None: return False
        return self.save_layout() if answer else True

    def reset_original(self):
        self.layout_var.set('original')
        self.switch_layout()

    def switch_layout(self, _event=None):
        name = self.layout_var.get()
        if not self.keep_draft():
            self.layout_var.set(self.layout_name)
            return
        try: document = None if name=='Current baked' else scene_data.layouts.load(name)
        except (ValueError,OSError) as exc:
            self.layout_var.set(self.layout_name)
            messagebox.showerror('Layout not loaded',str(exc),parent=self)
            return
        self.layout_name, self.document, self.unsaved = name,document,False
        self.saved_document=copy.deepcopy(document)
        self.undo_stack.clear(); self.redo_stack.clear(); self.history_buttons()
        self.layout_var.set(name)
        self.refresh_layouts()
        self.load()

    def choose_build(self):
        if self.document is None:
            try: scene_data.layouts.choose(None)
            except (ValueError,OSError) as exc:
                messagebox.showerror('Build selection not saved',str(exc),parent=self)
                return False
            self.refresh_layouts()
            self.notice.set('Next Clean build uses published Workshop meshes and original actor placements; current disc unchanged.')
            return True
        if self.unsaved and not self.save_layout(): return False
        try: scene_data.layouts.choose(self.layout_name)
        except (ValueError,OSError) as exc:
            messagebox.showerror('Build selection not saved',str(exc),parent=self)
            return False
        self.refresh_layouts()
        self.notice.set('Next Clean build uses '+self.layout_name+'. Selection saved; existing disc is unchanged.')
        return True

    def edit_actor(self):
        e = self.entities.get(self.selected)
        if self.document is None or self.layout_name=='original' or not e or not e.get('details',{}).get('editable'): return
        try:
            values = [int(self.fields[k].get()) for k in ('X','Y','Z','Yaw')]
            if e['details']['actor_id']==0x125: values[3] = e['details']['rotation'][1]
            candidate = copy.deepcopy(self.document)
            key = f"{self.scene['prefix']}_room_{self.scene['room']}"
            record = candidate['rooms'].setdefault(key,dict(sha256=self.scene['source_sha256'],actors={}))
            record['actors'][e['id'].rsplit('/',1)[1]] = dict(actor_id=e['details']['actor_id'],position=values[:3],yaw=values[3])
            scene_data.layouts.validate(candidate)
        except ValueError as exc:
            messagebox.showerror('Invalid placement',str(exc),parent=self)
            return
        self.apply_document(candidate)
        e['position'] = tuple(values[:3])
        e['details']['position'] = e['position']
        rotation = list(e['details']['rotation']); rotation[1] = values[3]
        e['details']['rotation'] = rotation
        self.show_details(e)
        self.refresh_layouts()
        self.redraw()

    def reload(self):
        scene_data.segments.cache_clear()
        scene_data.category.cache_clear()
        self.load()

    def load(self,preserve=False,selection_after_load=None):
        self.pending_selection=selection_after_load or (self.selected if preserve else None)
        self.restore_view=(copy.deepcopy(self.camera),self.selected) if preserve else None
        self.release_input()
        self.request_id += 1
        request = self.request_id
        args = self.room_choices[self.room_name.get()]
        document = copy.deepcopy(self.document)
        self.scene, self.entities, self.selected = None, {}, None
        self.fill_outliner()
        self.show_details(None)
        self.redraw()
        self.notice.set('Loading baked geometry and verified ROM metadata...')
        def work():
            try: self.results.put((request,scene_data.load_room(*args,document=document),None))
            except Exception as exc: self.results.put((request,None,str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def set_scene(self, scene):
        self.scene = scene
        self.entities = {e['id']:e for e in scene['entities']}
        self.selected = None
        self.search.set('')
        self.fill_outliner()
        self.show_details(None)
        if not any(f['layer']=='Mesh' for f in scene['faces']): self.layers['Collision'].set(True)
        self.notice.set(' | '.join(scene['warnings']) or
            ('Current baked mesh' if self.document is None else 'Original ROM geometry + '+self.layout_name+' placements')+
            '. Main header only; whole-scene collision/exits/spawns. Palette-average host preview.')
        self.frame_room()
        if self.restore_view:
            self.camera,selected=self.restore_view
            self.restore_view=None
            self.select(selected if selected in self.entities else None)
        if self.pending_selection in self.entities: self.select(self.pending_selection)
        self.pending_selection=None

    def fill_outliner(self):
        self.outliner.delete(*self.outliner.get_children())
        words = self.search.get().casefold().split()
        for e in self.entities.values():
            text = (e['label']+' '+e['kind']+' '+json.dumps(e.get('details',{}))).casefold()
            if all(w in text for w in words): self.outliner.insert('', 'end',iid=e['id'],text=e['label'],values=(e['kind'],))
        if self.selected and self.outliner.exists(self.selected): self.outliner.selection_set(self.selected)

    def outliner_select(self, _event=None):
        ids = self.outliner.selection()
        if ids: self.select(ids[0],from_tree=True)

    def select(self, eid, from_tree=False):
        self.selected = eid
        e = self.entities.get(eid)
        if e:
            self.layers[e['kind']].set(True)
            if 'position' in e: self.camera.pivot = e['position']
            elif 'bounds' in e: self.camera.pivot = mul(add(*e['bounds']),.5)
        if not from_tree and e and self.outliner.exists(eid):
            self.outliner.selection_set(eid)
            self.outliner.see(eid)
        self.show_details(e)
        self.redraw()

    def show_details(self, e):
        editable = self.document is not None and self.layout_name!='original' and e and e.get('details',{}).get('editable')
        self.apply_button.configure(state='normal' if editable else 'disabled')
        values = [*e['position'],e['details']['rotation'][1]] if editable else ['']*4
        for key,value in zip(('X','Y','Z','Yaw'),values): self.fields[key].set(value)
        for key,field in self.field_entries.items():
            field.configure(state='normal' if editable and (key!='Yaw' or e['details']['actor_id']!=0x125) else 'disabled')
        self.details.configure(state='normal')
        self.details.delete('1.0','end')
        self.details.insert('1.0',json.dumps(e,indent=2) if e else 'Select an object. Forest grass, signs and chests support XYZ/yaw edits. Save a named alternate, then Use for next build. Original ROM is never overwritten.')
        self.details.configure(state='disabled')

    def frame_room(self):
        if self.scene:
            self.camera.frame(self.scene['bounds'],max(1,self.canvas.winfo_width())/max(1,self.canvas.winfo_height()))
            self.redraw()

    def frame_selection(self):
        e = self.entities.get(self.selected)
        if not e: return self.frame_room()
        box = e.get('bounds')
        if box is None and 'position' in e:
            box = (sub(e['position'],(70,70,70)),add(e['position'],(70,70,70)))
        if box:
            self.camera.frame(box,max(1,self.canvas.winfo_width())/max(1,self.canvas.winfo_height()))
            self.redraw()

    def mouse_down(self, event, drag):
        self.canvas.focus_set()
        self.drag, self.last_mouse, self.dragged = drag,(event.x,event.y),False
        self.anchor = (event.x,event.y)
        self.canvas.grab_set()
        if drag=='look': self.canvas.configure(cursor='none')
        return 'break'

    def mouse_move(self, event):
        if not self.drag or self.last_mouse is None: return
        dx,dy = event.x-self.last_mouse[0],event.y-self.last_mouse[1]
        if not dx and not dy: return
        self.last_mouse = (event.x,event.y)
        if abs(event.x-self.anchor[0])+abs(event.y-self.anchor[1])>3: self.dragged=True
        if self.drag in ('look','orbit'): self.camera.look(dx,dy,self.drag=='orbit')
        elif self.drag=='pan': self.camera.pan(dx,dy)
        elif self.drag=='dolly': self.camera.dolly(-dy*self.camera.speed*.01)
        elif self.drag=='navigate':
            self.camera.look(dx,0)
            f = self.camera.basis()[0]
            flat = (f[0],0,f[2])
            length = math.sqrt(dot(flat,flat))
            if length: self.camera.position = add(self.camera.position,mul(flat,-dy*self.camera.speed*.005/length))
        self.redraw()
        if self.drag=='look':
            center = (self.canvas.winfo_width()//2,self.canvas.winfo_height()//2)
            self.last_mouse = center
            self.canvas.event_generate('<Motion>',warp=True,x=center[0],y=center[1])

    def mouse_up(self, event):
        picking = self.drag=='navigate' and not self.dragged
        self.release_input()
        if picking: self.pick(event.x,event.y)
        return 'break'

    def release_input(self):
        if self.drag: self.redraw()
        self.drag = self.last_mouse = None
        self.keys.clear()
        try:
            if self.canvas.grab_current()==self.canvas: self.canvas.grab_release()
            self.canvas.configure(cursor='')
        except tk.TclError: pass

    def wheel(self, event, steps=None):
        steps = steps if steps is not None else event.delta/120
        if self.drag=='look':
            self.camera.speed = max(20,min(20000,self.camera.speed*1.25**steps))
            self.speed_label.set(f'Speed: {self.camera.speed:.0f}')
        else: self.camera.dolly(steps*self.camera.speed*.2)
        self.redraw()
        return 'break'

    def key_down(self, event):
        key = event.keysym.lower()
        if key in ('w','a','s','d','q','e'):
            if self.drag=='look': self.keys.add(key)
        elif key=='f': self.frame_selection()
        elif key=='f1': self.help()
        elif key=='g': self.game_view=not self.game_view; self.redraw()
        elif key=='f11': self.toggle_immersive()
        elif key=='escape':
            self.release_input()
            if self.immersive: self.toggle_immersive()
        return 'break'

    def toggle_immersive(self):
        self.immersive = not self.immersive
        if self.immersive: self.panes.forget(self.sidebar)
        else: self.panes.add(self.sidebar,weight=1)
        self.attributes('-fullscreen',self.immersive)
        self.redraw()

    def pick(self, x, y):
        for px,py,eid in reversed(self.pick_markers):
            if (px-x)**2+(py-y)**2<=100: return self.select(eid)
        for poly,eid in reversed(self.pick_faces):
            if contains(poly,x,y): return self.select(eid)
        self.select(None)

    def visible(self, layer):
        return self.layers[layer].get() and (not self.game_view or layer=='Mesh')

    def render(self):
        start = time.perf_counter()
        width,height = self.canvas.winfo_width(),self.canvas.winfo_height()
        if width<2 or height<2: return
        self.canvas.delete('all')
        self.pick_faces,self.pick_markers = [],[]
        if not self.scene:
            self.canvas.create_text(width/2,height/2,text=self.notice.get(),fill='#d9e0e8',width=max(200,width-40))
            return
        f,r,u = self.camera.basis()
        eye = self.camera.position
        def view(p):
            d = sub(p,eye)
            return dot(d,r),dot(d,u),dot(d,f)
        queue_faces = []
        for face in self.scene['faces']:
            if not self.visible(face['layer']): continue
            points = clip_near([view(p) for p in face['points']])
            face['_near_clipped']=any(view(p)[2]<5 for p in face['points'])
            if len(points)<3: continue
            screen = [project(p,width,height) for p in points]
            if max(p[0] for p in screen)<0 or min(p[0] for p in screen)>width or max(p[1] for p in screen)<0 or min(p[1] for p in screen)>height: continue
            queue_faces.append((sum(p[2] for p in points)/len(points),screen,face))
        ordered=sorted(queue_faces,key=lambda v:v[0],reverse=True)
        textured=self.mode.get()=='Textured' and not self.drag and not self.keys
        if textured:
            from PIL import ImageTk
            from map_render import textured_frame
            self.texture_frame=ImageTk.PhotoImage(textured_frame(ordered,width,height))
            self.canvas.create_image(0,0,image=self.texture_frame,anchor='nw')
        for _,poly,face in ordered:
            selected = face['entity']==self.selected and not self.game_view
            colour = '#%02x%02x%02x' % tuple(max(30,min(230,int(c))) for c in face['colour'])
            wire = self.mode.get()=='Wireframe' or face['layer']=='Collision'
            outline = '#ffe077' if selected else colour if wire or face['layer']=='Exit' else ''
            if not textured or face['layer']!='Mesh' or selected:
                self.canvas.create_polygon(*[c for p in poly for c in p],fill='' if wire or (textured and face['layer']=='Mesh') else colour,
                                           outline=outline,width=2 if selected else 1)
            self.pick_faces.append((poly,face['entity']))
        markers = []
        for e in self.entities.values():
            if 'position' not in e or not self.visible(e['kind']): continue
            p = view(e['position'])
            if p[2]<5: continue
            x,y = project(p,width,height)
            if -10<x<width+10 and -10<y<height+10: markers.append((p[2],x,y,e))
        for _,x,y,e in sorted(markers,key=lambda v:v[0],reverse=True):
            selected = e['id']==self.selected
            colour = COLOURS.get(e['kind'],'#ffbd59')
            self.canvas.create_oval(x-6,y-6,x+6,y+6,fill=colour,outline='#fff0a0' if selected else '#111111',width=3 if selected else 1)
            if selected or self.layers['Labels'].get():
                self.canvas.create_text(x+10,y-9,text=e['label'],anchor='w',fill=colour,font=('Segoe UI',9,'bold'))
            self.pick_markers.append((x,y,e['id']))
        if not self.game_view:
            for axis,label,colour in (((1,0,0),'X','#fa7777'),((0,1,0),'Y','#70e695'),((0,0,1),'Z','#80b7ff')):
                x,y = 48+dot(axis,r)*30,height-48-dot(axis,u)*30
                self.canvas.create_line(48,height-48,x,y,fill=colour,width=2)
                self.canvas.create_text(x,y,text=label,fill=colour,anchor='s')
        elapsed = (time.perf_counter()-start)*1000
        pos = ', '.join(f'{n:.0f}' for n in self.camera.position)
        self.stats.set(f'{len(queue_faces)} faces | {len(markers)} markers (through walls) | Camera XYZ: {pos} | Draw {elapsed:.0f} ms | Host preview')

    def tick(self):
        now = time.perf_counter()
        if now-self.last_workflow_check>1:
            self.last_workflow_check=now
            self.update_workflow()
        seconds = min(.05,now-self.last_tick)
        self.last_tick = now
        try:
            while True:
                request,scene,error = self.results.get_nowait()
                if request!=self.request_id: continue
                if error:
                    self.notice.set('Room load failed: '+error)
                    self.redraw()
                else: self.set_scene(scene)
        except queue.Empty: pass
        try:
            success,prefix,room,result=self.bake_results.get_nowait()
            self.baking=False
            text=f'{prefix} room {room}: '+('UV bake/budgets passed (draft snapshot).' if success else 'Bake failed: '+str(result))
            self.notice.set(text)
            messagebox.showinfo('Room bake validation',text+'\n'+(json.dumps(result,indent=2) if success else ''),parent=self)
        except queue.Empty: pass
        if self.drag=='look' and self.keys:
            self.camera.fly(self.keys,seconds)
            self.redraw()
        if self.dirty:
            self.dirty = False
            self.render()
        self.after_id = self.after(16,self.tick)

    def help(self):
        window=tk.Toplevel(self); window.title('Map Workshop guide'); window.geometry('850x650')
        text=tk.Text(window,wrap='word',padx=14,pady=14)
        scroll=ttk.Scrollbar(window,command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y'); text.pack(fill='both',expand=True)
        text.insert('1.0',(scene_data.ROOT/'tools/map-workshop/README.md').read_text(encoding='utf-8'))
        text.configure(state='disabled')
        window.bind('<Escape>',lambda _:window.destroy())

    def close(self):
        if not self.keep_draft(): return
        self.request_id += 1
        self.release_input()
        if self.after_id: self.after_cancel(self.after_id)
        self.destroy()
