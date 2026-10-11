# -*- coding: utf-8 -*-
"""
ClientMod ESP v15.2
رابط کاربری همان پروژه (اتصال / خودت / اسکن / ESP / کالیبره / لاگ)
افست‌ها مخصوص CMLauncher + clientmod_game.dll هستند، نه CS2.

چرا v15.1 باکس نمی‌کشید:
  - حالت ce_chain فقط اسم و HP از PlayerResource می‌خواند و origin ندارد.
  - ماتریس OWN یک view ساده است، projection نیست؛ دشمن را وسط صفحه یا بیرون می‌اندازد.
  - اسلات‌های hp=1 و اسم تکراری (بازیکن مرده/قدیمی) شمارش را از ۲۴ به ۳۴ می‌برد.
"""
import ctypes
import ctypes.wintypes as wt
import json
import math
import os
import struct
import sys
from datetime import datetime
from collections import deque

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
except ImportError:
    sys.exit("tkinter لازم است")

k32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
PROCESS_ALL = 0x0010 | 0x0400
SNAP_PROC, SNAP_MOD = 0x2, 0x8 | 0x10
INVALID = ctypes.c_void_p(-1).value

LOG_DIR = os.path.join(os.path.expanduser("~"), "PPHunter_Logs")
os.makedirs(LOG_DIR, exist_ok=True)
CALIB_PATH = os.path.join(LOG_DIR, "calib_v152.json")

GAME_MOD = "clientmod_game.dll"
CLIENT_MOD = "clientmod_client.dll"
DEFAULT_W, DEFAULT_H = 1280, 900

# game.dll — تأییدشده با Cheat Engine
MY_POS_X, MY_POS_Y, MY_POS_Z = 0x242F510, 0x242F514, 0x242F518
MY_YAW, MY_PITCH, MY_ROLL = 0x25982CC, 0x25982D0, 0x25982D4
PLAYER_RES = 0x02478218
RES_HP, RES_TEAM, RES_NAME = 0x1270, 0x1128, 0x0CD4
RENDERER, MATRIX_RVA, REN_MAT = 0x0275FCE0, 0x027603B0, 0x6D0
HP_PTR_RVA, HP_PTR_OFF1, HP_PTR_OFF2 = 0x025278D4, 0x14, 0x1B4

# client.dll — زنجیره یک دشمن (HP و origin کنار هم)
CLIENT_HP_RVA = 0x00753344
CLIENT_HP_OFF1, CLIENT_HP_OFF2, CLIENT_HP_OFF3 = 0x58, 0x34, 0x11C
ORIGIN_FROM_HP = (0x170, 0x174, 0x130, 0x128, 0x120)

# جدول بازیکن. چند چیدمان تست می‌شود؛ اولین چیدمانی که origin معتبر بدهد قفل می‌شود.
PLAYER_ARRAY_RVA = 0x026B2364
PLAYER_MAX = 64
ARRAY_LAYOUTS = (
    {"name": "s14/obj0C/pos290", "stride": 0x14, "serial": 0x04, "obj": 0x0C,
     "hp": 0x11C, "team": 0xD4, "pos": 0x290},
    {"name": "s28/obj20/pos290", "stride": 0x28, "serial": None, "obj": 0x20,
     "hp": 0x11C, "team": 0xD4, "pos": 0x290},
    {"name": "s14/obj0C/pos170", "stride": 0x14, "serial": 0x04, "obj": 0x0C,
     "hp": 0x11C, "team": 0xD4, "pos": 0x170},
    {"name": "s28/obj20/pos170", "stride": 0x28, "serial": None, "obj": 0x20,
     "hp": 0x11C, "team": 0xD4, "pos": 0x170},
    {"name": "s14/noserial/pos290", "stride": 0x14, "serial": None, "obj": 0x0C,
     "hp": 0x11C, "team": 0xD4, "pos": 0x290},
)


class PE32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD), ("szExeFile", ctypes.c_char * 260),
    ]


class ME32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD), ("th32ModuleID", wt.DWORD), ("th32ProcessID", wt.DWORD),
        ("GlblcntUsage", wt.DWORD), ("ProccntUsage", wt.DWORD),
        ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
        ("modBaseSize", wt.DWORD), ("hModule", wt.HMODULE),
        ("szModule", ctypes.c_char * 256), ("szExePath", ctypes.c_char * 260),
    ]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def list_procs():
    out = []
    snap = k32.CreateToolhelp32Snapshot(SNAP_PROC, 0)
    if snap == INVALID:
        return out
    ent = PE32()
    ent.dwSize = ctypes.sizeof(ent)
    if k32.Process32First(snap, ctypes.byref(ent)):
        while True:
            try:
                name = ent.szExeFile.decode("utf-8", "ignore")
            except Exception:
                name = ent.szExeFile.decode("latin-1", "ignore")
            out.append((ent.th32ProcessID, name))
            if not k32.Process32Next(snap, ctypes.byref(ent)):
                break
    k32.CloseHandle(snap)
    return out


def list_mods(pid):
    out = []
    snap = k32.CreateToolhelp32Snapshot(SNAP_MOD, pid)
    if snap == INVALID:
        return out
    ent = ME32()
    ent.dwSize = ctypes.sizeof(ent)
    if k32.Module32First(snap, ctypes.byref(ent)):
        while True:
            try:
                name = ent.szModule.decode("utf-8", "ignore")
            except Exception:
                name = ent.szModule.decode("latin-1", "ignore")
            base = ctypes.cast(ent.modBaseAddr, ctypes.c_void_p).value or 0
            out.append((name, base, ent.modBaseSize))
            if not k32.Module32Next(snap, ctypes.byref(ent)):
                break
    k32.CloseHandle(snap)
    return out


