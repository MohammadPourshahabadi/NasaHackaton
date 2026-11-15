"""Crew assistant UI, conversation state and guided image upload."""

from pathlib import Path
from math import log10
import os
from queue import Empty, Queue
import re
from sqlite3 import Error as DatabaseError
from threading import Event, Thread
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from avatar3d import AvatarCanvas
from cloud_agent import classify, transcribe
from cloud_capture import input_devices, record_wave, WAVE_MAPPER
from dialogue import CrewDialogue, normalize, urgent_request
from quality import inspect_image
from voice import WindowsVoice


BG = '#101e31'
PANEL = '#172941'
FG = '#f1f6fa'
MUTED = '#a9bdd2'
CYAN = '#73e0df'
WAKE = re.compile(r'^(?:hey|hi|hello|okay|ok)[,\s]+(?:a\s*board|on\s+board)\b[\s,:.!-]*', re.I)
WAKE_PHRASES = ('hey aboard', 'hi aboard', 'hello aboard', 'okay aboard')
GUIDES = {'guide_bp': 'bp', 'guide_pulse': 'pulse', 'guide_temperature': 'temperature',
          'guide_sleep': 'sleep', 'guide_ultrasound': 'ultrasound'}


class CrewFrame(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=(18, 13))
        self.app = app
        self.voice = WindowsVoice()
        self.flow = CrewDialogue()
        self.events = Queue()
        self.active = False
        self.welcomed = False
        self.closed = False
        self.epoch = 0
        self.job = None
        self.after_speech = None
        self.pending_turn = None
        self.capture_cancel = None
        self.capture_finish = None
        self.window = None
        self.joined = False
        self.quiet_turns = 0
        self.follow_up = False
        self.voice_follow = False
        self.last_line = self.flow.welcome()
        self.state = tk.StringVar(value='Ready')
        self.spoken = tk.BooleanVar(value=True)
        self.cloud_enabled = tk.BooleanVar(value=False)
        self.devices = {'Windows default': WAVE_MAPPER}
        self.device_name = tk.StringVar(value='Windows default')
        self.signal_percent = tk.DoubleVar()
        self.peak_signal = 0
        self.hands_free = tk.BooleanVar(value=False)
        self.input = tk.StringVar()
        self.build()
        self.after(70, self.poll)

    def build(self):
        self.columnconfigure(0, weight=1, uniform='crew')
        self.columnconfigure(1, weight=1, uniform='crew')
        self.rowconfigure(0, weight=1)

        visual = ttk.Frame(self)
        visual.grid(row=0, column=0, sticky='nsew', padx=(0, 18))
        self.avatar = AvatarCanvas(visual, height=420, width=405, highlightthickness=0, background=BG)
        self.avatar.pack(fill='both', expand=True)
        ttk.Label(visual, text='Drag to rotate the 3D assistant', style='Muted.TLabel').pack(anchor='center', pady=(6, 0))

        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky='nsew')
        ttk.Label(right, text='Crew assistant', style='Section.TLabel').pack(anchor='w')
        self.status_line = ttk.Label(right, textvariable=self.state, style='Muted.TLabel', wraplength=470)
        self.status_line.pack(anchor='w', pady=(3, 7))

        log = ttk.Frame(right)
        log.pack(fill='both', expand=True)
        scrollbar = ttk.Scrollbar(log, orient='vertical')
        scrollbar.pack(side='right', fill='y')
        self.log = tk.Text(log, height=12, width=1, wrap='word', bg=PANEL, fg=FG,
                           selectbackground='#304763', relief='flat', padx=13, pady=12,
                           font=('Segoe UI', 11), state='disabled', yscrollcommand=scrollbar.set)
        self.log.pack(fill='both', expand=True)
        scrollbar.configure(command=self.log.yview)
        self.log.tag_configure('assistant', foreground=CYAN, font=('Segoe UI', 10, 'bold'))
        self.log.tag_configure('crew', foreground='#ffd181', font=('Segoe UI', 10, 'bold'))
        self.load_transcript()

        compose = ttk.Frame(right)
        compose.pack(fill='x', pady=(9, 0))
        entry = ttk.Entry(compose, textvariable=self.input, font=('Segoe UI', 11))
        entry.pack(side='left', fill='x', expand=True)
        entry.bind('<Return>', self.send_typed)
        ttk.Button(compose, text='Send', command=self.send_typed).pack(side='left', padx=(7, 0))

        controls = ttk.Frame(right)
        controls.pack(fill='x', pady=(9, 0))
        self.mic = ttk.Button(controls, text='Talk', style='Primary.TButton', command=self.toggle_listen)
        self.mic.pack(side='left')
        ttk.Checkbutton(controls, text='Spoken replies', variable=self.spoken,
                        command=self.switch_spoken).pack(side='left', padx=8)
        ttk.Checkbutton(controls, text='Hands-free', variable=self.hands_free,
                        command=self.switch_handsfree).pack(side='left')
        ttk.Button(controls, text='Replay reply', command=lambda: self.say(self.last_line)).pack(side='right')

        self.wake_hint = ttk.Label(right, text='Hands-free starts with “Hey Aboard.” It listens only on this tab.',
                                    style='Muted.TLabel', wraplength=455)
        self.wake_hint.pack(anchor='w', pady=(7, 5))
        cloud_row = ttk.Frame(right)
        cloud_row.pack(fill='x', pady=(0, 7))
        ttk.Checkbutton(cloud_row, text='Groq speech and commands', variable=self.cloud_enabled,
                        command=self.switch_cloud).pack(side='left')
        ttk.Button(cloud_row, text='API settings', command=lambda: self.app.tabs.select(self.app.ai_tab)).pack(side='right')
        microphone = ttk.Frame(right)
        microphone.pack(fill='x', pady=(0, 7))
        ttk.Label(microphone, text='Mic for Groq', style='Muted.TLabel').pack(side='left')
        self.device_select = ttk.Combobox(microphone, state='readonly', width=19, textvariable=self.device_name,
                                          values=list(self.devices), postcommand=self.refresh_microphones)
        self.device_select.pack(side='left', padx=6)
        ttk.Progressbar(microphone, maximum=100, length=85, variable=self.signal_percent).pack(side='left', padx=(0, 6))
        ttk.Button(microphone, text='Test mic', command=self.test_microphone).pack(side='left')
        suggestions = ttk.Frame(right)
        suggestions.pack(fill='x')
        for label, line in [('I feel sleepy', 'I feel sleepy'),
                            ('Injury photo', 'Upload an injury photo'),
                            ('Ultrasound', 'Upload an ultrasound picture')]:
            ttk.Button(suggestions, text=label, command=lambda phrase=line: self.turn(phrase)).pack(side='left', padx=(0, 5))

    def activate(self, welcome=False):
        if self.closed:
            return
        self.active = True
        if (welcome or not self.welcomed) and not self.welcomed:
            self.welcomed = True
            self.after(400, self.deliver_welcome)
        elif self.hands_free.get() and not self.job and not self.window:
            self.listen()

    def deliver_welcome(self):
        if self.active and self.epoch == 0:
            self.say(self.last_line)

    def deactivate(self):
        if self.active:
            self.active = False
            self.hands_free.set(False)
            self.joined = False
            self.voice_follow = False
            self.cancel()
            self.set_mode('idle', 'Ready')

    def reset_conversation(self):
        self.cancel()
        self.flow.reset()
        self.joined = False
        self.follow_up = False
        self.voice_follow = False
        self.hands_free.set(False)
        self.cloud_enabled.set(False)
        self.wake_hint.configure(text='Hands-free starts with “Hey Aboard.” It listens only on this tab.')
        self.input.set('')
        self.load_transcript()
        self.set_mode('idle', 'Ready')

    def close(self):
        self.active = False
        self.closed = True
        self.cancel()
        self.voice.close()

    def set_mode(self, mode, status):
        self.avatar.set_mode(mode)
        self.state.set(status)
        if self.job == 'cloud_listen' and mode == 'listening':
            label = 'Stop & transcribe'
        elif self.job == 'mic_test':
            label = 'Stop test'
        elif self.job == 'listen':
            label = 'Cancel listening'
        else:
            label = 'Talk'
        self.mic.configure(text=label, state='disabled' if mode == 'thinking' else 'normal')

    def load_transcript(self):
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')
        self.last_line = self.flow.welcome()
        self.write('assistant', self.last_line, save=False)
        for turn in self.app.journal.turns(self.app.profile.get()):
            self.write(turn['role'], turn['text'], save=False)
            if turn['role'] == 'assistant':
                self.last_line = turn['text']

    def write(self, role, text, save=True):
        if save:
            try:
                self.app.journal.save_turn(self.app.profile.get(), role, text)
            except DatabaseError:
                messagebox.showerror('Journal unavailable', 'This message appeared in chat but could not be saved.', parent=self.app)
        name = 'ABOARD' if role == 'assistant' else 'YOU'
        self.log.configure(state='normal')
        self.log.insert('end', name + '\n', role)
        self.log.insert('end', text + '\n\n')
        self.log.configure(state='disabled')
        self.log.see('end')

    def cancel(self):
        self.epoch += 1
        self.job = None
        self.after_speech = None
        if self.pending_turn is not None:
            self.after_cancel(self.pending_turn)
            self.pending_turn = None
        if self.capture_cancel is not None:
            self.capture_cancel.set()
            self.capture_cancel = None
        self.capture_finish = None
        self.voice.stop()

    def toggle_listen(self):
        if self.job in ('cloud_listen', 'mic_test') and self.capture_finish is not None:
            self.capture_finish.set()
            self.set_mode('thinking', 'Finishing microphone test…' if self.job == 'mic_test' else 'Finishing recording…')
        elif self.job == 'listen':
            self.hands_free.set(False)
            self.joined = False
            self.voice_follow = False
            self.cancel()
            self.set_mode('idle', 'Voice request stopped')
        elif self.job not in ('cloud_listen', 'route'):
            self.listen(direct=True, manual=True)

    def switch_spoken(self):
        if not self.spoken.get() and self.job == 'speak':
            after = self.after_speech
            self.cancel()
            if after:
                after()
            self.resume()

    def switch_handsfree(self):
        self.joined = False
        self.voice_follow = False
        self.quiet_turns = 0
        if self.hands_free.get():
            self.listen()
        else:
            self.cancel()
            self.set_mode('idle', 'Microphone off')

    def api_key(self):
        return self.app.groq_key.get().strip() or os.environ.get('GROQ_API_KEY', '').strip()

    def refresh_microphones(self):
        try:
            self.devices = input_devices()
        except OSError as error:
            self.state.set(str(error))
            return
        self.device_select.configure(values=list(self.devices))
        if self.device_name.get() not in self.devices:
            self.device_name.set('Windows default')

    def test_microphone(self):
        self.hands_free.set(False)
        self.joined = self.voice_follow = False
        self.start_capture(test=True)

    def start_capture(self, key='', manual=True, test=False):
        self.cancel()
        ticket = self.epoch
        stop, finish = Event(), Event()
        self.capture_finish = finish
        self.peak_signal = 0
        self.signal_percent.set(0)
        device = self.devices.get(self.device_name.get(), WAVE_MAPPER)

        def capture():
            def level(value):
                self.events.put(('mic_level', ticket, value, None, False))

            def ready():
                self.events.put(('mic_ready', ticket, status, None, False))

            wav = record_wave(timeout=4 if test else 20 if manual else 8, cancel=stop,
                              finish=finish, auto_pause=not manual, device=device, on_level=level, on_ready=ready)
            if test or not wav or stop.is_set():
                return bool(wav) if test else None
            self.events.put(('transcribing', ticket, None, None, False))
            return transcribe(wav, key)

        status = 'Speak for the microphone test. Audio stays on this device.' if test else (
            'Speak now, then press Stop & transcribe' if manual else 'Groq microphone on · speak now')
        self.cloud_job('mic_test' if test else 'cloud_listen', capture, cancel=stop)
        self.set_mode('thinking', 'Opening microphone…')

    def switch_cloud(self):
        if self.cloud_enabled.get():
            if not self.api_key():
                self.cloud_enabled.set(False)
                self.app.tabs.select(self.app.ai_tab)
                messagebox.showinfo('Groq API key', 'Enter your Groq key here, then return to Crew assistant to enable Groq speech.',
                                    parent=self.app)
                return
            allowed = messagebox.askyesno('Use Groq for this conversation?',
                'Aboard will send microphone audio to Groq after you tap Talk or activate it with the local wake phrase. '
                'It sends the resulting transcript, or the message you type, to recognize commands. '
                'Use simulated demo information. You can turn this off at any time.', parent=self.app)
            if not allowed:
                self.cloud_enabled.set(False)
                return
        self.cancel()
        self.joined = self.voice_follow = False
        self.wake_hint.configure(text=('Say “Hey Aboard,” wait for the reply, then speak your request.'
                                      if self.cloud_enabled.get()
                                      else 'Hands-free starts with “Hey Aboard.” It listens only on this tab.'))
        if self.hands_free.get():
            self.listen()
        else:
            self.set_mode('idle', 'Groq speech ready · tap Talk' if self.cloud_enabled.get() else 'Offline speech ready')

    def cloud_job(self, kind, task, cancel=None):
        self.job = kind
        ticket = self.epoch
        self.capture_cancel = cancel

        def work():
            try:
                result = task()
                self.events.put((kind, ticket, result, None, False))
            except (OSError, ValueError, RuntimeError) as error:
                self.events.put((kind, ticket, None, str(error), False))

        Thread(target=work, daemon=True).start()

    def listen(self, direct=False, manual=False):
        if not self.active or self.window or self.closed:
            return
        wake_only = not direct and not self.joined
        key = self.api_key() if self.cloud_enabled.get() else ''
        if self.cloud_enabled.get() and not key:
            self.set_mode('idle', 'Enter a Groq API key in API settings to use transcription.')
            return
        if key and not wake_only:
            self.start_capture(key=key, manual=manual)
            return
        self.cancel()
        ticket = self.epoch
        self.job = 'listen'
        self.set_mode('listening', 'Listening for “Hey Aboard”' if wake_only else 'Windows speech · pause when you finish')
        commands = self.flow.choices()
        if wake_only and key:
            choices = WAKE_PHRASES
        elif wake_only:
            choices = tuple(dict.fromkeys((*WAKE_PHRASES, *(f'hey aboard {command}' for command in commands
                                if not WAKE.match(command)), *commands)))
        else:
            choices = commands
        try:
            self.voice.listen(lambda text, error: self.events.put(('listen', ticket, text, error, wake_only)),
                              timeout=7, choices=choices, commands_only=bool(wake_only and key))
        except (OSError, RuntimeError, ValueError) as error:
            self.events.put(('listen', ticket, None, str(error), wake_only))

    def say(self, line, after=None):
        self.cancel()
        ticket = self.epoch
        if not self.spoken.get():
            if after:
                after()
            self.resume()
            return
        self.job = 'speak'
        self.after_speech = after
        self.set_mode('speaking', 'Speaking…')
        try:
            self.voice.speak(line, lambda error: self.events.put(('speak', ticket, after, error, False)))
        except (OSError, RuntimeError, ValueError) as error:
            self.events.put(('speak', ticket, after, str(error), False))

    def resume(self):
        if self.active and self.hands_free.get() and not self.window and not self.job:
            self.listen()
        elif self.active and self.voice_follow and self.follow_up and not self.window and not self.job:
            self.listen(direct=True)
        elif self.active and self.follow_up and not self.window:
            self.set_mode('idle', 'Reply with Talk, or type your answer.')
        elif self.active and not self.window:
            self.set_mode('idle', 'Groq speech ready · tap Talk' if self.cloud_enabled.get() else 'Ready')

    def poll(self):
        if self.closed:
            return
        while True:
            try:
                kind, ticket, value, error, wake_only = self.events.get_nowait()
            except Empty:
                break
            if ticket != self.epoch or not self.active:
                continue
            if kind == 'mic_ready':
                self.set_mode('listening', value)
                continue
            if kind == 'mic_level':
                self.peak_signal = max(self.peak_signal, value)
                self.signal_percent.set(min(100, 30 * log10(1 + value)))
                continue
            if kind == 'transcribing':
                self.set_mode('thinking', 'Transcribing with Groq…')
                continue
            self.job = None
            self.after_speech = None
            self.capture_cancel = None
            self.capture_finish = None
            if kind == 'mic_test':
                self.set_mode('idle', error or ('Signal detected. Enable Groq and press Talk to transcribe.' if value
                                                else 'No input signal. Select another mic or check Windows Sound → Input.'))
            elif kind == 'route':
                self.complete_route(value, error)
            elif kind == 'speak':
                if value:
                    value()
                self.resume()
                if error and not self.job and not self.window:
                    self.set_mode('idle', f'Spoken reply unavailable. {error}')
            elif error:
                self.hands_free.set(False)
                self.joined = False
                self.voice_follow = False
                if kind == 'cloud_listen':
                    self.set_mode('idle', f'{error} Type a message or turn off Groq speech to use Windows speech.')
                else:
                    self.set_mode('idle', f'Microphone unavailable. {error}')
            elif value:
                self.on_heard(value, wake_only)
            elif self.hands_free.get():
                if kind == 'cloud_listen':
                    self.joined = False
                self.quiet_turns += 1
                if self.quiet_turns >= 3:
                    self.joined = False
                self.listen()
            else:
                self.voice_follow = False
                if kind == 'cloud_listen' and self.peak_signal < 1:
                    hint = 'No input signal. Try Test mic and select another microphone if needed.'
                elif kind == 'cloud_listen':
                    hint = 'No transcript returned. Try again and speak a little longer before pressing Stop & transcribe.'
                else:
                    hint = 'Windows speech did not recognize a phrase. Enable Groq for free-form transcription or type your message.'
                self.set_mode('idle', hint)
        self.after(70, self.poll)

    def on_heard(self, heard, wake_only):
        heard = heard.strip()
        wake = WAKE.match(heard)
        if wake_only and not wake:
            self.resume()
            return
        if wake:
            self.joined = True
            self.quiet_turns = 0
            heard = heard[wake.end():]
        if heard:
            self.turn(heard, spoken=True)
        else:
            line = 'I’m listening. How are you feeling?'
            self.write('assistant', line)
            self.last_line = line
            self.say(line)

    def send_typed(self, _event=None):
        line = self.input.get().strip()
        self.input.set('')
        if line:
            self.turn(line)

    def turn(self, line, spoken=False):
        self.cancel()
        self.voice_follow = spoken
        self.quiet_turns = 0
        if self.hands_free.get():
            self.joined = True
        line = line[:750]
        self.write('crew', line)
        key = self.api_key() if self.cloud_enabled.get() else ''
        if key and not urgent_request(normalize(line)):
            pending = self.flow.pending
            if self.flow.upload_pending:
                pending = 'upload'
            self.route_line = line
            self.cloud_job('route', lambda: classify(line, key, pending))
            self.set_mode('thinking', 'Recognizing command with Groq…')
            return
        self.local_turn(line, line)

    def complete_route(self, canonical, error):
        original = self.route_line
        if error:
            self.write('assistant', f'{error} I’ll try the offline command flow.')
        self.local_turn(original, canonical or original)

    def local_turn(self, original, interpreted):
        reply = self.flow.respond(interpreted)
        if interpreted != original and self.flow.draft.get('notes') == interpreted:
            self.flow.draft['notes'] = original
        if interpreted != original and reply.fields.get('notes') == interpreted:
            reply.fields['notes'] = original
        if reply.action == 'urgent':
            self.deliver_turn(original, reply)
        else:
            self.set_mode('thinking', 'Preparing reply…')
            self.pending_turn = self.after(160, self.deliver_turn, original, reply)

    def deliver_turn(self, line, reply):
        self.pending_turn = None
        self.last_line = reply.text
        self.follow_up = reply.action == 'none' and bool(self.flow.pending)
        if self.cloud_enabled.get() and not self.follow_up:
            self.joined = False
        self.write('assistant', reply.text)
        action = reply.action
        if action == 'urgent':
            self.app.urgent.set(True)
            self.append_note(reply.fields.get('notes', line))
            self.say(reply.text)
            # Keep the spoken urgent message local while showing the next action immediately.
            self.after_idle(self.open_urgent)
        elif action.startswith('upload_'):
            self.upload(action.removeprefix('upload_'))
            self.say(reply.text)
        elif action == 'open_checkin':
            for key, value in reply.fields.items():
                if key in self.app.fields:
                    self.app.fields[key].set(value)
            if reply.fields.get('notes'):
                self.append_note(reply.fields['notes'])
            # Wait until the confirmation finishes before navigating out of the assistant.
            self.say(reply.text, lambda: self.app.tabs.select(self.app.check_tab))
        elif action in GUIDES:
            self.say(reply.text, lambda: self.app.show_guide(GUIDES[action]))
        else:
            self.say(reply.text)

    def append_note(self, line):
        current = self.app.notes.get('1.0', 'end-1c').strip()
        updated = (current + '\n' + line.strip()).strip()[:2500]
        self.app.notes.delete('1.0', 'end')
        self.app.notes.insert('1.0', updated)

    def open_urgent(self):
        if not self.active:
            return
        alert = tk.Toplevel(self.app)
        self.window = alert
        alert.title('Urgent crew response')
        alert.transient(self.app)
        alert.configure(bg=BG)
        panel = ttk.Frame(alert, padding=24)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='Alert the crew medical officer now', style='Section.TLabel').pack(anchor='w')
        ttk.Label(panel, text='Follow the mission emergency procedure. The urgent report has been added to the check-in.',
                  wraplength=410).pack(anchor='w', pady=(8, 14))
        ttk.Button(panel, text='Show urgent response guide', style='Primary.TButton',
                   command=lambda: (self.close_window(alert, resume=False), self.app.show_guide('urgent'))).pack(anchor='w')
        alert.protocol('WM_DELETE_WINDOW', lambda: self.close_window(alert))
        alert.grab_set()
        alert.lift()

    def close_window(self, window, resume=True):
        if self.window is window:
            self.window = None
        self.flow.clear_upload_choice()
        window.destroy()
        if resume:
            self.resume()

    def upload(self, category):
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return
        self.cancel()
        self.set_mode('idle', 'Image upload open')
        if category not in ('choice', 'ultrasound', 'injury'):
            category = 'choice'
        popup = tk.Toplevel(self.app)
        self.window = popup
        popup.title('Attach an image')
        popup.transient(self.app)
        popup.configure(bg=BG)
        popup.geometry('560x570')
        popup.minsize(500, 490)
        popup.protocol('WM_DELETE_WINDOW', lambda: self.close_window(popup))
        popup.grab_set()
        body = ttk.Frame(popup, padding=20)
        body.pack(fill='both', expand=True)
        kind = tk.StringVar(value=category if category != 'choice' else '')
        ttk.Label(body, text='Add an image to your check-in', style='Section.TLabel').pack(anchor='w')
        ttk.Label(body, text='Choose the image type, select a PNG or JPEG, then confirm the preview.',
                  style='Muted.TLabel', wraplength=470).pack(anchor='w', pady=(6, 9))
        row = ttk.Frame(body)
        row.pack(fill='x')
        for value, title in [('injury', 'Injury photo'), ('ultrasound', 'Ultrasound export')]:
            ttk.Radiobutton(row, text=title, variable=kind, value=value).pack(side='left', padx=(0, 15))
        instructions = ttk.Label(body, text='', wraplength=470)
        instructions.pack(anchor='w', pady=(9, 5))
        preview = tk.Label(body, text='Image preview', bg=PANEL, fg=MUTED, width=29, height=6)
        preview.pack(fill='both', expand=True, pady=8)
        selected = {'path': None}
        details = ttk.Label(body, style='Muted.TLabel', wraplength=475)
        details.pack(anchor='w')
        bar = ttk.Frame(body)
        bar.pack(fill='x', pady=(9, 0))

        def describe(*_args):
            instructions.configure(text={
                'ultrasound': 'Export a still image from the device, then select it here. Record a reviewer’s disposition on the check-in.',
                'injury': 'Select a saved injury photo. Review the preview before attaching it to your check-in.',
            }.get(kind.get(), 'Select Injury photo or Ultrasound export to continue.'))
            attach.configure(state='normal' if selected['path'] and kind.get() else 'disabled')

        def load(path):
            file_check = inspect_image(path)
            if file_check['status'] == 'error':
                messagebox.showerror('Image unavailable', file_check['detail'], parent=popup)
                return
            try:
                with Image.open(path) as image:
                    image.thumbnail((456, 238))
                    rendered = ImageTk.PhotoImage(image)
            except (OSError, ValueError) as error:
                messagebox.showerror('Image unavailable', str(error), parent=popup)
                return
            preview.configure(image=rendered, text='', width=0, height=0)
            preview.image = rendered
            selected['path'] = path
            details.configure(text=f'{Path(path).name}  ·  {file_check["detail"]}')
            describe()

        def browse():
            path = filedialog.askopenfilename(parent=popup, title='Select an image',
                                              filetypes=[('PNG and JPEG', '*.png *.jpg *.jpeg')])
            if path:
                load(path)

        def confirm():
            path, image_type = selected['path'], kind.get()
            if not path or not image_type:
                return
            try:
                if image_type == 'ultrasound':
                    if not self.app.load_attachment(path, Path(path).name):
                        return
                else:
                    self.app.attach_injury(path)
            except (OSError, ValueError) as error:
                messagebox.showerror('Image unavailable', str(error), parent=popup)
                return
            self.close_window(popup, resume=False)
            line = 'Image attached to your draft. Save your check-in when you’re ready.'
            self.write('assistant', line)
            self.last_line = line
            if self.active:
                self.say(line, lambda: self.app.tabs.select(self.app.check_tab))

        ttk.Button(bar, name='browse', text='Choose file', command=browse).pack(side='left')
        ttk.Button(bar, name='sample', text='Try sample ultrasound',
                   command=lambda: (kind.set('ultrasound'), load(Path(__file__).with_name('demo_scan.png')))).pack(side='left', padx=8)
        attach = ttk.Button(bar, name='attach', text='Attach to check-in', style='Primary.TButton', command=confirm)
        attach.pack(side='right')
        kind.trace_add('write', describe)
        describe()
        popup.lift()
