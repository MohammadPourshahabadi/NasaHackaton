"""Daily wellbeing rating controls and offline next-step animation."""
from math import cos, pi, sin
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk

INK = '#f3f5ed'
PANEL = '#203a3e'
BG = '#152a2e'
MINT = '#a1e7cc'
COLORS = ('#68e7cc', '#79dfc2', '#9ae0ae', '#bbe18d', '#d4db79',
          '#ead273', '#f2be72', '#ffab80', '#ff998b', '#ff8a99')


def rating_panel(parent, questions):
    cards = ttk.Frame(parent)
    cards.pack(fill='x', pady=(4, 8))
    values = {key: tk.IntVar(master=cards) for key in questions}
    keys = list(questions)
    index = 0
    title = ttk.Label(cards, style='Section.TLabel')
    title.pack(anchor='w')
    progress_bar = ttk.Progressbar(cards, maximum=len(keys), length=610)
    progress_bar.pack(fill='x', pady=(10,14))
    prompt = ttk.Label(cards, wraplength=600, justify='left', style='Prompt.TLabel')
    prompt.pack(anchor='w', pady=(0,14))
    row = ttk.Frame(cards)
    row.pack(fill='x')
    faces = []

    def rate(score):
        values[keys[index]].set(score)
        show()

    for score, color in enumerate(COLORS, 1):
        face = tk.Canvas(row, width=57, height=76, bg=PANEL, highlightthickness=2,
                         highlightbackground=PANEL, highlightcolor=INK, takefocus=True,
                         cursor='hand2')
        face.pack(side='left', padx=(0, 4))
        glyph=Image.new('RGBA',(176,176))
        pen=ImageDraw.Draw(glyph)
        pen.ellipse((6,10,169,173),fill='#14292b')
        pen.ellipse((7,5,168,166),fill=color,outline=INK,width=3)
        for x in (59,114):
            pen.ellipse((x-6,57,x+6,74),fill=BG)
        curve=19-(score-1)*37/9
        pen.line([(x,100+curve*(1-((x-88)/32)**2)) for x in range(56,121)],
                 fill=BG,width=8)
        face.glyph=ImageTk.PhotoImage(glyph.resize((44,44),Image.Resampling.LANCZOS),master=face)
        face.create_image(28,30,image=face.glyph)
        face.create_text(28,62,text=str(score),fill=INK,font=('Segoe UI',12,'bold'))
        face.bind('<Button-1>', lambda _, s=score: rate(s))
        face.bind('<Return>', lambda _, s=score: rate(s))
        face.bind('<space>', lambda _, s=score: rate(s))
        faces.append(face)

    legend = ttk.Label(cards, style='Muted.TLabel')
    legend.pack(anchor='w', pady=(8,14))
    controls = ttk.Frame(cards)
    controls.pack(fill='x')
    prev = ttk.Button(controls, text='Previous', command=lambda: jump(-1))
    prev.pack(side='left')
    forward = ttk.Button(controls, text='Next question', command=lambda: jump(1))
    forward.pack(side='left', padx=6)
    progress = ttk.Label(controls, style='Muted.TLabel')
    progress.pack(side='right')

    def show():
        key = keys[index]
        value = values[key].get()
        title.configure(text=f'Wellbeing  ·  {index+1} of {len(keys)}')
        prompt.configure(text=questions[key])
        legend.configure(text='1  None     ·     10  Extreme' + (f'     ·     Selected {value}' if value else ''))
        answered=sum(bool(v.get()) for v in values.values())
        progress_bar.configure(value=answered)
        progress.configure(text=f'{answered} of {len(keys)} answered')
        for score, face in enumerate(faces, 1):
            face.configure(highlightbackground=COLORS[score-1] if score == value else PANEL,
                           bg='#3e5d55' if score == value else PANEL)
        prev.state(['!disabled'] if index else ['disabled'])
        forward.state(['!disabled'] if index+1 < len(keys) else ['disabled'])

    def jump(delta):
        nonlocal index
        index += delta
        show()

    def show_missing():
        nonlocal index
        index = next(i for i, key in enumerate(keys) if not values[key].get())
        show()
        faces[0].focus_set()

    show()
    return values, show_missing


