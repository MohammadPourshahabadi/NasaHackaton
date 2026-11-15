"""Aboard desktop simulation for NASA Space Apps 2026."""

import os
from pathlib import Path
import queue
import sqlite3
import sys
import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

from analysis import analyze, get_numeric, history_medians
from assistants import image_bytes, request_summary
from motion import GuideFrame
from quality import inspect_image
from crew import CrewFrame
from storage import Journal, ROUTINE


NAVY = '#152a2e'
PANEL = '#203a3e'
EDGE = '#426169'
FG = '#f3f5ed'
MUTED = '#b7cbc5'
ACCENT = '#a1e7cc'
COLORS = {'red': '#ff9b9b', 'yellow': '#ffd181', 'green': '#80e8b5'}
FIELDS = [
    ('sleep', 'Sleep', 'hours', 'sleep'),
    ('fatigue', 'Fatigue', '1 low to 5 high', None),
    ('mood', 'Mood', '1 low to 5 good', None),
    ('pulse', 'Resting pulse', 'bpm', 'pulse'),
    ('systolic', 'Systolic', 'mmHg', 'bp'),
    ('diastolic', 'Diastolic', 'mmHg', 'bp'),
    ('temperature', 'Temperature', '°C', 'temperature'),
]
REVIEW = {'Awaiting review': 'unreviewed', 'Reviewer marked routine': 'routine',
          'Reviewer requests follow-up': 'followup', 'Reviewer requests urgent attention': 'urgent'}


def app_home():
    fallback = Path.home() / 'AppData' / 'Local'
    return Path(os.environ.get('ABOARD_DATA_DIR') or Path(os.environ.get('LOCALAPPDATA', fallback)) / 'Aboard')


def styles(root):
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', font=('Segoe UI', 11), background=NAVY, foreground=FG,
                    fieldbackground=PANEL, bordercolor=EDGE, troughcolor=NAVY)
    style.configure('TFrame', background=NAVY)
    style.configure('TLabel', background=NAVY, foreground=FG)
    style.configure('Muted.TLabel', foreground=MUTED)
    style.configure('Title.TLabel', font=('Segoe UI', 28, 'bold'))
    style.configure('Section.TLabel', font=('Segoe UI', 16, 'bold'))
    style.configure('Prompt.TLabel', font=('Segoe UI', 20, 'bold'))
    style.configure('TButton', background=PANEL, padding=(12, 6), borderwidth=0, relief='flat',
                    lightcolor=PANEL, darkcolor=PANEL, bordercolor=PANEL, focuscolor=PANEL)
    style.map('TButton', background=[('active', EDGE), ('disabled', NAVY)],
              lightcolor=[('active', EDGE)], darkcolor=[('active', EDGE)], bordercolor=[('active', EDGE)],
              foreground=[('disabled', '#6f8783')])
    style.configure('Primary.TButton', background=ACCENT, foreground=NAVY, font=('Segoe UI', 11, 'bold'))
    style.map('Primary.TButton', background=[('active', '#a0eeed')])
    style.configure('TNotebook', padding=0, borderwidth=0, background=NAVY)
    style.configure('TNotebook.Tab', background=PANEL, foreground=MUTED, padding=(19, 9))
    style.map('TNotebook.Tab', background=[('selected', EDGE)], foreground=[('selected', FG)])
    style.configure('TCombobox', foreground=FG, arrowcolor=ACCENT)
    style.map('TCombobox', fieldbackground=[('readonly', PANEL)], foreground=[('readonly', FG)])
    style.configure('TEntry', padding=5, insertcolor=FG)
    for kind in ('TCheckbutton', 'TRadiobutton'):
        style.configure(kind, background=NAVY, foreground=FG, indicatorbackground=PANEL,
                        indicatorforeground=ACCENT, indicatorrelief='flat', focuscolor=NAVY)
        style.map(kind, background=[('active', NAVY)],
                  indicatorbackground=[('selected', PANEL), ('active', EDGE)])
        style.configure(f'Card.{kind}', background=PANEL)
        style.map(f'Card.{kind}', background=[('active', PANEL)])
    style.configure('TNotebook.Tab', font=('Segoe UI', 11, 'bold'))
    # Tabs driven by the header pills: no visible tab strip or border.
    style.layout('Bare.TNotebook.Tab', [])
    style.configure('Bare.TNotebook', borderwidth=0, padding=0, background=NAVY,
                    bordercolor=NAVY, lightcolor=NAVY, darkcolor=NAVY)
    style.configure('Horizontal.TProgressbar', background=ACCENT, troughcolor=PANEL,
                    lightcolor=ACCENT, darkcolor=ACCENT)
    root.option_add('*TCombobox*Listbox.background', PANEL)
    root.option_add('*TCombobox*Listbox.foreground', FG)


def text_area(parent, height):
    return tk.Text(parent, height=height, width=1, wrap='word', bg=PANEL, fg=FG, insertbackground=FG,
                   selectbackground=EDGE, relief='flat', padx=10, pady=8, font=('Segoe UI', 11))


def set_text(widget, text):
    widget.configure(state='normal')
    widget.delete('1.0', 'end')
    widget.insert('1.0', text)
    widget.configure(state='disabled')


