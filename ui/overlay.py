import tkinter as tk
import math
import random
import threading
from enum import Enum
from datetime import datetime

class JarvisState(Enum):
    IDLE      = "idle"
    LISTENING = "listening"
    THINKING  = "thinking"
    SPEAKING  = "speaking"

# ─── Colour palette ────────────────────────────────────────────────────────────
BG    = "#020d1a"
C1    = "#00cfff"
C2    = "#0044dd"
C3    = "#00ffaa"
C4    = "#ffffff"
DIM   = "#0d3050"
GLOW  = "#001833"
WARN  = "#ff8800"
RED   = "#ff3333"
GRID  = "#040f1e"


def _dim(color: str, factor: float) -> str:
    r = int(color[1:3], 16); g = int(color[3:5], 16); b = int(color[5:7], 16)
    return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"


# ══════════════════════════════════════════════════════════════════════════════
#  SMALL ICON (bottom-right corner)
# ══════════════════════════════════════════════════════════════════════════════
class JarvisIcon:
    SIZE = 64
    def __init__(self, on_click):
        self.root = tk.Toplevel()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 1.0)
        self.root.configure(bg=BG)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        s  = self.SIZE
        self.root.geometry(f"{s}x{s}+{sw-s-14}+{sh-s-52}")
        self.cv = tk.Canvas(self.root, width=s, height=s, bg=BG, highlightthickness=0)
        self.cv.pack()
        self._a = 0.0; self._p = 0.0
        self._state = JarvisState.IDLE
        self._on_click_cb = on_click
        self._drag_data = {"x": 0, "y": 0, "dragged": False}
        self.cv.bind("<ButtonPress-1>", self._on_press)
        self.cv.bind("<B1-Motion>", self._on_drag)
        self.cv.bind("<ButtonRelease-1>", self._on_release)
        self._loop()

    def _on_press(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self._drag_data["dragged"] = False

    def _on_drag(self, event):
        deltax = event.x - self._drag_data["x"]
        deltay = event.y - self._drag_data["y"]
        if abs(deltax) > 3 or abs(deltay) > 3:
            self._drag_data["dragged"] = True
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def _on_release(self, event):
        if not self._drag_data["dragged"]:
            self._on_click_cb()

    def _loop(self):
        self._a = (self._a - 3) % 360; self._p += 0.13
        self._draw(); self.root.after(35, self._loop)

    def _draw(self):
        c = self.cv; c.delete("all")
        cx = cy = self.SIZE // 2
        col = {JarvisState.IDLE: C1, JarvisState.LISTENING: C3,
               JarvisState.THINKING: C2, JarvisState.SPEAKING: WARN}.get(self._state, C1)
        r = 26 + math.sin(self._p * 0.6) * 2
        c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=_dim(col, 0.25), width=10)
        c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=col, width=1)
        c.create_arc(cx-24, cy-24, cx+24, cy+24, start=self._a, extent=230, outline=col, width=2, style=tk.ARC)
        c.create_arc(cx-17, cy-17, cx+17, cy+17, start=(-self._a*.7)%360, extent=160, outline=C2, width=1, style=tk.ARC)
        dr = 5 + math.sin(self._p*2)*2
        c.create_oval(cx-dr, cy-dr, cx+dr, cy+dr, fill=col, outline="")

    def set_state(self, s): self._state = s


