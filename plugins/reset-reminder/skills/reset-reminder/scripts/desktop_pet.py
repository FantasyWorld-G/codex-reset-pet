"""Windows companion with local snapshots and on-demand Codex quota refresh."""
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
import queue
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time
import tkinter as tk
from tkinter import font as tkfont
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw, ImageFont
from functools import lru_cache
from collections import deque
from types import SimpleNamespace
from layered_sprite import LayeredSprite, premultiplied_bgra
from animation_state import AnimationStateMachine, State, animation_pose, sleep_particles

from check_reset import CN, account_snapshot, card_snapshot, epoch, read_json, write_json
from refresh_usage import RefreshError, fetch_snapshot, save_snapshot
from tibo_forecast import fetch_forecast, forecast_view, source_url
from auto_redeem import run_cycle, read_config, valid_policy, exact_credit_client, card_rows
from refresh_usage import account_operation, make_snapshot
from launch_desktop import in_windows_job, windows_job_flags
from pet_audio import PetAudio

TRANSPARENT = '#ff00ff'
BG = '#182735'
SURFACE = '#223545'
MUTED = '#93a8b8'
TEXT = '#edf4f8'
SPRITE_SIZE = 288
PET_X, PET_Y = 275,772
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
    quota = min(windows, key=lambda w: w['resets_at']) if windows else next(iter(account['windows']),None)
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
                     # Deadline urgency is independent of snapshot freshness.
                     # Freshness remains explicit in the footer and quota label.
                     'detail': detail, 'color': time_color(seconds)})
    deadlines = [r['seconds'] for r in rows if r['seconds'] is not None]
    return {'rows': rows, 'stale': stale, 'captured': captured,
            'remaining_percent': quota['remaining_percent'] if quota else None,
            'pet_color': time_color(min(deadlines)) if deadlines else MUTED,
            'footer': ('数据待同步 · 显示上次记录' if stale else '已同步 ' + datetime.fromtimestamp(captured, CN).strftime('%H:%M') + ' · 本机倒计时')}


def unavailable():
    return {'rows': [{'title': title, 'date': '等待账户同步', 'remaining': 'Codex 更新后会自动显示',
                       'detail': '', 'color': MUTED} for title in ('账户额度重置', '重置卡到期')],
            'remaining_percent': None,
            'pet_color': MUTED, 'stale': True, 'footer': '数据不可用 · 等待 Codex 同步'}


def display_model(envelope, manual, now):
    """Choose the newest valid quota without relabelling old card details as fresh."""
    models = []
    for source in (envelope, manual):
        try:
            models.append(view_model(source, now) if isinstance(source, dict) else None)
        except (ValueError, TypeError, KeyError, OverflowError):
            models.append(None)
    original, refreshed = models
    if refreshed is None or (original and original['captured'] >= refreshed['captured']):
        return original or unavailable()
    credits = manual['usage'].get('rateLimitResetCredits')
    if not isinstance(credits, dict) or not isinstance(credits.get('credits'), list):
        row = dict((original or unavailable())['rows'][1])
        row['title'] = '重置卡到期 · 上次记录' if original else '重置卡到期 · 待完整同步'
        refreshed['rows'][1] = row
        deadlines = [r['seconds'] for r in refreshed['rows'] if r.get('seconds') is not None]
        refreshed['pet_color'] = time_color(min(deadlines)) if deadlines else MUTED
    refreshed['footer'] = ('额度待刷新' if refreshed['stale'] else '额度已同步 ' +
                           datetime.fromtimestamp(refreshed['captured'], CN).strftime('%H:%M'))
    return refreshed