def open_proc(pid):
    return k32.OpenProcess(PROCESS_ALL, False, pid)


def rpm(handle, addr, size):
    if not addr or addr < 0x10000:
        return None
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)):
        return None
    return buf.raw if got.value == size else None


def u32(handle, addr):
    data = rpm(handle, addr, 4)
    return struct.unpack("<I", data)[0] if data else None


def i32(handle, addr):
    data = rpm(handle, addr, 4)
    return struct.unpack("<i", data)[0] if data else None


def f32(handle, addr):
    data = rpm(handle, addr, 4)
    return struct.unpack("<f", data)[0] if data else None


def vec3(handle, addr):
    data = rpm(handle, addr, 12)
    return struct.unpack("<3f", data) if data else None


def read_mat4(handle, addr):
    data = rpm(handle, addr, 64)
    return list(struct.unpack("<16f", data)) if data else None


def read_str(handle, addr, limit=32):
    data = rpm(handle, addr, limit)
    if not data:
        return None
    try:
        text = data.split(b"\x00")[0].decode("utf-8", "ignore").strip()
    except Exception:
        return None
    if not text or "unconnected" in text.lower():
        return None
    if not all(ch.isprintable() for ch in text):
        return None
    return text[:18]


def is_ptr(value):
    return value is not None and 0x10000 <= value <= 0x7FFEFFFF


def valid_pos(value):
    if not value or len(value) < 3:
        return False
    if any(v != v or abs(v) > 20000 for v in value):
        return False
    if all(abs(v) < 0.5 for v in value):
        return False
    return True


def dist3(a, b):
    if not a or not b:
        return 99999.0
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def placeholder_name(name, slot):
    key = (name or "").strip().lower()
    return key in ("", "unnamed", "p{}".format(slot))


def find_game():
    best = None
    for pid, name in list_procs():
        low = name.lower()
        if "cmlauncher" not in low and "clientmod" not in low:
            continue
        for mod, base, size in list_mods(pid):
            if GAME_MOD in mod.lower() and (best is None or size > best[3]):
                best = (pid, name, base, size)
    return best if best else (None, None, None, None)


def find_client_base(pid):
    for mod, base, _size in list_mods(pid):
        if CLIENT_MOD in mod.lower():
            return base
    return None


def find_game_res(pid):
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def visit(hwnd, _lp):
        proc = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc))
        if proc.value != pid or not user32.IsWindowVisible(hwnd) or user32.GetParent(hwnd):
            return True
        rect = RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if width >= 640 and height >= 480:
            found.append((width, height))
        return True

    user32.EnumWindows(visit, 0)
    if not found:
        return DEFAULT_W, DEFAULT_H
    found.sort(key=lambda wh: wh[0] * wh[1], reverse=True)
    return found[0]


def score_matrix(mat):
    if not mat or all(abs(c) < 1e-5 for c in mat):
        return -1000
    if any(c != c or abs(c) == float("inf") or abs(c) > 90000 for c in mat):
        return -1000
    nonzero = sum(1 for c in mat if abs(c) > 0.001)
    if nonzero < 5:
        return -400
    return float(min(nonzero, 12)) + (8 if abs(mat[15] - 1.0) < 0.4 else 0)


def w2s_col(mat, pos, sw, sh):
    x, y, z = pos
    clip_x = mat[0] * x + mat[4] * y + mat[8] * z + mat[12]
    clip_y = mat[1] * x + mat[5] * y + mat[9] * z + mat[13]
    clip_w = mat[3] * x + mat[7] * y + mat[11] * z + mat[15]
    if abs(clip_w) < 0.001:
        return None, None, False
    return (sw / 2) * (1 + clip_x / clip_w), (sh / 2) * (1 - clip_y / clip_w), clip_w > 0.01


def cam_basis(yaw_deg, pitch_deg, yaw_sign, pitch_sign):
    yaw = math.radians(yaw_deg * yaw_sign)
    pitch = math.radians(pitch_deg * pitch_sign)
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    forward = (cp * cy, cp * sy, -sp)
    right = (sy, -cy, 0.0)
    up = (sp * cy, sp * sy, cp)
    return forward, right, up


def w2s_cam(eye, yaw, pitch, pos, sw, sh, fov, yaw_sign, pitch_sign):
    forward, right, up = cam_basis(yaw, pitch, yaw_sign, pitch_sign)
    delta = (pos[0] - eye[0], pos[1] - eye[1], pos[2] - eye[2])
    depth = dot(delta, forward)
    if depth < 1.0:
        return None, None, depth
    focal = (sh / 2.0) / max(math.tan(math.radians(fov) / 2.0), 0.05)
    sx = sw / 2.0 + dot(delta, right) / depth * focal
    sy = sh / 2.0 - dot(delta, up) / depth * focal
    return sx, sy, depth


