"""Crew login, body map, and mission journal interface."""
import os
from pathlib import Path
from datetime import datetime, date, timedelta, time
import json
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from threading import Thread, Event, Lock
from queue import Queue, Empty
import subprocess
from http.client import HTTPConnection, HTTPException
from time import monotonic, sleep as wait
from tempfile import TemporaryDirectory

from PIL import Image, ImageTk
from aboard import app_home, styles, FIELDS, NAVY, PANEL, FG, MUTED, ACCENT, COLORS
from analysis import get_numeric
from assistants import image_bytes
from cloud_agent import transcribe
from cloud_capture import record_wave, input_devices
from credentials import read_key, save_key
from dialogue import urgent_request, normalize
from motion import GuideFrame
from quality import inspect_image
from storage import Journal
from nasa_reference import ARCHIVED_MEASUREMENTS, IMAGING, NASA_MEASUREMENTS, REFERENCES, assess, supported_entry
from demo_journal import seed_demo
from activity_gallery import inline_activity, open_activities
from wellbeing_ui import rating_panel, result_animation, result_face
from measurement_gallery import GUIDES as MEASUREMENT_GUIDES, KEY_GUIDES, equipment_photos, open_measurement
from medical_followup import AHA, BP_SYMPTOMS, WELLBEING, severe_bp, apply_followup, wellbeing_summary
from polish import (AnatomyAtlas, action, tile, metric_icon, CARD, MINT, METRIC_ART, STATUS_COLORS,
                    RoundedCard, range_tile, mood_sticker, starfield, shape, BADGE_COLORS, hex_rgb, glass_card)
from baseline import baseline as baseline_for, compare as compare_baseline, outside_range, fmt as fmt_value
from random import Random
from math import isfinite
from statistics import mean

METRICS = NASA_MEASUREMENTS
ZONES = {'Forehead':(190,77), 'Chest':(190,164), 'Left arm':(121,178),
         'Right arm':(259,178), 'Abdomen':(190,224), 'Kidneys':(207,239),
         'Left leg':(165,319), 'Right leg':(216,319)}
USERS = ('mo','parisa','nayan','admin')
CHECKIN_START = time(8)
CHECKIN_END = time(12)
from ai_core import snapshot as core_snapshot, mood_summary as core_mood_summary
from ai_core import *  # noqa: F401,F403  (Ollama, extraction and question answering)
from ai_core import (LABELS, OllamaUnavailable, ensure_ollama, warm_up, explain_entry, answer_journal,
                     clarifications, extract_entry, rule_extract, transcribe_audio, whisper_paths, TEXT_MODEL,
                     VISION_MODEL, KEEP_ALIVE, CLARIFICATIONS)


def pill_button(parent, text, command, fill='#2c4d50', hover='#3d6a66'):
    """Rounded secondary button whose label can change (button.label('…'))."""
    from tkinter import font as tkfont
    face = tkfont.Font(root=parent, family='Segoe UI', size=10, weight='bold')
    width = max(120, face.measure('Stop recording') + 36)
    canvas = tk.Canvas(parent, width=width, height=40, bg=parent.cget('background'), highlightthickness=0,
                       cursor='hand2')
    canvas.images = [ImageTk.PhotoImage(shape(width, 40, colour, 19), master=canvas) for colour in (fill, hover)]
    item = canvas.create_image(0, 0, image=canvas.images[0], anchor='nw')
    label = canvas.create_text(width / 2, 20, text=text, fill=FG, font=face)
    canvas.bind('<Enter>', lambda _e: canvas.itemconfigure(item, image=canvas.images[1]))
    canvas.bind('<Leave>', lambda _e: canvas.itemconfigure(item, image=canvas.images[0]))
    canvas.bind('<ButtonRelease-1>', lambda _e: command())
    canvas.label = lambda new: canvas.itemconfigure(label, text=new)
    return canvas


