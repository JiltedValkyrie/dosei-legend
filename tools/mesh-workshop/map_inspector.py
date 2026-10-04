"""Selected-object tools for Map Workshop; source code and material exchange."""
import copy
import json
import math
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

import viewport_scene as scene


def open_code(path):
    path=Path(path).resolve()
    if not path.is_file(): raise ValueError('Source file is missing: '+str(path))
    command=shutil.which('code')
    executable=Path(command).parent.parent/'Code.exe' if command else None
    if executable and executable.is_file():
        subprocess.Popen([str(executable),'--reuse-window',str(path)])
    elif command and os.name!='nt': subprocess.Popen([command,'--reuse-window',str(path)])
    else:
        editor=filedialog.askopenfilename(title='Choose code editor executable',filetypes=[('Editor','*.exe')])
        if editor: subprocess.Popen([editor,str(path)])


# OoT scene prefix -> game/levels folder name.
LEVEL_FOLDERS={'spot04':'kokiri','spot00':'hyrule','ydan':'ydan'}

class ObjectInspector(tk.Toplevel):
    def __init__(self,viewport,show=True):
        super().__init__(viewport)
        if not show: self.withdraw()
        self.viewport=viewport
        self.dialog_parent=self if show else viewport
        self.entity=copy.deepcopy(viewport.entities[viewport.selected])
        self.title('Map Workshop - '+self.entity['label'])
        self.geometry('650x650')
        self.raw=[f['source_face'] for f in viewport.scene['faces']
                  if f['entity']==viewport.selected and 'source_face' in f]
        self.key=self.entity.get('details',{}).get('mesh_key')
        self.editable=bool(self.key and viewport.document is not None and viewport.layout_name!='original')
        self.initial_document=viewport.document
        self.initial_scene=viewport.scene
        self.pivot=tuple((a+b)/2 for a,b in zip(*self.entity['bounds'])) if 'bounds' in self.entity else (0,0,0)
        bar=ttk.Frame(self,padding=8); bar.pack(fill='x')
        for text,action in [('Export named OBJ / textures',self.export),('Replace OBJ...',self.replace),
                            ('Re-import OBJ / UV',self.reimport)]:
            allowed=bool(self.raw) if action==self.export else self.editable
            ttk.Button(bar,text=text,command=lambda a=action:self.run(a),state='normal' if allowed else 'disabled').pack(side='left',padx=3)
        place=ttk.LabelFrame(self,text='Mesh placement (native XYZ; yaw degrees; uniform scale)',padding=8)
        place.pack(fill='x',padx=8)
        entry=viewport.document.get('meshes',{}).get(self.key,{}) if self.editable else {}
        values=[*entry.get('position',self.pivot),entry.get('yaw',0),entry.get('scale',1)]
        self.fields=[]
        for i,(name,value) in enumerate(zip(('X','Y','Z','Yaw','Scale'),values)):
            ttk.Label(place,text=name).grid(row=0,column=i)
            var=tk.StringVar(value=str(value)); self.fields.append(var)
            ttk.Entry(place,textvariable=var,width=10,state='normal' if self.editable else 'disabled').grid(row=1,column=i,padx=3)
        ttk.Button(place,text='Apply placement',command=lambda:self.run(self.place),state='normal' if self.editable else 'disabled').grid(row=2,column=0,columnspan=3,sticky='ew')
        ttk.Button(place,text='Restore original object',command=lambda:self.run(self.restore),state='normal' if self.editable else 'disabled').grid(row=2,column=3,columnspan=2)
        lod=ttk.LabelFrame(self,text='LOD: LOD0 = imported close-up OBJ, LOD1 = original geometry (distances from Link, native units)',padding=8)
        lod.pack(fill='x',padx=8,pady=(4,0))
        current=self.lod_entry()
        self.lod_fields={}
        for i,(name,key) in enumerate((('LOD0 distance','lod0_distance'),('Cull distance','cull_distance'))):
            ttk.Label(lod,text=name).grid(row=0,column=i)
            var=tk.StringVar(value=str(current[key])); self.lod_fields[key]=var
            ttk.Entry(lod,textvariable=var,width=10,state='normal' if self.editable else 'disabled').grid(row=1,column=i,padx=3)
        state='normal' if self.editable else 'disabled'
        ttk.Button(lod,text='Apply LOD distances',command=lambda:self.run(self.apply_lod),state=state).grid(row=1,column=2,padx=3)
        ttk.Button(lod,text='Add/Import LOD0...',command=lambda:self.run(self.import_lod0),state=state).grid(row=2,column=0,columnspan=2,sticky='ew',pady=3)
        ttk.Button(lod,text='Remove LOD0 (use original geometry)',command=lambda:self.run(self.remove_lod0),
                   state=state if current['bundle'] else 'disabled').grid(row=2,column=2,columnspan=2,sticky='ew',pady=3)
        ttk.Label(lod,text='LOD0: '+('imported '+current['bundle'][:12] if current['bundle'] else 'none (original draws near too)')).grid(row=3,column=0,columnspan=4,sticky='w')
        ttk.Label(self,text='Materials / textures (source sampler, not an N64 shader simulation)').pack(anchor='w',padx=8,pady=4)
        self.materials=[]; seen=set()
        for face in self.raw:
            tex=face['texture']
            if tex is not None and id(tex) not in seen: self.materials.append(tex); seen.add(id(tex))
        self.material=tk.StringVar()
        names=[f"{i}: {t.get('material','ROM texture')} {t['width']}x{t['height']} @ {t.get('address',0):08X}" for i,t in enumerate(self.materials)]
        picker=ttk.Combobox(self,textvariable=self.material,values=names,state='readonly')
        picker.pack(fill='x',padx=8); picker.bind('<<ComboboxSelected>>',self.show_texture)
        self.preview=ttk.Label(self); self.preview.pack(pady=5)
        self.sampler=tk.StringVar(); ttk.Label(self,textvariable=self.sampler,wraplength=610).pack(padx=8)
        textures=ttk.Frame(self); textures.pack(pady=5)
        ttk.Button(textures,text='Export texture PNG',command=lambda:self.run(self.export_texture)).pack(side='left',padx=3)
        ttk.Button(textures,text='Replace texture PNG',command=lambda:self.run(self.replace_texture),state='normal' if self.editable else 'disabled').pack(side='left',padx=3)
        ttk.Label(self,text='Source code (original actor behavior / current game converter)').pack(anchor='w',padx=8,pady=5)
        self.code=ttk.Combobox(self,values=self.entity.get('details',{}).get('code',[]),state='readonly')
        self.code.pack(fill='x',padx=8)
        if self.code['values']: self.code.current(0)
        ttk.Button(self,text='Open selected source in code editor',command=lambda:self.run(lambda:open_code(self.code.get()))).pack(pady=5)
        ttk.Label(self,text='OBJ uses local Y-up coordinates; repeating UVs are supported. Re-import reads OBJ + MTL + diffuse images.\nEdits change the draft only. Save alternate, validate UV bake, then choose build.\nCollision stays original; static mesh groups may contain several visual props.',wraplength=620).pack(padx=8,pady=5)
        if names: picker.current(0); self.show_texture()

    def confirm_rename(self,fixes):
        names='\n'.join(f'{a} -> {b}' for a,b in sorted(fixes.items())[:12])
        if len(fixes)>12: names+='\n...'
        return messagebox.askyesno('Fix Blender material names',
            'Blender renamed materials with a number suffix, so the sampler sidecar does not match:\n\n'
            f'{names}\n\nYes: rename them in the OBJ + MTL file and continue import.\nNo: cancel import.',
            default='yes',parent=self.dialog_parent)

    def run(self,action):
        try: action()
        except (OSError,ValueError,KeyError,IndexError) as exc: messagebox.showerror('Map object',str(exc),parent=self.dialog_parent)

    def ensure_current(self):
        if self.viewport.document is None or self.viewport.layout_name=='original':
            raise ValueError('Original is read-only. Save as a named alternate before editing meshes.')
        if self.viewport.document is not self.initial_document or self.viewport.scene is not self.initial_scene:
            raise ValueError('Map changed while inspector was open. Close and reopen selected object.')

    def entry(self,bundle=None):
        values=[float(v.get()) for v in self.fields]
        old=self.viewport.document.get('meshes',{}).get(self.key,{})
        return dict(sha256=self.viewport.scene['source_sha256'],bundle=bundle or old.get('bundle','original'),
                    position=values[:3],yaw=values[3],scale=values[4])

    def commit(self,entry):
        self.ensure_current()
        document=copy.deepcopy(self.viewport.document)
        meshes=document.setdefault('meshes',{})
        if entry is None: meshes.pop(self.key,None)
        else: meshes[self.key]=entry
        scene.layouts.validate(document)
        # Validate actual transformed geometry before accepting the draft.
        if entry and entry['bundle']!='original':
            room,_,obj=self.key.partition('/object/')
            scene.map_meshes.replacement_faces(entry,room,int(obj))
        self.viewport.apply_document(document)
        self.viewport.refresh_layouts(); self.viewport.load(preserve=True)
        self.destroy()

    def lod_entry(self,**changes):
        """Current LOD settings (defaults when none); changes override fields."""
        map_meshes=scene.map_meshes
        lods=self.viewport.document.get('lods',{}) if self.viewport.document else {}
        prefix=(self.key or '').split('_room_')[0]
        entry=dict(lods.get(self.key) or dict(sha256=self.viewport.scene['source_sha256'] if self.viewport.scene else '0'*64,
                   bundle=None,position=list(self.pivot),lod0_distance=map_meshes.LOD0_DISTANCE_DEFAULT,
                   cull_distance=map_meshes.default_cull(prefix)))
        entry.update(changes)
        return entry

    def commit_lod(self,entry):
        """Store LOD settings; an entry equal to the defaults is dropped."""
        map_meshes=scene.map_meshes
        self.ensure_current()
        document=copy.deepcopy(self.viewport.document)
        lods=document.setdefault('lods',{})
        prefix=self.key.split('_room_')[0]
        if entry['bundle'] is None and entry['lod0_distance']==map_meshes.LOD0_DISTANCE_DEFAULT and            entry['cull_distance']==map_meshes.default_cull(prefix):
            lods.pop(self.key,None)
        else: lods[self.key]=entry
        if not lods: document.pop('lods',None)
        scene.layouts.validate(document)
        if entry['bundle'] is not None:
            room,_,obj=self.key.partition('/object/')
            scene.map_meshes.replacement_faces(dict(entry,yaw=0,scale=1),room,int(obj))
        self.viewport.apply_document(document)
        self.viewport.refresh_layouts(); self.viewport.load(preserve=True)
        self.destroy()

    def apply_lod(self):
        values={k:int(v.get()) for k,v in self.lod_fields.items()}
        self.commit_lod(self.lod_entry(**values))

    def import_lod0(self,path=None):
        self.ensure_current()
        path=path or filedialog.askopenfilename(title='Import LOD0 (close-up) OBJ for selected mesh',filetypes=[('Wavefront OBJ','*.obj')],parent=self.dialog_parent)
        if not path: return
        def confirm_split(diagnostics):
            return messagebox.askyesno('LOD0 import requires splitting quads',
                f"{diagnostics['split_quads']} quads are concave/bent or mix materials and will be split into triangles. Import with splitting?",
                default='no',parent=self.dialog_parent)
        bundle=scene.map_meshes.store(path,confirm_split=confirm_split,confirm_rename=self.confirm_rename)
        if bundle is None: return
        values={k:int(v.get()) for k,v in self.lod_fields.items()}
        # Export pivots on the mesh bounds centre; LOD0 is placed back there.
        self.commit_lod(self.lod_entry(bundle=bundle,position=list(self.pivot),**values))

    def remove_lod0(self):
        self.commit_lod(self.lod_entry(bundle=None))

    def place(self): self.commit(self.entry())
    def restore(self): self.commit(None)

    def export(self):
        suggested=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',self.entity['label']).strip(' .') or 'mesh'
        # Default: game/levels/<level>/assets/static/LOD0/<mesh>/ (made on demand).
        prefix=(self.key or self.viewport.room_choices.get(self.viewport.room_name.get(),('',))[0]).split('_room_')[0]
        level=LEVEL_FOLDERS.get(prefix,prefix or 'misc')
        initial=scene.map_meshes.GAME/'levels'/level/'assets/static/LOD0'/suggested
        initial.mkdir(parents=True,exist_ok=True)
        folder=filedialog.asksaveasfilename(title='Export named mesh and original textures',initialdir=str(initial),initialfile=suggested+'.obj',defaultextension='.obj',filetypes=[('Wavefront OBJ','*.obj')],parent=self.dialog_parent)
        if (not folder or Path(folder).resolve().parent!=initial.resolve()) and not any(initial.iterdir()): initial.rmdir()  # cancelled or saved elsewhere
        if folder:
            replacement=self.entity['details'].get('replacement')
            if replacement:
                # Undo placement so exporting and re-importing cannot apply it twice.
                inverse=dict(position=(0,0,0),yaw=-replacement['yaw'],scale=1/replacement['scale'])
                faces=[]
                for face in self.raw:
                    vertices=[(*scene.map_meshes.transform(tuple(v[k]-replacement['position'][k] for k in range(3)),inverse),*v[3:]) for v in face['vertices']]
                    faces.append(dict(face,vertices=vertices))
                scene.map_meshes.export_faces(faces,folder)
            else: scene.map_meshes.export_faces(self.raw,folder,self.pivot)
            messagebox.showinfo('Mesh exported','Saved '+Path(folder).name+' with MTL, original texture PNGs and material sampler metadata. Keep these files together for re-import.',parent=self.dialog_parent)

    def replace(self,path=None):
        self.ensure_current()
        path=path or filedialog.askopenfilename(title='Replace selected mesh object',filetypes=[('Wavefront OBJ','*.obj')],parent=self.dialog_parent)
        if not path: return
        def confirm_split(diagnostics):
            lines=', '.join(map(str,diagnostics['split_lines'][:12]))
            if len(diagnostics['split_lines'])>12: lines+=', ...'
            return messagebox.askyesno('Import requires splitting quads',
                f"{Path(path).name}\n\n{diagnostics['split_quads']} quads cannot stay intact in the current importer. "
                'They will be split into triangles, changing your authored topology.\n\n'
                f'OBJ face lines: {lines}\n\n'
                'Yes: import with those quads split.\n'
                'No: cancel import and keep the current mesh.\n\n'
                'Import with splitting?',default='no',parent=self.dialog_parent)
        bundle=scene.map_meshes.store(path,confirm_split=confirm_split,confirm_rename=self.confirm_rename)
        if bundle is None: return
        self.viewport.reimport_paths[self.key]=str(Path(path).resolve())
        self.commit(self.entry(bundle))

    def reimport(self):
        self.replace(self.viewport.reimport_paths.get(self.key))

    def texture(self):
        if not self.material.get(): raise ValueError('Selected object has no diffuse texture')
        return self.materials[int(self.material.get().split(':')[0])]

    def show_texture(self,_event=None):
        tex=self.texture(); image=Image.new('RGBA',(tex['width'],tex['height'])); image.putdata(tex['colors'])
        image.thumbnail((256,140)); self.photo=ImageTk.PhotoImage(image)
        self.preview.configure(image=self.photo)
        self.sampler.set(json.dumps({k:tex[k] for k in ('scale','cms','cmt','masks','maskt','shifts','shiftt')}))

    def export_texture(self):
        tex=self.texture()
        path=filedialog.asksaveasfilename(title='Export diffuse texture',defaultextension='.png',filetypes=[('PNG','*.png')],parent=self.dialog_parent)
        if path:
            image=Image.new('RGBA',(tex['width'],tex['height'])); image.putdata(tex['colors']); image.save(path)

    def replace_texture(self):
        self.ensure_current(); tex=self.texture()
        path=filedialog.askopenfilename(title='Replacement texture (same dimensions)',filetypes=[('PNG','*.png')],parent=self.dialog_parent)
        if not path: return
        with Image.open(path) as image:
            if image.size!=(tex['width'],tex['height']): raise ValueError('Texture must keep current dimensions; use OBJ re-import for new UV layout')
            replacement=dict(tex,colors=list(image.convert('RGBA').getdata()))
        faces=[dict(f,texture=replacement) if f['texture'] is tex else f for f in self.raw]
        with tempfile.TemporaryDirectory() as folder:
            obj=scene.map_meshes.export_faces(faces,folder,self.pivot)
            bundle=scene.map_meshes.store(obj)
        entry=self.entry(bundle)
        entry.update(position=list(self.pivot),yaw=0,scale=1)
        self.commit(entry)