def result_face(parent, mood, heading):
    face = tk.Canvas(parent, width=108, height=96, bg=BG, highlightthickness=0)
    face.pack(side='left')
    color={'good':'#a1e7cc','better':'#afd5ff','watch':'#f3d487','support':'#ffb3ab'}[mood]
    face.create_oval(14,8,94,88,fill=PANEL,outline=color,width=2)
    face.create_oval(21,15,87,81,fill=color,outline='')
    for x in (42,66):
        face.create_oval(x-3,36,x+3,46,fill=BG,outline='')
    shape={'good':58,'better':65,'watch':54,'support':49}[mood]
    face.create_line(39,54,54,shape,69,54,smooth=True,fill=BG,width=3,capstyle='round')
    ttk.Label(parent,text=heading,style='Title.TLabel',wraplength=520).pack(side='left',padx=(10,0))


def result_animation(parent, scene):
    """Render a compact, looping illustration of the selected action."""
    canvas = tk.Canvas(parent, height=142, width=612, bg=PANEL, highlightthickness=0)
    canvas.pack(fill='x', pady=(5, 0))
    titles = {'routine': ('Keep your routine', 'Sleep  ·  Activity  ·  Connection'),
              'reset': ('Take a short reset', 'Pause  ·  Relax your shoulders'),
              'sleep': ('Protect your sleep window', 'Return to your scheduled rest routine'),
              'support': ('Request private support', 'Crew medical officer  →  Private conference'),
              'crew': ('Notify the crew', 'Share the repeat reading')}
    title, detail = titles[scene]
    sequence = scene in ('support','crew')
    if not sequence:
        canvas.create_text(150, 52, text=title, anchor='w', fill=INK, font=('Segoe UI', 17, 'bold'))
        canvas.create_text(150, 83, text=detail, anchor='w', fill=MINT, font=('Segoe UI', 11))
        canvas.create_oval(15, 10, 125, 120, fill=BG, outline='#426169', width=2)
    frame = 0
    timer = None

    def draw():
        nonlocal frame, timer
        canvas.delete('animated')
        phase = (1-cos(2*pi*frame/100))/2

        def circle(x, y, r, **options):
            canvas.create_oval(x-r, y-r, x+r, y+r, tags='animated', **options)

        if scene == 'reset':
            for i, color in enumerate(('#214e63', '#367b88', MINT)):
                circle(70, 65, 15 + (2-i)*9 + phase*14, outline=color, width=2)
        elif scene == 'sleep':
            circle(66, 63, 24, fill='#e2dbab', outline='')
            circle(76, 53, 22, fill=BG, outline='')
            for i, (x, y) in enumerate(((90, 45), (99, 66), (86, 81))):
                circle(x, y, 2+sin(frame/16+i), fill=INK, outline='')
        elif sequence:
            active = frame//60
            labels = (('Tell the crew lead','Share both readings','Contact flight surgeon') if scene=='crew'
                      else ('Contact crew medical','Request a private visit','Confirm the time'))
            canvas.create_line(108,62,504,62,fill='#52716b',width=2,tags='animated')
            for i, label in enumerate(labels):
                x=108+198*i
                color=MINT if i==active else '#b7cbc5'
                if i==active:
                    circle(x,62,34+phase*3,outline=MINT,width=2)
                circle(x,62,28,fill=BG,outline='',width=0)
                if i==0:
                    circle(x,55,6,outline=color,width=2)
                    canvas.create_arc(x-11,63,x+11,80,start=0,extent=180,style='arc',
                                      outline=color,width=2,tags='animated')
                elif i==1:
                    canvas.create_rectangle(x-12,53,x+12,69,outline=color,width=2,tags='animated')
                    canvas.create_line(x-10,54,x,62,x+10,54,fill=color,width=2,tags='animated')
                else:
                    canvas.create_rectangle(x-11,51,x+11,74,outline=color,width=2,tags='animated')
                    canvas.create_line(x-6,65,x-1,69,x+7,61,fill=color,width=2,tags='animated')
                canvas.create_text(x,113,text=label,fill=color,font=('Segoe UI',10,'bold'),tags='animated')
        else:
            for i in range(3):
                angle = 2*pi*(i/3 + frame/100)
                circle(70+34*cos(angle), 65+34*sin(angle), 5, fill=MINT, outline='')
            canvas.create_line(59, 65, 67, 73, 82, 56, fill=INK, width=3,
                               capstyle='round', joinstyle='round', tags='animated')
        frame = (frame+1) % (180 if sequence else 100)
        timer = canvas.after(40, draw)

    canvas.bind('<Destroy>', lambda _: canvas.after_cancel(timer) if timer is not None else None)
    draw()
