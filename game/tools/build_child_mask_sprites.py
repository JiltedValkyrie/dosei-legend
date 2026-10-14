"""Offline source mask attachments, including the runner's two rigid ears."""
import xml.etree.ElementTree as ET
import build_link_model as link

class MaskLists(link.LimbLists):
    def __init__(self,data,keep,limb,rotation,origin,bunny=False):
        super().__init__(b'',b'')
        self.segments={6:data,4:keep};self.current_limb=limb
        self.base=(rotation,origin);self.extra=None;self.bunny=bunny
    def matrix(self,word,address):
        if word==0xDA380003 and address>>24==13:
            self.extra=None;return
        if self.bunny and word==0xDA380001 and address>>24==11:
            left=(address&0xffffff)==64
            rot=(-0x3E2,-0xDBE,-0x348A) if left else (0x3E2,0xDBE,-0x348A)
            # Source Matrix_SetTranslateRotateYXZ, not ZYX.
            rx=link.rotation_matrix((rot[0],0,0));ry=link.rotation_matrix((0,rot[1],0));rz=link.rotation_matrix((0,0,rot[2]))
            self.extra=(link.matmul(link.matmul(ry,rx),rz),(97,-1203,240 if left else -240));return
        return super().matrix(word,address)
    def load_vertex(self,index,vertex):
        xyz=vertex[:3]
        if self.extra:xyz=link.transform(*self.extra,xyz)
        xyz=link.transform(*self.base,xyz)
        return super().load_vertex(index,xyz+tuple(vertex[3:]))


def attachment(oot,rom_dir,obj,limb,keep):
    # Exact source PostLimbDraw attachment slots and constant transforms.
    if (obj,limb) not in (('object_cs',14),('object_mm',14),('object_skj',10),('object_sd',15)):return []
    mask_obj='object_skj' if obj=='object_skj' else 'object_link_child'
    data=link.read_object(oot,mask_obj,rom_dir)
    named={e.attrib['Name']:int(e.attrib['Offset'],16) for e in ET.parse(oot/'assets/xml/objects'/(mask_obj+'.xml')).iter()
           if 'Name' in e.attrib and 'Offset' in e.attrib and not e.attrib['Offset'].startswith('.')}
    if obj=='object_sd':
        symbol='gLinkChildKeatonMaskDL';rot=link.rotation_matrix((0,0,round(65536*70/360)));origin=(-570,0,0)
    elif obj=='object_cs':
        symbol='gLinkChildSpookyMaskDL';rot=link.rotation_matrix((0,0,round(65536*100/360)));origin=(0,-200,0)
    elif obj=='object_mm':
        symbol='gLinkChildBunnyHoodDL';rot=link.rotation_matrix((0,0,round(65536*2/5)))
        origin=link.transform(rot,(260,20,0),(-260,58,10))
    else:
        symbol='gSkullKidSkullMaskDL';rot=link.rotation_matrix((-0x4000,0,0));origin=(0,0,0)
    lists=MaskLists(data,keep,limb,rot,origin,obj=='object_mm')
    lists.walk(0x06000000|named[symbol])
    return lists.faces