class Aboard(tk.Tk):
    def __init__(self, journal):
        super().__init__()
        self.title('Aboard | Astronaut health simulation')
        self.geometry('1180x860')
        self.minsize(970, 730)
        self.configure(background=NAVY)
        self.journal = journal
        self.result = None
        self.last_checkin = None
        self.attachment = None
        self.injury = None
        self.outputs = queue.Queue()
        self.task = 0
        self.provider = tk.StringVar(value='Disabled')
        self.model = tk.StringVar()
        self.key = tk.StringVar()
        self.groq_key = tk.StringVar()
        self.include_image = tk.BooleanVar()
        self.profile = tk.StringVar(value='Simulated crew')
        styles(self)
        self.layout()
        self.journal.seed()
        self.restore_history()
        self.select_demo('yellow')
        self.crew.activate(welcome=True)
        self.protocol('WM_DELETE_WINDOW', self.close_app)
        self.after(150, self.poll_responses)
        self.after(60000, self.refresh_schedule)

    def layout(self):
        top = ttk.Frame(self, padding=(25, 12, 25, 10))
        top.pack(fill='x')
        brand = ttk.Frame(top)
        brand.pack(side='left')
        ttk.Label(brand, text='Aboard', style='Title.TLabel').pack(anchor='w')
        ttk.Label(brand, text='Astronaut health simulation', style='Muted.TLabel').pack(anchor='w')
        selector = ttk.Frame(top)
        selector.pack(side='right', anchor='n', pady=12)
        ttk.Label(selector, text='Astronaut', style='Muted.TLabel').pack(side='left', padx=(0, 8))
        self.profiles = ttk.Combobox(selector, state='readonly', width=20, textvariable=self.profile,
                                    values=self.journal.profiles())
        self.profiles.pack(side='left')
        self.profiles.bind('<<ComboboxSelected>>', self.profile_changed)
        ttk.Button(selector, text='Add astronaut', command=self.add_astronaut).pack(side='left', padx=(8, 0))

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill='both', expand=True, padx=25)
        self.check_tab = ttk.Frame(self.tabs, padding=(18, 13))
        self.result_tab = ttk.Frame(self.tabs, padding=(18, 13))
        self.trend_tab = ttk.Frame(self.tabs, padding=(18, 13))
        self.guide = GuideFrame(self.tabs)
        self.ai_tab = ttk.Frame(self.tabs, padding=(18, 13))
        self.history_tab = ttk.Frame(self.tabs, padding=(18, 13))
        self.crew = CrewFrame(self.tabs, self)
        for tab, label in [(self.crew, 'Crew assistant'), (self.check_tab, 'Check-in'), (self.result_tab, 'Assessment'),
                           (self.trend_tab, 'Trends'), (self.history_tab, 'Journal'),
                           (self.guide, 'Animated guides'), (self.ai_tab, 'AI settings')]:
            self.tabs.add(tab, text=label)
        self.build_checkin()
        self.build_result()
        self.build_trends()
        self.build_history()
        self.build_ai()
        self.notice = tk.StringVar()
        ttk.Label(self, textvariable=self.notice, padding=(25, 8), style='Muted.TLabel').pack(fill='x')
        self.tabs.bind('<<NotebookTabChanged>>', self.tab_changed)
        self.update_notice()

    def build_checkin(self):
        body = self.check_tab
        row = ttk.Frame(body)
        row.pack(fill='x', pady=(0, 12))
        ttk.Label(row, text='Daily check-in', style='Section.TLabel').pack(side='left')
        self.demo = ttk.Frame(row)
        self.demo.pack(side='right')
        ttk.Label(self.demo, text='Load demo', style='Muted.TLabel').pack(side='left', padx=(0, 7))
        for color, label in [('green', 'Routine'), ('yellow', 'Fatigue'), ('red', 'Urgent')]:
            ttk.Button(self.demo, text=label, command=lambda c=color: self.select_demo(c)).pack(side='left', padx=3)

        content = ttk.Frame(body)
        content.pack(fill='both', expand=True)
        for col in range(2):
            content.columnconfigure(col, weight=1, uniform='panel')
        measure = ttk.Frame(content)
        measure.grid(row=0, column=0, sticky='nsew', padx=(0, 20))
        context = ttk.Frame(content)
        context.grid(row=0, column=1, sticky='nsew', padx=(12, 0))
        ttk.Label(measure, text='Readings and questionnaire', style='Section.TLabel').grid(row=0, column=0, columnspan=4, sticky='w')
        self.fields = {}
        for index, (name, label, unit, guide) in enumerate(FIELDS, start=1):
            var = self.fields[name] = tk.StringVar()
            ttk.Label(measure, text=label).grid(row=index, column=0, sticky='w', pady=5, padx=(0, 5))
            if name in ('fatigue', 'mood'):
                entry = ttk.Combobox(measure, state='readonly', textvariable=var,
                                     values=['', '1', '2', '3', '4', '5'], width=8)
            else:
                entry = ttk.Entry(measure, textvariable=var, width=10)
            entry.grid(row=index, column=1, sticky='w', padx=(8, 10))
            ttk.Label(measure, text=unit, style='Muted.TLabel').grid(row=index, column=2, sticky='w')
            if guide:
                ttk.Button(measure, text='How to', command=lambda g=guide: self.show_guide(g)).grid(row=index, column=3, padx=10)
        self.urgent = tk.BooleanVar()
        ttk.Checkbutton(measure, variable=self.urgent,
                        text='Urgent symptom or immediate help needed').grid(row=8, column=0, columnspan=4, sticky='w', pady=(13, 4))
        ttk.Label(measure, text='Use the mission emergency procedure if you need help now.',
                  wraplength=440, style='Muted.TLabel').grid(row=9, column=0, columnspan=4, sticky='w')

        ttk.Label(context, text='Symptoms and context', style='Section.TLabel').pack(anchor='w')
        ttk.Label(context, text='Describe what changed, when it started, or what you were doing.',
                  style='Muted.TLabel', wraplength=445).pack(anchor='w', pady=(3, 6))
        self.notes = text_area(context, 5)
        self.notes.pack(fill='x')
        self.notes.bind('<KeyRelease>', self.limit_notes)
        ttk.Label(context, text='Ultrasound export', style='Section.TLabel').pack(anchor='w', pady=(12, 3))
        attachments = ttk.Frame(context)
        attachments.pack(fill='x', pady=(0, 4))
        ttk.Button(attachments, text='Attach PNG / JPEG', command=self.add_attachment).pack(side='left')
        ttk.Button(attachments, text='View', command=self.view_image).pack(side='left', padx=5)
        ttk.Button(attachments, text='Remove', command=self.remove_attachment).pack(side='left')
        ttk.Button(attachments, text='Guide', command=lambda: self.show_guide('ultrasound')).pack(side='left', padx=5)
        ttk.Button(context, text='Load synthetic scan', command=self.load_sample).pack(anchor='w', pady=(2, 4))
        self.attach_label = ttk.Label(context, text='No image attached', style='Muted.TLabel', wraplength=450)
        self.attach_label.pack(anchor='w')
        self.review = tk.StringVar(value=next(iter(REVIEW)))
        self.review_combo = ttk.Combobox(context, state='disabled', values=list(REVIEW),
                                         textvariable=self.review, width=34)
        self.review_combo.pack(anchor='w', pady=(7, 0))
        self.review_combo.bind('<<ComboboxSelected>>', self.update_preview)
        self.preview = ttk.Label(context, text='The offline assessment uses the reviewer’s entry.',
                                 wraplength=440, style='Muted.TLabel')
        self.preview.pack(anchor='w', pady=(5, 0))
        injury_line = ttk.Frame(context)
        injury_line.pack(fill='x', pady=(8, 0))
        self.injury_label = ttk.Label(injury_line, text='No injury photo attached', style='Muted.TLabel', wraplength=220)
        self.injury_label.pack(side='left', padx=(0, 5))
        ttk.Button(injury_line, text='Injury photo', command=lambda: self.crew.upload('injury')).pack(side='left')
        ttk.Button(injury_line, text='Remove', command=self.remove_injury).pack(side='left', padx=4)

        bottom = ttk.Frame(body)
        bottom.pack(fill='x', pady=(12, 0))
        ttk.Button(bottom, text='Assess and save', style='Primary.TButton', command=self.submit).pack(side='left')
        ttk.Label(bottom, text='Use the demo cases to rehearse all three responses.', style='Muted.TLabel').pack(side='left', padx=15)

    def update_preview(self, _event=None):
        if self.attachment:
            details = self.attachment['quality']['detail']
            self.preview.configure(text=details + ' Record a disposition after human review.')
        else:
            self.preview.configure(text='The offline assessment uses the reviewer’s entry.')

    def limit_notes(self, _event):
        if len(self.notes.get('1.0', 'end-1c')) > 2500:
            self.notes.delete('1.0+2500c', 'end-1c')

    def profile_changed(self, _event=None):
        self.crew.reset_conversation()
        self.result = self.last_checkin = None
        self.task += 1
        self.render_result()
        if self.profile.get() == 'Simulated crew':
            self.demo.pack(side='right')
            self.select_demo('yellow')
        else:
            self.demo.pack_forget()
            self.fill({})
        self.restore_history()
        if self.tabs.select() == str(self.trend_tab):
            self.redraw_trend()
        self.update_notice()

    def add_astronaut(self):
        name = simpledialog.askstring('Add astronaut', 'Enter a name or crew ID.', parent=self)
        if name is None:
            return
        try:
            name = self.journal.add_profile(name)
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror('Profile could not be created', str(error), parent=self)
            return
        self.profiles.configure(values=self.journal.profiles())
        self.profile.set(name)
        self.profile_changed()

    def fill(self, checkin):
        for name, var in self.fields.items():
            var.set(checkin.get(name, ''))
        self.urgent.set(checkin.get('urgent', False))
        self.notes.delete('1.0', 'end')
        self.notes.insert('1.0', checkin.get('notes', ''))
        self.remove_attachment()
        self.remove_injury()

    def select_demo(self, case):
        sample = dict(ROUTINE)
        if case == 'yellow':
            sample.update(sleep=5, fatigue=4, mood=3,
                          notes='Third short night after a shift change. I feel unusually tired before the maintenance shift.')
        if case == 'red':
            sample.update(urgent=True, notes='Sudden chest discomfort. I need help now.')
        self.fill(sample)
        self.update_notice()

    def add_attachment(self):
        path = filedialog.askopenfilename(parent=self, title='Choose an ultrasound export',
                                          filetypes=[('PNG and JPEG', '*.png *.jpg *.jpeg')])
        if not path:
            return
        self.load_attachment(path, Path(path).name)

    def attach_injury(self, path):
        quality = inspect_image(path)
        if quality['status'] == 'error':
            raise ValueError(quality['detail'])
        self.injury = {'source': str(path), 'quality': quality}
        self.injury_label.configure(text=Path(path).name)

    def remove_injury(self):
        self.injury = None
        self.injury_label.configure(text='No injury photo attached')

    def load_sample(self):
        self.load_attachment(Path(__file__).with_name('demo_scan.png'), 'Synthetic scan · practice image')

    def load_attachment(self, path, name):
        try:
            image_bytes(path)
            quality = inspect_image(path)
            if quality['status'] == 'error':
                raise ValueError(quality['detail'])
            self.attachment = {'source': str(path), 'quality': quality}
            self.attach_label.configure(text=name)
            self.review_combo.configure(state='readonly')
            self.review.set(next(iter(REVIEW)))
            self.update_preview()
            return True
        except (ValueError, OSError) as error:
            self.remove_attachment()
            messagebox.showerror('Image unavailable', str(error), parent=self)
            return False

    def view_image(self):
        if not self.attachment:
            messagebox.showinfo('Ultrasound export', 'Attach a PNG or JPEG first.', parent=self)
            return
        self.preview_image(self.attachment['source'], 'Ultrasound attachment')

    def preview_image(self, path, title):
        try:
            with Image.open(path) as image:
                image.thumbnail((760, 590))
                preview = ImageTk.PhotoImage(image)
            window = tk.Toplevel(self)
            window.title(title)
            window.configure(background=NAVY)
            label = ttk.Label(window, image=preview)
            label.image = preview
            label.pack(padx=12, pady=12)
            window.transient(self)
            window.grab_set()
        except (tk.TclError, OSError) as error:
            messagebox.showerror('Image unavailable', str(error), parent=self)

    def remove_attachment(self):
        self.attachment = None
        self.review.set(next(iter(REVIEW)))
        self.review_combo.configure(state='disabled')
        self.attach_label.configure(text='No image attached')
        self.update_preview()

    def show_guide(self, key):
        self.guide.show_guide(key)
        self.tabs.select(self.guide)

    def submit(self):
        checkin = {name: var.get().strip() for name, var in self.fields.items()}
        checkin.update(urgent=self.urgent.get(), notes=self.notes.get('1.0', 'end-1c').strip(),
                       ultrasound_review=REVIEW[self.review.get()])
        try:
            if self.attachment and 'stored' not in self.attachment:
                self.attachment['stored'] = self.journal.attach(self.attachment['source'])
            if self.attachment:
                checkin['ultrasound_path'] = self.attachment['stored']
            if self.injury:
                if 'stored' not in self.injury:
                    self.injury['stored'] = self.journal.attach(self.injury['source'])
                checkin['injury_path'] = self.injury['stored']
            history = self.journal.records(self.profile.get())
            # Previous days define the baseline. Repeated practice runs today never change it.
            prior_by_day = {item['stamp'][:10]: item for item in history
                            if item['stamp'][:10] < date.today().isoformat()}
            prior = list(prior_by_day.values())
            result = analyze(checkin, prior)
            stamp = datetime.now().astimezone()
            result['next_at'] = (stamp + timedelta(hours=result['next_hours'])).isoformat(timespec='seconds')
            if self.attachment:
                result['modalities']['Image file preflight'] = self.attachment['quality']['detail']
            if self.injury:
                result['modalities']['Injury photo'] = 'Attached for crew review. ' + self.injury['quality']['detail']
            record = {'checkin': checkin, 'status': result['status'], 'next_at': result['next_at'],
                      'assessment': result, 'stamp': stamp.isoformat(timespec='microseconds')}
            self.journal.save(self.profile.get(), record['stamp'], record)
        except (ValueError, OSError, sqlite3.Error) as error:
            messagebox.showerror('Check-in could not be saved', str(error), parent=self)
            return
        self.task += 1
        self.show_assessment(record)
        self.restore_history()
        self.update_notice()
        self.tabs.select(self.result_tab)

    def show_assessment(self, record):
        self.result = record['assessment']
        self.last_checkin = record['checkin']
        self.assessment_stamp = record['stamp']
        self.render_result()
        self.ai_summary = self.journal.draft(self.profile.get(), self.assessment_stamp)
        if self.ai_summary:
            set_text(self.ai_output, 'Saved AI draft for review\n' + self.ai_summary)

    def build_history(self):
        layout = self.history_tab
        ttk.Label(layout, text='Saved check-ins', style='Section.TLabel').pack(anchor='w')
        panel = ttk.Frame(layout)
        panel.pack(fill='both', expand=True, pady=8)
        self.history_list = ttk.Treeview(panel, columns=('date', 'status'), show='headings', selectmode='browse')
        self.history_list.heading('date', text='Recorded')
        self.history_list.heading('status', text='Status')
        self.history_list.column('date', width=170)
        self.history_list.column('status', width=95)
        scroll = ttk.Scrollbar(panel, command=self.history_list.yview)
        self.history_list.configure(yscrollcommand=scroll.set)
        self.history_list.pack(side='left', fill='y')
        scroll.pack(side='left', fill='y')
        self.history_list.bind('<<TreeviewSelect>>', self.history_selection)
        self.history_detail = text_area(panel, 12)
        self.history_detail.pack(side='left', fill='both', expand=True, padx=(10, 0))
        controls = ttk.Frame(layout)
        controls.pack(anchor='w')
        self.history_actions = {}
        for key, label, action in (
            ('assessment', 'Open saved assessment', self.open_saved_assessment),
            ('ultrasound_path', 'View ultrasound', lambda: self.history_image('ultrasound_path', 'Saved ultrasound')),
            ('injury_path', 'View injury photo', lambda: self.history_image('injury_path', 'Saved injury photo')),
        ):
            button = ttk.Button(controls, text=label, command=action, state='disabled')
            button.pack(side='left', padx=(0, 6))
            self.history_actions[key] = button

    def restore_history(self):
        self.history_records = list(reversed(self.journal.records(self.profile.get())))
        self.history_list.delete(*self.history_list.get_children())
        for index, record in enumerate(self.history_records):
            self.history_list.insert('', 'end', iid=str(index), values=(record['stamp'][:16].replace('T', ' '), record['status'].capitalize()))
        if self.history_records:
            self.history_list.selection_set('0')
        self.history_selection()

    def selected_record(self):
        selection = self.history_list.selection()
        return self.history_records[int(selection[0])] if selection else None

    def history_selection(self, _event=None):
        record = self.selected_record() or {}
        values = record.get('checkin', {})
        lines = [f'{label}  {values.get(name) or "—"} {unit}' for name, label, unit, _ in FIELDS]
        lines += ['', f'Notes  {values.get("notes") or "—"}']
        if values.get('ultrasound_path'):
            lines += ['', f'Ultrasound review  {values.get("ultrasound_review", "unreviewed")}']
        if record and not record.get('assessment'):
            lines += ['', 'Earlier record. Readings are available.']
        set_text(self.history_detail, '\n'.join(lines) if record else 'No saved check-ins for this astronaut.')
        for key, button in self.history_actions.items():
            button.configure(state='normal' if (record.get(key) or values.get(key)) else 'disabled')

    def open_saved_assessment(self):
        record = self.selected_record()
        if record and record.get('assessment'):
            self.task += 1
            self.show_assessment(record)
            self.tabs.select(self.result_tab)

    def history_image(self, field, title):
        path = (self.selected_record() or {}).get('checkin', {}).get(field)
        if path:
            self.preview_image(path, title)

    def build_result(self):
        self.result_head = tk.Label(self.result_tab, bg=NAVY, fg=FG, anchor='w',
                                    font=('Segoe UI', 24, 'bold'))
        self.result_head.pack(fill='x')
        self.next_check = ttk.Label(self.result_tab, style='Muted.TLabel', wraplength=980)
        self.next_check.pack(anchor='w', pady=(1, 9))
        self.result_text = text_area(self.result_tab, 12)
        self.result_text.pack(fill='both', expand=True)
        buttons = ttk.Frame(self.result_tab)
        buttons.pack(fill='x', pady=10)
        self.action_button = ttk.Button(buttons, text='Open action guide', style='Primary.TButton', state='disabled',
                                       command=lambda: self.show_guide(self.result.get('guide') or 'sleep'))
        self.action_button.pack(side='left')
        self.export_button = ttk.Button(buttons, text='Export handoff', command=self.export_handoff, state='disabled')
        self.export_button.pack(side='left', padx=9)
        self.ai_button = ttk.Button(buttons, text='Draft with optional AI', command=self.generate, state='disabled')
        self.ai_button.pack(side='left')
        self.ai_output = text_area(self.result_tab, 4)
        self.ai_output.pack(fill='x')
        self.render_result()

    def report(self):
        out = self.result
        parts = ['ONBOARD ACTIONS', *['• ' + str(item) for item in out.get('actions', [])],
                 '', 'WHY THIS STATUS', *['• ' + str(item) for item in out.get('rationale', [])],
                 '', 'INPUTS USED']
        parts += [f'{name.replace("_", " ").capitalize()}  {value}' for name, value in out.get('modalities', {}).items()]
        if out.get('missing'):
            parts += ['', 'Missing  ' + ', '.join(out['missing'])]
        if out.get('invalid'):
            parts += ['', 'Needs entry correction  ' + ', '.join(out['invalid'])]
        model = out.get('model') or {}
        if isinstance(model.get('probability'), (int, float)):
            parts += ['', f'Local model matched the simulated fatigue pattern with a score of {model["probability"]:.0%}.',
                      'Trained on synthetic cases. The score does not set the status.']
        elif model.get('message'):
            parts += ['', str(model['message'])]
        return '\n'.join(parts)

    def render_result(self):
        enabled = 'normal' if self.result else 'disabled'
        for button in (self.action_button, self.export_button, self.ai_button):
            button.configure(state=enabled)
        self.ai_summary = ''
        self.ai_notice()
        if not self.result:
            self.result_head.configure(text='No assessment yet', fg=FG)
            self.next_check.configure(text='')
            set_text(self.result_text, 'Complete and save a check-in to see the assessment.')
            return
        status = self.result['status']
        if not self.result.get('guide'):
            self.action_button.configure(state='disabled')
        self.result_head.configure(text=f'{status.upper()}   {self.result["title"]}', fg=COLORS[status])
        next_text = self.result['recheck']
        if self.result.get('next_hours'):
            next_text += f'  •  {datetime.fromisoformat(self.result["next_at"]):%d %b at %H:%M}'
        self.next_check.configure(text=f'Next check  {next_text}')
        set_text(self.result_text, self.report())

    def export_handoff(self):
        target = filedialog.asksaveasfilename(parent=self, defaultextension='.txt',
                                              initialfile=f'Aboard-{date.today()}.txt',
                                              filetypes=[('Text document', '*.txt')])
        if not target:
            return
        payload = f'ABOARD SIMULATION HANDOFF\n{self.assessment_stamp}\n{self.profile.get()}\n'
        payload += f'{self.result["status"].upper()} {self.result["title"]}\nNext check  {self.result["recheck"]}\n\n'
        if self.result.get('next_hours'):
            payload += f'Scheduled follow-up  {self.result["next_at"]}\n\n'
        payload += self.report() + '\n\nRECORDED READINGS\n'
        payload += '\n'.join(f'{label}  {self.last_checkin.get(name) or "Missing"} {unit}'
                               for name, label, unit, _ in FIELDS)
        payload += '\nContext  ' + (self.last_checkin.get('notes') or 'None provided')
        if self.last_checkin.get('ultrasound_path'):
            payload += '\nUltrasound image retained on device. Review disposition: ' + self.last_checkin['ultrasound_review']
        if self.last_checkin.get('injury_path'):
            payload += '\nInjury photo retained on device for human review.'
        if self.ai_summary:
            payload += '\n\nOPTIONAL AI DRAFT FOR REVIEW\n' + self.ai_summary
        try:
            Path(target).write_text(payload, encoding='utf-8')
            self.notice.set('Handoff saved locally.')
        except OSError as error:
            messagebox.showerror('Handoff could not be saved', str(error), parent=self)

    def build_ai(self):
        tab = self.ai_tab
        ttk.Label(tab, text='AI providers', style='Section.TLabel').pack(anchor='w')
        ttk.Label(tab, text='Use a Groq Free Plan key for speech and commands. Enable it in Crew assistant. '
                            'The handoff provider is a separate setting.', wraplength=900).pack(anchor='w', pady=(7, 15))
        form = ttk.Frame(tab)
        form.pack(anchor='w')
        ttk.Label(form, text='Groq API key').grid(row=0, column=0, sticky='w', padx=(0, 18), pady=6)
        ttk.Entry(form, textvariable=self.groq_key, width=34, show='•').grid(row=0, column=1, sticky='w')
        ttk.Label(form, text='Handoff provider').grid(row=1, column=0, sticky='w', pady=6)
        provider = ttk.Combobox(form, state='readonly', textvariable=self.provider, width=29,
                                values=['Disabled', 'Local Ollama', 'OpenAI'])
        provider.grid(row=1, column=1, sticky='w')
        provider.bind('<<ComboboxSelected>>', self.set_provider)
        ttk.Label(form, text='Handoff model').grid(row=2, column=0, sticky='w', pady=6)
        ttk.Entry(form, textvariable=self.model, width=34).grid(row=2, column=1, sticky='w')
        ttk.Label(form, text='OpenAI key for handoff').grid(row=3, column=0, sticky='w', pady=6)
        ttk.Entry(form, textvariable=self.key, width=34, show='•').grid(row=3, column=1, sticky='w')
        ttk.Checkbutton(tab, text='Include the attached image with this AI request',
                        variable=self.include_image).pack(anchor='w', pady=(9, 12))
        self.provider_note = ttk.Label(tab, wraplength=910, style='Muted.TLabel')
        self.provider_note.pack(anchor='w')
        self.set_provider()

    def set_provider(self, _event=None):
        choice = self.provider.get()
        self.model.set({'Disabled': '', 'Local Ollama': 'gemma3:4b', 'OpenAI': 'gpt-4.1-mini'}[choice])
        self.include_image.set(False)
        self.provider_note.configure(text={
            'Disabled': 'Handoff drafting is off.',
            'Local Ollama': 'Requires Ollama and a compatible installed model at 127.0.0.1. Use a vision-capable model for images.',
            'OpenAI': 'Key stays in memory. You can also set OPENAI_API_KEY. A confirmation shows what leaves your device.',
        }[choice])
        if hasattr(self, 'notice'):
            self.update_notice()

    def ai_notice(self):
        set_text(self.ai_output, 'Optional AI draft appears here after you request it.')

    def generate(self):
        choice, model = self.provider.get(), self.model.get().strip()
        if choice == 'Disabled':
            self.tabs.select(self.ai_tab)
            return
        if not model:
            messagebox.showinfo('Choose a model', 'Enter a model name in AI settings.', parent=self)
            return
        key = self.key.get().strip() or os.environ.get('OPENAI_API_KEY')
        attach = self.include_image.get() and bool(self.last_checkin.get('ultrasound_path'))
        if choice == 'OpenAI':
            if not key:
                messagebox.showinfo('OpenAI key required', 'Enter an API key in AI settings.', parent=self)
                return
            if self.profile.get() != 'Simulated crew':
                messagebox.showinfo('Cloud demo uses simulated data', 'Use Local Ollama for a manual-practice journal.',
                                    parent=self)
                return
            extra = ' The attached image will also be sent.' if attach else ''
            if not messagebox.askyesno('Send to OpenAI?',
                                       'Send the current readings, notes, and rule evidence to OpenAI?'
                                       + extra + ' Use synthetic or appropriately de-identified demo inputs.', parent=self):
                return
        self.task += 1
        ticket = self.task
        checkin, result = dict(self.last_checkin), self.result
        set_text(self.ai_output, f'Waiting for {choice}. The onboard assessment is available above.')
        self.ai_button.configure(state='disabled')

        def run():
            try:
                summary = request_summary(choice, model, key, checkin, result, attach)
                self.outputs.put((ticket, summary, None))
            except Exception as error:
                self.outputs.put((ticket, '', str(error)))

        threading.Thread(target=run, daemon=True).start()

    def poll_responses(self):
        while not self.outputs.empty():
            ticket, summary, error = self.outputs.get_nowait()
            if ticket != self.task:
                continue
            self.ai_button.configure(state='normal')
            self.ai_summary = summary
            set_text(self.ai_output, error or 'AI draft for review\n' + summary)
            if summary:
                try:
                    self.journal.save_draft(self.profile.get(), self.assessment_stamp, summary)
                except sqlite3.Error:
                    self.notice.set('AI draft shown, but it could not be saved to this journal.')
        self.after(150, self.poll_responses)

    def build_trends(self):
        tab = self.trend_tab
        row = ttk.Frame(tab)
        row.pack(fill='x')
        ttk.Label(row, text='Trends', style='Section.TLabel').pack(side='left')
        labels = [label for _, label, _, _ in FIELDS]
        self.metric = tk.StringVar(value='Sleep')
        combo = ttk.Combobox(row, state='readonly', textvariable=self.metric, values=labels, width=20)
        combo.pack(side='right')
        combo.bind('<<ComboboxSelected>>', self.redraw_trend)
        self.trend_detail = ttk.Label(tab, text='Select a data point to see its reading.', style='Muted.TLabel')
        self.trend_detail.pack(anchor='w', pady=(10, 8))
        self.chart = tk.Canvas(tab, background=PANEL, highlightthickness=0)
        self.chart.pack(fill='both', expand=True)
        self.chart.bind('<Configure>', self.redraw_trend)

    def redraw_trend(self, _event=None):
        canvas = self.chart
        canvas.delete('all')
        field, label, unit, _ = next(item for item in FIELDS if item[1] == self.metric.get())
        records = self.journal.records(self.profile.get())
        daily = {item['stamp'][:10]: item for item in records}
        days = [(date.today() - timedelta(days=ago)).isoformat() for ago in range(6, -1, -1)]
        samples = []
        for day in days:
            item = daily.get(day, {})
            value, _ = get_numeric(item.get('checkin', {}), field)
            samples.append((day, item.get('status'), value))
        values = [value for _, _, value in samples if value is not None]
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 150 or height < 150:
            return
        self.trend_detail.configure(text='Last seven days · last entry each day · select a point for details.')
        if not values:
            canvas.create_text(width / 2, height / 2, text=f'No {label.lower()} readings in this journal yet.', fill=MUTED,
                               font=('Segoe UI', 15))
            return
        prior = [item for day, item in daily.items() if day < date.today().isoformat()]
        baseline = history_medians(prior).get(field)
        extents = values if baseline is None else [*values, baseline]
        low, high = min(extents), max(extents)
        padding = max((high - low) / 5, 0.2)
        low, high = low - padding, high + padding
        left, right, top, bottom = 84, width - 44, 53, height - 52
        canvas.create_text(left, 23, text=f'{label} ({unit})', fill=FG, anchor='w', font=('Segoe UI', 13, 'bold'))
        for tick in range(5):
            offset = tick / 4
            y = bottom - offset * (bottom - top)
            canvas.create_line(left, y, right, y, fill=EDGE)
            canvas.create_text(left - 12, y, anchor='e', text=f'{low + (high - low)*offset:.1f}', fill=MUTED)
        if baseline is not None:
            baseline_y = bottom - (baseline - low) / (high - low) * (bottom - top)
            canvas.create_line(left, baseline_y, right, baseline_y, fill=MUTED, dash=(5, 5))
            canvas.create_text(right, 23, anchor='e', text=f'Prior baseline  {baseline:g} {unit}', fill=MUTED)
        previous = None
        points = []
        for index, (day, status, value) in enumerate(samples):
            x = left + (right - left) * index / 6
            canvas.create_text(x, bottom + 19, text=day[5:], fill=MUTED)
            if value is None:
                previous = None
                continue
            y = bottom - (value - low) / (high - low) * (bottom - top)
            if previous:
                canvas.create_line(*previous, x, y, fill=ACCENT, width=3)
            previous = (x, y)
            points.append((x, y, day, status, value))
        for x, y, day, status, value in points:
            point = canvas.create_oval(x-8, y-8, x+8, y+8, fill=COLORS.get(status, ACCENT), outline=PANEL, width=2)
            canvas.tag_bind(point, '<Button-1>', lambda _e, d=day, v=value, s=status:
                            self.trend_detail.configure(text=f'{d}   {label} {v:g} {unit}   •   {s.capitalize()}'))

    def tab_changed(self, _event):
        if self.tabs.select() == str(self.trend_tab):
            self.redraw_trend()
        if self.tabs.select() == str(self.crew):
            self.crew.activate()
        else:
            self.crew.deactivate()

    def close_app(self):
        self.crew.close()
        self.journal.close()
        self.destroy()

    def update_notice(self):
        journal = self.profile.get()
        records = self.journal.records(journal)
        upcoming = records[-1].get('next_at') if records else None
        when = datetime.fromisoformat(upcoming) if upcoming else None
        if when and when > datetime.now().astimezone():
            message = f'Next check-in {when:%d %b at %H:%M}'
        elif when and records[-1]['status'] == 'red':
            message = 'Crew medical review requested now'
        else:
            message = 'Check-in due'
        self.notice.set(f'{journal}   •   {message}   •   Simulation only')

    def refresh_schedule(self):
        self.update_notice()
        self.after(60000, self.refresh_schedule)


