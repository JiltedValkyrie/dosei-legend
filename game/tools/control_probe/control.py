"""Control the Astra diagnostic game in the normal, visible Kronos application.

No keyboard hooks or desktop capture. Host writes are restricted to the game's
versioned command mailbox; the game performs normal input/physics updates.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "game/build/astra-control"
EMU = ROOT / "game/build/kronos-fix/kronos.exe"
DISC = RUN / "oot-sat/game/build/game.cue"
MAGIC = 0x41535452
OFFSET = 0x1D800
HEADER_WORDS = 35
FACE_WORDS = 48
TRACE_WORDS = 23 + 10 * FACE_WORDS
MAIL_BYTES = (HEADER_WORDS + 2 * TRACE_WORDS) * 4
BUTTONS = dict(l=8, z=16, y=32, x=64, r=128, b=256, c=512,
               a=1024, start=2048, up=4096, down=8192, left=16384, right=32768)
PARENT_POINTS = {
    746: {(0,0,3400),(0,320,5100),(1472,400,4250),(0,160,4250),(736,360,4675),(736,200,3825)},
    738: {(-736,0,4675),(0,320,5100),(0,0,3400),(0,160,4250)},
    745: {(1472,400,5950),(1472,400,4250),(0,320,5100),(736,360,4675)},
    613: {(1472,0,2550),(0,0,3400),(1472,400,4250),(736,200,3825)},
}


def t2(data):
    """Saturn big-endian bytes <-> Kronos little-endian 16-bit word storage."""
    out = bytearray(data)
    out[0::2], out[1::2] = data[1::2], data[0::2]
    return bytes(out)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def symbols():
    output = subprocess.check_output(["C:/msys64/mingw64/bin/nm.exe", "-n", str(EMU)], text=True)
    names = ("LowWram", "HighWram", "Vdp1Ram", "MSH2", "SSH2")
    return {name: int(re.search(r"^([0-9a-f]+) [A-Za-z] " + name + r"$", output, re.M)[1], 16)
            for name in names}


class Process:
    def __init__(self, pid):
        self.pid = pid
        self.k = C.WinDLL("kernel32", use_last_error=True)
        self.k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        self.k.OpenProcess.restype = W.HANDLE
        self.k.ReadProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
        self.k.WriteProcessMemory.argtypes = self.k.ReadProcessMemory.argtypes
        self.k.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
        self.k.CloseHandle.argtypes = [W.HANDLE]
        self.handle = self.k.OpenProcess(0x438, False, pid)
        if not self.handle:
            raise C.WinError(C.get_last_error())
        path, length = C.create_unicode_buffer(32768), W.DWORD(32768)
        if not self.k.QueryFullProcessImageNameW(self.handle, 0, path, C.byref(length)):
            raise C.WinError(C.get_last_error())
        if Path(path.value).resolve() != EMU.resolve():
            raise RuntimeError("Refusing process outside configured Kronos")
        ps = C.WinDLL("psapi", use_last_error=True)
        ps.EnumProcessModules.argtypes = [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)]
        modules, needed = (C.c_void_p * 1024)(), W.DWORD()
        if not ps.EnumProcessModules(self.handle, modules, C.sizeof(modules), C.byref(needed)):
            raise C.WinError(C.get_last_error())
        base = modules[0]
        pe = EMU.read_bytes()
        off = struct.unpack_from("<I", pe, 0x3c)[0]
        preferred = struct.unpack_from("<Q", pe, off + 24 + 24)[0]
        self.ptrs = {n: struct.unpack("<Q", self.read(base + s - preferred, 8))[0]
                     for n, s in symbols().items()}
        self.mail = self.ptrs["LowWram"] + OFFSET

    def read(self, address, size):
        buf, got = C.create_string_buffer(size), C.c_size_t()
        if not self.k.ReadProcessMemory(self.handle, address, buf, size, C.byref(got)) or got.value != size:
            raise C.WinError(C.get_last_error())
        return buf.raw

    def words(self):
        raw = t2(self.read(self.mail, MAIL_BYTES))
        words = list(struct.unpack(">" + "I" * (MAIL_BYTES // 4), raw))
        if words[:3] != [MAGIC, 1, MAIL_BYTES]:
            raise RuntimeError(f"Probe not ready or mailbox version mismatch: {words[:3]}")
        return words

    def write(self, word, values):
        if not (word == 3 and len(values) == 1 or 5 <= word and word + len(values) <= 21):
            raise ValueError("Write outside permitted command fields")
        self.words()  # Revalidate the live build before every write.
        raw = t2(struct.pack(">" + "I" * len(values), *(v & 0xffffffff for v in values)))
        count = C.c_size_t()
        if not self.k.WriteProcessMemory(self.handle, self.mail + word * 4, raw, len(raw), C.byref(count)):
            raise C.WinError(C.get_last_error())
        if count.value != len(raw):
            raise RuntimeError("Incomplete mailbox write")

    def command(self, opcode, **kwargs):
        w = self.words()
        if w[3] != w[4]:
            raise RuntimeError("Previous command is pending")
        fields = dict(steps=6, buttons=7, axis_x=8, axis_y=9, legacy=19, hud=20)
        w[5] = opcode
        for name, value in kwargs.items():
            if name == "pose": w[10:14] = value
            elif name == "camera": w[14:19] = value
            else: w[fields[name]] = value
        self.write(5, w[5:21])
        request = (w[3] + 1) & 0xffffffff
        self.write(3, [request])
        end = time.monotonic() + 45
        idle_frame = None
        while time.monotonic() < end:
            w = self.words()
            if w[4] == request and w[24] == 0:
                if w[21]: raise RuntimeError(f"Game rejected command: {w[21]}")
                # Allow slSynch and previous-frame trace publication to complete.
                completed = HEADER_WORDS + TRACE_WORDS
                if idle_frame is None: idle_frame = w[22]
                if w[completed + 1] == request and w[22] >= idle_frame + 3:
                    return status(w)
            time.sleep(.04)
        raise TimeoutError("Probe did not complete command within 45 seconds")


def signed(n):
    return n - 0x100000000 if n & 0x80000000 else n


def status(w):
    return dict(request=w[4], error=w[21], frame=w[22], sim_steps=w[23], remaining=w[24],
                link=list(map(signed, w[25:29])), camera=list(map(signed, w[29:34])))


def trace(p):
    for _ in range(100):
        w = p.words()
        if not w[34] & 1 and p.words()[34] == w[34]: break
    else: raise RuntimeError("Could not read a coherent trace")
    at = HEADER_WORDS + TRACE_WORDS
    t = list(map(signed, w[at:at + TRACE_WORDS]))
    out = dict(status=status(w), frame=t[0], request=t[1], visible=t[3], total=t[4], accepted=t[5],
               camera=t[6:11], matrix_q16=t[11:23], faces=[])
    for n in range(t[2]):
        f = t[23 + n*FACE_WORDS:23 + (n+1)*FACE_WORDS]
        world = [f[8+i*3:11+i*3] for i in range(4)]
        points = {tuple(p) for p in world}
        parents = [source for source, vertices in PARENT_POINTS.items() if points <= vertices]
        source_face = parents[0] if len(parents) == 1 else None
        child_key = hashlib.sha256(repr(sorted(points)).encode()).hexdigest()[:12]
        view = [[v/65536 for v in f[20+i*3:23+i*3]] for i in range(4)]
        cmd = f[32:48]
        corners = [[v - 65536 if v & 32768 else v for v in cmd[6+i*2:8+i*2]] for i in range(4)]
        width, height = ((f[4] >> 8) & 63)*8, f[4] & 255
        pixels = p.read(p.ptrs["Vdp1Ram"] + f[3]*8, width*height//2)
        palette = p.read(p.ptrs["Vdp1Ram"] + f[5]*8, 32)
        out["faces"].append(dict(source_face=source_face, child_key=child_key,
            poly=f[0], slot=f[1], submitted=f[2], source=f[3],
            size=[width,height], palette=f[5], attr=f[6], matches=f[7], world=world, view=view,
            command=cmd, screen=corners, texture_sha256=hashlib.sha256(pixels+palette).hexdigest()))
    return out


def main():
    ap=argparse.ArgumentParser(__doc__)
    ap.add_argument("action",choices=["status","pose","step","camera","freeze","trace","capture","stop","mode"])
    ap.add_argument("--mode",type=int,choices=[0,1,2],default=0,help="0 SGL baseline; 1 guard diagnostic; 2 bounded local split")
    ap.add_argument("--pose",type=int,nargs=4,metavar=("X","FEET_Y","Z","YAW"))
    ap.add_argument("--camera",type=int,nargs=5,metavar=("X","Y","Z","YAW","PITCH"))
    ap.add_argument("--legacy",type=int,choices=[0,1],default=0)
    ap.add_argument("--steps",type=int,default=1)
    ap.add_argument("--buttons",default="")
    ap.add_argument("--stick",type=int,nargs=2,default=[128,128])
    ap.add_argument("--out",type=Path)
    args=ap.parse_args()
    session=json.loads((RUN/"session.json").read_text(encoding="utf-8-sig"))
    p=Process(session["pid"])
    if sha(EMU)!=session["exe_sha256"]:raise RuntimeError("Emulator changed since launch")
    if args.action=="status": result=status(p.words())
    elif args.action=="mode": result=p.command(4,hud=1+(args.mode<<8))
    elif args.action=="pose":
        if args.pose is None or args.camera is None:ap.error("pose needs --pose and --camera")
        if any(abs(v)>30000 for v in args.pose[:3]+args.camera[:3]):ap.error("pose outside native bounds")
        result=p.command(1,pose=args.pose,camera=args.camera,legacy=args.legacy)
    elif args.action=="step":
        if not 1<=args.steps<=600 or any(not 0<=n<=255 for n in args.stick):ap.error("invalid steps/stick")
        buttons=0
        for name in args.buttons.split(","):
            if name:buttons|=BUTTONS[name.lower()]
        result=p.command(2,steps=args.steps,buttons=buttons,axis_x=args.stick[0],axis_y=args.stick[1])
    elif args.action=="camera":result=p.command(3,legacy=args.legacy)
    elif args.action=="freeze":result=p.command(4)
    elif args.action=="trace":result=trace(p)
    elif args.action=="capture":
        if not args.out:ap.error("capture needs --out")
        subprocess.run(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(ROOT/"game/tools/capture-kronos.ps1"),
                        "-ViewerId",str(p.pid),"-OutputPath",str(args.out.resolve())],check=True)
        return
    elif args.action=="stop":
        # Close only the recorded, path-verified controlled session.
        user=C.WinDLL("user32");cb=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
        user.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
        user.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
        def close(h,_):
            pid=W.DWORD();user.GetWindowThreadProcessId(h,C.byref(pid))
            if pid.value==p.pid:user.PostMessageW(h,0x10,0,0)
            return True
        user.EnumWindows(cb(close),0);return
    text=json.dumps(result,indent=2)
    if args.out:args.out.write_text(text,encoding="utf-8")
    else:print(text)


if __name__=="__main__":main()
