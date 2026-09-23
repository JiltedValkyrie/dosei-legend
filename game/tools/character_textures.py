"""Character policy: flat bodies, textured hair and faces only.

VDP1 widths are multiples of eight. A 4x4 logical tile is stored as 8x4 with
each column repeated, preserving the original UV domain without cropping.
Flat colours are already cheaper and remain flat.
"""
import re
import xml.etree.ElementTree as ET

FACE_NAME = re.compile(r'Eye|Mouth|Nose|Nostril|Ear|Forehead|Jaw|Cheek|Teeth|UpperLip|HeadGradient')
NON_FACE_NAME = re.compile(r'Hair|Mane|Sideburn|Cap|Hood|Hat|Veil|Fabric|Neck|Saddle')
HAIR_NAME = re.compile(r'Hair|Mane|Sideburn')


def mark_faces(faces, xml_path, head_limb=None, expression_segments=()):
    """Resolve source facial materials before flattening changes texture state.

    Anonymous head materials conservatively retain face detail; named hair,
    headwear and neck materials do not get the face exemption. New importers
    must supply their source head/expression bindings rather than guessing a
    global limb number (horses and humans have different skeletons).
    """
    names = {int(n.attrib['Offset'], 16): n.attrib.get('Name', '')
             for n in ET.parse(xml_path).iter('Texture')}
    for face in faces:
        texture = face.get('texture') or {}
        address = texture.get('address', 0)
        segment = face.get('texture_segment')
        name = names.get(address & 0xffffff, '') if segment == 6 else ''
        head = head_limb is not None and face.get('limb') == head_limb
        named_face = bool(FACE_NAME.search(name)) and not NON_FACE_NAME.search(name)
        anonymous_head = head and (not name or re.match(r'object_.*Tex', name))
        # RDP texture state can remain bound while a later body list draws.
        # Facial names/segments are not sufficient outside a humanoid's head.
        facial_limb = head_limb is None or head
        face['face_detail'] = bool(facial_limb and
                                  (segment in expression_segments or named_face or anonymous_head))
        # Shared gameplay_keep hair has no name in the actor's own XML.
        if segment == 4:
            face['face_detail'] = False
        face['hair_detail'] = bool((HAIR_NAME.search(name) and facial_limb) or (segment == 4 and head))


def keep_texture(face):
    """A full_texture request must never bypass the global body policy."""
    return bool(face.get('face_detail') or face.get('hair_detail'))


def bake_character_tile(face, original_size, bake):
    logical = original_size if face.get('face_detail') else max(2, original_size // 2)
    tile = bake(face, logical)
    width = max(8, logical)
    if width != logical:
        indices = [v for byte in tile[32:] for v in (byte >> 4, byte & 15)]
        expanded = [v for v in indices for _ in range(width // logical)]
        tile = tile[:32] + bytes((expanded[i] << 4) | expanded[i + 1]
                                for i in range(0, len(expanded), 2))
    return tile, width, logical