class Mission(tk.Tk):
    def __init__(self, journal):
        super().__init__()
        self.journal = journal
        for table, sql in {
            'alerts':'CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, owner TEXT, stamp TEXT, message TEXT, details TEXT)',
            'reminders':'CREATE TABLE IF NOT EXISTS reminders (owner TEXT, day TEXT, PRIMARY KEY(owner,day))',
        }.items():
            journal.db.execute(sql)
        for name in USERS:
            if name not in journal.profiles():
                journal.add_profile(name)
        self.title('Healthy Astronauts • Crew health')
        self.geometry('1120x790')
        self.minsize(940,730)
        self.configure(bg=NAVY)
        styles(self)
        self.user = None
        self.profile_choice = tk.StringVar()
        self.generation = 0
        self.jobs = Queue()
        self.listen_stop = None
        self.alert_cursor = 0
        self.questionnaire_timer = tk.StringVar()
        self.checkin_saved = False
        self.profile_screen()
        self.tick_questionnaire()
        self.after(120, self.poll)
        self.after(10000, self.remind)

    def clear(self):
        self.generation += 1
        if self.listen_stop:
            self.listen_stop.set()
            self.listen_stop = None
        for widget in self.winfo_children():
            widget.destroy()

    def profile_picker(self, parent, centered=False):
        self.profile_choice = tk.StringVar(value=self.user or '')
        side = 'top' if centered else 'left'
        ttk.Label(parent, text='Crew profile').pack(side=side, padx=(0, 8))
        picker = ttk.Combobox(parent, textvariable=self.profile_choice, values=USERS,
                              state='readonly', width=26 if centered else 12)
        picker.pack(side=side, padx=(0, 8), pady=8 if centered else 0)
        picker.bind('<Return>', lambda _event: self.open_profile())
        if centered:
            action(parent,'Open dashboard',self.open_profile,True,width=230).pack(pady=(6,0))
            picker.focus_set()
        else:
            ttk.Button(parent, text='Log in', style='Primary.TButton',
                       command=self.open_profile).pack(side='left')

    def open_profile(self):
        name = self.profile_choice.get()
        if name in USERS:
            self.user = name
            self.dashboard()

    def profile_screen(self):
        self.clear()
        self.user = None
        sky=tk.Canvas(self,bg=NAVY,highlightthickness=0)
        sky.pack(fill='both',expand=True)
        body=tk.Frame(sky,bg='#10232b')
        card_id=sky.create_window(0,0,window=body)
        tk.Label(body,text='TEAM SOLUTIONFINDERS',bg='#10232b',fg=MINT,font=('Segoe UI',11,'bold')).pack(pady=(8,0))
        tk.Label(body,text='Healthy Astronauts',bg='#10232b',fg=FG,font=('Segoe UI',26,'bold')).pack()
        tk.Label(body,text='Offline health monitor for long missions',bg='#10232b',fg=MUTED,
                 font=('Segoe UI',10)).pack(pady=(2,22))
        tk.Label(body,text='Who is checking in?',bg='#10232b',fg=FG,font=('Segoe UI',13,'bold')).pack(pady=(0,10))
        crew=tk.Frame(body,bg='#10232b'); crew.pack()
        def choose(name):
            self.profile_choice.set(name)
            self.open_profile()
        for name in USERS:
            action(crew,name.title(),lambda n=name:choose(n),name!='admin',width=250).pack(pady=4)
        def paint(event):
            w,h=event.width,event.height
            art=starfield(w,h,seed=11)
            body.update_idletasks()
            cw,ch=body.winfo_reqwidth()+80,body.winfo_reqheight()+70
            cx,cy=w*.32,h/2
            art=glass_card(art,(cx-cw/2,cy-ch/2,cx+cw/2,cy+ch/2),'#10232b')
            sky.photo=ImageTk.PhotoImage(art,master=sky)
            sky.delete('scenery')
            sky.create_image(0,0,image=sky.photo,anchor='nw',tags='scenery')
            sky.tag_lower('scenery')
            sky.coords(card_id,cx,cy)
        sky.bind('<Configure>',paint)

    def dashboard(self):
        self.clear()
        self.header=tk.Canvas(self,height=104,bg=NAVY,highlightthickness=0)
        self.header.pack(fill='x')
        self.header.bind('<Configure>',lambda _e:self.paint_header())
        self.tabs=ttk.Notebook(self,style='Bare.TNotebook'); self.tabs.pack(fill='both',expand=True,padx=18,pady=(10,14))
        self.main=ttk.Frame(self.tabs,padding=(4,4))
        self.stats=ttk.Frame(self.tabs,padding=(10,6))
        self.tabs.add(self.main,text='Today')
        self.tabs.add(self.stats,text='Trends')
        self.tabs.bind('<<NotebookTabChanged>>',lambda _e:self.paint_header())
        self.alert_cursor = self.journal.db.execute('SELECT COALESCE(MAX(id),0) FROM alerts').fetchone()[0]
        self.render()
        self.check_due()
        self.background(lambda:warm_up(self.model_name()),lambda _r:None,lambda _e:None)

    def paint_header(self):
        bar=self.header
        if not bar.winfo_exists():
            return
        w,h=max(bar.winfo_width(),200),104
        bar.delete('all')
        bar.art=ImageTk.PhotoImage(starfield(w,h,seed=3),master=bar)
        bar.create_image(0,0,image=bar.art,anchor='nw')
        title=bar.create_text(28,30,text='Healthy Astronauts',fill=FG,font=('Segoe UI',24,'bold'),anchor='w')
        bar.create_text(bar.bbox(title)[2]+14,33,text=self.user.title(),fill=MINT,font=('Segoe UI',15,'bold'),anchor='w')
        bar.create_text(28,57,text=f'Crew health monitor · offline · {date.today():%A %d %B}',fill=MUTED,
                        font=('Segoe UI',9),anchor='w')
        bar.pills=[]
        def pill(x,y,text,command,selected=False,primary=False,anchor='w'):
            from tkinter import font as tkfont
            face=tkfont.Font(root=bar,family='Segoe UI',size=10,weight='bold')
            width=face.measure(text)+34
            if anchor=='e':
                x-=width
            fill=(MINT if selected else ('#2a4b52' if not primary else '#365650'))
            image=ImageTk.PhotoImage(shape(width,30,fill,14),master=bar)
            hover=ImageTk.PhotoImage(shape(width,30,'#a9f9e9' if selected else '#46706a',14),master=bar)
            bar.pills.extend((image,hover))
            tag=f'pill{len(bar.pills)}'
            item=bar.create_image(x,y,image=image,anchor='w',tags=tag)
            bar.create_text(x+width/2,y,text=text,fill=NAVY if selected else FG,font=face,tags=tag)
            bar.tag_bind(tag,'<Enter>',lambda _e:(bar.itemconfigure(item,image=hover),bar.configure(cursor='hand2')))
            bar.tag_bind(tag,'<Leave>',lambda _e:(bar.itemconfigure(item,image=image),bar.configure(cursor='')))
            bar.tag_bind(tag,'<ButtonRelease-1>',lambda _e:command())
            return x-12 if anchor=='e' else x+width+8
        current=self.tabs.index('current') if self.tabs.winfo_exists() else 0
        x=28
        for index,name in enumerate(('Today','Trends')):
            x=pill(x,86,name,lambda i=index:self.tabs.select(i),selected=current==index)
        x=w-24
        for name,command in (('Settings',self.settings),('Alerts',self.alerts),('Switch crew',self.profile_screen)):
            x=pill(x,32,name,command,anchor='e')

    def records(self):
        return self.journal.records(self.user)

    def render(self):
        for tab in (self.main,self.stats):
            for widget in tab.winfo_children(): widget.destroy()
        records=self.records()
        self.refresh_questionnaire(records)
        latest,status=self.snapshot(records)
        frame=ttk.Frame(self.main); frame.pack(fill='both',expand=True)
        frame.columnconfigure(0,weight=1)
        frame.rowconfigure(0,weight=1)

        # ---- body map
        left_card=RoundedCard(frame,width=290); left_card.grid(row=0,column=0,sticky='nsew',padx=(0,10))
        left=left_card.body
        tk.Label(left,text='Body status',bg=CARD,fg=FG,font=('Segoe UI',15,'bold')).pack(anchor='w',padx=6)
        tk.Label(left,text='Tap a glowing area to see its readings',bg=CARD,fg=MUTED,
                 font=('Segoe UI',9)).pack(anchor='w',padx=6)
        viewbar=tk.Frame(left,bg=CARD); viewbar.pack(fill='x',padx=2,pady=(5,3))
        body=AnatomyAtlas(left,self.metric_trend,status)
        body.configure(bg=CARD)
        view=tk.StringVar(value='Front')
        for angle in ('Front','Angled','Back'):
            ttk.Radiobutton(viewbar,text=angle,value=angle,variable=view,style='Card.TRadiobutton',
                            command=lambda name=angle:body.switch(name)).pack(side='left',padx=(0,6))
        legend=tk.Frame(left,bg=CARD); legend.pack(side='bottom',fill='x',padx=4,pady=(4,0))
        for level,word in (('ok','OK'),('watch','Check'),('alert','Urgent'),('none','None')):
            dot=tk.Canvas(legend,width=12,height=12,bg=CARD,highlightthickness=0)
            dot.create_oval(1,1,11,11,fill=STATUS_COLORS[level],outline='')
            dot.pack(side='left',padx=(0,3))
            tk.Label(legend,text=word,bg=CARD,fg=MUTED,font=('Segoe UI',9)).pack(side='left',padx=(0,6))
        body.pack(fill='both',expand=True)

        # ---- actions, tasks and mood
        center_card=RoundedCard(frame,width=300); center_card.grid(row=0,column=1,sticky='nsew',padx=(0,10))
        center=center_card.body
        tk.Label(center,text='Daily questionnaire',bg=CARD,fg=FG,font=('Segoe UI',13,'bold')).pack(anchor='w')
        tk.Label(center,textvariable=self.questionnaire_timer,bg=CARD,fg=MINT,
                 wraplength=250,justify='left',font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(1,8))
        action(center,'Open questionnaire',self.questionnaire,True,width=250).pack(anchor='w')
        action(center,'＋  New entry',self.entry,width=250).pack(anchor='w',pady=(8,0))
        action(center,'Ask me about your health',self.search,width=250).pack(anchor='w',pady=(8,0))
        tk.Frame(center,bg='#36565a',height=1).pack(fill='x',pady=12)
        self.task_list(center,records)
        mood_sticker(center,self.mood_summary(records),width=250).pack(anchor='w',pady=(10,0))

        # ---- readings
        column=ttk.Frame(frame); column.grid(row=0,column=2,sticky='nsew')
        scroller=tk.Canvas(column,bg=NAVY,highlightthickness=0,width=10)
        bar=ttk.Scrollbar(column,command=scroller.yview)
        scroller.configure(yscrollcommand=bar.set)
        scroller.pack(side='left',fill='both',expand=True)
        right=ttk.Frame(scroller)
        scroller.create_window(0,0,window=right,anchor='nw')
        def resize(_event=None):
            scroller.configure(scrollregion=scroller.bbox('all'),width=right.winfo_reqwidth())
            if right.winfo_reqheight()>scroller.winfo_height()>1:
                if not bar.winfo_ismapped(): bar.pack(side='right',fill='y')
            elif bar.winfo_ismapped():
                bar.pack_forget()
        right.bind('<Configure>',resize)
        scroller.bind('<Configure>',resize)
        def wheel(event):
            if bar.winfo_ismapped():
                scroller.yview_scroll(-1 if event.delta>0 else 1,'units')
        column.bind_all('<MouseWheel>',lambda e:wheel(e) if str(e.widget).startswith(str(column)) else None)
        ttk.Label(right,text='Readings vs baseline',style='Section.TLabel').pack(anchor='w')
        key_row=tk.Frame(right,bg=NAVY); key_row.pack(anchor='w',pady=(2,4))
        for kind,text in (('nasa','NASA  range from NASA website data'),('sim','SIM  simulated preflight baseline')):
            bg,fg=BADGE_COLORS[kind]
            tag,_,rest=text.partition('  ')
            tk.Label(key_row,text=tag,bg=bg,fg=fg,font=('Segoe UI',8,'bold'),padx=5).pack(side='left')
            tk.Label(key_row,text=' '+rest,bg=NAVY,fg=MUTED,font=('Segoe UI',8)).pack(side='left',padx=(0,10))
        flagged=[label for label,(key,_) in METRICS.items() if status.get(key) in ('watch','alert')]
        sections=(('Needs attention',lambda key:True),
                  ('Vital signs',lambda key:key in ('sleep','pulse','systolic','diastolic')),
                  ('Blood labs',lambda key:key.startswith('serum')),
                  ('Muscle and eyes',lambda key:key.startswith(('calf','trt'))))
        shown=set()
        for title,belongs in sections:
            labels=[label for label in (flagged if title=='Needs attention' else METRICS)
                    if label not in shown and belongs(METRICS[label][0])]
            if not labels:
                continue
            emphasis=title=='Needs attention'
            tk.Label(right,text=title.upper(),bg=NAVY,fg='#ffb9b8' if emphasis else MUTED,
                     font=('Segoe UI',9,'bold')).pack(anchor='w',pady=(8,3))
            tiles=ttk.Frame(right)
            tiles.pack(anchor='w')
            for i,label in enumerate(labels):
                shown.add(label)
                key,unit=METRICS[label]
                value=latest.get(key,'—')
                comparison=compare_baseline(self.user,key,value) or baseline_for(self.user,key)
                range_tile(tiles,label,value,unit,key,METRIC_ART.get(label,(None,MINT))[1],
                           lambda name=label:self.snapshot_entry(name),status=status.get(key,'none'),
                           comparison=comparison,emphasis=emphasis).grid(row=i//2,column=i%2,padx=(0,6),pady=(0,6))
        self.plots(records)
    def snapshot(self,records):
        return core_snapshot(records)

    def baseline_line(self,parent,key,value,bg=CARD,wrap=420):
        """One line: badge + 'within NASA range 44–79 bpm · +3 vs baseline'."""
        row=tk.Frame(parent,bg=bg)
        result=compare_baseline(self.user,key,value)
        if not result:
            return row
        badge_bg,badge_fg=BADGE_COLORS[result['kind']]
        tk.Label(row,text='NASA' if result['kind']=='nasa' else 'SIM',bg=badge_bg,fg=badge_fg,
                 font=('Segoe UI',7,'bold'),padx=4).pack(side='left',padx=(0,6))
        colour=STATUS_COLORS['ok'] if result['inside'] else STATUS_COLORS['watch']
        tk.Label(row,text=result['summary'],bg=bg,fg=colour,font=('Segoe UI',9),wraplength=wrap,
                 justify='left').pack(side='left')
        return row

    @staticmethod
    def mood_summary(records):
        return core_mood_summary(records)

    def task_list(self,parent,records):
        today=date.today().isoformat()
        todays=[r for r in records if r['stamp'][:10]==today]
        def has(*keys):
            return any(r['checkin'].get(key) not in (None,'') for r in todays for key in keys)
        tasks=(('Daily questionnaire',any(r.get('daily') for r in todays),self.questionnaire),
               ('Log last night\'s sleep',has('sleep'),lambda:self.snapshot_entry('Sleep')),
               ('Heart rate and blood pressure',has('pulse','systolic'),self.entry))
        done=sum(1 for _,ok,_ in tasks if ok)
        tk.Label(parent,text=f"Today's tasks  ·  {done}/{len(tasks)}",bg=CARD,fg=FG,
                 font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,4))
        for label,ok,command in tasks:
            row=tk.Frame(parent,bg=CARD,cursor='hand2'); row.pack(anchor='w',fill='x',pady=1)
            mark=tk.Canvas(row,width=20,height=20,bg=CARD,highlightthickness=0)
            if ok:
                mark.create_oval(1,1,19,19,fill=STATUS_COLORS['ok'],outline='')
                mark.create_line(6,10,9,14,15,6,fill=NAVY,width=2)
            else:
                mark.create_oval(2,2,18,18,outline=MUTED,width=2)
            mark.pack(side='left',padx=(0,8))
            text=tk.Label(row,text=label,bg=CARD,fg=MUTED if ok else FG,
                          font=('Segoe UI',10,'overstrike' if ok else 'normal'))
            text.pack(side='left')
            if not ok:
                for widget in (row,mark,text):
                    widget.bind('<Button-1>',lambda _e,c=command:c())

    def metric_trend(self,*keys):
        by_key={key:(label,unit) for label,(key,unit) in METRICS.items()}
        win=tk.Toplevel(self)
        names={frozenset(('pulse','systolic','diastolic')):'Heart',frozenset(('systolic','diastolic')):'Blood pressure',
               frozenset(('trt250_left','trt250_right')):'Eyes · optic nerve OCT',
               frozenset(('serum_sodium','serum_potassium','serum_creatinine','serum_glucose')):'Blood labs'}
        win.title(names.get(frozenset(keys),by_key[keys[0]][0]))
        win.configure(bg=NAVY)
        win.transient(self)
        panel=ttk.Frame(win,padding=18)
        panel.pack(fill='both',expand=True)
        ttk.Label(panel,text=win.title(),style='Section.TLabel').pack(anchor='w')
        records=self.records()
        cutoff=date.today()-timedelta(days=6)
        ttk.Label(panel,text='Last 7 days vs baseline · select a point to see its reading',style='Muted.TLabel').pack(anchor='w',pady=(2,8))
        for key in keys:
            label,unit=by_key[key]
            series=[]
            for record in records:
                try:
                    value=float(record['checkin'][key])
                except (KeyError,ValueError,TypeError):
                    continue
                if isfinite(value):
                    series.append((record['stamp'],value,bool(record.get('demo_series'))))
            if key.startswith('calf_csa') and series:
                series=[row for row in series if row[2]==series[-1][2] and row[1]>0]
                comparable=[(stamp,value) for stamp,value,_ in series]
                if len(comparable)>=2:
                    change=100*(comparable[-1][1]/comparable[0][1]-1)
                    text=f'{change:+.1f}% since {comparable[0][0][:10]}'
                    if series[-1][2]:
                        text+=' · Simulated data'
                    tk.Label(panel,text=text,fg='#ffce99' if change<0 else MINT,bg=CARD,
                             font=('Segoe UI',15,'bold'),padx=11,pady=7).pack(anchor='w')
                    ttk.Label(panel,text='Compare repeat scans from the same leg and scan site.',
                              style='Muted.TLabel').pack(anchor='w',pady=(3,6))
            chart=tk.Canvas(panel,width=520,height=164,bg=PANEL,highlightthickness=0)
            chart.pack(fill='x',pady=(0,6))
            samples=[(stamp,value) for stamp,value,_ in series if stamp[:10]>=cutoff.isoformat()]
            chart.bind('<Configure>',lambda e,c=chart,l=label,u=unit,k=key,d=samples:
                       self.draw_metric(c,e.width,l,u,k,d,cutoff))
        ttk.Button(panel,text='Close',command=win.destroy).pack(anchor='e',pady=(8,0))

    @staticmethod
    def has_short_sleep(record):
        value,_=get_numeric(record['checkin'],'sleep')
        return value is not None and (value<=5.5 or record.get('assessment',{}).get('short_sleep',False))

    def sleep_banner(self,parent,value,command=None):
        banner=tk.Frame(parent,bg='#472d34',padx=14,pady=8)
        labels=(tk.Label(banner,text='Short sleep · Check alertness',bg='#472d34',fg='#ffc3c2',
                         font=('Segoe UI',11,'bold')),
                tk.Label(banner,text=f'{value} h',bg='#472d34',fg='#fff3ee',
                         font=('Segoe UI',25,'bold')))
        for label in labels:
            label.pack(anchor='w')
        if command:
            action(banner,'＋  Log sleep',command,width=114).place(relx=1,rely=1,x=-9,y=-3,anchor='se')
        return banner
    def plots(self, records):
        ttk.Label(self.stats, text='Trends vs baseline', style='Section.TLabel').pack(anchor='w')
        ttk.Label(self.stats, text='Last 60 days · shaded band = baseline range (NASA data or simulated preflight) · '
                  'select a point to see its date and value',
                  style='Muted.TLabel').pack(anchor='w', pady=(2, 12))
        charts = self.stats
        container = tk.Canvas(charts, bg=NAVY, highlightthickness=0)
        scrollbar = ttk.Scrollbar(charts, command=container.yview)
        container.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        container.pack(fill='both', expand=True)
        inner = ttk.Frame(container)
        window = container.create_window(0, 0, anchor='nw', window=inner)
        inner.columnconfigure((0, 1), weight=1, uniform='chart')
        inner.bind('<Configure>', lambda _e: container.configure(scrollregion=container.bbox('all')))
        container.bind('<Configure>', lambda e: container.itemconfigure(window, width=e.width))
        def scroll(event):
            container.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        chart_metrics = dict(METRICS)
        chart_metrics.update({f'{label} · Archived': (key, unit)
                              for key, (label, unit) in ARCHIVED_MEASUREMENTS.items()
                              if any(key in record['checkin'] for record in records)})
        for i, (label, (key, unit)) in enumerate(chart_metrics.items()):
            chart = tk.Canvas(inner, width=220, height=164, bg=PANEL, highlightthickness=0)
            chart.grid(row=i//2, column=i%2, padx=5, pady=5, sticky='ew')
            samples = []
            cutoff=(date.today()-timedelta(days=60)).isoformat()
            for record in records:
                if record['stamp'][:10]<cutoff:
                    continue
                try:
                    value = float(record['checkin'][key])
                    if isfinite(value):
                        samples.append((record['stamp'], value))
                except (KeyError, ValueError, TypeError):
                    continue
            chart.bind('<Configure>', lambda e, c=chart, n=label, u=unit, k=key, d=samples:
                       self.draw_metric(c, e.width, n, u, k, d))
            chart.bind('<MouseWheel>', scroll)
        inner.bind('<MouseWheel>', scroll)
        container.bind('<MouseWheel>', scroll)

    def draw_metric(self, chart, width, label, unit, key, samples, week_start=None):
        chart.delete('all')
        accent = METRIC_ART.get(label, (None, MINT))[1]
        metric_icon(chart,key,accent,30,29)
        chart.create_text(55, 21, text=label, fill=FG, anchor='w', font=('Segoe UI', 10, 'bold'))
        chart.create_text(55, 38, text=unit, fill=MUTED, anchor='w', font=('Segoe UI', 9))
        base = baseline_for(self.user, key)
        if base:
            bg, fg = BADGE_COLORS[base['kind']]
            tag = chart.create_text(width-14, 21, text='NASA' if base['kind']=='nasa' else 'SIM', fill=fg,
                                    anchor='e', font=('Segoe UI', 8, 'bold'))
            x0, y0, x1, y1 = chart.bbox(tag)
            chart.tag_lower(chart.create_rectangle(x0-6, y0-2, x1+6, y1+2, fill=bg, outline=fg), tag)
            chart.create_text(x0-12, 21, text=base['range_text'], fill=MUTED, anchor='e', font=('Segoe UI', 8))
        if not samples:
            chart.create_text(width/2, 100, text='No recorded readings', fill=MUTED)
            return
        top, bottom = 58, 128
        values = [v for _, v in samples]
        scale = values + ([base['low'], base['high'], base['value']] if base else [])
        low, high = min(scale), max(scale)
        pad = (high - low) * .08 or 1
        low, high = low - pad, high + pad
        def level(value):
            return bottom - (value - low) * (bottom - top) / (high - low)
        right = width - 92
        if base:
            band = '#1c3552' if base['kind'] == 'nasa' else '#2e2748'
            chart.create_rectangle(16, level(base['high']), right, level(base['low']), fill=band, outline='')
            chart.create_text(width-14, level(base['high']), text=fmt_value(base['high']), fill=MUTED, anchor='e',
                              font=('Segoe UI', 8))
            chart.create_text(width-14, level(base['low']), text=fmt_value(base['low']), fill=MUTED, anchor='e',
                              font=('Segoe UI', 8))
            y = level(base['value'])
            chart.create_line(16, y, right, y, fill=FG, dash=(6, 3))
            word = 'NASA' if base['kind'] == 'nasa' else 'preflight'
            chart.create_text(width-14, y, text=f"{word} {fmt_value(base['value'])}", fill=FG, anchor='e',
                              font=('Segoe UI', 8, 'bold'))
        points=[]
        for i,(stamp,value) in enumerate(samples):
            progress=(date.fromisoformat(stamp[:10])-week_start).days/6 if week_start else i/max(1,len(samples)-1)
            x=22+min(1,progress)*(right-28)
            points.append((x,level(value)))
        if len(points)>1:
            chart.create_line(*[n for point in points for n in point], fill=accent, width=2)
        latest = samples[-1][1]
        where = ''
        if base:
            where = '  ·  ' + ('within' if base['low'] <= latest <= base['high'] else 'outside') + \
                    (' NASA range' if base['kind'] == 'nasa' else ' normal range')
        detail = chart.create_text(16, 148, text=f'Latest {latest:g} {unit}  ·  {len(samples)} readings{where}',
                                   fill=MUTED, anchor='w', font=('Segoe UI', 9))
        radius=5 if len(samples)<=14 else 3
        for index,((x,y),(stamp,value)) in enumerate(zip(points,samples)):
            r=radius+2 if index==len(samples)-1 else radius
            inside = not base or base['low'] <= value <= base['high']
            point=chart.create_oval(x-r,y-r,x+r,y+r,fill=accent if inside else STATUS_COLORS['watch'],outline='')
            chart.tag_bind(point,'<Button-1>',lambda _e,s=stamp,v=value:
                           chart.itemconfigure(detail,text=f'{s[:10]}  ·  {v:g} {unit}'))
    def questionnaire(self):
        win=tk.Toplevel(self)
        win.title('Daily questionnaire')
        win.transient(self)
        win.grab_set()
        panel=ttk.Frame(win,padding=22)
        panel.pack(fill='both',expand=True)
        ttk.Label(panel,text='Daily questionnaire',style='Title.TLabel').pack(anchor='w')
        ttk.Label(panel,textvariable=self.questionnaire_timer,style='Muted.TLabel').pack(anchor='w',pady=(2,16))
        answers,show_missing=rating_panel(panel,WELLBEING)
        feedback=ttk.Label(panel,style='Muted.TLabel')
        feedback.pack(anchor='w')
        def submit():
            ratings={key:value.get() for key,value in answers.items()}
            if not all(ratings.values()):
                show_missing()
                feedback.configure(text='Answer all six questions before saving.')
                return
            try:
                self.save_entry({},True,ratings)
            except (sqlite3.Error,ValueError) as error:
                messagebox.showerror('Questionnaire could not be saved',str(error),parent=win)
                return
            win.destroy()
        action(panel,'Save questionnaire',submit,True).pack(anchor='e',pady=(10,0))

    def valid_reading(self,key,value):
        try:
            number=float(value)
        except (TypeError,ValueError):
            return False
        if not -10000<number<10000 or ((key in REFERENCES or key in IMAGING) and number<=0):
            return False
        return key not in {field[0] for field in FIELDS} or get_numeric({key:value},key)[0] is not None

    def snapshot_entry(self,label):
        self.reading_entry((METRICS[label][0],))

    def reading_entry(self,keys,repeat_of=None):
        """Small dialog that asks only for the given readings (a single tile, or a flagged repeat)."""
        keys=list(dict.fromkeys(keys))
        original=next((r for r in self.records() if r['stamp']==repeat_of),None) if repeat_of else None
        names={frozenset(('systolic','diastolic')):'Blood pressure'}
        title=names.get(frozenset(keys),' and '.join(LABELS[k][0] for k in keys))
        win=tk.Toplevel(self); win.title(('Repeat · ' if repeat_of else '')+title)
        win.transient(self); win.grab_set(); win.configure(bg=NAVY)
        panel=tk.Frame(win,bg=NAVY,padx=24,pady=20); panel.pack(fill='both',expand=True)
        tk.Label(panel,text=('Repeat ' if repeat_of else '')+title,bg=NAVY,fg=FG,
                 font=('Segoe UI',18,'bold')).pack(anchor='w')
        if original:
            before=' / '.join(f"{original['checkin'].get(k,'—')}" for k in keys)
            unit=LABELS[keys[0]][1]
            tk.Label(panel,text=f"Earlier reading {before} {unit} at {original['stamp'][11:16]}. "
                                'Measure again and enter only the new value.',
                     bg=NAVY,fg=MUTED,font=('Segoe UI',10),wraplength=430,justify='left').pack(anchor='w',pady=(2,10))
        box=tk.Frame(panel,bg=CARD,padx=16,pady=12); box.pack(fill='x')
        fields={}
        for row,key in enumerate(keys):
            label,unit=LABELS[key]
            tk.Label(box,text=label,bg=CARD,fg=FG,font=('Segoe UI',11,'bold')).grid(row=row*2,column=0,sticky='w',pady=(4,0))
            var=tk.StringVar()
            field=ttk.Entry(box,textvariable=var,width=9,font=('Segoe UI',13))
            field.grid(row=row*2,column=1,padx=10,pady=(4,0))
            tk.Label(box,text=unit,bg=CARD,fg=MUTED,font=('Segoe UI',10)).grid(row=row*2,column=2,sticky='w')
            holder=tk.Frame(box,bg=CARD); holder.grid(row=row*2+1,column=0,columnspan=3,sticky='w',pady=(2,6))
            def refresh(_e=None,key=key,var=var,holder=holder):
                for widget in holder.winfo_children(): widget.destroy()
                if var.get().strip():
                    self.baseline_line(holder,key,var.get().strip(),wrap=380).pack(anchor='w')
            field.bind('<KeyRelease>',refresh)
            fields[key]=(var,field)
        error=tk.Label(panel,text='',bg=NAVY,fg=STATUS_COLORS['watch'],font=('Segoe UI',9))
        error.pack(anchor='w',pady=(6,0))
        guide=tk.Label(panel,text='How to measure',bg=NAVY,fg=MINT,cursor='hand2',font=('Segoe UI',9,'underline'))
        guide.pack(anchor='w')
        guide.bind('<Button-1>',lambda _e:open_measurement(win,KEY_GUIDES[keys[0]]))
        def submit(_e=None):
            data={}
            for key,(var,_field) in fields.items():
                value=var.get().strip()
                if not self.valid_reading(key,value):
                    error.configure(text=f'Enter a valid {LABELS[key][0].lower()} in {LABELS[key][1]}.'); return
                data[key]=value
            try:
                self.save_entry(data,False,repeat_of=repeat_of)
            except (sqlite3.Error,ValueError) as exc:
                error.configure(text=str(exc)); return
            win.destroy()
        action(panel,'Save reading',submit,True,width=150).pack(anchor='e',pady=(10,0))
        win.bind('<Return>',submit)
        next(iter(fields.values()))[1].focus_set()

    def entry(self,repeat_fields=(),repeat_of=None):
        if repeat_fields:  # a repeat asks only for the reading that was off
            return self.reading_entry(repeat_fields,repeat_of)
        win=tk.Toplevel(self); win.title('New entry'); win.transient(self); win.grab_set()
        win.configure(bg=NAVY); win.minsize(640,0)
        panel=tk.Frame(win,bg=NAVY,padx=24,pady=18); panel.pack(fill='both',expand=True)
        tk.Label(panel,text='New entry',bg=NAVY,fg=FG,font=('Segoe UI',20,'bold')).pack(anchor='w')
        tk.Label(panel,text='Type, speak or add a photo. Aboard reads it and fills in the numbers for you.',
                 bg=NAVY,fg=MUTED,font=('Segoe UI',10)).pack(anchor='w',pady=(0,10))
        notes=tk.Text(panel,height=5,width=64,wrap='word',bg=PANEL,fg=FG,insertbackground=FG,
                      padx=14,pady=12,font=('Segoe UI',11),relief='flat',highlightthickness=1,
                      highlightbackground='#36516a',highlightcolor=MINT)
        notes.pack(fill='x')
        hint='e.g. "Slept 6 hours. BP 128/84, pulse 72. Small scrape on my left forearm."'
        notes.insert('1.0',hint); notes.configure(fg=MUTED)
        def clear_hint(_e=None):
            if notes.get('1.0','end-1c')==hint:
                notes.delete('1.0','end'); notes.configure(fg=FG)
        notes.bind('<FocusIn>',clear_hint)
        def typed(_e=None):
            text=note_text()
            if text==state.get('typed'): return
            state['typed']=text
            quick_rules(text)
            if state['timer']: win.after_cancel(state['timer'])
            state['timer']=win.after(1200,lambda:analyse(auto=True))
        notes.bind('<KeyRelease>',typed)
        def note_text():
            text=notes.get('1.0','end-1c').strip()
            return '' if text==hint else text

        tools=tk.Frame(panel,bg=NAVY); tools.pack(fill='x',pady=(10,4))
        status=tk.Label(panel,text='Runs on this device: Windows OCR reads photos, Llama 3.2 reads the text.',
                        bg=NAVY,fg=MUTED,font=('Segoe UI',9),anchor='w')
        preview=tk.Frame(panel,bg=NAVY)
        found=tk.Frame(panel,bg=CARD,padx=14,pady=10)
        state={'image':None,'kind':'none','region':'General','analysed':'','from_photo':set(),'listening':None,
               'run':0,'timer':None,'ai_keys':set(),'manual':set()}
        values={}

        def refresh_found():
            for widget in found.winfo_children(): widget.destroy()
            tk.Label(found,text='Aboard found',bg=CARD,fg=FG,font=('Segoe UI',12,'bold')).grid(row=0,column=0,columnspan=4,sticky='w')
            region_text=f"Body area: {state['region']}" + ('  ·  detected' if state['analysed'] else '')
            tk.Label(found,text=region_text,bg=CARD,fg=MINT,font=('Segoe UI',9,'bold')).grid(row=0,column=4,columnspan=2,sticky='e')
            if not values:
                tk.Label(found,text='No readings yet. Write or say a number, add a photo of a device, or add one by hand.',
                         bg=CARD,fg=MUTED,font=('Segoe UI',9)).grid(row=1,column=0,columnspan=6,sticky='w',pady=(4,0))
            for row,(key,var) in enumerate(values.items(),start=1):
                label,unit=LABELS[key]
                tk.Label(found,text=label,bg=CARD,fg=FG,font=('Segoe UI',10,'bold')).grid(row=row,column=0,sticky='w',pady=3)
                field=ttk.Entry(found,textvariable=var,width=8); field.grid(row=row,column=1,padx=8)
                field.bind('<Return>',lambda _e:refresh_found())
                field.bind('<KeyRelease>',lambda _e,k=key:state['manual'].add(k),add='+')
                tk.Label(found,text=unit,bg=CARD,fg=MUTED,font=('Segoe UI',9)).grid(row=row,column=2,sticky='w')
                note=self.baseline_line(found,key,var.get(),wrap=250)
                note.grid(row=row,column=3,sticky='w',padx=(10,0))
                if key in state['from_photo']:
                    tk.Label(found,text='from photo · check',bg=CARD,fg=STATUS_COLORS['watch'],
                             font=('Segoe UI',8,'bold')).grid(row=row,column=4,padx=4)
                remove=tk.Label(found,text='✕',bg=CARD,fg=MUTED,cursor='hand2',font=('Segoe UI',10))
                remove.grid(row=row,column=5,padx=(6,0))
                remove.bind('<Button-1>',lambda _e,k=key:(values.pop(k,None),refresh_found()))
            manual=tk.Frame(found,bg=CARD); manual.grid(row=len(values)+1,column=0,columnspan=6,sticky='w',pady=(8,0))
            choice=tk.StringVar(value='Add a reading by hand…')
            box=ttk.Combobox(manual,textvariable=choice,values=list(METRICS),state='readonly',width=26)
            box.pack(side='left')
            def add_manual(_e=None):
                if choice.get() in METRICS:
                    key=METRICS[choice.get()][0]
                    values.setdefault(key,tk.StringVar()); state['manual'].add(key)
                    refresh_found()
            box.bind('<<ComboboxSelected>>',add_manual)
            guide=tk.Label(manual,text='How to measure',bg=CARD,fg=MINT,cursor='hand2',font=('Segoe UI',9,'underline'))
            guide.pack(side='left',padx=10)
            guide.bind('<Button-1>',lambda _e:open_measurement(win,KEY_GUIDES[METRICS[choice.get()][0]]
                                                                if choice.get() in METRICS else 'pulse'))
        for key in repeat_fields:
            values[key]=tk.StringVar()

        def show_photo(path):
            for widget in preview.winfo_children(): widget.destroy()
            with Image.open(path) as source:
                thumb=source.convert('RGB'); thumb.thumbnail((150,110))
            preview.photo=ImageTk.PhotoImage(thumb,master=preview)
            tk.Label(preview,image=preview.photo,bg=NAVY).pack(side='left')
            tk.Label(preview,text=Path(path).name,bg=NAVY,fg=MUTED,font=('Segoe UI',9)).pack(side='left',padx=10)
            preview.pack(fill='x',pady=(6,0),before=found)

        def quick_rules(text):
            """Instant first pass while typing; the local model refines it after a short pause."""
            result=rule_extract(text)
            fresh={k:v for k,v in result['readings'].items() if self.valid_reading(k,v)}
            for key in list(state['ai_keys']-set(fresh)-state['manual']):
                values.pop(key,None)
            for key,value in fresh.items():
                if key not in state['manual']:
                    values.setdefault(key,tk.StringVar()).set(value)
            state['ai_keys']=set(fresh)
            if result['region']!='General': state['region']=result['region']
            refresh_found()

        def analyse(then=None,auto=False):
            if state['timer']:
                win.after_cancel(state['timer']); state['timer']=None
            text=note_text()
            if not text and not state['image']:
                if not auto:
                    status.configure(text='Write, speak or add a photo first.',fg=STATUS_COLORS['watch'])
                return
            state['run']+=1; run=state['run']
            status.configure(text=('Reading as you type…' if auto else 'Reading your entry on this device…')
                             + (' Reading the photo first.' if state['image'] else ''),fg=MINT)
            image=state['image']
            def done(result):
                if not win.winfo_exists(): return
                if run!=state['run'] and not then: return  # a newer reading is on its way
                fresh={k:v for k,v in result['readings'].items() if self.valid_reading(k,v)}
                for key in list(state['ai_keys']-set(fresh)-state['manual']):
                    values.pop(key,None)
                for key,value in fresh.items():
                    if key not in state['manual']:
                        values.setdefault(key,tk.StringVar()).set(value)
                state['ai_keys']=set(fresh)
                state['from_photo']=set(result.get('from_photo',[]))
                state['region']=result['region']; state['kind']=result.get('image_kind','none')
                state['analysed']=text+str(image)
                symptoms=', '.join(result.get('symptoms') or [])
                seen=' · '.join(line for line in (result.get('photo_text') or '').splitlines() if line.strip())[:90]
                status.configure(text=f"Read by {result['engine']}" + (f"  ·  noted: {symptoms}" if symptoms else '')
                                 + (f"\nPhoto says: {seen}" if seen else ('\nNo printed numbers in the photo. '
                                    'It is attached for human review.' if image else '')),fg=MUTED,justify='left')
                refresh_found()
                if then: then()
            def failed(error):
                if win.winfo_exists():
                    status.configure(text=f'Could not read the entry: {error}',fg=STATUS_COLORS['watch'])
            self.background(lambda:extract_entry(text,image,self.model_name()),done,failed)

        def speak():
            if state['listening'] is not None:
                state['listening'].set(); speak_button.label('Transcribing…'); return
            stop=Event(); state['listening']=stop; speak_button.label('Stop recording')
            status.configure(text='Listening… speak your entry, then press Stop recording.',fg=MINT)
            def work():
                wave=record_wave(timeout=20,finish=stop,auto_pause=False)
                if not wave: raise ValueError('No audio captured. Check Windows Sound → Input.')
                return transcribe_audio(wave,self.journal.home)
            def done(text,error=False):
                state['listening']=None
                if not win.winfo_exists(): return
                speak_button.label('Speak')
                if error or not text:
                    status.configure(text=text or 'No words were recognised.',fg=STATUS_COLORS['watch']); return
                clear_hint(); notes.insert('end',(' ' if note_text() else '')+text)
                analyse()
            self.background(work,done,lambda error:done(error,True))

        def add_photo():
            path=filedialog.askopenfilename(parent=win,filetypes=[('Photos','*.png *.jpg *.jpeg')])
            if not path: return
            reading=inspect_image(path)
            if reading['status']=='error':
                messagebox.showerror('Image unavailable',reading['detail'],parent=win); return
            state['image']=path; show_photo(path); analyse()

        speak_button=pill_button(tools,'Speak',speak)
        speak_button.pack(side='left')
        pill_button(tools,'Add photo',add_photo).pack(side='left',padx=8)
        action(tools,'✦  Read it for me',analyse,True,width=170).pack(side='left')
        status.pack(fill='x',pady=(2,6))
        refresh_found(); found.pack(fill='x',pady=(6,0))

        def save(urgent=False):
            text=note_text()
            if not urgent and text and state['analysed']!=text+str(state['image']):
                analyse(then=lambda:save(False)); return
            data={k:v.get().strip() for k,v in values.items() if v.get().strip()}
            for key,value in data.items():
                if not self.valid_reading(key,value):
                    messagebox.showerror('Check value',f'Enter a valid {LABELS[key][0].lower()} reading.',parent=win); return
            if not (data or state['image'] or text or urgent):
                status.configure(text='Nothing to save yet.',fg=STATUS_COLORS['watch']); return
            data.update(notes=text,region=state['region'],region_attention=state['region']!='General',
                        urgent=urgent or urgent_request(normalize(text)))
            try:
                if state['image']:
                    kind='ultrasound_path' if state['kind']=='ultrasound' else 'injury_path'
                    data[kind]=self.journal.attach(state['image'])
                self.save_entry(data,False,repeat_of=repeat_of)
            except (OSError,sqlite3.Error,ValueError) as error:
                messagebox.showerror('Entry could not be saved',str(error),parent=win); return
            win.destroy()
        bottom=tk.Frame(panel,bg=NAVY); bottom.pack(fill='x',pady=(14,0))
        action(bottom,'Save entry',save,True,width=150).pack(side='right')
        notes.focus_set() if not repeat_fields else None

    def save_entry(self,data,daily,wellbeing=None,repeat_of=None):
        stamp=datetime.now().astimezone().isoformat(timespec='microseconds')
        data=supported_entry(data)
        if severe_bp(data) and not data.get('urgent'):
            data['bp_followup']=self.bp_questions()
        history=self.records()
        result=apply_followup(data,assess(data,history))
        if repeat_of and result['status']!='red':
            self.check_persistent_repeat(data,result,history,repeat_of)
        record={'checkin':data,'assessment':result,'status':result['status'],'daily':daily,'stamp':stamp}
        if repeat_of:
            record['repeat_of']=repeat_of
        if wellbeing is not None:
            record['wellbeing']=wellbeing_summary(wellbeing)
        with self.journal.db:
            self.journal.db.execute('INSERT INTO entries(stamp,profile,record) VALUES(?,?,?)',
                                    (stamp,self.user,json.dumps(record)))
            if result['status']=='red':
                details={**record,'astronaut':self.user,'doctor_delivery':'Queued on this device'}
                self.journal.db.execute('INSERT INTO alerts(owner,stamp,message,details) VALUES(?,?,?,?)',
                    (self.user,stamp,'Immediate crew medical attention requested.',json.dumps(details)))
        self.render()
        if wellbeing is not None and not data:
            self.questionnaire_result(record)
        else:
            self.assessment(record)

    @staticmethod
    def check_persistent_repeat(data,result,history,repeat_of):
        index=next((i for i,row in enumerate(history) if row['stamp']==repeat_of),None)
        if index is None:
            return
        original=history[index]['checkin']
        prior=history[:index]
        before=assess(original,prior)
        after=apply_followup(data,assess(data,prior))
        def direction(assessment,key,value):
            evidence=next((item for item in assessment.get('nasa_reference',[])
                           if item['metric']==key and item.get('outside')),None)
            limits={'pulse':(45,110),'systolic':(90,150),'diastolic':(50,95)}
            if evidence:
                low,high=evidence['comparison_band']
            else:
                low,high=limits.get(key,(float('-inf'),float('inf')))
            number=float(value)
            if number<low:
                return -1
            if number>=high:
                return 1
            anchor=assessment['baseline'].get(key,number)
            return (number>anchor)-(number<anchor)
        persistent=[key for key in before['flagged_metrics'] if key!='sleep'
                    and key in after['flagged_metrics'] and key in original and key in data
                    and direction(before,key,original[key])==direction(after,key,data[key])]
        previous=result['previous_readings']
        result.update(after,previous_readings=previous)
        if not persistent:
            return
        result.update(status='yellow', title='This reading is still off',
                      persistent_repeat={key:{'original':original[key],'repeat':data[key]} for key in persistent},
                      flagged_metrics=list(dict.fromkeys([*result['flagged_metrics'],*persistent])),
                      next_hours=0, recheck='Contact flight medicine now.')
        result['rationale'].insert(0,'The same measurement still warrants review when compared with the reading before the initial flag.')
        result['actions']=[
            'Tell the crew lead now and share both readings with the crew medical officer.',
            'Contact the flight surgeon on Earth through the mission medical channel. Send both readings and any symptoms.',
        ]

    def export_repeat_handoff(self,record,parent):
        path=filedialog.asksaveasfilename(parent=parent,title='Save private flight surgeon handoff',
                                         defaultextension='.json',filetypes=[('JSON record','*.json')])
        if not path:
            return
        original=next((row for row in self.records() if row['stamp']==record['repeat_of']),{})
        payload={'astronaut':self.user,'request':'Flight surgeon review of a persistent reading',
                 'original_time':record['repeat_of'],'repeat_time':record['stamp'],
                 'readings':record['assessment']['persistent_repeat'],
                 'original_notes':original.get('checkin',{}).get('notes',''),
                 'repeat_notes':record['checkin'].get('notes','')}
        try:
            Path(path).write_text(json.dumps(payload,indent=2),encoding='utf-8')
        except OSError as error:
            messagebox.showerror('Could not save handoff',str(error),parent=parent)
        else:
            messagebox.showinfo('Handoff saved','Share the file through your mission medical channel.',parent=parent)

    def questionnaire_result(self,record):
        check=record['wellbeing']
        win=tk.Toplevel(self)
        win.title('Healthy Astronauts · Wellbeing result')
        win.transient(self)
        panel=ttk.Frame(win,padding=26)
        panel.pack(fill='both',expand=True)
        ttk.Label(panel,text='Wellbeing check-in saved',style='Muted.TLabel').pack(anchor='w')
        previous=next((r['wellbeing'] for r in reversed(self.records())
                       if r['stamp']<record['stamp'] and 'wellbeing' in r
                       and r['wellbeing'].get('scale_min')==check.get('scale_min')),None)
        improving=previous and (sum(previous['ratings'].values())-sum(check['ratings'].values()))>=3
        if check['scene']=='support':
            mood,heading='support','Talk with a psychologist'
        elif improving:
            mood,heading='better','Less strain than last check-in'
        elif check['scene']=='routine':
            mood,heading='good','Low strain today'
        else:
            mood,heading='watch','Take care of yourself today'
        face=ttk.Frame(panel)
        face.pack(fill='x',pady=(5,12))
        result_face(face,mood,heading)
        ttk.Label(panel,text='Your next step',style='Section.TLabel').pack(anchor='w')
        result_animation(panel,check['scene'])
        ttk.Label(panel,text=check['action'],wraplength=612,justify='left').pack(anchor='w',pady=(4,16))
        summary=tk.Frame(panel,bg=CARD,padx=16,pady=14)
        summary.pack(fill='x')
        tk.Label(summary,text='Your six ratings',bg=CARD,fg=FG,font=('Segoe UI',12,'bold')).grid(
            row=0,column=0,columnspan=2,sticky='w',pady=(0,6))
        labels=('Mental fatigue','Stress','Workload','Sleep difficulty','Low mood','Impact on duties')
        for i,(key,label) in enumerate(zip(WELLBEING,labels)):
            score=check['ratings'][key]
            tk.Label(summary,text=f'{label}  ·  {score}/10',bg=CARD,fg=FG,font=('Segoe UI',10),
                     anchor='w',width=24).grid(row=1+i//2,column=i%2,sticky='w',padx=(0,30),pady=2)
        buttons=ttk.Frame(panel)
        buttons.pack(fill='x',pady=(15,0))
        self.show_ai_review(panel,record,before=buttons)
        if check['scene']=='reset':
            ttk.Button(buttons,text='Watch meditation',
                       command=lambda:open_activities(win,'Meditate with music')).pack(side='left',padx=7)
        action(buttons,'Done',win.destroy,True,width=96).pack(side='right')
        win.bind('<Escape>',lambda _:win.destroy())
        win.after_idle(win.lift)

    def bp_questions(self):
        modal=tk.Toplevel(self); modal.title('Very high blood pressure'); modal.transient(self)
        previous=self.grab_current(); modal.grab_set()
        body=ttk.Frame(modal,padding=20); body.pack(fill='both')
        ttk.Label(body,text='Are any of these symptoms present now?',style='Section.TLabel').pack(anchor='w')
        ttk.Label(body,text='If present, alert the crew medical officer now. Do not wait for a repeat reading.',
                  wraplength=470).pack(anchor='w',pady=5)
        flags={label:tk.BooleanVar() for label in BP_SYMPTOMS}
        for label,var in flags.items():
            ttk.Checkbutton(body,text=label,variable=var).pack(anchor='w')
        ttk.Label(body,text='If symptom-free, wait at least one minute before repeating. A repeat is optional here.',
                  wraplength=470).pack(anchor='w',pady=5)
        readings={}
        for key,label in [('systolic','Repeat systolic (mmHg)'),('diastolic','Repeat diastolic (mmHg)')]:
            row=ttk.Frame(body); row.pack(fill='x')
            ttk.Label(row,text=label).pack(side='left')
            readings[key]=tk.StringVar()
            ttk.Entry(row,textvariable=readings[key],width=8).pack(side='right')
        captured={}
        def submit():
            symptoms=[label for label,var in flags.items() if var.get()]
            repeat={k:v.get().strip() for k,v in readings.items() if v.get().strip()}
            if not symptoms and repeat:
                numbers=[get_numeric(repeat,k)[0] for k in ('systolic','diastolic')]
                if None in numbers or numbers[0]<=numbers[1]:
                    messagebox.showerror('Repeat reading','Enter both repeat values in order, or leave them blank.',parent=modal); return
            captured.update(symptoms=symptoms,repeat=repeat if not symptoms else {},source=AHA)
            modal.destroy()
        modal.protocol('WM_DELETE_WINDOW',submit)
        action(body,'Save answers',submit,True).pack(anchor='e')
        self.wait_window(modal)
        if previous and previous.winfo_exists(): previous.grab_set()
        return captured

    def show_ai_review(self,parent,record,before=None,visible=True):
        if not visible:
            return
        box=tk.Frame(parent,bg=PANEL,padx=14,pady=10)
        box.pack(fill='x',pady=(12,0),before=before)
        head=tk.Frame(box,bg=PANEL); head.pack(fill='x')
        tk.Label(head,text='✦  What this means',bg=PANEL,fg=FG,font=('Segoe UI',11,'bold')).pack(side='left')
        tk.Label(head,text=f'Local AI · {self.model_name()} · on this device',bg=PANEL,fg=MUTED,
                 font=('Segoe UI',8)).pack(side='right')
        line=tk.Label(box,text='Thinking on this device…',bg=PANEL,fg=MUTED,font=('Segoe UI',10),
                      wraplength=600,justify='left',anchor='w')
        line.pack(anchor='w',fill='x',pady=(6,0))
        questions=clarifications(record)
        if questions:
            tk.Label(box,text='Worth noting in your reply',bg=PANEL,fg=MUTED,
                     font=('Segoe UI',9,'bold')).pack(anchor='w',pady=(8,0))
            for question in questions:
                tk.Label(box,text='•  '+question,bg=PANEL,fg=FG,font=('Segoe UI',9),wraplength=600,
                         justify='left').pack(anchor='w')
        tk.Label(box,text='Explains the rule result above. It never changes the status or gives a diagnosis.',
                 bg=PANEL,fg=MUTED,font=('Segoe UI',8)).pack(anchor='w',pady=(8,0))
        owner=self.user
        def update(text):
            if line.winfo_exists():
                line.configure(text=text or 'Thinking on this device…',fg=FG)
        def save(text):
            try:
                self.journal.save_draft(owner,record['stamp'],text)
            except sqlite3.Error:
                pass
            update(text)
        def failed(error):
            if line.winfo_exists():
                line.configure(text=f'Local AI unavailable · {error} The rule result above still applies.',fg=MUTED)
        self.stream(lambda emit:explain_entry(record,self.model_name(),emit),update,save,failed)

    def assessment(self,record):
        assessment=record['assessment']
        win=tk.Toplevel(self)
        win.title('Healthy Astronauts · Entry review')
        win.transient(self)
        if assessment['status']=='green':
            panel=ttk.Frame(win,padding=26)
            panel.pack(fill='both',expand=True)
            top=ttk.Frame(panel); top.pack(fill='x',pady=(0,14))
            badge=tk.Canvas(top,width=64,height=64,bg=NAVY,highlightthickness=0)
            badge.create_oval(4,4,60,60,fill=STATUS_COLORS['ok'],outline='')
            badge.create_line(19,33,28,43,45,22,fill=NAVY,width=5,capstyle='round',joinstyle='round')
            badge.pack(side='left',padx=(0,16))
            words=ttk.Frame(top); words.pack(side='left')
            ttk.Label(words,text='All clear',style='Section.TLabel').pack(anchor='w')
            ttk.Label(words,text='These readings are within your usual range.',
                      style='Muted.TLabel').pack(anchor='w')
            readings=tk.Frame(panel,bg=CARD,padx=14,pady=10); readings.pack(fill='x')
            logged=[(label,record['checkin'][key],unit) for label,(key,unit) in METRICS.items()
                    if record['checkin'].get(key) not in (None,'')]
            for label,value,unit in logged[:6]:
                key=METRICS[label][0]
                tk.Label(readings,text=f'●  {label}   {value} {unit}',bg=CARD,fg=FG,
                         font=('Segoe UI',10,'bold'),anchor='w').pack(anchor='w')
                self.baseline_line(readings,key,value).pack(anchor='w',padx=(18,0),pady=(0,4))
            if not logged:
                tk.Label(readings,text='Note saved to your journal.',bg=CARD,fg=FG,
                         font=('Segoe UI',10)).pack(anchor='w')
            tk.Frame(panel,bg=NAVY,height=14).pack()
            done=action(panel,'Done',win.destroy,True,width=120)
            done.pack(anchor='e')
            win.bind('<Escape>',lambda _:win.destroy())
            done.focus_set()
            return
        win.geometry('690x590')
        canvas=tk.Canvas(win,bg=NAVY,highlightthickness=0)
        scrollbar=ttk.Scrollbar(win,command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y')
        canvas.pack(fill='both',expand=True)
        panel=ttk.Frame(canvas,padding=22)
        interior=canvas.create_window(0,0,window=panel,anchor='nw')
        canvas.bind('<Configure>',lambda event:canvas.itemconfigure(interior,width=event.width))
        panel.bind('<Configure>',lambda _:canvas.configure(scrollregion=canvas.bbox('all')))
        win.bind('<MouseWheel>',lambda event:canvas.yview_scroll(-1 if event.delta>0 else 1,'units'))
        severity=assessment['status']
        persistent=assessment.get('persistent_repeat')
        repeat_guides=set(assessment.get('repeat_guides',[]))
        bp_flag=bool({'systolic','diastolic'}&set(assessment.get('flagged_metrics',[])))
        badge,color={'red':('Immediate attention',COLORS['red']),
                     'yellow':('Follow up',COLORS['yellow'])}[severity]
        tk.Label(panel,text=badge,bg=PANEL,fg=color,padx=12,pady=5,
                 font=('Segoe UI',11,'bold')).pack(anchor='w')
        ttk.Label(panel,text=assessment['title'],style='Title.TLabel',wraplength=610).pack(
            anchor='w',pady=(7,12))

        short_sleep=self.has_short_sleep(record)
        if short_sleep:
            self.sleep_banner(panel,record['checkin']['sleep']).pack(fill='x',pady=(0,8))
        if persistent:
            result_animation(panel,'crew')
        elif severity=='yellow' and not severe_bp(record['checkin']):
            if short_sleep:
                inline_activity(panel,'Lie down','Protect your next sleep period',
                                'Use your scheduled rest window. If fatigue affects safe duty, tell the crew lead first.')
            if bp_flag:
                supine=record['checkin'].get('nasa_supine_confirmed',False)
                position='Rest face up as specified by your ground protocol.' if supine else 'Stabilize your body and arm using the onboard cuff procedure.'
                cuff=equipment_photos('orbit_bp',MEASUREMENT_GUIDES['orbit_bp'],False)
                inline_activity(panel,'Lie down' if supine else 'Sit down','Settle before the cuff repeat',
                                position,(
                                   'Fit the correct cuff on your bare upper arm.',
                                   'Keep still and quiet until the reading is complete.',
                                   'Record both pressure values in mmHg.',
                                ),lambda:self.entry(repeat_fields=('systolic','diastolic'),repeat_of=record['stamp']),
                                equipment=cuff[0] if cuff and not supine else None)
            elif 'pulse' in repeat_guides and not short_sleep:
                inline_activity(panel,'Sit down','Settle before the repeat',
                                'Use the resting position and timing in your onboard measurement procedure.')
        readings=ttk.Frame(panel)
        readings.pack(fill='x',pady=(0,10))
        for label,(key,unit) in METRICS.items():
            value=record['checkin'].get(key)
            if value not in (None,'') and not (key=='sleep' and short_sleep):
                index=len(readings.winfo_children())
                cell=tk.Frame(readings,bg=PANEL,padx=10,pady=6)
                cell.grid(row=index//2,column=index%2,sticky='nw',padx=(0,5),pady=2)
                tk.Label(cell,text=f'{label}  {value} {unit}',bg=PANEL,fg=FG,
                         font=('Segoe UI',10,'bold')).pack(anchor='w')
                self.baseline_line(cell,key,value,bg=PANEL,wrap=230).pack(anchor='w')
                if len(readings.winfo_children())>=4:
                    break

        ttk.Label(panel,text='What to do next',style='Section.TLabel').pack(anchor='w')
        for number,hint in enumerate(assessment['actions'],1):
            row=tk.Frame(panel,bg=PANEL,padx=11,pady=8)
            row.pack(fill='x',pady=(5,0))
            tk.Label(row,text=str(number),fg=color,bg=PANEL,font=('Segoe UI',12,'bold')).pack(side='left',padx=(0,10))
            tk.Label(row,text=hint,fg=FG,bg=PANEL,font=('Segoe UI',11),
                     wraplength=548,justify='left').pack(side='left')
        if severity=='red':
            ttk.Label(panel,text='Crew alert saved · Earth handoff queued for export',
                      style='Muted.TLabel').pack(anchor='w',pady=(8,0))
        if persistent and not severe_bp(record['checkin']):
            inline_activity(panel,'Sit down','Stay settled while you contact the crew',
                            'Rest in a safe position as directed by your crew medical officer.')
            inline_activity(panel,'Drink water','Follow your usual hydration plan',
                            'If permitted by your care instructions, sip water while you wait for guidance.')

        bar=ttk.Frame(panel)
        bar.pack(fill='x',pady=(12,0))
        guide=assessment.get('guide')
        kinds=dict.fromkeys(KEY_GUIDES[key] for key in IMAGING if key in record['checkin'])
        for kind in kinds:
            label=MEASUREMENT_GUIDES[kind].label
            ttk.Button(bar,text=f'{label} guide',command=lambda k=kind:open_measurement(win,k)).pack(side='left',padx=(0,4))
        if short_sleep:
            ttk.Button(bar,text='Review sleep log',command=lambda:open_measurement(win,'sleep_review')).pack(side='left',padx=(0,4))
        if persistent:
            ttk.Button(bar,text='Prepare Earth handoff',
                       command=lambda:self.export_repeat_handoff(record,win)).pack(side='left',padx=(0,4))
        elif severity=='yellow':
            keys=[item['metric'] for item in assessment.get('nasa_reference',[])
                  if item.get('outside') and item['metric'] in KEY_GUIDES]
            vital_keys={'bp':('systolic','diastolic'),'pulse':('pulse',)}
            for repeat_kind in assessment.get('repeat_guides',[]):
                keys.extend(vital_keys.get(repeat_kind,()))
            if any(key in ('systolic','diastolic') for key in keys):
                keys.extend(('systolic','diastolic'))
            keys=list(dict.fromkeys(keys))
            for kind in dict.fromkeys(KEY_GUIDES[key] for key in keys):
                if kind=='bp' and bp_flag and not severe_bp(record['checkin']):
                    continue
                fields=[key for key in keys if KEY_GUIDES[key]==kind]
                ttk.Button(panel,text=f'{MEASUREMENT_GUIDES[kind].label} · Repeat guide',
                           command=lambda k=kind,f=fields:open_measurement(
                               win,k,lambda:self.entry(repeat_fields=f,repeat_of=record['stamp']),
                               supine=record['checkin'].get('nasa_supine_confirmed',False))).pack(anchor='w',pady=(5,0))
        elif severity=='red' and guide:
            ttk.Button(bar,text='Open emergency guide',command=lambda:self.guide(guide)).pack(side='left')
        def details():
            detail=tk.Toplevel(win)
            detail.title('Entry details')
            detail.transient(win)
            view=tk.Text(detail,wrap='word',width=66,height=12,bg=PANEL,fg=FG,padx=14,pady=12)
            view.pack(fill='both',expand=True)
            view.insert('end','\n\n'.join(assessment['rationale']))
            view.configure(state='disabled')
        ttk.Button(bar,text='Why this result?',command=details).pack(side='right')
        self.show_ai_review(panel,record)

    def guide(self,kind):
        window=tk.Toplevel(self); window.title('Procedure'); window.geometry('900x675')
        guide=GuideFrame(window); guide.pack(fill='both',expand=True); guide.show_guide(kind)

    def model_name(self):
        return os.environ.get('ABOARD_OLLAMA_MODEL',TEXT_MODEL)

    def search(self):
        term=simpledialog.askstring('Ask me about your health','Ask anything about your health, for example:\n'
                                    '"Is my blood pressure normal compared with NASA data?"\n'
                                    '"How has my mood been this week?"   "When did I sleep the least?"',parent=self)
        if not term: return
        records=self.records()
        win=tk.Toplevel(self); win.title('Ask me about your health'); win.geometry('660x480'); win.configure(bg=NAVY)
        ttk.Label(win,text=term,style='Section.TLabel',wraplength=620,padding=(16,14,16,4)).pack(anchor='w')
        ttk.Label(win,text=f'Local AI · {self.model_name()} · on this device · answers from your entries and baselines',
                  style='Muted.TLabel',padding=(16,0)).pack(anchor='w')
        out=tk.Text(win,wrap='word',bg=PANEL,fg=FG,padx=14,pady=12,relief='flat',font=('Segoe UI',11),
                    highlightthickness=0)
        out.pack(fill='both',expand=True,padx=16,pady=(8,16))
        out.insert('end','Thinking on this device…')
        cleaned=[]
        for record in records:
            values={k:v for k,v in supported_entry(record['checkin']).items() if not k.endswith('_path')}
            cleaned.append({'date':record['stamp'][:10],'simulated':bool(record.get('demo_series')),'values':values,
                            'strain':mean(record['wellbeing']['ratings'].values()) if record.get('wellbeing') else None})
        def show(text):
            if win.winfo_exists():
                out.configure(state='normal'); out.delete('1.0','end'); out.insert('end',text); out.configure(state='disabled')
        user=self.user
        self.stream(lambda emit:answer_journal(term,cleaned,self.model_name(),emit,user),show,show,
                    lambda error:show(f'Local AI unavailable · {error}'))

    def stream(self,work,on_update,on_done,on_error):
        """Run work(emit) in a thread; emit(text) pushes partial text to the UI at most ~10 times a second."""
        token=self.generation
        last=[0.0]
        def emit(text):
            if monotonic()-last[0]>.1:
                last[0]=monotonic()
                self.jobs.put((token,on_update,text))
        def run():
            try: self.jobs.put((token,on_done,work(emit)))
            except Exception as error:
                self.jobs.put((token,on_error,str(error)))
        Thread(target=run,daemon=True).start()

    def background(self,work,done,on_error=None):
        token=self.generation
        def run():
            try: self.jobs.put((token,done,work()))
            except Exception as error:
                self.jobs.put((token,on_error or done,str(error)))
        Thread(target=run,daemon=True).start()

    def poll(self):
        while True:
            try: generation,done,result=self.jobs.get_nowait()
            except Empty: break
            if generation==self.generation and self.user: done(result)
        self.after(120,self.poll)

    def dictate(self,win,notes,button):
        if self.listen_stop is not None:
            self.listen_stop.set()
            button.configure(text='Transcribing…',state='disabled')
            return
        stop=Event(); self.listen_stop=stop
        button.configure(text='Stop & transcribe')
        def work():
            wave=record_wave(timeout=20,finish=stop,auto_pause=False)
            if not wave: raise ValueError('No audio captured. Check Windows Sound → Input.')
            local,model=whisper_paths()
            if local and model:
                with TemporaryDirectory() as tmp:
                    audio=Path(tmp)/'record.wav'; audio.write_bytes(wave)
                    dest=Path(tmp)/'transcript'
                    subprocess.run([str(local),'-m',str(model),'-f',str(audio),'-otxt','-of',str(dest),'-np'],
                                   check=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW,
                                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    return dest.with_suffix('.txt').read_text(encoding='utf8').strip()
            key=read_key(self.journal.home)
            if not key: raise ValueError('Set the Groq key in Settings or configure local Whisper.')
            return transcribe(wave,key)
        def done(text,error=False):
            self.listen_stop=None
            if win.winfo_exists():
                button.configure(text='Dictate notes',state='normal')
                if error or not text: messagebox.showinfo('Dictation',text or 'The service returned no words.',parent=win)
                else: notes.insert('end',text+' ')
        self.background(work,done,lambda error:done(error,True))

    def settings(self):
        window=tk.Toplevel(self)
        window.title('Local AI settings')
        window.transient(self)
        pane=ttk.Frame(window,padding=22)
        pane.pack(fill='both',expand=True)
        ttk.Label(pane,text='Local AI',style='Section.TLabel').pack(anchor='w')
        model=self.model_name()
        ttk.Label(pane,text=f'{model} · Text entry review and journal search').pack(anchor='w',pady=(4,4))
        ttk.Label(pane,text=f'{VISION_MODEL} · Entries with attachments').pack(anchor='w',pady=(0,10))
        ttk.Label(pane,text='Offline dictation: '+('Whisper installed' if whisper_paths()[0] else 'Whisper missing')).pack(anchor='w')
        status=tk.StringVar(value='Checking Ollama…')
        ttk.Label(pane,textvariable=status,wraplength=440).pack(anchor='w',pady=8)
        def check():
            installed={item.get('name') for item in ensure_ollama().get('models',[])}
            return 'Ready on this device.' if model in installed else f'Model missing. Run: ollama pull {model}'
        def refresh():
            status.set('Checking Ollama…')
            self.background(check,status.set,lambda error:status.set(error+' Start Ollama and try again.'))
        ttk.Button(pane,text='Check again',command=refresh).pack(anchor='w',pady=4)
        ttk.Button(pane,text='Groq dictation key',command=self.configure_groq).pack(anchor='w',pady=4)
        refresh()

    def configure_groq(self):
        value=simpledialog.askstring('Groq key','Enter a Groq API key to enable online dictation.',parent=self,show='•')
        if value:
            try: save_key(self.journal.home,value)
            except OSError: messagebox.showerror('Settings','Windows could not store the key.',parent=self)
            else: messagebox.showinfo('Settings','Groq key stored for this Windows account.',parent=self)

    def alerts(self):
        rows=list(self.journal.db.execute('SELECT owner,stamp,message,details FROM alerts ORDER BY id DESC'))
        win=tk.Toplevel(self); win.title('Crew alerts and Earth outbox'); win.geometry('660x460')
        box=tk.Listbox(win,bg=PANEL,fg=FG); box.pack(fill='both',expand=True,padx=12,pady=12)
        for owner,stamp,message,_ in rows:
            box.insert('end',f'{stamp[:16]}  {owner}  {message}')
        def export():
            selection=box.curselection()
            if not selection: return
            row=rows[selection[0]]
            if row[0]!=self.user and self.user!='admin':
                messagebox.showinfo('Crew alert','The astronaut or demo admin can export the full handoff.',parent=win); return
            path=filedialog.asksaveasfilename(parent=win,defaultextension='.json',initialfile='aboard-handoff.json')
            if path:
                data=json.loads(row[3]); data['request']='Flight surgeon review and feedback requested'
                Path(path).write_text(json.dumps(data,indent=2),encoding='utf8')
        ttk.Button(win,text='Export Earth handoff',command=export).pack(pady=8)

    def refresh_questionnaire(self,records):
        today=date.today().isoformat()
        self.checkin_saved=any(r.get('daily') and r['stamp'][:10]==today for r in records)
        self.update_questionnaire_timer(datetime.now())

    def update_questionnaire_timer(self,now):
        start=datetime.combine(now.date(),CHECKIN_START)
        end=datetime.combine(now.date(),CHECKIN_END)
        if self.checkin_saved:
            status='Completed today'
        elif now>=end:
            status='Window closed · Late check-in available'
        else:
            opens=now<start
            seconds=max(1,int(((start if opens else end)-now).total_seconds()+.999))
            hours,remainder=divmod(seconds,3600)
            minutes,seconds=divmod(remainder,60)
            status=f'{"Opens in" if opens else "Time left"}  {hours:02}:{minutes:02}:{seconds:02}'
        self.questionnaire_timer.set(status)

    def tick_questionnaire(self):
        now=datetime.now()
        day=now.date()
        if self.user and getattr(self,'questionnaire_day',day)!=day:
            self.refresh_questionnaire(self.records())
        self.questionnaire_day=day
        self.update_questionnaire_timer(now)
        self.after(1000,self.tick_questionnaire)

    def check_due(self):
        if not self.user: return
        now=datetime.now(); today=now.date().isoformat()
        if now.time()<CHECKIN_END or any(r.get('daily') and r['stamp'].startswith(today) and
                                     CHECKIN_START.isoformat(timespec='minutes')<=r['stamp'][11:16]<CHECKIN_END.isoformat(timespec='minutes')
                                     for r in self.records()): return
        with self.journal.db:
            cursor=self.journal.db.execute('INSERT OR IGNORE INTO reminders VALUES (?,?)',(self.user,today))
        if cursor.rowcount:
            self.after_idle(lambda:messagebox.showinfo('Daily questionnaire missed','The 08:00–12:00 local window has closed. You can still log a check-in.',parent=self))

    def remind(self):
        self.check_due()
        if self.user:
            rows=list(self.journal.db.execute('SELECT id,owner,message FROM alerts WHERE id>? ORDER BY id',
                                             (self.alert_cursor,)))
            if rows:
                self.alert_cursor=rows[-1][0]
                for _,owner,message in rows:
                    if owner!=self.user:
                        messagebox.showwarning('Crew medical alert',f'{owner} — {message}',parent=self)
        self.after(10000,self.remind)


def run():
    journal=Journal(app_home())
    app=Mission(journal)
    import sys
    seed_demo(journal)
    if '--smoke-test' in sys.argv:
        app.update()
        app.check_due=lambda: None
        app.profile_choice.set('mo')
        app.open_profile()
        app.update()
        assert app.tabs.tabs() and all(user in journal.profiles() for user in USERS)
        assert len(app.records())==60 and len(journal.records('parisa'))==60
        assert all(r['status']=='green' for name in ('mo','parisa') for r in journal.records(name))
        app.profile_choice.set('parisa')
        app.open_profile()
        app.update()
        assert app.user=='parisa' and app.records()==journal.records('parisa')
        app.destroy()
    else:
        app.mainloop()
    journal.close()