def camera_dialog(viewport):
    window=tk.Toplevel(viewport); window.title('Viewport camera')
    values=[*viewport.camera.position,math.degrees(viewport.camera.yaw),math.degrees(viewport.camera.pitch),viewport.camera.speed]
    fields=[]
    for row,(name,value) in enumerate(zip(('X','Y','Z','Yaw degrees','Pitch degrees','Fly speed'),values)):
        ttk.Label(window,text=name).grid(row=row,column=0,padx=8,pady=3)
        var=tk.StringVar(value=str(round(value,2))); fields.append(var)
        ttk.Entry(window,textvariable=var).grid(row=row,column=1,padx=8)
    def apply():
        try:
            x,y,z,yaw,pitch,speed=[float(v.get()) for v in fields]
            if not all(math.isfinite(v) for v in (x,y,z,yaw,pitch,speed)) or not 20<=speed<=20000 or not -87<=pitch<=87: raise ValueError('Finite values required; pitch -87..87, speed 20..20000')
            viewport.camera.position=(x,y,z); viewport.camera.yaw=math.radians(yaw); viewport.camera.pitch=math.radians(pitch)
            viewport.camera.speed=speed; viewport.speed_label.set(f'Speed: {speed:g}'); viewport.redraw(); window.destroy()
        except ValueError as exc: messagebox.showerror('Camera',str(exc),parent=window)
    ttk.Button(window,text='Apply camera',command=apply).grid(row=6,columnspan=2,pady=8)
