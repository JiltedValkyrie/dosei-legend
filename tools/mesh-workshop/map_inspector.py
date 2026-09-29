"""Selected-object tools for Map Workshop; source code and material exchange."""
import copy
import json
import math
import os
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


class ObjectInspector(tk.Toplevel):
    def __init__(self,viewport):
        super().__init__(viewport)
        self.viewport=viewport
        self.entity=copy.deepcopy(viewport.entities[viewport.selected])
        self.title('Map Workshop - '+self.entity['label'])
        self.geometry('650x650')
        self.raw=[f['source_face'] for f in viewport.scene['faces']
                  if f['entity']==viewport.selected and 'source_face' in f]
        self.key=self.entity.get('details',{}).get('mesh_key')
        self.editable=bool(self.key and viewport.document is not None)
        self.initial_document=viewport.document
        self.initial_scene=viewport.scene
        self.pivot=tuple((a+b)/2 for a,b in zip(*self.entity['bounds'])) if 'bounds' in self.entity else (0,0,0)
        bar=ttk.Frame(self,padding=8); bar.pack(fill='x')
        for text,action in [('Export OBJ / MTL / atlas',self.export),('Replace OBJ...',self.replace),
                            ('Re-import OBJ / UV',self.reimport)]:
            ttk.Button(bar,text=text,command=lambda a=action:self.run(a),state='normal' if self.editable else 'disabled').pack(side='left',padx=3)
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
        ttk.Label(self,text='OBJ uses local Y-up coordinates; keep UVs in 0..1. Re-import reads OBJ + MTL + diffuse images.\nEdits change the draft only. Save alternate, validate UV bake, then choose build.\nCollision stays original; static mesh groups may contain several visual props.',wraplength=620).pack(padx=8,pady=5)
        if names: picker.current(0); self.show_texture()

    def run(self,action):
        try: action()
        except (OSError,ValueError,KeyError,IndexError) as exc: messagebox.showerror('Map object',str(exc),parent=self)

    def ensure_current(self):
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
        self.viewport.document=document; self.viewport.unsaved=True
        self.viewport.refresh_layouts(); self.viewport.load(preserve=True)
        self.destroy()

    def place(self): self.commit(self.entry())
    def restore(self): self.commit(None)

    def export(self):
        folder=filedialog.askdirectory(title='Export selected object bundle',parent=self)
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
            messagebox.showinfo('Mesh exported','mesh.obj, mesh.mtl and atlas.png saved. OBJ origin is selected bounds centre.',parent=self)

    def replace(self,path=None):
        self.ensure_current()
        path=path or filedialog.askopenfilename(title='Replace selected mesh object',filetypes=[('Wavefront OBJ','*.obj')],parent=self)
        if not path: return
        bundle=scene.map_meshes.store(path)
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
        path=filedialog.asksaveasfilename(title='Export diffuse texture',defaultextension='.png',filetypes=[('PNG','*.png')],parent=self)
        if path:
            image=Image.new('RGBA',(tex['width'],tex['height'])); image.putdata(tex['colors']); image.save(path)

    def replace_texture(self):
        self.ensure_current(); tex=self.texture()
        path=filedialog.askopenfilename(title='Replacement texture (same dimensions)',filetypes=[('PNG','*.png')],parent=self)
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