# ══════════════════════════════════════════════════════════════════════════════
#  FULL-SCREEN HUD
# ══════════════════════════════════════════════════════════════════════════════
class JarvisOverlay:
    def __init__(self, on_close=None):
        self.root = tk.Toplevel()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 1.0)
        self.root.configure(bg=BG)

        self.W = self.root.winfo_screenwidth()
        self.H = self.root.winfo_screenheight()
        self.root.geometry(f"{self.W}x{self.H}+0+0")

        self.cv = tk.Canvas(self.root, width=self.W, height=self.H, bg=BG, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)

        self._cx   = self.W // 2
        self._cy   = self.H // 2
        self._a    = 0.0
        self._p    = 0.0
        self._state    = JarvisState.IDLE
        self._user_txt = ""
        self._ai_txt   = ""
        self._cmd_log  = []          # list of (user, ai) tuples
        self._stats    = {}          # system stats dict
        self._bars     = [random.randint(10, 90) for _ in range(40)]
        self._on_close = on_close

        # ── close button ──────────────────────────────────────────────────────
        btn = tk.Label(self.root, text=" ✕ ", fg=RED, bg=BG,
                       font=("Consolas", 14, "bold"), cursor="hand2")
        btn.place(x=self.W - 52, y=10)
        btn.bind("<Button-1>", lambda e: self._close())
        btn.bind("<Enter>",    lambda e: btn.config(fg=C4, bg=RED))
        btn.bind("<Leave>",    lambda e: btn.config(fg=RED, bg=BG))
        self.root.bind("<Escape>", lambda e: self._close())

        self._loop()

    def _close(self):
        self.root.withdraw()
        if self._on_close: self._on_close()

    def _loop(self):
        self._a  = (self._a - 1.5) % 360
        self._p += 0.06
        # animate bars
        for i in range(len(self._bars)):
            if random.random() < 0.08:
                self._bars[i] = max(8, min(95, self._bars[i] + random.randint(-15, 15)))
        self._draw()
        self.root.after(35, self._loop)

    # ── helpers ───────────────────────────────────────────────────────────────
    def _bar(self, x, y, w, h, pct, col, bg=GLOW, label=""):
        c = self.cv
        c.create_rectangle(x, y, x+w, y+h, fill=bg, outline=_dim(col, 0.3))
        filled = int(w * pct / 100)
        if filled > 0:
            c.create_rectangle(x+1, y+1, x+filled, y+h-1, fill=col, outline="")
        if label:
            c.create_text(x+w+6, y+h//2, text=label, fill=col,
                          font=("Consolas", 8), anchor="w")

    def _panel_border(self, x, y, w, h, title=""):
        c = self.cv
        c.create_rectangle(x, y, x+w, y+h, outline=DIM, width=1)
        # corner ticks
        tl = 12
        for ox, oy, dx, dy in [(x,y,1,1),(x+w,y,-1,1),(x,y+h,1,-1),(x+w,y+h,-1,-1)]:
            c.create_line(ox, oy, ox+dx*tl, oy, fill=C1, width=2)
            c.create_line(ox, oy, ox, oy+dy*tl, fill=C1, width=2)
        if title:
            c.create_text(x+16, y-1, text=f" {title} ", fill=C1,
                          font=("Consolas", 8, "bold"), anchor="sw")

    def _wrap(self, text, chars):
        words = text.split(); lines = []; line = ""
        for w in words:
            if len(line)+len(w)+1 > chars: lines.append(line); line = w
            else: line += (" " if line else "") + w
        if line: lines.append(line)
        return "\n".join(lines[:5])

    # ── main draw ─────────────────────────────────────────────────────────────
    def _draw(self):
        c  = self.cv; c.delete("all")
        W, H = self.W, self.H
        cx, cy = self._cx, self._cy
        p, a   = self._p, self._a
        st     = self._state

        COL = {JarvisState.IDLE: C1, JarvisState.LISTENING: C3,
               JarvisState.THINKING: C2, JarvisState.SPEAKING: WARN}.get(st, C1)
        LABEL = {JarvisState.IDLE: "STANDBY", JarvisState.LISTENING: "LISTENING...",
                 JarvisState.THINKING: "PROCESSING...", JarvisState.SPEAKING: "SPEAKING..."}.get(st, "STANDBY")

        # ── background grid ───────────────────────────────────────────────────
        for x in range(0, W, 50): c.create_line(x, 0, x, H, fill=GRID, width=1)
        for y in range(0, H, 50): c.create_line(0, y, W, y, fill=GRID, width=1)

        # subtle radial gradient behind center
        for r in [280, 260, 230, 190]:
            alpha = 0.04 + (280-r)*0.0003
            c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=_dim(COL, alpha), width=r//5)

        # ── TOP BAR ───────────────────────────────────────────────────────────
        c.create_rectangle(0, 0, W, 46, fill="#030f1f", outline=DIM)
        c.create_line(0, 46, W, 46, fill=_dim(C1, 0.4), width=1)
        now = datetime.now().strftime("%A, %B %d %Y  │  %H:%M:%S")
        c.create_text(24, 23, text="J.A.R.V.I.S  //  JUST A RATHER VERY INTELLIGENT SYSTEM  //  v2.0",
                      fill=C1, font=("Consolas", 11, "bold"), anchor="w")
        c.create_text(W-200, 23, text=now, fill=_dim(C4, 0.6), font=("Consolas", 9), anchor="w")

        # ── LEFT PANEL — SYSTEM STATUS ────────────────────────────────────────
        PW = 280; PX = 24; PY = 64; PH = H - 200
        self._panel_border(PX, PY, PW, PH, "SYSTEM STATUS")

        iy = PY + 22
        def stat_row(label, value, col=_dim(C4, 0.7)):
            nonlocal iy
            c.create_text(PX+14, iy, text=label, fill=_dim(C1, 0.5),
                          font=("Consolas", 8), anchor="w")
            c.create_text(PX+PW-14, iy, text=value, fill=col,
                          font=("Consolas", 9, "bold"), anchor="e")
            iy += 20

        s = self._stats
        cpu  = s.get("cpu",  0)
        rp   = s.get("ram_pct", 0)
        dp   = s.get("disk_pct", 0)
        ru   = s.get("ram_used", 0)
        rt   = s.get("ram_total", 0)
        df   = s.get("disk_free", 0)
        dt   = s.get("disk_total", 0)
        pr   = s.get("processes", 0)
        up   = s.get("uptime", "N/A")
        net  = s.get("network", "N/A")

        stat_row("CPU LOAD",    f"{cpu}%",         C3 if cpu < 70 else WARN)
        self._bar(PX+14, iy, PW-28, 8, cpu, C3 if cpu < 70 else WARN); iy += 18
        stat_row("RAM USAGE",   f"{ru}/{rt} GB",   C1 if rp < 80 else WARN)
        self._bar(PX+14, iy, PW-28, 8, rp,  C1 if rp < 80 else WARN);  iy += 18
        stat_row("DISK C:",     f"{df} GB free",   C1 if dp < 85 else RED)
        self._bar(PX+14, iy, PW-28, 8, dp,  C1 if dp < 85 else RED);   iy += 22
        c.create_line(PX+14, iy, PX+PW-14, iy, fill=DIM, width=1); iy += 12
        stat_row("PROCESSES",   str(pr))
        stat_row("UPTIME",      up,                _dim(C3, 0.8))
        stat_row("NETWORK",     net,               _dim(C1, 0.8))
        stat_row("LLM ENGINE",  "OLLAMA / LLAMA3", _dim(C3, 0.8))
        stat_row("STATUS",      "ONLINE",          C3)

        # ── RIGHT PANEL — COMMAND LOG ─────────────────────────────────────────
        RPW = 280; RPX = W - RPW - 24; RPY = 64; RPH = H - 200
        self._panel_border(RPX, RPY, RPW, RPH, "COMMAND LOG")
        ly = RPY + 22
        max_log = 6
        recent = self._cmd_log[-max_log:] if self._cmd_log else []
        for i, (user, ai) in enumerate(recent):
            alpha = 0.4 + (i / max(len(recent), 1)) * 0.6
            c.create_text(RPX+14, ly, text=f"› {user[:30]}", fill=_dim(C3, alpha),
                          font=("Consolas", 8, "italic"), anchor="w")
            ly += 16
            ai_short = ai[:120] if ai else "..."
            wrapped = self._wrap(ai_short, 32)
            for ln in wrapped.split("\n"):
                c.create_text(RPX+20, ly, text=ln, fill=_dim(C1, alpha*0.8),
                              font=("Consolas", 8), anchor="w")
                ly += 14
            ly += 6
            if ly > RPY + RPH - 20:
                break

        # ── CENTRAL RINGS ─────────────────────────────────────────────────────
        # Ring 0 — faint outermost glow
        r0 = 270 + math.sin(p*0.4)*5
        c.create_oval(cx-r0, cy-r0, cx+r0, cy+r0, outline=_dim(COL, 0.06), width=28)
        c.create_oval(cx-r0, cy-r0, cx+r0, cy+r0, outline=_dim(COL, 0.4), width=1)

        # Ring 1 — main segmented spinner
        r1 = 240
        for i in range(36):
            ang = (a + i*10) % 360
            alpha = 0.9 if i%9==0 else (0.55 if i%3==0 else 0.18)
            c.create_arc(cx-r1, cy-r1, cx+r1, cy+r1,
                         start=ang, extent=8, outline=_dim(COL, alpha), width=2, style=tk.ARC)
        # tick marks
        for deg in range(0, 360, 5):
            rad  = math.radians(deg)
            tlen = 16 if deg%90==0 else (9 if deg%30==0 else 4)
            tcol = COL if deg%90==0 else (_dim(C1, 0.5) if deg%30==0 else DIM)
            x1 = cx + r1*math.cos(rad); y1 = cy + r1*math.sin(rad)
            x2 = cx + (r1-tlen)*math.cos(rad); y2 = cy + (r1-tlen)*math.sin(rad)
            c.create_line(x1, y1, x2, y2, fill=tcol, width=1)
        # degree labels every 45°
        for deg in range(0, 360, 45):
            rad = math.radians(deg)
            lx  = cx + (r1+20)*math.cos(rad); ly2 = cy + (r1+20)*math.sin(rad)
            c.create_text(lx, ly2, text=f"{deg:03d}°", fill=_dim(C1, 0.45),
                          font=("Consolas", 7), anchor="center")

        # Ring 2 — counter-rotating mid
        r2 = 192; a2 = (-a*1.1)%360
        c.create_arc(cx-r2, cy-r2, cx+r2, cy+r2, start=a2, extent=210, outline=C2, width=2, style=tk.ARC)
        c.create_arc(cx-r2, cy-r2, cx+r2, cy+r2, start=(a2+230)%360, extent=100, outline=_dim(C3, 0.7), width=1, style=tk.ARC)
        c.create_arc(cx-r2, cy-r2, cx+r2, cy+r2, start=(a2+340)%360, extent=16, outline=COL, width=4, style=tk.ARC)

        # Ring 3 — fast inner spinner
        r3 = 148; a3 = (a*2.2)%360
        c.create_arc(cx-r3, cy-r3, cx+r3, cy+r3, start=a3, extent=150, outline=_dim(COL, 0.9), width=1, style=tk.ARC)
        c.create_arc(cx-r3, cy-r3, cx+r3, cy+r3, start=(a3+175)%360, extent=90, outline=_dim(C2, 0.6), width=2, style=tk.ARC)

        # Ring 4 — pulsing glow halo
        r4 = 108 + math.sin(p)*7
        c.create_oval(cx-r4, cy-r4, cx+r4, cy+r4, outline=_dim(COL, 0.8), width=1)
        c.create_oval(cx-r4+5, cy-r4+5, cx+r4-5, cy+r4-5, outline=_dim(COL, 0.2), width=8)

        # inner core
        rc = 72
        c.create_oval(cx-rc, cy-rc, cx+rc, cy+rc, fill=GLOW, outline=COL, width=2)

        # ── listening bars inside core ─────────────────────────────────────────
        if st == JarvisState.LISTENING:
            for i in range(7):
                ox = (i-3)*14
                bh = 6 + math.sin(p*2.5 + i*0.8)*18
                c.create_rectangle(cx+ox-4, cy-bh, cx+ox+4, cy+bh, fill=C3, outline="")

        # scanning line when thinking
        if st == JarvisState.THINKING:
            sy = cy - rc + int(p*28) % (rc*2)
            c.create_line(cx-rc+4, sy, cx+rc-4, sy, fill=_dim(C3, 0.7), width=1)

        # ── state label ───────────────────────────────────────────────────────
        c.create_text(cx, cy+10, text=LABEL, fill=COL, font=("Consolas", 12, "bold"))

        # ── user text ─────────────────────────────────────────────────────────
        if self._user_txt:
            c.create_text(cx, cy-r1-30,
                          text=f"› {self._user_txt[:70]}",
                          fill=_dim(C3, 0.85), font=("Consolas", 10, "italic"),
                          width=500, anchor="center")

        # ── AI response below rings ───────────────────────────────────────────
        if self._ai_txt:
            short = self._ai_txt[:250]
            c.create_text(cx, cy+r1+40,
                          text=short, fill=COL,
                          font=("Consolas", 11), width=560, anchor="center")

        # ── BOTTOM — frequency analyzer ───────────────────────────────────────
        BH = 80; BY = H - BH - 8
        c.create_rectangle(0, BY-4, W, H, fill="#020c18", outline="")
        c.create_line(0, BY-4, W, BY-4, fill=DIM, width=1)
        bw = W // len(self._bars)
        for i, val in enumerate(self._bars):
            bx  = i * bw
            bh2 = int(val / 100 * (BH - 8))
            col2 = _dim(C1, 0.3 + val/100*0.7)
            c.create_rectangle(bx+2, BY + (BH-8) - bh2, bx+bw-2, BY + BH - 8,
                                fill=col2, outline="")
        c.create_text(16, BY + BH//2, text="FREQ ANALYSIS", fill=DIM, font=("Consolas", 7), anchor="w")
        c.create_text(W-16, BY + BH//2, text="[ ESC ] CLOSE",  fill=DIM, font=("Consolas", 7), anchor="e")

        # ── HUD corner brackets (full screen) ────────────────────────────────
        blen = 36
        for bx, by, dx, dy in [(0,0,1,1),(W,0,-1,1),(0,H,1,-1),(W,H,-1,-1)]:
            c.create_line(bx, by, bx+dx*blen, by, fill=C1, width=2)
            c.create_line(bx, by, bx, by+dy*blen, fill=C1, width=2)

    # ── public API ────────────────────────────────────────────────────────────
    def set_state(self, s: JarvisState):
        self._state = s

    def set_user_text(self, t: str):
        self._user_txt = t
        self._ai_txt   = ""

    def set_jarvis_text(self, t: str):
        self._ai_txt = t
        if self._user_txt or t:
            self._cmd_log.append((self._user_txt, t))
            if len(self._cmd_log) > 20:
                self._cmd_log = self._cmd_log[-20:]

    def update_stats(self, stats: dict):
        self._stats = stats

    def show(self):
        self.root.deiconify()
        self.root.attributes("-alpha", 1.0)

    def hide(self):
        self._close()


# ══════════════════════════════════════════════════════════════════════════════
#  APP CONTROLLER
# ══════════════════════════════════════════════════════════════════════════════
class JarvisApp:
    def __init__(self, on_query_callback):
        self.root = tk.Tk()
        self.root.withdraw()
        self._on_query  = on_query_callback
        self._hud_open  = False

        self.icon    = JarvisIcon(on_click=self.toggle_overlay)
        self.overlay = JarvisOverlay(on_close=self._on_hud_closed)
        self.overlay.root.withdraw()

    def toggle_overlay(self):
        if self._hud_open:
            self.overlay.hide()
        else:
            self._hud_open = True
            self.overlay.show()

    def _on_hud_closed(self):
        self._hud_open = False

    def set_state(self, s: JarvisState):
        self.icon.set_state(s)
        self.overlay.set_state(s)
        if s == JarvisState.LISTENING and not self._hud_open:
            self.toggle_overlay()

    def set_user_text(self, t):    self.overlay.set_user_text(t)
    def set_jarvis_text(self, t):  self.overlay.set_jarvis_text(t)
    def update_stats(self, stats): self.overlay.update_stats(stats)

    def run(self):
        self.root.mainloop()
