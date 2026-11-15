"""Presentation widgets for the mission dashboard."""
import tkinter as tk
from tkinter import ttk
from functools import lru_cache
from PIL import Image, ImageDraw, ImageTk
from ai_label import ai_tag

BG='#152a2e'
CARD='#203a3e'
INK='#f3f5ed'
MUTE='#b7cbc5'
MINT='#a1e7cc'
METRIC_ART = {
    'Sleep': ('☾', '#a9bdff'), 'Fatigue': ('ϟ', '#ffc480'), 'Mood': ('☺', '#a9bdff'),
    'Stress': ('〰', MINT), 'Resting pulse': ('♥', '#f7a2b9'), 'Temperature': ('☀', '#ffd08a'),
    'Systolic': ('↗', '#ffd08a'), 'Diastolic': ('↘', MINT),
    'Grip strength': ('✊', '#f7a2b9'), 'Muscle circumference': ('◈', MINT),
    'Resting heart rate': ('♥', '#f7a2b9'), 'Systolic pressure': ('↗', '#ffd08a'),
    'Diastolic pressure': ('↘', '#ffd08a'),
}

@lru_cache
def shape(w,h,fill,r):
    image=Image.new('RGBA',(w*3,h*3))
    ImageDraw.Draw(image).rounded_rectangle((0,0,w*3-1,h*3-1),radius=r*3,fill=fill)
    return image.resize((w,h),Image.Resampling.LANCZOS)


STATUS_COLORS={'ok':'#80e8b5','watch':'#ffd181','alert':'#ff9b9b','none':'#6f8783'}


def fit_text(font,text,limit):
    """Shorten text with an ellipsis so it fits within limit pixels."""
    if font.measure(text)<=limit:
        return text
    while text and font.measure(text+'…')>limit:
        text=text[:-1]
    return text.rstrip()+'…'


