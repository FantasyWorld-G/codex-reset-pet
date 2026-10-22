"""True per-pixel alpha Windows sprite window, owned by the companion app.

No color-key transparency, no circular mask, no external window automation.
"""
import ctypes as ct
from ctypes import wintypes as wt
from collections import deque
import logging
from PIL import ImageChops


def premultiplied_bgra(image):
    r,g,b,a = image.convert('RGBA').split()
    from PIL import Image
    return Image.merge('RGBA', (ImageChops.multiply(r,a),ImageChops.multiply(g,a),
                                ImageChops.multiply(b,a),a)).tobytes('raw','BGRA')


class POINT(ct.Structure):
    _fields_ = [('x',wt.LONG),('y',wt.LONG)]


class SIZE(ct.Structure):
    _fields_ = [('cx',wt.LONG),('cy',wt.LONG)]


class BLEND(ct.Structure):
    _fields_ = [('op',ct.c_ubyte),('flags',ct.c_ubyte),('alpha',ct.c_ubyte),('format',ct.c_ubyte)]


class BITMAPINFOHEADER(ct.Structure):
    _fields_ = [('size',wt.DWORD),('width',wt.LONG),('height',wt.LONG),
                ('planes',wt.WORD),('bits',wt.WORD),('compression',wt.DWORD),
                ('sizeimage',wt.DWORD),('xppm',wt.LONG),('yppm',wt.LONG),
                ('used',wt.DWORD),('important',wt.DWORD)]


