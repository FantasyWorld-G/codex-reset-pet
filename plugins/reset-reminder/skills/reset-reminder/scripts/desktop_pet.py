"""Local Windows companion. Reads only the snapshot written by Codex; no network."""
import argparse
import ctypes
import hashlib
import json
import math
import os
import sys
import logging
import faulthandler
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time
import tkinter as tk
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw, ImageFont
from functools import lru_cache
from collections import deque
from types import SimpleNamespace
from layered_sprite import LayeredSprite, premultiplied_bgra
from animation_state import AnimationStateMachine, State, animation_pose, sleep_particles

from check_reset import CN, account_snapshot, card_snapshot, epoch, read_json, write_json

TRANSPARENT = '#ff00ff'
BG = '#182735'
SURFACE = '#223545'
MUTED = '#93a8b8'
TEXT = '#edf4f8'
SPRITE_SIZE = 288
PET_X, PET_Y = 275,449
TARGET_FPS = 60
TIBO_URL = 'https://codex-reset.com/zh/tibo'


def time_color(seconds):
    """Continuous neutral -> gold -> orange -> red across the last 24 hours."""
    if seconds is None:
        return MUTED
    stops = [(0, (248, 72, 83)), (3600, (246, 92, 84)),
             (21600, (251, 159, 81)), (86400, (237, 205, 113)),
             (172800, (193, 210, 223))]
    seconds = max(0, seconds)
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if seconds <= b:
            fraction = max(0, (seconds-a)/(b-a))
            rgb = [round(x+(y-x)*fraction) for x, y in zip(ca, cb)]
            return '#%02x%02x%02x' % tuple(rgb)
    return '#c1d2df'


def remaining(seconds, expired):
    if seconds is None:
        return '等待账户同步'
    if seconds <= 0:
        return expired
    minutes = math.ceil(seconds/60)
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    return '还剩 ' + (f'{days}天 ' if days else '') + f'{hours}小时 {minutes}分钟'


def view_model(envelope, now):
    captured = epoch(envelope.get('captured_at'))
    if captured is None or captured > now+60:
        raise ValueError('账户快照时间无效')
    # Parse the historical snapshot, explicitly labelling its freshness below.
    account = account_snapshot(envelope, captured)
    stale = now-captured > 5400
    windows = [w for w in account['windows'] if w['resets_at'] is not None]
    quota = min(windows, key=lambda w: w['resets_at']) if windows else None
    raw_cards = envelope['usage'].get('rateLimitResetCredits')
    current_cards = card_snapshot(raw_cards, now)
    cards = current_cards['cards'] if current_cards is not None else []
    known_cards = [c for c in cards if c['expires_at'] is not None]
    card = min(known_cards, key=lambda c: c['expires_at']) if known_cards else None
    rows = []
    for title, deadline, detail, empty in (
        ('账户额度重置', quota['resets_at'] if quota else None,
         f"剩余额度 {quota['remaining_percent']:g}%" if quota and quota['remaining_percent'] is not None else '额度待同步', '重置时间未知'),
        ('重置卡到期', card['expires_at'] if card else None,
         f"有效卡 {len(cards)} 张 · 最早到期" if current_cards is not None else '重置卡待同步',
         '暂无有效重置卡' if current_cards is not None and not cards else '到期时间未知')):
        seconds = deadline-now if deadline is not None else None
        rows.append({'title': title, 'deadline': deadline, 'seconds': seconds,
                     'date': datetime.fromtimestamp(deadline, CN).strftime('%m/%d  %H:%M') if deadline is not None else empty,
                     'remaining': remaining(seconds, '已到预计时间 · 等待确认'),
                     'detail': detail, 'color': time_color(seconds) if not stale else MUTED})
    deadlines = [r['seconds'] for r in rows if r['seconds'] is not None]
    return {'rows': rows, 'stale': stale, 'captured': captured,
            'pet_color': time_color(min(deadlines)) if deadlines and not stale else MUTED,
            'footer': ('数据待同步 · 显示上次记录' if stale else '已同步 ' + datetime.fromtimestamp(captured, CN).strftime('%H:%M') + ' · 本机实时倒计时')}


def unavailable():
    return {'rows': [{'title': title, 'date': '等待账户同步', 'remaining': 'Codex 更新后会自动显示',
                       'detail': '', 'color': MUTED} for title in ('账户额度重置', '重置卡到期')],
            'pet_color': MUTED, 'stale': True, 'footer': '数据不可用 · 等待 Codex 同步'}