def action(parent,label,command,primary=False,width=182):
    from tkinter import font as tkfont
    face=tkfont.Font(root=parent,family='Segoe UI',size=10,weight='bold')
    width=max(width,face.measure(label)+40)
    height=max(40,face.metrics('linespace')+18)
    button=tk.Canvas(parent,width=width,height=height,bg=parent.cget('background') if isinstance(parent,tk.Frame) else BG,
                     highlightthickness=0,takefocus=True,cursor='hand2')
    button.invoke=command
    normal=MINT if primary else '#365650'
    button.images=[ImageTk.PhotoImage(shape(width,height,c,height//2-1),master=button)
                   for c in (normal,'#a9f9e9' if primary else '#52766d')]
    item=button.create_image(0,0,anchor='nw',image=button.images[0])
    button.create_text(width/2,height/2,text=label,fill='#102738' if primary else INK,font=face)
    for event,idx in (('<Enter>',1),('<Leave>',0),('<FocusIn>',1),('<FocusOut>',0)):
        button.bind(event,lambda _e,i=idx:button.itemconfigure(item,image=button.images[i]))
    for event in ('<ButtonRelease-1>','<Return>','<space>'):
        button.bind(event,lambda _e:command())
    return button


def status_banner(parent,level,title,detail,facts=()):
    """Full-width 'how am I today' strip with a coloured status light."""
    colour=STATUS_COLORS[level]
    fill={'ok':'#1f4a3f','watch':'#4a4128','alert':'#4d2c33','none':CARD}[level]
    strip=tk.Frame(parent,bg=fill,padx=18,pady=10)
    light=tk.Canvas(strip,width=46,height=46,bg=fill,highlightthickness=0)
    light.create_oval(3,3,43,43,fill='',outline=colour,width=3)
    light.create_oval(13,13,33,33,fill=colour,outline='')
    light.pack(side='left',padx=(0,14))
    for value,caption in reversed(facts):
        box=tk.Frame(strip,bg=fill,padx=14); box.pack(side='right')
        tk.Label(box,text=value,bg=fill,fg=INK,font=('Segoe UI',16,'bold')).pack()
        tk.Label(box,text=caption,bg=fill,fg=MUTE,font=('Segoe UI',9)).pack()
    text=tk.Frame(strip,bg=fill); text.pack(side='left',fill='x',expand=True)
    tk.Label(text,text=title,bg=fill,fg=INK,font=('Segoe UI',15,'bold'),anchor='w').pack(anchor='w')
    tk.Label(text,text=detail,bg=fill,fg=MUTE,font=('Segoe UI',10),anchor='w',
             justify='left',wraplength=560).pack(anchor='w')
    return strip


def metric_icon(canvas,key,color,x,y):
    canvas.create_oval(x-16,y-16,x+17,y+17,fill='#314d50',outline='')
    def bounds(*coords):
        return tuple(value+(x-26 if i%2==0 else y-30) for i,value in enumerate(coords))
    def stroke(*coords):
        canvas.create_line(*bounds(*coords),fill=color,width=2,capstyle='round',joinstyle='round')
    if key=='sleep':
        canvas.create_arc(*bounds(17,20,34,38),start=70,extent=245,style='arc',outline=color,width=2)
        canvas.create_arc(*bounds(24,19,36,35),start=85,extent=180,style='arc',outline=color,width=2)
    elif key.startswith('trt'):
        canvas.create_line(*bounds(16,30,26,22,36,30,26,38,16,30),smooth=True,fill=color,width=2)
        canvas.create_oval(*bounds(23,27,29,33),fill=color,outline='')
    elif key.startswith('calf'):
        for line_y in (25,30,35):
            canvas.create_line(*bounds(17,line_y,26,line_y-3,35,line_y),smooth=True,fill=color,width=2)
    elif key.startswith('serum'):
        canvas.create_polygon(*bounds(26,20,18,31,20,37,26,40,33,36,34,31),
                            smooth=True,outline=color,fill='',width=2)
    else:
        stroke(15,30,21,30,24,23,28,37,31,30,37,30)


def tile(parent,label,value,unit,key,color,command,emphasis=False,status=None):
    from tkinter import font as tkfont
    small=tkfont.Font(root=parent,family='Segoe UI',size=9)
    big=tkfont.Font(root=parent,family='Segoe UI',size=14,weight='bold')
    width=max(204,big.measure('000.0')+small.measure('mEq/L')+86)
    height=max(62,small.metrics('linespace')+big.metrics('linespace')+18)
    card=tk.Canvas(parent,width=width,height=height,bg=BG,highlightthickness=0,
                   takefocus=True,cursor='hand2')
    card.invoke=command
    fills=('#572f38','#733d47') if emphasis else (CARD,'#36565a')
    card.images=[ImageTk.PhotoImage(shape(width-4,height-4,fill,15),master=card) for fill in fills]
    background=card.create_image(0,0,image=card.images[0],anchor='nw')
    metric_icon(card,key,color,26,height/2)
    left,right=51,width-26
    card.create_text(left,9,text=fit_text(small,label,right-left),font=small,anchor='nw',fill=MUTE)
    shown='—' if value in ('—',None,'') else str(value)
    number=card.create_text(left,height-9,text=shown,font=big,anchor='sw',fill=INK)
    if shown!='—':
        x=card.bbox(number)[2]+5
        card.create_text(x,height-12,text=fit_text(small,unit,right-x),font=small,anchor='sw',fill=MUTE)
    level=status or ('watch' if emphasis else ('none' if shown=='—' else 'ok'))
    card.create_oval(width-20,height/2-5,width-10,height/2+5,fill=STATUS_COLORS[level],outline='')
    for event,index in (('<Enter>',1),('<Leave>',0),('<FocusIn>',1),('<FocusOut>',0)):
        card.bind(event,lambda _e,i=index:card.itemconfigure(background,image=card.images[i]))
    for event in ('<ButtonRelease-1>','<Return>','<space>'):
        card.bind(event,lambda _:command())
    return card

ATLAS = {
    'Front': (22, 0, 530, 968),
    'Angled': (554, 0, 983, 968),
    'Back': (1004, 0, 1510, 968),
}


# Body sites on each plate: (x, y, label, metric keys). Coordinates are plate pixels.
BODY_SITES = {
    'Front': ((254,26,'Brain · sleep',('sleep',)),
              (236,82,'Eyes · SANS',('trt250_left','trt250_right')),
              (277,235,'Heart',('pulse','systolic','diastolic')),
              (254,335,'Blood labs',('serum_sodium','serum_potassium','serum_creatinine','serum_glucose'))),
    'Angled': ((247,235,'Heart',('pulse','systolic','diastolic')),),
    'Back': ((196,755,'Left calf',('calf_csa_left',)),(313,755,'Right calf',('calf_csa_right',))),
}


class AnatomyAtlas(tk.Canvas):
    """Clickable body: each site is coloured by the status of its latest readings."""

    def __init__(self, parent, on_metric, status=None):
        super().__init__(parent, height=450, width=363, bg='#102729', highlightthickness=0)
        from pathlib import Path
        with Image.open(Path(__file__).with_name('anatomy-atlas.png')) as source:
            self.plates = {name: source.crop(bounds).convert('RGB') for name, bounds in ATLAS.items()}
        self.view = 'Front'
        self.on_metric = on_metric
        self.status = status or {}
        self.halo_centres = {}
        self.pulse_phase = 0
        self.bind('<Configure>', lambda _: self.paint())
        self.after(600, self.breathe)

    def switch(self, view):
        self.view = view
        self.paint()

    def site_level(self, keys):
        levels = [self.status.get(key, 'none') for key in keys]
        for level in ('alert', 'watch', 'ok'):
            if level in levels:
                return level
        return 'none'

    def breathe(self):
        """Gently pulse the rings of sites that need attention."""
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        self.pulse_phase = (self.pulse_phase + 1) % 8
        grow = (0, 1, 2, 3, 4, 3, 2, 1)[self.pulse_phase]
        for item, (x, y) in self.halo_centres.items():
            r = 13 + grow
            self.coords(item, x-r, y-r, x+r, y+r)
        self.after(120, self.breathe)

    def paint(self):
        width, height = self.winfo_width(), self.winfo_height()
        if min(width, height) < 40:
            return
        plate = self.plates[self.view]
        ratio = min((height-18)/plate.height, (width-28)/plate.width)
        size = (round(plate.width*ratio), round(plate.height*ratio))
        scaled = plate.resize(size, Image.Resampling.LANCZOS)
        glows = [(px*ratio, py*ratio, STATUS_COLORS[self.site_level(keys)])
                 for px, py, _label, keys in BODY_SITES[self.view] if self.site_level(keys) != 'none']
        self.photo = ImageTk.PhotoImage(ai_tag(glow_sites(scaled, glows)), master=self)
        self.delete('all')
        self.halo_centres = {}
        self.create_image(width/2, height/2, image=self.photo)
        for px,py,label,keys in BODY_SITES[self.view]:
            x=(width-size[0])/2+px*ratio
            y=(height-size[1])/2+py*ratio
            level=self.site_level(keys)
            colour=STATUS_COLORS[level]
            tag='site_'+label.split()[0]
            if level in ('watch','alert'):
                halo=self.create_oval(x-13,y-13,x+13,y+13,outline=colour,width=2,tags=(tag,))
                self.halo_centres[halo]=(x,y)
            self.create_oval(x-9,y-9,x+9,y+9,fill='#203a3e',outline=colour,width=2,tags=tag)
            self.create_oval(x-4,y-4,x+4,y+4,fill=colour,outline='',tags=tag)
            text=self.create_text(x+17,y,text=label,fill=INK,font=('Segoe UI',9,'bold'),anchor='w',tags=tag)
            x0,y0,x1,y1=self.bbox(text)
            pill=self.create_rectangle(x0-5,y0-1,x1+5,y1+1,fill='#152a2e',outline=colour,tags=tag)
            self.tag_lower(pill,text)
            self.tag_bind(tag,'<ButtonRelease-1>',lambda _,k=keys:self.on_metric(*k))
            self.tag_bind(tag,'<Enter>',lambda _:self.configure(cursor='hand2'))
            self.tag_bind(tag,'<Leave>',lambda _:self.configure(cursor=''))


# ----------------------------------------------------------------------------- visual layer (art, cards, sticker)
from random import Random as _Random
from pathlib import Path as _Path
from PIL import ImageFilter, ImageFont

FONT_DIR = _Path('C:/Windows/Fonts')
BADGE_COLORS = {'nasa': ('#16345a', '#8fc2ff'), 'sim': ('#3a2a55', '#cdb4ff')}


@lru_cache(maxsize=32)
def font(size, bold=False):
    for name in (('segoeuib.ttf', 'arialbd.ttf') if bold else ('segoeui.ttf', 'arial.ttf')):
        try:
            return ImageFont.truetype(str(FONT_DIR / name), size)
        except OSError:
            continue
    return ImageFont.load_default()


def hex_rgb(colour, alpha=255):
    colour = colour.lstrip('#')
    return tuple(int(colour[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)


def starfield(width, height, seed=7, planet=True, top='#071423', bottom='#163640'):
    """Deep-space backdrop: vertical gradient, stars, a glowing planet limb and an orbit line."""
    width, height = max(2, int(width)), max(2, int(height))
    image = Image.new('RGBA', (width, height))
    draw = ImageDraw.Draw(image)
    a, b = hex_rgb(top), hex_rgb(bottom)
    for y in range(height):
        t = y / max(1, height - 1)
        draw.line((0, y, width, y), fill=tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,))
    rng = _Random(seed)
    stars = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(stars)
    for _ in range(width * height // 900):
        x, y = rng.uniform(0, width), rng.uniform(0, height)
        r = rng.choice((0.6, 0.8, 1.0, 1.0, 1.4, 2.0))
        alpha = rng.randint(90, 255)
        tint = rng.choice(((255, 255, 255), (200, 225, 255), (255, 240, 210)))
        sdraw.ellipse((x - r, y - r, x + r, y + r), fill=tint + (alpha,))
    image.alpha_composite(stars.filter(ImageFilter.GaussianBlur(0.4)))
    image.alpha_composite(stars)
    if planet:
        glow = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        g = ImageDraw.Draw(glow)
        radius = max(width, height) * 0.62
        cx, cy = width * 0.93, height + radius * 0.55
        g.ellipse((cx - radius - 26, cy - radius - 26, cx + radius + 26, cy + radius + 26), fill=(120, 230, 205, 120))
        glow = glow.filter(ImageFilter.GaussianBlur(28))
        image.alpha_composite(glow)
        body = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        p = ImageDraw.Draw(body)
        p.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(20, 62, 74, 255))
        p.ellipse((cx - radius + 10, cy - radius + 6, cx + radius - 4, cy + radius), fill=(28, 84, 92, 255))
        p.arc((cx - radius, cy - radius, cx + radius, cy + radius), 180, 360, fill=(161, 231, 204, 255), width=2)
        image.alpha_composite(body)
        orbit = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        ImageDraw.Draw(orbit).ellipse((width * 0.35, height * 0.18, width * 1.25, height * 1.6),
                                      outline=(161, 231, 204, 70), width=1)
        image.alpha_composite(orbit)
    return image


class RoundedCard(tk.Canvas):
    """A canvas that paints a rounded, softly shadowed card; put widgets in .body."""

    def __init__(self, parent, fill=CARD, radius=18, pad=14, page=BG, **options):
        super().__init__(parent, bg=page, highlightthickness=0, **options)
        self.fill, self.radius, self.pad = fill, radius, pad
        self.body = tk.Frame(self, bg=fill)
        self.window = self.create_window(pad, pad, window=self.body, anchor='nw')
        self.bind('<Configure>', self._paint)

    def _paint(self, event):
        width, height = event.width, event.height
        if width < 10 or height < 10:
            return
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        shadow = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((3, 6, width - 3, height - 1), self.radius, fill=(0, 0, 0, 120))
        image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(4)))
        card = Image.new('RGBA', (width * 2, height * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(card)
        d.rounded_rectangle((2, 2, width * 2 - 6, height * 2 - 10), self.radius * 2, fill=hex_rgb(self.fill),
                            outline=(66, 97, 105, 255), width=2)
        image.alpha_composite(card.resize((width, height), Image.Resampling.LANCZOS))
        self.photo = ImageTk.PhotoImage(image, master=self)
        self.delete('card')
        self.create_image(0, 0, image=self.photo, anchor='nw', tags='card')
        self.tag_lower('card')
        self.itemconfigure(self.window, width=width - 2 * self.pad, height=height - 2 * self.pad - 4)


def range_tile(parent, label, value, unit, key, color, command, status='none', comparison=None, emphasis=False):
    """Reading tile with a NASA/SIM badge and a bar showing the reading against its baseline range."""
    from tkinter import font as tkfont
    small = tkfont.Font(root=parent, family='Segoe UI', size=9)
    big = tkfont.Font(root=parent, family='Segoe UI', size=15, weight='bold')
    width = max(232, big.measure('000.0') + small.measure('mEq/L') + 120)
    height = max(86, small.metrics('linespace') + big.metrics('linespace') + 34)
    card = tk.Canvas(parent, width=width, height=height, bg=BG, highlightthickness=0, takefocus=True, cursor='hand2')
    card.invoke = command
    level_colour = STATUS_COLORS[status]
    fills = (('#4a2a33', '#5c3540') if emphasis else (CARD, '#2b4c50'))
    card.images = []
    for fill in fills:
        art = Image.new('RGBA', (width * 2, height * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(art)
        d.rounded_rectangle((0, 0, width * 2 - 4, height * 2 - 4), 26, fill=hex_rgb(fill),
                            outline=hex_rgb(level_colour, 150 if status in ('watch', 'alert') else 60), width=3)
        d.rounded_rectangle((0, 18, 7, height * 2 - 22), 4, fill=hex_rgb(level_colour))
        card.images.append(ImageTk.PhotoImage(art.resize((width - 2, height - 2), Image.Resampling.LANCZOS), master=card))
    background = card.create_image(0, 0, image=card.images[0], anchor='nw')
    metric_icon(card, key, color, 30, 30)
    left = 56
    shown = '—' if value in ('—', None, '') else str(value)
    badge = None
    if comparison:
        kind = comparison['kind']
        bg, fg = BADGE_COLORS[kind]
        text = 'NASA' if kind == 'nasa' else 'SIM'
        bw = small.measure(text) + 14
        card.create_rectangle(width - bw - 12, 9, width - 12, 9 + small.metrics('linespace') + 2, fill=bg, outline=fg)
        badge = card.create_text(width - 12 - bw / 2, 10 + small.metrics('linespace') / 2, text=text, fill=fg,
                                 font=('Segoe UI', 8, 'bold'))
    right = width - (70 if badge else 16)
    card.create_text(left, 10, text=fit_text(small, label, right - left), font=small, anchor='nw', fill=MUTE)
    number = card.create_text(left, 26, text=shown, font=big, anchor='nw', fill=INK)
    if shown != '—':
        x = card.bbox(number)[2] + 5
        card.create_text(x, card.bbox(number)[3] - 4, text=fit_text(small, unit, width - 16 - x), font=small,
                         anchor='sw', fill=MUTE)
    # range bar: track, baseline band, baseline tick, current reading dot
    y = height - 15
    x0, x1 = 16, width - 18
    card.create_line(x0, y, x1, y, fill='#35545a', width=6, capstyle='round')
    if comparison:
        lo, hi, base = comparison['low'], comparison['high'], comparison['value']
        reading = comparison.get('reading')
        points = [lo, hi, base] + ([reading] if reading is not None else [])
        span = (max(points) - min(points)) or 1
        start, end = min(points) - span * .12, max(points) + span * .12
        def at(v):
            return x0 + (v - start) / (end - start) * (x1 - x0)
        band_colour = '#3f6fa8' if comparison['kind'] == 'nasa' else '#6b55a0'
        card.create_line(at(lo), y, at(hi), y, fill=band_colour, width=6, capstyle='round')
        card.create_line(at(base), y - 7, at(base), y + 7, fill=INK, width=2)
        if reading is not None:
            card.create_oval(at(reading) - 6, y - 6, at(reading) + 6, y + 6, fill=level_colour, outline=BG, width=2)
    for event, index in (('<Enter>', 1), ('<Leave>', 0), ('<FocusIn>', 1), ('<FocusOut>', 0)):
        card.bind(event, lambda _e, i=index: card.itemconfigure(background, image=card.images[i]))
    for event in ('<ButtonRelease-1>', '<Return>', '<space>'):
        card.bind(event, lambda _e: command())
    return card


def _wrap(draw, text, face, limit):
    words, lines, line = text.split(), [], ''
    for word in words:
        trial = (line + ' ' + word).strip()
        if draw.textlength(trial, font=face) <= limit:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def mood_sticker(parent, mood, width=262):
    """A die-cut 'sticker' summarising mental health, drawn with PIL and slightly rotated."""
    scale = 3
    w = width * scale
    fill = hex_rgb(mood['colour'])
    title_font, small_font, comment_font = font(17 * scale, True), font(9 * scale), font(10 * scale)
    probe = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    lines = _wrap(probe, mood['comment'], comment_font, w - 60 * scale)[:4]
    h = (118 + 17 * len(lines)) * scale
    sticker = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(sticker)
    d.rounded_rectangle((0, 0, w - 1, h - 1), 26 * scale, fill=(250, 250, 244, 255))       # white die-cut edge
    d.rounded_rectangle((7 * scale, 7 * scale, w - 8 * scale, h - 8 * scale), 20 * scale, fill=fill)
    # face
    cx, cy, r = 44 * scale, 50 * scale, 26 * scale
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 247, 214, 255), outline=(40, 40, 40, 255), width=2 * scale)
    for ex in (cx - 9 * scale, cx + 9 * scale):
        d.ellipse((ex - 3 * scale, cy - 8 * scale, ex + 3 * scale, cy - 2 * scale), fill=(40, 40, 40, 255))
    curve = {'happy': (200, 340), 'up': (200, 340), 'ok': None, 'down': (20, 160), 'low': (20, 160)}[mood['face']]
    if curve and mood['face'] in ('happy', 'up'):
        d.arc((cx - 13 * scale, cy - 6 * scale, cx + 13 * scale, cy + 14 * scale), 20, 160, fill=(40, 40, 40, 255), width=3 * scale)
    elif curve:
        d.arc((cx - 12 * scale, cy + 6 * scale, cx + 12 * scale, cy + 22 * scale), 200, 340, fill=(40, 40, 40, 255), width=3 * scale)
    else:
        d.line((cx - 10 * scale, cy + 10 * scale, cx + 10 * scale, cy + 10 * scale), fill=(40, 40, 40, 255), width=3 * scale)
    ink = (20, 30, 34, 255)
    d.text((84 * scale, 20 * scale), mood['kicker'].upper(), font=font(8 * scale, True), fill=(20, 30, 34, 180))
    d.text((84 * scale, 33 * scale), mood['title'], font=title_font, fill=ink)
    d.text((84 * scale, 58 * scale), mood['detail'], font=small_font, fill=(20, 30, 34, 200))
    # sparkline of strain (inverted: higher = calmer)
    series = mood.get('series') or []
    if len(series) > 1:
        sx0, sx1, sy0, sy1 = 84 * scale, w - 22 * scale, 78 * scale, 98 * scale
        pts = [(sx0 + i * (sx1 - sx0) / (len(series) - 1), sy1 - (10 - v) / 9 * (sy1 - sy0)) for i, v in enumerate(series)]
        d.line(pts, fill=(20, 30, 34, 200), width=2 * scale, joint='curve')
        d.ellipse((pts[-1][0] - 4 * scale, pts[-1][1] - 4 * scale, pts[-1][0] + 4 * scale, pts[-1][1] + 4 * scale), fill=ink)
    y = 108 * scale
    for line in lines:
        d.text((22 * scale, y), line, font=comment_font, fill=ink)
        y += 17 * scale
    sticker = sticker.rotate(-3, resample=Image.Resampling.BICUBIC, expand=True)
    shadow = Image.new('RGBA', (sticker.width + 30, sticker.height + 30), (0, 0, 0, 0))
    mask = sticker.split()[3].point(lambda a: 110 if a > 0 else 0)
    shadow.paste((0, 0, 0, 255), (12, 18), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    shadow.alpha_composite(sticker, (6, 4))
    final = shadow.resize((shadow.width // scale, shadow.height // scale), Image.Resampling.LANCZOS)
    canvas = tk.Canvas(parent, width=final.width, height=final.height, bg=parent.cget('background'),
                       highlightthickness=0)
    canvas.photo = ImageTk.PhotoImage(final, master=canvas)
    canvas.create_image(0, 0, image=canvas.photo, anchor='nw')
    return canvas


def glow_sites(image, sites):
    """Paint soft radial glows under body-map sites. sites: [(x, y, colour)] in image pixels."""
    glow = Image.new('RGBA', image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    for x, y, colour in sites:
        for radius, alpha in ((30, 40), (20, 70), (11, 110)):
            d.ellipse((x - radius, y - radius, x + radius, y + radius), fill=hex_rgb(colour, alpha))
    base = image.convert('RGBA')
    base.alpha_composite(glow.filter(ImageFilter.GaussianBlur(9)))
    return base


def glass_card(image, box, fill, radius=26):
    """Paint a rounded card with a soft shadow and thin edge straight into a backdrop image."""
    image = image.copy()
    x0, y0, x1, y1 = (int(v) for v in box)
    shadow = Image.new('RGBA', image.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((x0 + 4, y0 + 10, x1 + 4, y1 + 12), radius, fill=(0, 0, 0, 150))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14)))
    card = Image.new('RGBA', image.size, (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle((x0, y0, x1, y1), radius, fill=hex_rgb(fill),
                                           outline=(110, 170, 165, 160), width=1)
    image.alpha_composite(card)
    return image
