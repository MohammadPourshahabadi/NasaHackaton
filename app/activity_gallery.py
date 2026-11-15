"""Offline illustrated activity clips."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from ai_label import ai_tag

CLIPS = ('Drink water', 'Lie down', 'Sit down', 'Walk', 'Eat a snack', 'Meditate with music')
CHARACTERS = {'Woman': ('activity-frames.png', 'activity-woman-extra.png'),
              'Man': ('activity-man.png', 'activity-man-extra.png')}


def inline_activity(parent, name, title, guidance, steps=(), on_repeat=None, equipment=None):
    """Loop the corresponding recovery clip beside its next step."""
    panel = tk.Frame(parent, bg='#203a3e', padx=10, pady=10)
    panel.pack(fill='x', pady=(0,10))
    picture = tk.Label(panel, bg='#203a3e')
    picture.pack(side='left', padx=(0,16))
    text = tk.Frame(panel, bg='#203a3e')
    text.pack(side='left', fill='x', expand=True)
    tk.Label(text, text=title, bg='#203a3e', fg='#f3f5ed',
             font=('Segoe UI',16,'bold'), wraplength=400, justify='left').pack(anchor='w')
    tk.Label(text, text=guidance, bg='#203a3e', fg='#b7cbc5',
             font=('Segoe UI',11), wraplength=360, justify='left').pack(anchor='w', pady=(5,0))
    for index, step in enumerate(steps,1):
        tk.Label(text,text=f'{index}.  {step}',bg='#203a3e',fg='#f3f5ed',
                 font=('Segoe UI',10),wraplength=410,justify='left').pack(anchor='w',pady=(4,0))
    if on_repeat:
        ttk.Button(text,text='Log repeat reading',style='Primary.TButton',command=on_repeat).pack(anchor='w',pady=(8,0))
    row = CLIPS.index(name)
    with Image.open(Path(__file__).with_name(CHARACTERS['Woman'][0])) as source:
        width,height=source.size
        frames = [ImageTk.PhotoImage(ai_tag(source.crop(
            (i*width//4,row*height//4,(i+1)*width//4,(row+1)*height//4)).resize(
                (142,142),Image.Resampling.LANCZOS)),master=picture) for i in range(4)]
    order=(0,1,2,3,3,3)
    if equipment is not None:
        frames.append(ImageTk.PhotoImage(ai_tag(equipment.resize((142,142),Image.Resampling.LANCZOS)),master=picture))
        order += (4,4,4,4)
    index=0
    timer=None
    def draw():
        nonlocal index,timer
        picture.configure(image=frames[order[index]])
        index=(index+1)%len(order)
        timer=picture.after(470,draw)
    picture.bind('<Destroy>',lambda _:picture.after_cancel(timer) if timer else None)
    draw()
    return panel


def load_frames(window, filename, count):
    with Image.open(Path(__file__).with_name(filename)) as source:
        width, height = source.size
        return [[ImageTk.PhotoImage(ai_tag(source.crop((x*width//count, y*height//count, (x+1)*width//count,
                                                 (y+1)*height//count)).resize((456,456), Image.Resampling.LANCZOS)),
                                    master=window) for x in range(count)] for y in range(count)]


def open_activities(parent, initial=CLIPS[0]):
    window = tk.Toplevel(parent)
    window.title('Aboard · Activity animations')
    window.transient(parent)
    panel = ttk.Frame(window, padding=24)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Activity animations', style='Section.TLabel').pack(anchor='w')
    selected = tk.StringVar(value=initial)
    character = tk.StringVar(value='Woman')
    cast = ttk.Frame(panel)
    cast.pack(fill='x', pady=(10,0))
    ttk.Label(cast,text='Astronaut').pack(side='left',padx=(0,12))
    for name in CHARACTERS:
        ttk.Radiobutton(cast,text=name,value=name,variable=character).pack(side='left',padx=5)
    row = ttk.Frame(panel)
    row.pack(fill='x', pady=12)
    for index,name in enumerate(CLIPS):
        ttk.Radiobutton(row, text=name, value=name, variable=selected).grid(row=index//3,column=index%3,sticky='w',padx=5,pady=3)
    canvas = tk.Canvas(panel, width=456, height=456, bg='#0d2032', highlightthickness=0)
    canvas.pack()
    picture = canvas.create_image(228, 228)
    frames = {}
    playing = tk.BooleanVar(value=True)
    counter = 0
    scheduled = None
    sequences = ((0,0,1,2,2,2,3,0), (0,0,1,2,3,3,3), (0,0,1,2,3,3,3), (0,1,2,3),
                 (0,0,1,1,0), (0,0,1,1,1,1,1,1))

    def draw():
        index = CLIPS.index(selected.get())
        sequence = sequences[index]
        name = character.get()
        if name not in frames:
            main, extra = CHARACTERS[name]
            frames[name] = load_frames(window,main,4) + load_frames(window,extra,2)
        canvas.itemconfigure(picture, image=frames[name][index][sequence[counter % len(sequence)]])

    def tick():
        nonlocal counter, scheduled
        if playing.get():
            draw()
            counter += 1
        scheduled = window.after(240 if selected.get() == 'Walk' else 420, tick)

    def restart(*_):
        nonlocal counter
        counter = 0
        draw()

    selected.trace_add('write', restart)
    character.trace_add('write', restart)
    controls = ttk.Frame(panel)
    controls.pack(fill='x', pady=(12,0))
    ttk.Checkbutton(controls, text='Play loop', variable=playing).pack(side='left')
    ttk.Button(controls, text='Restart', command=restart).pack(side='right')
    window.bind('<Destroy>', lambda e: window.after_cancel(scheduled) if e.widget is window and scheduled else None)
    tick()
    return window