class Companion:
    WIDTH, HEIGHT = 370, 550

    def __init__(self, usage, settings, windowed=False):
        self.usage, self.settings = Path(usage), Path(settings)
        self.closed = False
        self.root = tk.Tk()
        self.root.report_callback_exception = lambda kind,value,tb: logging.error(
            'Desktop UI callback failed',exc_info=(kind,value,tb))
        self.root.title('重置小精灵 · 桌面倒计时')
        self.root.overrideredirect(not windowed)
        self.root.attributes('-topmost', True)
        self.root.configure(bg=TRANSPARENT)
        if os.name == 'nt' and not windowed:
            self.root.attributes('-transparentcolor', TRANSPARENT)
            self.root.attributes('-toolwindow', False)
        self.expanded = True
        self.topmost = True
        self.drag_start = None
        self.dragged = False
        self.animation = AnimationStateMachine(time.monotonic())
        self.rendered_revision = -1
        self.click_count = 0
        self.drag_angle = 0
        self.smooth_angle = 0.0
        self.frame_times = deque(maxlen=180)
        self.frame_deadline = time.perf_counter()
        self.previous_frame_time = self.frame_deadline
        self.last_frame = None
        self.sprites = self.load_sprites()
        self.layered_sprite = None
        if os.name == 'nt':
            self.layered_sprite = LayeredSprite(SPRITE_SIZE,
                self.press_pet,
                lambda x,y:self.drag(SimpleNamespace(x_root=x,y_root=y)),
                lambda x,y:self.release(SimpleNamespace(x_root=x,y_root=y)),
                lambda x,y:self.menu(SimpleNamespace(x_root=x,y_root=y)),
                self.cancel_drag)
        self.envelope = None
        self.last_read = 0
        self.model = unavailable()
        x = max(0, self.root.winfo_screenwidth()-self.WIDTH-34)
        y = max(0, self.root.winfo_screenheight()-self.HEIGHT-90)
        try:
            saved = read_json(self.settings)
            x = max(0, min(int(saved.get('x', x)), self.root.winfo_screenwidth()-self.WIDTH))
            y = max(0, min(int(saved.get('y', y)), self.root.winfo_screenheight()-self.HEIGHT))
            self.expanded = bool(saved.get('expanded', True))
        except (OSError, ValueError, TypeError):
            pass
        self.root.geometry(f'{self.WIDTH}x{self.HEIGHT}+{x}+{y}')
        self.canvas = tk.Canvas(self.root, width=self.WIDTH, height=self.HEIGHT,
                                bg=BG if windowed else TRANSPARENT, highlightthickness=0)
        self.canvas.pack()
        self.tibo_button = tk.Button(self.canvas,text='tibo restar',command=self.open_tibo,
            font=('Microsoft YaHei UI',-12),fg='#ffffff',bg=SURFACE,
            activeforeground='#ffffff',activebackground='#365469',
            relief='flat',borderwidth=0,highlightthickness=0,cursor='hand2',takefocus=True)
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Button-3>', self.menu)
        self.root.bind('<Escape>', lambda _: self.collapse())
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.tick()
        self.animate()
        self.root.after(300, self.show)
        self.root.after(5000, self.show)

    @property
    def interaction(self):
        return self.animation.state.value

    def load_sprites(self):
        path = Path(__file__).resolve().parents[3] / 'assets/maid-sprites.png'
        if not path.exists():
            raise FileNotFoundError(f'小精灵表情素材不存在：{path}')
        sheet = Image.open(path).convert('RGBA')
        width, height = sheet.width//3, sheet.height//2
        frames = {}
        for index in range(6):
            x,y = index%3*width,index//3*height
            frame = sheet.crop((x,y,x+width,y+height))
            frame.thumbnail((174,174), Image.Resampling.LANCZOS)
            padded = Image.new('RGBA',(SPRITE_SIZE,SPRITE_SIZE),(0,0,0,0))
            padded.alpha_composite(frame,((SPRITE_SIZE-frame.width)//2,(SPRITE_SIZE-frame.height)//2))
            frames[index] = padded
        return frames

    @lru_cache(maxsize=160)
    def rendered_sprite(self, frame, angle):
        # Padding preserves the head, hair and hands at every rotation angle.
        rotated = self.sprites[frame].rotate(angle,resample=Image.Resampling.BICUBIC,expand=False)
        if self.layered_sprite:
            return premultiplied_bgra(rotated)
        return ImageTk.PhotoImage(rotated,master=self.root)

    @staticmethod
    @lru_cache(maxsize=20)
    def sleep_font(size):
        for name in ('C:/Windows/Fonts/seguisb.ttf','DejaVuSans.ttf'):
            try:
                return ImageFont.truetype(name,size)
            except OSError:
                pass
        return ImageFont.load_default()

    def rendered_sleep(self, elapsed):
        # Text is composited into the same per-pixel-alpha surface as the pet.
        # It is above the head, clear of both the face and the reminder panel.
        image = self.sprites[5].copy()
        draw = ImageDraw.Draw(image)
        for x,y,size,alpha in sleep_particles(elapsed):
            draw.text((round(x),round(y)),'zzz',font=self.sleep_font(round(size)),
                      anchor='ms',fill=(210,235,255,alpha),
                      stroke_width=1,stroke_fill=(28,52,73,alpha))
        if self.layered_sprite:
            return premultiplied_bgra(image)
        return ImageTk.PhotoImage(image,master=self.root)

    def show(self):
        if self.closed:
            return
        self.root.deiconify()
        self.root.lift()
        self.root.update_idletasks()
        help_text = [{'text':self.canvas.itemcget(item,'text'),
                      'color':self.canvas.itemcget(item,'fill'),
                      'bounds':self.canvas.bbox(item)}
                     for item in self.canvas.find_withtag('help') if self.canvas.type(item)=='text']
        write_json(self.settings.with_name('desktop-runtime.json'), {
            'pid': os.getpid(), 'visible': bool(self.root.winfo_viewable()),
            'topmost': bool(self.root.attributes('-topmost')), 'expanded': self.expanded,
            'geometry': self.root.geometry(), 'rows': self.model['rows'],
            'snapshot_stale': self.model['stale'], 'started_at': time.time(),
            'sprite_loaded': len(self.sprites), 'interaction': self.interaction,
            'sleep_after_seconds':self.animation.SLEEP_AFTER,
            'help_text':help_text, 'sprite_border':False,
            'tibo_button_visible':bool(self.tibo_button.winfo_ismapped()),
            'tibo_url':TIBO_URL,
            'alpha_mode':'per_pixel' if self.layered_sprite else 'tk',
            'target_fps':TARGET_FPS,
            'measured_callback_fps':round((len(self.frame_times)-1)/(self.frame_times[-1]-self.frame_times[0]),1) if len(self.frame_times)>1 else None})

    def rounded(self, x, y, w, h, radius, fill, **kw):
        points = [x+radius,y,x+w-radius,y,x+w,y,x+w,y+radius,x+w,y+h-radius,
                  x+w,y+h,x+w-radius,y+h,x+radius,y+h,x,y+h,x,y+h-radius,x,y+radius,x,y]
        return self.canvas.create_polygon(points, smooth=True, splinesteps=24,
                                          fill=fill, outline=fill, **kw)

    def text(self, x, y, text, size=13, color=TEXT, bold=False, **kw):
        return self.canvas.create_text(x, y, text=text, anchor='nw', fill=color,
                                       font=('Microsoft YaHei UI', -size, 'bold' if bold else 'normal'), **kw)

    def draw(self):
        c, model = self.canvas, self.model
        c.delete('all')
        self.row_items = []
        self.last_frame = None
        if self.expanded:
            self.rounded(5, 5, 360, 282, 22, BG, tags='bubble')
            c.create_polygon(274,283,304,283,289,306, fill=BG, outline=BG, tags='bubble')
            self.text(25, 21, '重置时间', 15, bold=True, tags='header')
            self.text(212, 25, '北京时间 · UTC+8', 11, MUTED)
            self.text(338, 18, '×', 21, MUTED, tags='collapse')
            for i, row in enumerate(model['rows']):
                y = 58+i*99
                self.rounded(20, y, 330, 91, 13, SURFACE)
                dot = c.create_oval(32,y+14,38,y+20,fill=row['color'],outline='')
                self.text(46,y+9,row['title'],12, MUTED)
                date = self.text(32,y+29,row['date'],25,row['color'],True)
                left = self.text(32,y+65,row['remaining'],12,TEXT)
                self.row_items.append((dot,date,left))
            self.footer_item = self.text(25, 260, model['footer'],11,MUTED)
            c.create_window(238,254,anchor='nw',width=112,height=28,
                            window=self.tibo_button,tags='tibo_link')
        # Opaque backplates prevent ClearType and alpha edges mixing with the
        # Windows transparency key. Static text is not deleted every frame.
        if self.expanded:
            self.rounded(16,321,160,142,14,BG,tags='help')
            self.text(28,334,'点击 · 表情 / 展开气泡',12,'#ffffff',tags='help')
            self.text(28,359,'拖拽 · 提起并晃动',12,'#ffffff',tags='help')
            self.text(28,384,'松手 · 落地弹跳',12,'#ffffff',tags='help')
            self.text(28,410,'右键 · 玩法与退出',11,'#ffffff',tags='help')
            self.state_text = self.text(28,440,'点击互动',11,'#ffffff',tags='help')
        else:
            self.state_text = None
        self.sprite_item = None if self.layered_sprite else c.create_image(PET_X,PET_Y,image=self.rendered_sprite(0,0),tags='pet')
        self.last_label = None

    def update_display(self):
        for row, (dot,date,left) in zip(self.model['rows'], self.row_items):
            self.canvas.itemconfigure(dot,fill=row['color'])
            self.canvas.itemconfigure(date,text=row['date'],fill=row['color'])
            self.canvas.itemconfigure(left,text=row['remaining'])
        if self.expanded:
            self.canvas.itemconfigure(self.footer_item,text=self.model['footer'])

    def react(self, action):
        self.animation.play(action,time.monotonic())

    def open_tibo(self):
        self.animation.touch(time.monotonic())
        try:
            if not webbrowser.open(TIBO_URL,new=2):
                logging.error('Default browser could not open the Tibo page')
        except OSError:
            logging.exception('Failed to open Tibo page')

    def animate(self):
        if self.closed:
            return
        if self.layered_sprite:
            self.layered_sprite.drain_events()
        if self.closed:
            return
        now = time.perf_counter()
        dt = min(.1,now-self.previous_frame_time)
        self.previous_frame_time = now
        self.frame_times.append(now)
        state,elapsed = self.animation.update(time.monotonic())
        frame,angle,offset,label = animation_pose(state,elapsed,self.drag_angle)
        if self.rendered_revision != self.animation.revision:
            self.smooth_angle = angle
            self.rendered_revision = self.animation.revision
        self.smooth_angle += (angle-self.smooth_angle)*(1-math.exp(-dt*18))
        angle = max(-12,min(12,round(self.smooth_angle)))
        image = self.rendered_sleep(elapsed) if state == State.SLEEP else self.rendered_sprite(frame,angle)
        if self.layered_sprite:
            self.layered_sprite.present(image,self.root.winfo_x()+PET_X-SPRITE_SIZE//2,
                                        self.root.winfo_y()+PET_Y+offset-SPRITE_SIZE//2)
        else:
            if state == State.SLEEP or (frame,angle) != self.last_frame:
                self.canvas.itemconfigure(self.sprite_item,image=image)
            self.current_image = image
            self.canvas.coords(self.sprite_item,PET_X,PET_Y+offset)
        self.last_frame = frame,angle
        if self.state_text is not None and label != self.last_label:
            self.canvas.itemconfigure(self.state_text,text=label)
            self.last_label = label
        self.frame_deadline += 1/TARGET_FPS
        if self.frame_deadline < time.perf_counter():
            self.frame_deadline = time.perf_counter()+1/TARGET_FPS
        self.root.after(max(1,round((self.frame_deadline-time.perf_counter())*1000)),self.animate)

    def tick(self):
        if self.closed:
            return
        now = time.time()
        if now-self.last_read >= 5:
            self.last_read = now
            try:
                self.envelope = read_json(self.usage)
            except (OSError, ValueError):
                # An unavailable input is not silently represented as a fresh account.
                self.envelope = None
        try:
            self.model = view_model(self.envelope, now) if self.envelope else unavailable()
        except (ValueError, TypeError, KeyError, OverflowError):
            self.model = unavailable()
        if not hasattr(self,'sprite_item'):
            self.draw()
        else:
            self.update_display()
        self.root.after(500, self.tick)

    def press(self, event):
        self.animation.touch(time.monotonic())
        tags = self.canvas.gettags('current')
        if 'collapse' in tags:
            self.collapse()
            return
        self.drag_start = (event.x_root,event.y_root,self.root.winfo_x(),self.root.winfo_y(),'pet' in tags)
        self.dragged = False
        self.animation.press(time.monotonic())

    def press_pet(self, x, y):
        self.animation.press(time.monotonic())
        self.drag_start = (x,y,self.root.winfo_x(),self.root.winfo_y(),True)
        self.dragged = False

    def drag(self, event):
        if self.drag_start:
            self.animation.touch(time.monotonic())
            x,y,wx,wy,_ = self.drag_start
            dx,dy = event.x_root-x,event.y_root-y
            if abs(dx)+abs(dy)>5:
                self.dragged = True
                if self.drag_start[4]:
                    if self.interaction != 'drag':
                        self.react('drag')
                    self.drag_angle = max(-12,min(12,dx/6))
                self.root.geometry(f'+{max(0,wx+dx)}+{max(0,wy+dy)}')

    def release(self, event):
        self.animation.release(time.monotonic())
        if self.drag_start:
            if self.drag_start[4] and not self.dragged:
                self.click_count += 1
                self.react('pout' if self.click_count%3 == 0 else 'click')
                self.expanded = not self.expanded
                self.draw()
            elif self.drag_start[4] and self.dragged:
                self.react('land')
            self.save()
        self.drag_start = None

    def cancel_drag(self):
        self.animation.cancel(time.monotonic())
        if self.drag_start:
            self.drag_start = None
            self.dragged = False
            self.save()

    def collapse(self):
        self.animation.touch(time.monotonic())
        self.expanded = False
        self.draw()
        self.save()

    def toggle(self):
        self.animation.touch(time.monotonic())
        self.expanded = not self.expanded
        self.draw()
        self.save()

    def menu(self, event):
        self.animation.touch(time.monotonic())
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label='摸摸头 · 眨眼挥手', command=lambda: self.react('click'))
        menu.add_command(label='逗一下 · 鼓脸', command=lambda: self.react('pout'))
        menu.add_command(label='开心跳一跳', command=lambda: self.react('land'))
        menu.add_separator()
        menu.add_command(label='收起气泡' if self.expanded else '展开重置时间', command=self.toggle)
        menu.add_command(label='重新读取账户快照', command=lambda: setattr(self,'last_read',0))
        if not self.root.overrideredirect():
            menu.add_command(label='切换为无边框桌面悬浮', command=self.enable_overlay)
        menu.add_separator()
        menu.add_command(label='退出桌面小精灵', command=self.close)
        try:
            menu.tk_popup(event.x_root,event.y_root)
        finally:
            menu.grab_release()

    def save(self):
        try:
            write_json(self.settings, {'x': self.root.winfo_x(),'y': self.root.winfo_y(),'expanded': self.expanded})
        except OSError:
            pass

    def enable_overlay(self):
        self.canvas.configure(bg=TRANSPARENT)
        if os.name == 'nt':
            self.root.attributes('-transparentcolor',TRANSPARENT)
        self.root.overrideredirect(True)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.save()
        if self.layered_sprite:
            self.layered_sprite.close()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--usage', required=True)
    parser.add_argument('--settings', required=True)
    parser.add_argument('--windowed', action='store_true', help='Windowed preview for desktop QA')
    args = parser.parse_args()
    mutex = None
    if os.name == 'nt':
        # This is the application's own window/single-instance setup, not UI automation.
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except OSError:
            pass
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        key = hashlib.sha256(str(Path(args.usage).resolve()).casefold().encode()).hexdigest()[:20]
        mutex = kernel.CreateMutexW(None, False, 'Local\\CodexResetCompanion_'+key)
        if ctypes.get_last_error() == 183:
            if mutex:
                kernel.CloseHandle(mutex)
            return
    try:
        log_dir = Path(args.settings).resolve().parent
        log_dir.mkdir(parents=True,exist_ok=True)
        logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',
            handlers=[RotatingFileHandler(log_dir/'desktop-events.log',maxBytes=262144,
                                          backupCount=2,encoding='utf-8')])
        # pythonw has no stderr. Keep a file alive for native fatal traces too.
        crash_log = open(log_dir/'desktop-crash.log','a',encoding='utf-8',buffering=1)
        if sys.stderr is None:
            sys.stderr = crash_log
        faulthandler.enable(file=crash_log)
        logging.info('Desktop companion 0.4.1 starting, pid=%s',os.getpid())
        app = Companion(args.usage,args.settings,args.windowed)
        app.root.mainloop()
        logging.info('Desktop companion closed normally')
    except Exception:
        logging.exception('Desktop companion stopped unexpectedly')
        raise
    finally:
        if mutex:
            kernel.CloseHandle(mutex)


if __name__ == '__main__':
    main()