def main():
    journal = Journal(app_home())
    app = Aboard(journal)
    if '--smoke-test' in sys.argv:
        from threading import Event
        from unittest.mock import patch

        crew = app.crew
        crew.spoken.set(False)

        def finish_turn(text):
            crew.turn(text)
            app.after(250, lambda: app.quit())
            app.mainloop()

        def button(parent, name):
            for child in parent.winfo_children():
                if child.winfo_name() == name:
                    return child
                found = button(child, name)
                if found:
                    return found
            return None

        app.update()
        finish_turn('I feel sleepy')
        finish_turn('five and a half hours')
        finish_turn('four out of five')
        assert app.fields['sleep'].get() == '5.5' and app.fields['fatigue'].get() == '4'
        assert app.tabs.select() == str(app.check_tab)
        app.tabs.select(crew)
        app.update()
        finish_turn('I want to upload an ultrasound picture')
        assert crew.window and crew.window.winfo_exists()
        button(crew.window, 'sample').invoke()
        button(crew.window, 'attach').invoke()
        app.update()
        assert app.attachment and Path(app.attachment['source']).name == 'demo_scan.png'
        app.tabs.select(crew)
        app.update()
        finish_turn('Attach a photo of my injury')
        mock_image = Path(__file__).with_name('demo_scan.png')
        with patch('crew.filedialog.askopenfilename', return_value=str(mock_image)):
            button(crew.window, 'browse').invoke()
        button(crew.window, 'attach').invoke()
        app.update()
        assert app.injury and Path(app.injury['source']).name == 'demo_scan.png'
        app.tabs.select(crew)
        app.update()
        finish_turn('I need urgent help')
        assert app.urgent.get() and crew.window.winfo_exists()
        crew.close_window(crew.window)

        crew.cloud_enabled.set(True)
        app.groq_key.set('test-only-key')
        raw_transcript = 'Could you pull up the screen for the image I took of my scrape?'
        began_capture = Event()

        def mock_capture(*, timeout, cancel, finish, auto_pause, device, on_level, on_ready):
            began_capture.set()
            assert timeout == 20 and not auto_pause
            on_ready()
            on_level(40)
            assert finish.wait(4) and not cancel.is_set()
            return b'fake-wave'

        with patch('crew.record_wave', side_effect=mock_capture), \
             patch('crew.transcribe', return_value=raw_transcript), \
             patch('crew.classify', return_value='upload an injury photo') as routed:
            crew.mic.invoke()
            assert began_capture.wait(2)
            crew.poll()
            assert crew.mic.cget('text') == 'Stop & transcribe'
            crew.mic.invoke()
            app.after(450, app.quit)
            app.mainloop()
            routed.assert_called_once_with(raw_transcript, 'test-only-key', None)
        assert raw_transcript in crew.log.get('1.0', 'end')
        assert any(turn['text'] == raw_transcript for turn in journal.turns('Simulated crew'))
        assert crew.window and crew.window.winfo_exists()
        crew.close_window(crew.window)
        crew.cloud_enabled.set(False)
        app.groq_key.set('')

        for color in ('green', 'yellow', 'red'):
            app.select_demo(color)
            app.submit()
            app.update()
            assert app.result['status'] == color, app.result
            app.show_guide(app.result.get('guide') or 'sleep')
            app.update()
        app.select_demo('green')
        app.load_sample()
        assert app.attachment['quality']['status'] != 'error'
        app.view_image()
        app.submit()
        app.update()
        assert app.result['status'] == 'yellow'
        assert 'Image file preflight' in app.result['modalities']
        assert Path(app.last_checkin['ultrasound_path']).is_file()
        app.review.set('Reviewer requests urgent attention')
        app.submit()
        assert app.result['status'] == 'red'
        app.tabs.select(app.trend_tab)
        app.update()
        saved = journal.records('Simulated crew')
        if [item['status'] for item in saved[-5:]] != ['green', 'yellow', 'red', 'yellow', 'red']:
            raise RuntimeError('The journal did not persist the five assessments.')
        profile = journal.add_profile('Test astronaut')
        app.profile.set(profile)
        app.profile_changed()
        assert not app.history_records and raw_transcript not in crew.log.get('1.0', 'end')
        app.fill(ROUTINE)
        app.submit()
        assert len(journal.records(profile)) == 1
        assert journal.records(profile)[0]['assessment']['status'] == 'green'
        app.profile.set('Simulated crew')
        app.profile_changed()
        assert raw_transcript in crew.log.get('1.0', 'end')
        app.close_app()
        print('Aboard GUI smoke test passed.')
    else:
        app.mainloop()


if __name__ == '__main__':
    main()