class Companion:
    WIDTH, HEIGHT = 370, 873

    def __init__(self, usage, settings, windowed=False, tibo_enabled=True, sound_enabled=None):
        self.usage, self.settings = Path(usage), Path(settings)
        self.closed = False
        self.started_at = time.time()
        self.close_reason = None
        self.in_job = in_windows_job()
        self.job_flags = windows_job_flags()
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
        self.pending_click = None
        self.click_timer = None
        self.double_click = False
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
        self.manual_usage = self.usage.with_name('desktop-usage.json')
        self.manual_envelope = None
        self.refresh_results = queue.Queue()
        self.refresh_cancel = threading.Event()
        self.refresh_thread = None
        self.refresh_busy = False
        self.refresh_message = ''
        self.refresh_message_until = 0
        self.auto_config_path=self.usage.with_name('auto-redeem.json')
        self.auto_state_path=self.usage.with_name('auto-redeem-state.json')
        self.auto_policy=read_config(self.auto_config_path)
        self.auto_message='自动使用：检查中' if valid_policy(self.auto_policy) else '自动使用：关闭'
        self.auto_results=queue.Queue()
        self.auto_busy=False
        self.auto_next_check=0
        self.auto_revision=0
        self.auto_thread=None
        self.tibo_enabled = tibo_enabled
        self.tibo_path = self.usage.with_name('tibo-forecast.json')
        self.tibo_snapshot = None
        self.tibo_results = queue.Queue()
        self.tibo_busy = False
        self.tibo_failed = False
        self.tibo_next_refresh = 0
        self.tibo_thread = None
        try:
            self.tibo_snapshot = read_json(self.tibo_path)
        except (OSError,ValueError):
            pass
        self.tibo_model = forecast_view(None,time.time())
        self.last_read = 0
        self.model = unavailable()
        saved_sound = True
        x = max(0, self.root.winfo_screenwidth()-self.WIDTH-34)
        y = max(0, self.root.winfo_screenheight()-self.HEIGHT-90)
        try:
            saved = read_json(self.settings)
            x = max(0, min(int(saved.get('x', x)), self.root.winfo_screenwidth()-self.WIDTH))
            y = max(0, min(int(saved.get('y', y)), self.root.winfo_screenheight()-self.HEIGHT))
            self.expanded = bool(saved.get('expanded', True))
            saved_sound = saved.get('sound_enabled', True) is not False
        except (OSError, ValueError, TypeError):
            pass
        self.audio = PetAudio(Path(__file__).resolve().parents[3]/'assets/sounds',
                              saved_sound if sound_enabled is None else sound_enabled,
                              personal_assets=self.settings.parent/'voice-amitaro')
        self.root.geometry(f'{self.WIDTH}x{self.HEIGHT}+{x}+{y}')
        self.canvas = tk.Canvas(self.root, width=self.WIDTH, height=self.HEIGHT,
                                bg=BG if windowed else TRANSPARENT, highlightthickness=0)
        self.canvas.pack()
        self.history_font = tkfont.Font(family='Microsoft YaHei UI',size=-12)
        self.history_dialog = None
        self.tibo_button = tk.Button(self.canvas,text='tibo reset',command=self.open_tibo,
            font=('Microsoft YaHei UI',-12),fg='#ffffff',bg=SURFACE,
            activeforeground='#ffffff',activebackground='#365469',
            relief='flat',borderwidth=0,highlightthickness=0,cursor='hand2',takefocus=True)
        self.refresh_button = tk.Button(self.canvas,text='刷新',command=self.refresh_usage,
            font=('Microsoft YaHei UI',-12),fg='#ffffff',bg='#365469',
            activeforeground='#ffffff',activebackground='#44657d',disabledforeground=MUTED,
            relief='flat',borderwidth=0,highlightthickness=0,cursor='hand2',takefocus=True)
        self.tibo_refresh_button = tk.Button(self.canvas,text='更新预估',command=self.refresh_tibo,
            font=('Microsoft YaHei UI',-11),fg=TEXT,bg='#365469',
            activeforeground=TEXT,activebackground='#44657d',disabledforeground=MUTED,
            relief='flat',borderwidth=0,highlightthickness=0,cursor='hand2',takefocus=True)
        self.tibo_source_button = tk.Button(self.canvas,text='查看原帖',command=self.open_tibo_source,
            font=('Microsoft YaHei UI',-11),fg=TEXT,bg='#365469',
            activeforeground=TEXT,activebackground='#44657d',disabledforeground=MUTED,
            relief='flat',borderwidth=0,highlightthickness=0,cursor='hand2',takefocus=True)
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Button-3>', self.menu)
        self.root.bind('<Escape>', lambda _: self.collapse())
        self.root.protocol('WM_DELETE_WINDOW', lambda: self.close('window_close'))
        self.tick()
        self.animate()
        self.root.after(300, self.show)
        self.root.after(5000, self.show)
        self.root.after(30000, self.heartbeat)

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
        self.write_runtime()

    def heartbeat(self):
        if self.closed:
            return
        try:
            self.write_runtime()
        except Exception:
            logging.exception('Runtime heartbeat write failed')
        finally:
            self.root.after(30000, self.heartbeat)

    def write_runtime(self):
        help_text = [{'text':self.canvas.itemcget(item,'text'),
                      'color':self.canvas.itemcget(item,'fill'),
                      'bounds':self.canvas.bbox(item)}
                     for item in self.canvas.find_withtag('help') if self.canvas.type(item)=='text']
        write_json(self.settings.with_name('desktop-runtime.json'), {
            'pid': os.getpid(), 'visible': bool(self.root.winfo_viewable()),
            'topmost': bool(self.root.attributes('-topmost')), 'expanded': self.expanded,
            'geometry': self.root.geometry(), 'rows': self.model['rows'],
            'remaining_percent': self.model['remaining_percent'],
            'snapshot_stale': self.model['stale'], 'started_at': self.started_at,
            'heartbeat_at': time.time(), 'in_windows_job': self.in_job,
            'windows_job_flags': self.job_flags,
            'sound_enabled': self.audio.enabled,
            'sound_pack': self.audio.provider,
            'happy_sound_seconds': self.audio.drag_happy_seconds,
            'lifecycle': 'closed' if self.closed else 'running',
            'close_reason': self.close_reason,
            'sprite_loaded': len(self.sprites), 'interaction': self.interaction,
            'sleep_after_seconds':self.animation.SLEEP_AFTER,
            'help_text':help_text, 'sprite_border':False,
            'tibo_button_visible':bool(self.tibo_button.winfo_ismapped()),
            'refresh_button_visible':bool(self.refresh_button.winfo_ismapped()),
            'tibo_forecast':self.tibo_model,
            'tibo_refresh_button_visible':bool(self.tibo_refresh_button.winfo_ismapped()),
            'tibo_source_button_visible':bool(self.tibo_source_button.winfo_ismapped()),
            'tibo_url':TIBO_URL,
            'auto_redeem_enabled':valid_policy(self.auto_policy),
            'auto_redeem_status':self.auto_message,
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
            self.rounded(5, 5, 360, 605, 22, BG, tags='bubble')
            c.create_polygon(274,606,304,606,289,629, fill=BG, outline=BG, tags='bubble')
            self.text(25, 21, '重置时间', 15, bold=True, tags='header')
            self.text(212, 25, '北京时间 · UTC+8', 11, MUTED)
            self.text(338, 18, '×', 21, MUTED, tags='collapse')
            for i, row in enumerate(model['rows']):
                y = 58+i*139
                self.rounded(20, y, 330, 131 if i == 0 else 96, 13, SURFACE)
                dot = c.create_oval(32,y+14,38,y+20,fill=row['color'],outline='')
                title = self.text(46,y+9,row['title'],12, MUTED)
                date = self.text(32,y+29,row['date'],25,row['color'],True)
                left = self.text(32,y+65,row['remaining'],12,row['color'])
                self.row_items.append((dot,date,left,title))
            self.auto_status_item=self.text(32,280,self.auto_message[:31]+('…' if len(self.auto_message)>31 else ''),9,MUTED)
            self.quota_text = self.text(32,147,'',12,TEXT,bold=True,tags='quota')
            c.create_rectangle(32,173,338,179,fill=BG,outline='',tags='quota')
            self.quota_fill = c.create_rectangle(32,173,32,179,fill='#8acdf0',outline='',tags='quota')
            self.update_quota()
            c.create_window(274,142,anchor='nw',width=64,height=26,
                            window=self.refresh_button,tags='refresh')
            self.rounded(20,296,330,132,13,SURFACE)
            self.tibo_items = (
                self.text(32,305,'',12,MUTED),
                self.text(32,331,'',22,TEXT,True),
                self.text(32,362,'',12,TEXT),
                self.text(32,385,'',11,MUTED),
                self.text(32,407,'',10,MUTED))
            c.create_window(264,301,anchor='nw',width=74,height=24,
                            window=self.tibo_refresh_button,tags='tibo_refresh')
            self.rounded(20,436,330,130,13,SURFACE)
            self.tibo_history_items = (
                self.text(32,445,'',12,MUTED),
                self.text(32,470,'',22,TEXT,True),
                self.text(32,501,'',12,TEXT,tags='history_details'),
                self.text(32,523,'',11,MUTED),
                self.text(32,545,'',10,MUTED))
            c.create_window(264,441,anchor='nw',width=74,height=24,
                            window=self.tibo_source_button,tags='tibo_source')
            self.update_tibo_display()
            c.tag_bind('history_details','<Enter>',lambda _:c.configure(cursor='hand2'))
            c.tag_bind('history_details','<Leave>',lambda _:c.configure(cursor=''))
            self.footer_item = self.text(25, 583, self.footer_text(),11,MUTED,width=207)
            c.create_window(238,577,anchor='nw',width=112,height=28,
                            window=self.tibo_button,tags='tibo_link')
        # Opaque backplates prevent ClearType and alpha edges mixing with the
        # Windows transparency key. Static text is not deleted every frame.
        if self.expanded:
            self.rounded(16,644,160,142,14,BG,tags='help')
            self.text(28,657,'单击 · 气泡 / 双击 · 摸头',11,'#ffffff',tags='help')
            self.text(28,682,'拖拽 · 提起并晃动',12,'#ffffff',tags='help')
            self.text(28,707,'松手 · 落地弹跳',12,'#ffffff',tags='help')
            self.text(28,733,'右键 · 玩法与退出',11,'#ffffff',tags='help')
            self.state_text = self.text(28,763,'点击互动',11,'#ffffff',tags='help')
        else:
            self.state_text = None
        self.sprite_item = None if self.layered_sprite else c.create_image(PET_X,PET_Y,image=self.rendered_sprite(0,0),tags='pet')
        self.last_label = None

    def update_quota(self):
        percent = self.model['remaining_percent']
        stale = self.model['stale']
        label = '剩余额度 -- · 等待同步' if percent is None else f'剩余额度 {percent:g}%'
        if percent is not None and stale:
            label += ' · 上次同步'
        self.canvas.itemconfigure(self.quota_text,text=label,fill=MUTED if stale else TEXT)
        self.canvas.coords(self.quota_fill,32,173,32+306*(percent or 0)/100,179)
        self.canvas.itemconfigure(self.quota_fill,fill=MUTED if stale else '#8acdf0',
                                  state='normal' if percent is not None and percent > 0 else 'hidden')

    def update_display(self):
        for row, (dot,date,left,title) in zip(self.model['rows'], self.row_items):
            self.canvas.itemconfigure(dot,fill=row['color'])
            self.canvas.itemconfigure(date,text=row['date'],fill=row['color'])
            self.canvas.itemconfigure(left,text=row['remaining'],fill=row['color'])
            self.canvas.itemconfigure(title,text=row['title'])
        if self.expanded:
            self.update_quota()
            self.canvas.itemconfigure(self.auto_status_item,text=self.auto_message[:31]+('…' if len(self.auto_message)>31 else ''))
            self.update_tibo_display()
            self.canvas.itemconfigure(self.footer_item,text=self.footer_text())

    def update_tibo_display(self):
        model = self.tibo_model
        color = time_color(model['seconds'])
        for item,key in zip(self.tibo_items,('title','date','remaining','detail','status')):
            label = '正在读取网站预估…' if key=='status' and self.tibo_busy else model[key]
            self.canvas.itemconfigure(item,text=label,fill=color if key in ('date','remaining') else MUTED)
        for item,key in zip(self.tibo_history_items,('last_title','last_date','last_reason','last_category','last_status')):
            label=model[key]
            if key=='last_reason':
                suffix='（详情）'
                if self.history_font.measure(label+suffix)>306:
                    lo,hi=0,len(label)
                    while lo<hi:
                        mid=(lo+hi+1)//2
                        if self.history_font.measure(label[:mid]+'…'+suffix)<=306:lo=mid
                        else:hi=mid-1
                    label=label[:lo]+'…'
                label+=suffix
            self.canvas.itemconfigure(item,text=label)
        self.tibo_source_button.configure(state='normal' if model['last_url'] else 'disabled')

    def refresh_tibo(self):
        if self.closed or self.tibo_busy or not self.tibo_enabled:
            return
        self.tibo_busy = True
        self.tibo_refresh_button.configure(text='读取中',state='disabled')
        def worker():
            try:
                snapshot = fetch_forecast(cancel=self.refresh_cancel)
                if self.refresh_cancel.is_set():
                    return
                save_snapshot(self.tibo_path,snapshot)
                self.tibo_results.put(snapshot)
            except Exception:
                self.tibo_results.put(None)
        self.tibo_thread = threading.Thread(target=worker,daemon=False)
        self.tibo_thread.start()

    def disable_auto(self):
        self.auto_revision+=1
        policy=dict(self.auto_policy,enabled=False)
        try:save_snapshot(self.auto_config_path,policy)
        except OSError:
            self.auto_message='自动使用：关闭失败，请退出精灵'
            return
        self.auto_policy=policy
        self.auto_message='自动使用：关闭'

    def enable_auto(self,start,stop):
        if self.auto_busy:return
        self.auto_revision+=1
        revision=self.auto_revision
        self.auto_busy=True
        self.auto_message='自动使用：核对账户和接口…'
        def enroll():
            try:
                client=exact_credit_client()
                def inspect(account,limits,request):
                    if not account.get('email'):raise RefreshError('无法核对账户')
                    card_rows(limits)
                    snapshot=make_snapshot(account,limits)
                    return {'enabled':True,'start_before':start,'stop_before':stop,
                            'account_id':snapshot['usage']['accountId']}
                policy=account_operation(inspect,cancel=self.refresh_cancel,executable=client)
                self.auto_results.put((revision,{'policy':policy}))
            except Exception as error:
                self.auto_results.put((revision,{'message':'自动使用：'+str(error),'delay':60}))
        self.auto_thread=threading.Thread(target=enroll,daemon=False)
        self.auto_thread.start()

    def tick_auto(self):
        try:revision,result=self.auto_results.get_nowait()
        except queue.Empty:pass
        else:
            self.auto_busy=False
            if revision==self.auto_revision:
                if 'policy' in result:
                    try:
                        save_snapshot(self.auto_config_path,result['policy'])
                        self.auto_policy=result['policy']
                        self.auto_message='自动使用：已开启，仅限临期卡'
                        self.auto_next_check=0
                    except OSError:self.auto_message='自动使用：设置保存失败，未开启'
                else:
                    self.auto_message=result['message']
                    self.auto_next_check=time.time()+result.get('delay',60)
                    if result.get('snapshot'):
                        self.manual_envelope=result['snapshot']
                        self.last_read=0
                    if result.get('outcome'):
                        logging.info('Auto redeem result: %s',result['outcome'])
        if self.closed or self.auto_busy or not valid_policy(self.auto_policy) or time.time()<self.auto_next_check:return
        self.auto_busy=True
        revision=self.auto_revision
        def worker():
            try:
                result=run_cycle(self.auto_config_path,self.auto_state_path,self.manual_usage,self.refresh_cancel)
            except Exception as error:
                result={'message':'自动使用：'+str(error),'delay':30}
            self.auto_results.put((revision,result))
        self.auto_thread=threading.Thread(target=worker,daemon=False)
        self.auto_thread.start()

    def tick_tibo(self,now):
        try:
            snapshot = self.tibo_results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.tibo_busy = False
            self.tibo_failed = snapshot is None
            if snapshot is not None:
                self.tibo_snapshot = snapshot
            self.tibo_next_refresh = time.monotonic()+300
            self.tibo_refresh_button.configure(text='更新预估',state='normal')
        try:
            self.tibo_model = forecast_view(self.tibo_snapshot,now,self.tibo_failed)
        except (ValueError,TypeError,KeyError,OverflowError,OSError):
            self.tibo_model = forecast_view(None,now,True)
        if self.tibo_enabled and not self.tibo_busy and time.monotonic()>=self.tibo_next_refresh:
            self.refresh_tibo()

    def footer_text(self):
        if self.refresh_busy:
            return '正在读取 Codex 额度…'
        if time.monotonic() < self.refresh_message_until:
            return self.refresh_message
        return self.model['footer']

    def refresh_usage(self):
        if self.closed or self.refresh_busy:
            return
        self.animation.touch(time.monotonic())
        self.refresh_busy = True
        self.refresh_button.configure(text='刷新中',state='disabled')
        self.update_display()

        def worker():
            try:
                snapshot = fetch_snapshot(cancel=self.refresh_cancel)
                if self.refresh_cancel.is_set():
                    return
                save_snapshot(self.manual_usage, snapshot)
                self.refresh_results.put((True, '额度刷新成功'))
            except RefreshError as error:
                self.refresh_results.put((False, str(error)))
            except OSError:
                self.refresh_results.put((False, '无法保存额度，请重试'))
            except Exception:
                logging.exception('Quota refresh failed')
                self.refresh_results.put((False, '刷新失败，请重试'))

        # Background I/O never calls Tk or the native sprite window.
        # Keep Python alive briefly after the window closes so cancellation can
        # reach fetch_snapshot's finally and reap the account-server process.
        self.refresh_thread = threading.Thread(target=worker,daemon=False)
        self.refresh_thread.start()

    def collect_refresh(self):
        try:
            success, message = self.refresh_results.get_nowait()
        except queue.Empty:
            return
        self.refresh_busy = False
        self.refresh_button.configure(text='刷新',state='normal')
        self.refresh_message = message
        self.refresh_message_until = time.monotonic()+12
        if success:
            self.last_read = 0

    def react(self, action):
        self.cancel_pending_click()
        self.animation.play(action,time.monotonic())

    def open_tibo(self):
        self.animation.touch(time.monotonic())
        try:
            if not webbrowser.open(TIBO_URL,new=2):
                logging.error('Default browser could not open the Tibo page')
        except OSError:
            logging.exception('Failed to open Tibo page')

    def open_tibo_source(self,url=None):
        url=source_url(self.tibo_model.get('last_url') if url is None else url)
        if not url:return
        self.animation.touch(time.monotonic())
        try:
            if not webbrowser.open(url,new=2):
                logging.error('Default browser could not open the reset source')
        except OSError:
            logging.exception('Failed to open reset source')

    def show_history_details(self):
        self.animation.touch(time.monotonic())
        if self.history_dialog is not None and self.history_dialog.winfo_exists():
            self.history_dialog.lift()
            return
        model=dict(self.tibo_model)
        dialog=self.history_dialog=tk.Toplevel(self.root)
        dialog.title('上次 Tibo 重置 · 网站说明')
        dialog.configure(bg=BG)
        dialog.attributes('-topmost',True)
        dialog.geometry('480x340')
        dialog.minsize(360,260)
        tk.Label(dialog,text=model['last_date']+' · 北京时间',bg=BG,fg=TEXT,
                 font=('Microsoft YaHei UI',12,'bold')).pack(anchor='w',padx=16,pady=12)
        frame=tk.Frame(dialog,bg=BG)
        frame.pack(fill='both',expand=True,padx=16)
        scrollbar=tk.Scrollbar(frame)
        scrollbar.pack(side='right',fill='y')
        content=tk.Text(frame,wrap='word',bg=SURFACE,fg=TEXT,relief='flat',
                        font=('Microsoft YaHei UI',11),padx=10,pady=10,
                        yscrollcommand=scrollbar.set)
        content.pack(fill='both',expand=True)
        scrollbar.configure(command=content.yview)
        explanation=model.get('last_announcement') or '网站暂未提供这次重置的公告说明。'
        content.insert('1.0',model['last_status']+'\n'+model['last_category']+
                       '\n\n网站公告说明：\n'+explanation+
                       '\n\n来源：codex-reset.com 时间线。公告内容不一定说明因果；网站分类不等于官方重置原因。')
        content.configure(state='disabled')
        tk.Button(dialog,text='查看原帖',command=lambda:self.open_tibo_source(model['last_url']),
                  state='normal' if model['last_url'] else 'disabled').pack(side='left',padx=16,pady=12)
        tk.Button(dialog,text='关闭',command=dialog.destroy).pack(side='right',padx=16,pady=12)
        dialog.bind('<Escape>',lambda _:dialog.destroy())

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
        self.audio.observe(state, self.animation.revision)
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
        self.collect_refresh()
        if now-self.last_read >= 5:
            self.last_read = now
            try:
                self.envelope = read_json(self.usage)
            except (OSError, ValueError):
                # An unavailable input is not silently represented as a fresh account.
                self.envelope = None
            try:
                self.manual_envelope = read_json(self.manual_usage)
            except (OSError, ValueError):
                self.manual_envelope = None
        self.model = display_model(self.envelope, self.manual_envelope, now)
        self.tick_tibo(now)
        self.tick_auto()
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
        if 'history_details' in tags:
            self.show_history_details()
            return
        if 'pet' in tags:
            self.press_pet(event.x_root,event.y_root)
            return
        self.cancel_pending_click()
        self.drag_start = (event.x_root,event.y_root,self.root.winfo_x(),self.root.winfo_y(),'pet' in tags)
        self.dragged = False
        self.animation.press(time.monotonic())

    def press_pet(self, x, y):
        self.double_click = False
        if self.pending_click:
            previous_x,previous_y,when = self.pending_click
            if time.monotonic()-when <= .3 and math.hypot(x-previous_x,y-previous_y) <= 12:
                self.cancel_pending_click()
                self.double_click = True
            else:
                self.finish_single_click()
        self.animation.press(time.monotonic())
        self.drag_start = (x,y,self.root.winfo_x(),self.root.winfo_y(),True)
        self.dragged = False

    def drag(self, event):
        if self.drag_start:
            self.animation.touch(time.monotonic())
            x,y,wx,wy,_ = self.drag_start
            dx,dy = event.x_root-x,event.y_root-y
            if abs(dx)+abs(dy)>5:
                self.cancel_pending_click()
                self.double_click = False
                self.dragged = True
                next_x,next_y = max(0,wx+dx),max(0,wy+dy)
                if self.drag_start[4]:
                    if self.interaction != 'drag':
                        self.react('drag')
                    self.drag_angle = max(-12,min(12,dx/6))
                    self.audio.drag_distance(math.hypot(next_x-wx,next_y-wy),
                                             self.animation.revision)
                self.root.geometry(f'+{next_x}+{next_y}')

    def release(self, event):
        self.animation.release(time.monotonic())
        if self.drag_start:
            if self.drag_start[4] and not self.dragged:
                if self.double_click:
                    self.react('pat')
                else:
                    self.pending_click = (event.x_root,event.y_root,time.monotonic())
                    self.click_timer = self.root.after(300,self.finish_single_click)
            elif self.drag_start[4] and self.dragged:
                self.react('land')
            self.save()
        self.drag_start = None
        self.double_click = False

    def cancel_pending_click(self):
        if self.click_timer is not None:
            self.root.after_cancel(self.click_timer)
        self.click_timer = None
        self.pending_click = None

    def finish_single_click(self):
        pending = self.pending_click
        self.cancel_pending_click()
        if not pending or self.closed:
            return
        self.click_count += 1
        self.react('pout' if self.click_count%3 == 0 else 'click')
        self.expanded = not self.expanded
        self.draw()
        self.save()

    def cancel_drag(self):
        self.cancel_pending_click()
        self.double_click = False
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
        self.cancel_pending_click()
        self.animation.touch(time.monotonic())
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label='摸摸头 · 开心轻笑', command=lambda: self.react('pat'))
        menu.add_command(label='逗一下 · 鼓脸', command=lambda: self.react('pout'))
        menu.add_command(label='开心跳一跳', command=lambda: self.react('land'))
        menu.add_command(label='关闭语气音效' if self.audio.enabled else '开启语气音效',
                         command=self.toggle_sound)
        menu.add_separator()
        menu.add_command(label='收起气泡' if self.expanded else '展开重置时间', command=self.toggle)
        menu.add_command(label='重新读取账户快照', command=lambda: setattr(self,'last_read',0))
        menu.add_command(label='刷新 Codex 额度', command=self.refresh_usage,
                         state='disabled' if self.refresh_busy else 'normal')
        automatic=tk.Menu(menu,tearoff=False)
        automatic.add_command(label='开启：到期前 16–6 分钟',command=lambda:self.enable_auto(960,360),
                              state='disabled' if self.auto_busy else 'normal')
        automatic.add_command(label='开启：到期前 5 分钟至到期',command=lambda:self.enable_auto(300,0),
                              state='disabled' if self.auto_busy else 'normal')
        automatic.add_command(label='关闭自动使用',command=self.disable_auto)
        menu.add_cascade(label='临期重置卡自动使用',menu=automatic)
        if not self.root.overrideredirect():
            menu.add_command(label='切换为无边框桌面悬浮', command=self.enable_overlay)
        menu.add_separator()
        menu.add_command(label='退出桌面小精灵', command=lambda: self.close('user_menu'))
        try:
            menu.tk_popup(event.x_root,event.y_root)
        finally:
            menu.grab_release()

    def save(self):
        try:
            write_json(self.settings, {'x': self.root.winfo_x(),'y': self.root.winfo_y(),
                                      'expanded': self.expanded,'sound_enabled':self.audio.enabled})
        except OSError:
            pass

    def enable_overlay(self):
        self.canvas.configure(bg=TRANSPARENT)
        if os.name == 'nt':
            self.root.attributes('-transparentcolor',TRANSPARENT)
        self.root.overrideredirect(True)

    def toggle_sound(self):
        self.audio.set_enabled(not self.audio.enabled)
        self.save()

    def close(self, reason='programmatic'):
        if self.closed:
            return
        logging.info('Desktop close requested: reason=%s', reason)
        self.close_reason = reason
        self.closed = True
        self.cancel_pending_click()
        self.refresh_cancel.set()
        self.audio.close()
        try:
            self.write_runtime()
        except Exception:
            logging.exception('Final runtime status write failed')
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
        logging.info('Desktop companion 0.4.5 starting, pid=%s',os.getpid())
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