class App:
    def __init__(self, root):
        self.root = root
        root.title("ClientMod ESP v15.2")
        root.geometry("1380x940")
        root.configure(bg="#1a1a1a")

        self.h = self.pid = self.gbase = self.cbase = None
        self.game_w, self.game_h = DEFAULT_W, DEFAULT_H
        self.w2s_mode = "cam"
        self.player_mode = "both"
        self.matrix = None
        self.matrix_src = "-"
        self.my_pos = None
        self.my_yaw = self.my_pitch = self.my_roll = None
        self.my_slot = self.my_team = None
        self.local_hp = None
        self.enemy_hp = self.enemy_pos = self.enemy_hp_addr = self.origin_off_used = None
        self.players_raw = []
        self.players = []
        self.layout = None
        self.layout_hits = 0
        self.esp_running = False
        self.events = deque(maxlen=2000)
        self._load_calib()
        self._ui()

    def _load_calib(self):
        self.fov = 90.0
        self.eye_z = 64.0
        self.player_h = 72.0
        self.unit_to_m = 0.0254
        self.yaw_sign = 1.0
        self.pitch_sign = 1.0
        self.max_dist = 8000.0
        self.hide_dead = True
        self.enemies_only = True
        self.edge_marks = False
        try:
            data = json.load(open(CALIB_PATH, encoding="utf-8"))
            for key in ("fov", "eye_z", "player_h", "unit_to_m", "yaw_sign",
                        "pitch_sign", "max_dist"):
                if key in data:
                    setattr(self, key, float(data[key]))
            self.hide_dead = bool(data.get("hide_dead", True))
            self.enemies_only = bool(data.get("enemies_only", True))
            self.edge_marks = bool(data.get("edge_marks", False))
            if data.get("w2s") in ("cam", "matrix"):
                self.w2s_mode = data["w2s"]
        except Exception:
            pass

    def _save_calib(self):
        try:
            json.dump({
                "fov": self.fov, "eye_z": self.eye_z, "player_h": self.player_h,
                "unit_to_m": self.unit_to_m, "yaw_sign": self.yaw_sign,
                "pitch_sign": self.pitch_sign, "max_dist": self.max_dist,
                "hide_dead": self.hide_dead, "enemies_only": self.enemies_only,
                "edge_marks": self.edge_marks, "w2s": self.w2s_mode,
            }, open(CALIB_PATH, "w", encoding="utf-8"), indent=2)
        except Exception:
            pass

    def _ui(self):
        top = tk.Frame(self.root, bg="#0e639c", height=42)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="  ClientMod ESP v15.2  —  CMLauncher",
                 font=("Segoe UI", 11, "bold"), bg="#0e639c", fg="white").pack(side="left", padx=12)

        bar = tk.Frame(self.root, bg="#252526")
        bar.pack(fill="x", padx=6, pady=4)
        self._btn(bar, "① اتصال", self.connect, "#16825d")
        self._btn(bar, "② خودت", self.pick_self, "#7b1fa2")
        self._btn(bar, "نزدیک‌ترین به من", self.pick_nearest, "#6a1b9a")
        self._btn(bar, "③ اسکن", self.scan_players, "#455a64")
        self.btn_esp = self._btn(bar, "④ ESP", self.toggle_esp, "#0e639c")
        self._btn(bar, "لاگ", self.save_log, "#555")

        modes = tk.Frame(self.root, bg="#1a1a1a")
        modes.pack(fill="x", padx=8)
        tk.Label(modes, text="W2S:", bg="#1a1a1a", fg="#4ec9b0",
                 font=("Consolas", 9)).pack(side="left")
        self.var_w2s = tk.StringVar(value=self.w2s_mode)
        box = ttk.Combobox(modes, values=["cam", "matrix"], textvariable=self.var_w2s,
                           width=8, state="readonly")
        box.pack(side="left", padx=(4, 14))
        box.bind("<<ComboboxSelected>>", lambda _e: self._set_w2s(self.var_w2s.get()))
        tk.Label(modes, text="Players:", bg="#1a1a1a", fg="#4ec9b0",
                 font=("Consolas", 9)).pack(side="left")
        self.var_players = tk.StringVar(value=self.player_mode)
        box2 = ttk.Combobox(modes, values=["both", "array", "ce_chain"],
                            textvariable=self.var_players, width=10, state="readonly")
        box2.pack(side="left", padx=4)
        box2.bind("<<ComboboxSelected>>",
                  lambda _e: setattr(self, "player_mode", self.var_players.get()))
        tk.Label(modes, text="  cam = زاویه دوربین تو   |   both = اسم از Resource + مختصات از Array",
                 bg="#1a1a1a", fg="#888", font=("Segoe UI", 8)).pack(side="left", padx=8)

        cal = tk.Frame(self.root, bg="#141414")
        cal.pack(fill="x", padx=6, pady=2)
        self.sc_fov = self._scale(cal, "FOV", 60, 120, self.fov, self._on_fov)
        self.sc_eye = self._scale(cal, "EyeZ", 0, 90, self.eye_z, self._on_eye)
        self.sc_h = self._scale(cal, "قد", 48, 96, self.player_h, self._on_h)
        self.sc_unit = self._scale(cal, "متر", 10, 40, self.unit_to_m * 1000, self._on_unit)
        self.btn_yaw = self._btn(cal, "Yaw {}".format("+" if self.yaw_sign > 0 else "-"),
                                 self.flip_yaw, "#37474f")
        self.btn_pitch = self._btn(cal, "Pitch {}".format("+" if self.pitch_sign > 0 else "-"),
                                   self.flip_pitch, "#37474f")
        self.var_dead = tk.BooleanVar(value=self.hide_dead)
        self.var_enemy = tk.BooleanVar(value=self.enemies_only)
        self.var_edge = tk.BooleanVar(value=self.edge_marks)
        tk.Checkbutton(cal, text="مخفی مرده", variable=self.var_dead, command=self._flags,
                       bg="#141414", fg="#ddd", selectcolor="#222").pack(side="left", padx=4)
        tk.Checkbutton(cal, text="فقط دشمن", variable=self.var_enemy, command=self._flags,
                       bg="#141414", fg="#ddd", selectcolor="#222").pack(side="left")
        tk.Checkbutton(cal, text="لبه", variable=self.var_edge, command=self._flags,
                       bg="#141414", fg="#ddd", selectcolor="#222").pack(side="left")

        self.status = tk.Label(self.root, text="بازی را باز کن → اتصال → خودت → ESP   (Run as Admin)",
                               font=("Consolas", 10), bg="#1a1a1a", fg="#4ec9b0")
        self.status.pack(fill="x", padx=8)

        main = tk.Frame(self.root, bg="#1a1a1a")
        main.pack(fill="both", expand=True, padx=6, pady=4)
        left = tk.Frame(main, bg="#0a0a0a")
        left.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(left, bg="#0a0a0a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        right = tk.Frame(main, bg="#1e1e1e", width=360)
        right.pack(side="right", fill="y", padx=(6, 0))
        right.pack_propagate(False)
        tk.Label(right, text=" INFO ", font=("Segoe UI", 10, "bold"),
                 bg="#0e639c", fg="white").pack(fill="x")
        self.info = tk.Text(right, font=("Consolas", 9), bg="#101010", fg="#dcdcaa",
                            highlightthickness=0, borderwidth=0, padx=6, pady=6)
        self.info.pack(fill="both", expand=True)
        for tag, color in (("me", "#00FF88"), ("en", "#FFD700"), ("head", "#9E9E9E"), ("bad", "#FF6B6B")):
            self.info.tag_configure(tag, foreground=color)

        book = ttk.Notebook(self.root)
        book.pack(fill="both", expand=True, padx=6, pady=4)
        tab = tk.Frame(book, bg="#1e1e1e")
        book.add(tab, text="Log")
        self.logb = scrolledtext.ScrolledText(tab, font=("Consolas", 8), bg="#121212", fg="#d4d4d4", height=8)
        self.logb.pack(fill="both", expand=True)
        help_tab = tk.Frame(book, bg="#1e1e1e")
        book.add(help_tab, text="کالیبر")
        msg = (
            "اگر باکس چپ/راست برعکس است: Yaw را بزن.\n"
            "اگر بالا/پایین برعکس است: Pitch را بزن.\n"
            "اگر باکس خیلی بزرگ یا کوچک است: FOV را تکان بده تا وقتی نشانه‌گیری وسط است، باکس وسط بیاید.\n"
            "EyeZ ارتفاع چشم است. قد، بلندی باکس است.\n"
            "متر فقط نوشته فاصله را عوض می‌کند، جای باکس را نه.\n"
            "حالت both را نگه دار. cam را نگه دار مگر ماتریس واقعی رندر (نه OWN) وسط صفحه را درست کند.\n"
            "اگر تعداد هنوز زیاد است، «مخفی مرده» روشن بماند. اسم تکراری، اسلات با HP بالاتر می‌ماند."
        )
        tk.Label(help_tab, text=msg, justify="right", bg="#1e1e1e", fg="#ddd",
                 font=("Segoe UI", 10), anchor="e").pack(fill="both", expand=True, padx=12, pady=8)

    def _btn(self, parent, text, cmd, color):
        btn = tk.Button(parent, text=text, command=cmd, bg=color, fg="white",
                        relief="flat", padx=8, pady=4)
        btn.pack(side="left", padx=2, pady=4)
        return btn

    def _scale(self, parent, label, lo, hi, value, cmd):
        tk.Label(parent, text=label, bg="#141414", fg="#9cdcfe",
                 font=("Consolas", 8)).pack(side="left", padx=(6, 0))
        scale = tk.Scale(parent, from_=lo, to=hi, orient="horizontal", resolution=1,
                         length=90, bg="#141414", fg="#ddd", highlightthickness=0,
                         troughcolor="#333", command=cmd)
        scale.set(value)
        scale.pack(side="left")
        return scale

    def _on_fov(self, value):
        self.fov = float(value)
        self._save_calib()

    def _on_eye(self, value):
        self.eye_z = float(value)
        self._save_calib()

    def _on_h(self, value):
        self.player_h = float(value)
        self._save_calib()

    def _on_unit(self, value):
        self.unit_to_m = float(value) / 1000.0
        self._save_calib()

    def _set_w2s(self, mode):
        self.w2s_mode = mode
        self._save_calib()

    def flip_yaw(self):
        self.yaw_sign *= -1
        self.btn_yaw.config(text="Yaw {}".format("+" if self.yaw_sign > 0 else "-"))
        self._save_calib()

    def flip_pitch(self):
        self.pitch_sign *= -1
        self.btn_pitch.config(text="Pitch {}".format("+" if self.pitch_sign > 0 else "-"))
        self._save_calib()

    def _flags(self):
        self.hide_dead = bool(self.var_dead.get())
        self.enemies_only = bool(self.var_enemy.get())
        self.edge_marks = bool(self.var_edge.get())
        self._save_calib()

    def log(self, msg, **kw):
        line = "[{}] {}".format(datetime.now().strftime("%H:%M:%S"), msg)
        if kw:
            line += " " + " ".join("{}={}".format(k, v) for k, v in list(kw.items())[:8])
        self.events.append({"ts": datetime.now().isoformat(), "msg": msg, "data": kw})
        self.logb.insert("end", line + "\n")
        self.logb.see("end")

    def read_my_state(self):
        if not self.h:
            return
        base = self.gbase
        self.my_pos = (f32(self.h, base + MY_POS_X), f32(self.h, base + MY_POS_Y), f32(self.h, base + MY_POS_Z))
        self.my_yaw = f32(self.h, base + MY_YAW)
        self.my_pitch = f32(self.h, base + MY_PITCH)
        self.my_roll = f32(self.h, base + MY_ROLL)
        ptr = u32(self.h, base + HP_PTR_RVA)
        if is_ptr(ptr):
            ptr2 = u32(self.h, ptr + HP_PTR_OFF1)
            if is_ptr(ptr2):
                self.local_hp = i32(self.h, ptr2 + HP_PTR_OFF2)

    def resolve_enemy_hp_addr(self):
        if not self.h or not self.cbase:
            return None
        p1 = u32(self.h, self.cbase + CLIENT_HP_RVA)
        if not is_ptr(p1):
            return None
        p2 = u32(self.h, p1 + CLIENT_HP_OFF1)
        if not is_ptr(p2):
            return None
        p3 = u32(self.h, p2 + CLIENT_HP_OFF2)
        return (p3 + CLIENT_HP_OFF3) if is_ptr(p3) else None

    def pick_origin_from_hp(self, hp_addr):
        best = None
        for off in ORIGIN_FROM_HP:
            pos = vec3(self.h, hp_addr + off)
            if not valid_pos(pos):
                continue
            score = 30 if off == 0x170 else 10
            if valid_pos(self.my_pos):
                dist = dist3(pos, self.my_pos)
                if 30 < dist < 4000:
                    score += 25
                elif dist < 8:
                    score -= 30
            if best is None or score > best[0]:
                best = (score, list(pos), off)
        return (best[1], best[2]) if best else (None, None)

    def read_enemy_ce(self):
        self.enemy_hp = self.enemy_pos = self.enemy_hp_addr = self.origin_off_used = None
        hp_addr = self.resolve_enemy_hp_addr()
        if not hp_addr:
            return
        hp = i32(self.h, hp_addr)
        if hp is None or not (1 <= hp <= 150):
            return
        self.enemy_hp_addr = hp_addr
        self.enemy_hp = hp
        pos, off = self.pick_origin_from_hp(hp_addr)
        if pos:
            self.enemy_pos = pos
            self.origin_off_used = off

    def _array_bases(self):
        ptr = u32(self.h, self.gbase + PLAYER_ARRAY_RVA)
        bases = []
        if is_ptr(ptr):
            bases.append(ptr)
        bases.append(self.gbase + PLAYER_ARRAY_RVA)
        return bases

    def _read_layout(self, base, layout, check_serial):
        stride = layout["stride"]
        raw = rpm(self.h, base, PLAYER_MAX * stride)
        if not raw or len(raw) < PLAYER_MAX * stride:
            return []
        found = []
        for index in range(PLAYER_MAX):
            entry = index * stride
            if check_serial and layout["serial"] is not None:
                serial = struct.unpack_from("<I", raw, entry + layout["serial"])[0]
                if (serial >> 16) != index and (serial & 0xFFFF) != index:
                    continue
            obj = struct.unpack_from("<I", raw, entry + layout["obj"])[0]
            if not is_ptr(obj):
                continue
            hp = i32(self.h, obj + layout["hp"])
            team = i32(self.h, obj + layout["team"])
            if hp is None or team is None or not (1 <= hp <= 150 and 1 <= team <= 5):
                continue
            pos = vec3(self.h, obj + layout["pos"])
            if not valid_pos(pos):
                continue
            found.append({"slot": index, "hp": hp, "team": team, "name": "P{}".format(index),
                          "pos": list(pos), "obj": obj})
        return found

    def probe_array(self):
        self.layout = None
        self.layout_hits = 0
        if not self.h:
            return []
        best = []
        best_name = None
        for base in self._array_bases():
            for layout in ARRAY_LAYOUTS:
                for check in (True, False):
                    found = self._read_layout(base, layout, check)
                    if len(found) > len(best):
                        best = found
                        best_name = "{} @{} serial={}".format(layout["name"], hex(base), check)
                        self.layout = (base, layout, check)
        self.layout_hits = len(best)
        if best_name:
            self.log("array", layout=best_name, n=len(best))
        else:
            self.log("array_empty")
        return best

    def read_array_cached(self):
        if not self.layout:
            return self.probe_array()
        base, layout, check = self.layout
        found = self._read_layout(base, layout, check)
        if len(found) < max(1, self.layout_hits // 3):
            return self.probe_array()
        return found

    def get_players_legacy(self):
        if not self.h:
            return []
        res = u32(self.h, self.gbase + PLAYER_RES)
        if not is_ptr(res):
            return []
        out = []
        for index in range(64):
            hp = i32(self.h, res + RES_HP + index * 4)
            team = i32(self.h, res + RES_TEAM + index * 4)
            if hp is None or team is None or not (1 <= hp <= 150 and 1 <= team <= 5):
                continue
            name = "P{}".format(index)
            for stride in (8, 4):
                ptr = u32(self.h, res + RES_NAME + index * stride)
                if is_ptr(ptr):
                    text = read_str(self.h, ptr)
                    if text:
                        name = text
                        break
            out.append({"slot": index, "hp": hp, "team": team, "name": name})
        return out

    def _dedupe(self, players):
        named = {}
        extras = []
        for player in players:
            if placeholder_name(player["name"], player["slot"]):
                if player["hp"] > 1 or player.get("pos"):
                    extras.append(player)
                continue
            key = player["name"].strip().lower()
            old = named.get(key)
            if old is None or player["hp"] > old["hp"] or (player.get("pos") and not old.get("pos") and player["hp"] >= old["hp"]):
                named[key] = player
        return list(named.values()) + extras

    def _upgrade_slot(self):
        if self.my_slot is None:
            return
        me = next((p for p in self.players_raw if p["slot"] == self.my_slot), None)
        if not me or placeholder_name(me["name"], me["slot"]) or me["hp"] > 1:
            if me:
                self.my_team = me["team"]
            return
        key = me["name"].strip().lower()
        better = [p for p in self.players_raw
                  if p["name"].strip().lower() == key and p["hp"] > me["hp"]]
        if not better:
            return
        best = max(better, key=lambda p: p["hp"])
        self.log("slot_fix", frm=self.my_slot, to=best["slot"], name=best["name"], hp=best["hp"])
        self.my_slot = best["slot"]
        self.my_team = best["team"]

    def rebuild_players(self):
        legacy = self.get_players_legacy()
        array = []
        if self.player_mode in ("both", "array"):
            array = self.read_array_cached()
        by_slot = {p["slot"]: p for p in array}
        if self.player_mode == "array" and array:
            merged = []
            names = {p["slot"]: p for p in legacy}
            for player in array:
                row = dict(player)
                if player["slot"] in names:
                    row["name"] = names[player["slot"]]["name"]
                    row["hp"] = names[player["slot"]]["hp"]
                    row["team"] = names[player["slot"]]["team"]
                merged.append(row)
        else:
            merged = []
            for player in legacy:
                row = dict(player)
                other = by_slot.get(player["slot"])
                if other and other.get("pos"):
                    row["pos"] = other["pos"]
                    row["obj"] = other.get("obj")
                merged.append(row)
            if self.enemy_pos and self.enemy_hp is not None:
                far = all(dist3(self.enemy_pos, p.get("pos")) > 40 for p in merged if p.get("pos"))
                if far or not any(p.get("pos") for p in merged):
                    merged.append({"slot": -1, "hp": self.enemy_hp, "team": 0,
                                   "name": "CE", "pos": list(self.enemy_pos)})
        self.players_raw = merged
        self._upgrade_slot()
        shown = list(merged)
        if self.hide_dead:
            shown = [p for p in shown if p["hp"] > 1 or p["slot"] == self.my_slot]
        shown = self._dedupe(shown)
        shown.sort(key=lambda p: p["slot"] if p["slot"] >= 0 else 99)
        self.players = shown

    def update_info(self):
        self.info.delete("1.0", "end")
        alive = [p for p in self.players if p["hp"] > 1]
        with_pos = [p for p in self.players if p.get("pos")]
        self.info.insert("end", "w2s={}  src={}  layout_hits={}\n".format(
            self.w2s_mode, self.matrix_src, self.layout_hits), "head")
        self.info.insert("end", "raw={}  shown={}  alive={}  pos={}\n".format(
            len(self.players_raw), len(self.players), len(alive), len(with_pos)), "head")
        self.info.insert("end", "\n★ ME\n", "me")
        if valid_pos(self.my_pos):
            self.info.insert("end", "  POS ({:.1f}, {:.1f}, {:.1f})\n".format(*self.my_pos), "me")
        self.info.insert("end", "  HP {}   yaw {:.1f}  pitch {:.1f}\n".format(
            self.local_hp, self.my_yaw or 0, self.my_pitch or 0), "me")
        self.info.insert("end", "  slot {}  team {}\n".format(self.my_slot, self.my_team), "me")
        self.info.insert("end", "  FOV {:.0f}  eye {:.0f}  H {:.0f}  yaw{} pitch{}\n".format(
            self.fov, self.eye_z, self.player_h,
            "+" if self.yaw_sign > 0 else "-", "+" if self.pitch_sign > 0 else "-"), "head")
        self.info.insert("end", "\nPLAYERS\n", "head")
        for player in self.players:
            mark = " ★" if player["slot"] == self.my_slot else ""
            pos = player.get("pos")
            if pos and valid_pos(self.my_pos):
                meters = dist3(pos, self.my_pos) * self.unit_to_m
                self.info.insert("end", "{:>2} {:>3}hp t{} {:>5.1f}m {}{}\n".format(
                    player["slot"], player["hp"], player["team"], meters, player["name"], mark), "en" if mark == "" else "me")
            else:
                self.info.insert("end", "{:>2} {:>3}hp t{} {} {}{}\n".format(
                    player["slot"], player["hp"], player["team"], player["name"],
                    "DEAD" if player["hp"] <= 1 else "no-pos", mark), "bad" if not pos else "head")

    def eye(self):
        if not valid_pos(self.my_pos):
            return None
        return (self.my_pos[0], self.my_pos[1], self.my_pos[2] + self.eye_z)

    def project(self, pos, gw, gh):
        if self.w2s_mode == "matrix" and self.matrix and self.matrix_src != "OWN":
            return w2s_col(self.matrix, pos, gw, gh)
        eye = self.eye()
        if not eye:
            return None, None, False
        sx, sy, depth = w2s_cam(eye, self.my_yaw or 0, self.my_pitch or 0, pos, gw, gh,
                                self.fov, self.yaw_sign, self.pitch_sign)
        if sx is None:
            return None, None, False
        return sx, sy, depth > 1

    def test_matrix(self):
        if not self.h or not valid_pos(self.my_pos):
            self.read_my_state()
        if not valid_pos(self.my_pos):
            return False
        gw, gh = float(self.game_w), float(self.game_h)
        best = None
        for name, addr in (("REN+6D0", self.gbase + RENDERER + REN_MAT),
                           ("MATRIX", self.gbase + MATRIX_RVA)):
            mat = read_mat4(self.h, addr)
            quality = score_matrix(mat)
            if quality < 5:
                continue
            sx, sy, front = w2s_col(mat, self.my_pos, gw, gh)
            if sx is None:
                continue
            dist = math.hypot(sx - gw / 2, sy - gh / 2)
            score = quality + max(0, 300 - dist)
            if best is None or score > best[0]:
                best = (score, name, mat, dist)
        if not best:
            self.matrix = None
            self.matrix_src = "-"
            self.log("matrix_none_use_cam")
            return False
        _score, name, mat, dist = best
        self.matrix, self.matrix_src = mat, name
        self.log("matrix", src=name, dist=round(dist, 1))
        return True

    def connect(self):
        pid, name, base, _size = find_game()
        if not pid:
            self.status.config(text="CMLauncher با clientmod_game.dll پیدا نشد", fg="#f48771")
            return
        handle = open_proc(pid)
        if not handle:
            self.status.config(text="Access denied — پایتون را Run as administrator اجرا کن", fg="#f48771")
            return
        self.h, self.pid, self.gbase = handle, pid, base
        self.cbase = find_client_base(pid)
        self.game_w, self.game_h = find_game_res(pid)
        self.layout = None
        self.read_my_state()
        self.read_enemy_ce()
        self.rebuild_players()
        self.test_matrix()
        self.update_info()
        pos_n = sum(1 for p in self.players if p.get("pos"))
        self.log("connected", pid=pid, gbase=hex(base),
                 cbase=hex(self.cbase) if self.cbase else None,
                 shown=len(self.players), pos=pos_n, res="{}x{}".format(self.game_w, self.game_h))
        self.status.config(
            text="متصل {}x{}  |  بازیکن {}  |  مختصات {}  |  برو ②".format(
                self.game_w, self.game_h, len(self.players), pos_n),
            fg="#4ec9b0" if pos_n else "#d7ba7d")

    def pick_self(self):
        if not self.h:
            return
        self.read_enemy_ce()
        self.rebuild_players()
        self.update_info()
        if not self.players:
            messagebox.showwarning("!", "بازیکنی نیست")
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("اسلات خودت — اگر اسمت دو بار است HP بالاتر را بگیر")
        dlg.geometry("560x420")
        dlg.configure(bg="#1a1a1a")
        dlg.grab_set()
        lb = tk.Listbox(dlg, font=("Consolas", 10), bg="#1e1e1e", fg="#eee")
        lb.pack(fill="both", expand=True, padx=8, pady=8)
        for player in self.players:
            pos = player.get("pos")
            extra = " ({:.0f},{:.0f},{:.0f})".format(*pos) if pos else ""
            lb.insert("end", "slot {:>2} | hp{:>3} | t{} | {}{}".format(
                player["slot"], player["hp"], player["team"], player["name"], extra))
        picked = {"slot": None}

        def ok():
            sel = lb.curselection()
            if sel:
                picked["slot"] = self.players[sel[0]]["slot"]
            dlg.destroy()

        tk.Button(dlg, text="همین", command=ok, bg="#16825d", fg="white", relief="flat").pack(pady=6)
        dlg.wait_window()
        if picked["slot"] is None:
            return
        self._apply_slot(picked["slot"])

    def _apply_slot(self, slot):
        self.my_slot = slot
        for player in self.players_raw + self.players:
            if player["slot"] == slot:
                self.my_team = player["team"]
                break
        self._upgrade_slot()
        self.log("picked", slot=self.my_slot, team=self.my_team)
        self.update_info()
        self.status.config(text="اسلات {} تیم {} — ESP را بزن".format(self.my_slot, self.my_team), fg="#4ec9b0")

    def pick_nearest(self):
        if not self.h or not valid_pos(self.my_pos):
            messagebox.showwarning("!", "اول اتصال، و داخل مپ باش")
            return
        self.rebuild_players()
        best = None
        for player in self.players_raw:
            if not player.get("pos") or player["hp"] <= 1:
                continue
            dist = dist3(player["pos"], self.my_pos)
            if best is None or dist < best[0]:
                best = (dist, player)
        if not best or best[0] > 120:
            messagebox.showinfo("!", "مختصات نزدیک خودت پیدا نشد. دستی انتخاب کن.\narray hits = {}".format(self.layout_hits))
            return
        self._apply_slot(best[1]["slot"])
        self.log("nearest", slot=best[1]["slot"], dist=round(best[0], 1))

    def scan_players(self):
        if not self.h:
            return
        self.layout = None
        self.read_my_state()
        self.read_enemy_ce()
        self.rebuild_players()
        self.update_info()
        pos_n = sum(1 for p in self.players if p.get("pos"))
        self.status.config(text="shown={} alive_pos={} layout={}".format(
            len(self.players), pos_n, self.layout_hits), fg="#4ec9b0")

    def toggle_esp(self):
        if not self.h or self.my_slot is None:
            messagebox.showwarning("!", "اول اتصال و انتخاب خودت")
            return
        self.esp_running = not self.esp_running
        if self.esp_running:
            self.btn_esp.config(text="توقف", bg="#a02020")
            self.log("esp_on", w2s=self.w2s_mode, players=self.player_mode)
            self._tick()
        else:
            self.btn_esp.config(text="④ ESP", bg="#0e639c")
            self.save_log()

    def draw_players(self, gw, gh, sx_s, sy_s, cw, ch):
        drawn = 0
        for player in self.players:
            if player["slot"] == self.my_slot:
                continue
            pos = player.get("pos")
            if not pos:
                continue
            enemy = self.my_team is None or player["team"] in (0, None) or player["team"] != self.my_team
            if self.enemies_only and not enemy:
                continue
            units = dist3(pos, self.my_pos) if valid_pos(self.my_pos) else 0
            if units > self.max_dist:
                continue
            feet = tuple(pos)
            head = (feet[0], feet[1], feet[2] + self.player_h)
            fx, fy, front = self.project(feet, gw, gh)
            hx, hy, _hfront = self.project(head, gw, gh)
            if fx is None or hx is None:
                continue
            on = 0 <= fx <= gw and 0 <= fy <= gh
            if not on:
                if not (self.edge_marks and front):
                    continue
                fx = min(max(fx, 20), gw - 20)
                fy = min(max(fy, 20), gh - 20)
                hx, hy = fx, fy - 36
            box_h = abs((fy - hy) * sy_s)
            if box_h < 6 or box_h > ch * 0.85:
                continue
            box_w = max(box_h * 0.45, 10)
            gx, gy = fx * sx_s, fy * sy_s
            color = "#FF4444" if enemy else "#44DDFF"
            self.canvas.create_rectangle(gx - box_w / 2, gy - box_h, gx + box_w / 2, gy,
                                         outline=color, width=2)
            self.canvas.create_text(gx, gy - box_h - 12, text="{} {}".format(player["name"], player["hp"]),
                                    fill=color, font=("Consolas", 9, "bold"))
            self.canvas.create_text(gx, gy + 12, text="{:.0f}u  {:.1f}m".format(units, units * self.unit_to_m),
                                    fill=color, font=("Consolas", 8))
            drawn += 1
        return drawn

    def _tick(self):
        if not self.esp_running:
            return
        try:
            self.read_my_state()
            if self.w2s_mode == "matrix":
                self.test_matrix()
            self.read_enemy_ce()
            self.rebuild_players()
            self.update_info()
            gw, gh = float(self.game_w), float(self.game_h)
            cw = max(self.canvas.winfo_width(), 640)
            ch = max(self.canvas.winfo_height(), 360)
            sx_s, sy_s = cw / gw, ch / gh
            self.canvas.delete("all")
            self.canvas.create_line(cw / 2 - 10, ch / 2, cw / 2 + 10, ch / 2, fill="#4ec9b0")
            self.canvas.create_line(cw / 2, ch / 2 - 10, cw / 2, ch / 2 + 10, fill="#4ec9b0")
            drawn = self.draw_players(gw, gh, sx_s, sy_s, cw, ch)
            pos_n = sum(1 for p in self.players if p.get("pos"))
            self.canvas.create_text(
                8, 8, anchor="nw", fill="#4ec9b0", font=("Consolas", 9),
                text="{} | shown {} | pos {} | boxes {} | slot {} t{} | {:.0f}x{:.0f}".format(
                    self.w2s_mode, len(self.players), pos_n, drawn, self.my_slot, self.my_team, gw, gh))
            me = next((p for p in self.players if p["slot"] == self.my_slot), None)
            me_name = me["name"] if me else "?"
            self.canvas.create_text(8, 26, anchor="nw", fill="#00FF88", font=("Consolas", 9),
                                    text="ME {} hp {}  ({})".format(
                                        me_name, self.local_hp,
                                        "{:.0f},{:.0f},{:.0f}".format(*self.my_pos) if valid_pos(self.my_pos) else "?"))
            self.status.config(text="ESP | shown {} | pos {} | box {} | {}".format(
                len(self.players), pos_n, drawn, self.matrix_src if self.w2s_mode == "matrix" else "cam"),
                               fg="#4ec9b0")
        except Exception as exc:
            self.log("err", e=str(exc))
        if self.esp_running:
            self.root.after(50, self._tick)

    def save_log(self):
        path = os.path.join(LOG_DIR, "esp152_{}.json".format(datetime.now().strftime("%Y%m%d_%H%M%S")))
        try:
            json.dump({
                "ver": "15.2",
                "time": datetime.now().isoformat(),
                "w2s_mode": self.w2s_mode,
                "player_mode": self.player_mode,
                "matrix_src": self.matrix_src,
                "layout_hits": self.layout_hits,
                "game": [self.game_w, self.game_h],
                "calib": {"fov": self.fov, "eye_z": self.eye_z, "player_h": self.player_h,
                          "yaw_sign": self.yaw_sign, "pitch_sign": self.pitch_sign,
                          "unit_to_m": self.unit_to_m},
                "my_pos": list(self.my_pos) if self.my_pos else None,
                "my_slot": self.my_slot, "my_team": self.my_team, "local_hp": self.local_hp,
                "enemy_hp": self.enemy_hp,
                "enemy_pos": list(self.enemy_pos) if self.enemy_pos else None,
                "players": self.players,
                "events": list(self.events)[-60:],
            }, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
            self.log("saved", path=path)
        except Exception as exc:
            self.log("save_err", e=str(exc))


def main():
    if sys.platform != "win32":
        sys.exit("فقط ویندوز")
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
