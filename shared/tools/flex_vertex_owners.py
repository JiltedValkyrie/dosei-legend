"""Reusable OoT Flex skeleton matrix/vertex ownership, independent of Link.

Use before DisplayLists in a reader's bases. Populate matrix_limbs in the
source draw traversal order and set current_limb before each limb display list.
Only the verified segment-D model-view LOAD form is supported; fail on others.
"""


class FlexVertexOwners:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vertex_limbs = [None] * len(self.cache)
        self.current_limb = None
        self.matrix_limbs = []

    def matrix(self, word, address):
        if word != 0xDA380003 or address >> 24 != 0xD or address & 63:
            raise ValueError(f'Unsupported Flex matrix {word:08x} {address:08x}')
        slot = (address & 0xFFFFFF) // 64
        if slot >= len(self.matrix_limbs):
            raise ValueError(f'Flex matrix slot {slot} outside skeleton')
        self.current_limb = self.matrix_limbs[slot]

    def load_vertex(self, index, vertex):
        if self.current_limb is None:
            raise ValueError('Flex vertex loaded before matrix owner was set')
        super().load_vertex(index, vertex)
        # RSP transforms at G_VTX time, not when a later triangle uses the slot.
        self.vertex_limbs[index] = self.current_limb