class LayeredSprite:
    def __init__(self, size, press, move, release, menu, cancel=None):
        self.size = size
        self.on_press,self.on_move,self.on_release,self.on_menu = press,move,release,menu
        self.on_cancel = cancel
        self.events = deque()
        self.pointer_down = False
        self.closed = False
        self.user = ct.WinDLL('user32',use_last_error=True)
        self.gdi = ct.WinDLL('gdi32',use_last_error=True)
        self.kernel = ct.WinDLL('kernel32',use_last_error=True)
        callback = ct.WINFUNCTYPE(ct.c_ssize_t,wt.HWND,wt.UINT,wt.WPARAM,wt.LPARAM)

        class WNDCLASS(ct.Structure):
            _fields_ = [('style',wt.UINT),('proc',callback),('clsextra',ct.c_int),
                        ('wndextra',ct.c_int),('instance',wt.HINSTANCE),('icon',wt.HICON),
                        ('cursor',wt.HANDLE),('background',wt.HBRUSH),
                        ('menu',wt.LPCWSTR),('name',wt.LPCWSTR)]

        def bind(lib,name,args,result):
            fn = getattr(lib,name)
            fn.argtypes,fn.restype = args,result
            return fn

        bind(self.kernel,'GetModuleHandleW',[wt.LPCWSTR],wt.HMODULE)
        bind(self.user,'DefWindowProcW',[wt.HWND,wt.UINT,wt.WPARAM,wt.LPARAM],ct.c_ssize_t)
        bind(self.user,'RegisterClassW',[ct.POINTER(WNDCLASS)],wt.WORD)
        bind(self.user,'UnregisterClassW',[wt.LPCWSTR,wt.HINSTANCE],wt.BOOL)
        bind(self.user,'CreateWindowExW',[wt.DWORD,wt.LPCWSTR,wt.LPCWSTR,wt.DWORD,
             ct.c_int,ct.c_int,ct.c_int,ct.c_int,wt.HWND,wt.HMENU,wt.HINSTANCE,ct.c_void_p],wt.HWND)
        bind(self.user,'DestroyWindow',[wt.HWND],wt.BOOL)
        bind(self.user,'GetCursorPos',[ct.POINTER(POINT)],wt.BOOL)
        bind(self.user,'SetCapture',[wt.HWND],wt.HWND)
        bind(self.user,'ReleaseCapture',[],wt.BOOL)
        bind(self.user,'GetDC',[wt.HWND],wt.HDC)
        bind(self.user,'ReleaseDC',[wt.HWND,wt.HDC],ct.c_int)
        bind(self.user,'UpdateLayeredWindow',[wt.HWND,wt.HDC,ct.POINTER(POINT),ct.POINTER(SIZE),
             wt.HDC,ct.POINTER(POINT),wt.DWORD,ct.POINTER(BLEND),wt.DWORD],wt.BOOL)
        bind(self.gdi,'CreateCompatibleDC',[wt.HDC],wt.HDC)
        bind(self.gdi,'CreateDIBSection',[wt.HDC,ct.POINTER(BITMAPINFOHEADER),wt.UINT,
             ct.POINTER(ct.c_void_p),wt.HANDLE,wt.DWORD],wt.HBITMAP)
        bind(self.gdi,'SelectObject',[wt.HDC,wt.HGDIOBJ],wt.HGDIOBJ)
        bind(self.gdi,'DeleteObject',[wt.HGDIOBJ],wt.BOOL)
        bind(self.gdi,'DeleteDC',[wt.HDC],wt.BOOL)
        self.callback = callback(self.window_proc)
        self.instance = self.kernel.GetModuleHandleW(None)
        self.classname = 'CodexResetAlphaSprite_'+str(id(self))
        klass = WNDCLASS(0,self.callback,0,0,self.instance,None,None,None,None,self.classname)
        if not self.user.RegisterClassW(ct.byref(klass)):
            raise ct.WinError(ct.get_last_error())
        # WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self.hwnd = self.user.CreateWindowExW(0x08080088,self.classname,'重置小精灵人物',
                     0x90000000,0,0,size,size,None,None,self.instance,None)
        if not self.hwnd:
            raise ct.WinError(ct.get_last_error())
        screen = self.user.GetDC(None)
        self.dc = self.gdi.CreateCompatibleDC(screen)
        self.user.ReleaseDC(None,screen)
        header = BITMAPINFOHEADER(ct.sizeof(BITMAPINFOHEADER),size,-size,1,32,0,0,0,0,0,0)
        self.bits = ct.c_void_p()
        self.bitmap = self.gdi.CreateDIBSection(self.dc,ct.byref(header),0,ct.byref(self.bits),None,0)
        if not self.bitmap:
            raise ct.WinError(ct.get_last_error())
        self.old = self.gdi.SelectObject(self.dc,self.bitmap)
        self.last_pixels = None
        self.last_position = None

    def window_proc(self, hwnd, message, wparam, lparam):
        # Never enter Tcl/Tk from this ctypes callback. Windows may dispatch
        # sent input during another native call, outside Tk's Python/GIL bridge.
        # Tk's own animation timer drains the queue after this callback returns.
        try:
            return self.handle_message(hwnd,message,wparam,lparam)
        except Exception:
            logging.exception('Sprite native message failed: %#x',message)
            return 0

    def enqueue(self, kind, x=0, y=0):
        event = (kind,x,y)
        if kind == 'move' and self.events and self.events[-1][0] == 'move':
            self.events[-1] = event
        else:
            self.events.append(event)

    def drain_events(self):
        handlers = {'press':self.on_press,'move':self.on_move,
                    'release':self.on_release,'menu':self.on_menu}
        # A menu can run a nested native message loop. Leave its newly queued
        # input for the next frame rather than recursively entering handlers.
        for _ in range(len(self.events)):
            if self.closed:
                break
            kind,x,y = self.events.popleft()
            if kind == 'cancel':
                if self.on_cancel:
                    self.on_cancel()
            else:
                handlers[kind](x,y)

    def handle_message(self, hwnd, message, wparam, lparam):
        if self.closed:
            return self.user.DefWindowProcW(hwnd,message,wparam,lparam)
        if message in (0x201,0x200,0x202,0x205):
            point = POINT()
            self.user.GetCursorPos(ct.byref(point))
            if message == 0x201:
                self.pointer_down = True
                self.enqueue('press',point.x,point.y)
                self.user.SetCapture(hwnd)
            elif message == 0x200:
                if self.pointer_down:
                    self.enqueue('move',point.x,point.y)
            elif message == 0x202:
                was_down = self.pointer_down
                self.pointer_down = False
                if was_down:
                    self.enqueue('release',point.x,point.y)
                self.user.ReleaseCapture()
            else:
                self.enqueue('menu',point.x,point.y)
            return 0
        if (message == 0x1F or (message == 0x215 and lparam != hwnd)) and self.pointer_down:
            self.pointer_down = False
            self.enqueue('cancel')
            if message == 0x1F:
                self.user.ReleaseCapture()
            return 0
        if message == 0x14:
            return 1
        return self.user.DefWindowProcW(hwnd,message,wparam,lparam)

    def present(self, pixels, x, y):
        if self.closed:
            return
        if len(pixels) != self.size*self.size*4:
            raise ValueError('Sprite buffer must match the allocated 32-bit bitmap')
        position = (round(x),round(y))
        if pixels is self.last_pixels and position == self.last_position:
            return
        if pixels is not self.last_pixels:
            ct.memmove(self.bits,pixels,len(pixels))
        dest,source = POINT(*position),POINT(0,0)
        size,blend = SIZE(self.size,self.size),BLEND(0,0,255,1)
        if not self.user.UpdateLayeredWindow(self.hwnd,None,ct.byref(dest),ct.byref(size),
                 self.dc,ct.byref(source),0,ct.byref(blend),2):
            raise ct.WinError(ct.get_last_error())
        self.last_pixels,self.last_position = pixels,position

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.events.clear()
        if self.pointer_down:
            self.pointer_down = False
            self.user.ReleaseCapture()
        self.user.DestroyWindow(self.hwnd)
        self.gdi.SelectObject(self.dc,self.old)
        self.gdi.DeleteObject(self.bitmap)
        self.gdi.DeleteDC(self.dc)
        self.user.UnregisterClassW(self.classname,self.instance)
