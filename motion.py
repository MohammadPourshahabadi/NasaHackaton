"""Offline, illustrated rehearsal guides for the Aboard check-in."""

from dataclasses import dataclass
from math import pi, sin
from time import monotonic
import tkinter as tk
from tkinter import ttk
import webbrowser


@dataclass(frozen=True)
class Step:
    title: str
    instruction: str
    cue: str


@dataclass(frozen=True)
class Guide:
    title: str
    scope: str
    source_name: str
    source_url: str
    steps: tuple[Step, ...]


GUIDES = {
    "bp": Guide(
        "Blood pressure", "Earth-based training example. Use the mission procedure for in-flight positioning.",
        "American Heart Association", "https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings/monitoring-your-blood-pressure-at-home",
        (
            Step("Rest and support your arm", "For Earth-based practice, sit with your back and arm supported. Rest quietly for at least five minutes. Keep the center of the cuff at heart level.", "Heart level"),
            Step("Fit the upper-arm cuff", "Use the approved device and the correct cuff size. Place it over the bare upper arm, above the elbow, and align its marking as directed by the device.", "Cuff above elbow"),
            Step("Measure and record", "Stay still and quiet while the device runs. Log both numbers in mmHg and record any repeat reading according to the mission checklist.", "Record both values"),
        ),
    ),
    "pulse": Guide(
        "Resting pulse", "Earth-based training example. Follow the mission protocol for device choice and timing.",
        "MedlinePlus", "https://medlineplus.gov/ency/article/003399.htm",
        (
            Step("Settle at rest", "For this practice method, rest quietly for at least ten minutes before measuring. Support the arm with the palm up.", "Palm facing up"),
            Step("Find the wrist pulse", "Place the pads of your index and middle fingers on the inner wrist just below the base of the thumb. Press lightly until you feel a beat.", "Two fingertips"),
            Step("Count and log", "Count the beats for one full minute using a clock. Enter the result in beats per minute and identify the method used.", "1 minute"),
        ),
    ),
    "temperature": Guide(
        "Body temperature", "Digital oral thermometer example. Use the approved device and measurement site for your mission.",
        "MedlinePlus", "https://medlineplus.gov/ency/article/003400.htm",
        (
            Step("Prepare the device", "Clean the approved thermometer, check the battery, and confirm the measurement site and units required by the mission procedure.", "Check device and units"),
            Step("Take the reading", "For an approved oral measurement, place the probe under your tongue and close your lips around it. Keep it in place until the device signals that the reading is ready.", "Oral example: probe under tongue"),
            Step("Record the method", "Log the value with its units and note where it was measured. Clean the device using the approved procedure.", "Value, unit and site"),
        ),
    ),
    "ultrasound": Guide(
        "Ultrasound handoff", "Acquisition workflow for a trained operator. The displayed scan is a schematic.",
        "NASA Advanced Diagnostic Ultrasound in Microgravity", "https://www.nasa.gov/missions/station/ultrasound-scans-in-space-transform-medicine-on-earth/",
        (
            Step("Confirm the exam", "Ask the crew medical officer which exam and view are needed. The trained operator selects the approved protocol and probe.", "Approved exam"),
            Step("Capture the prescribed view", "Follow the scan checklist and applicable expert guidance. Confirm that the image or clip corresponds to the requested view before saving it.", "Prescribed view"),
            Step("Attach for review", "Record the exam, view, capture time, and operator concerns. Attach the file for authorized medical review.", "Send for medical review"),
        ),
    ),
    "urgent": Guide(
        "Urgent crew response", "Rehearsal for a simulated urgent case. The spacecraft’s approved emergency procedure takes precedence.",
        "NASA Earth-Independent Medical Operations", "https://ntrs.nasa.gov/citations/20250000009",
        (
            Step("Alert the crew medical officer now", "Use the local emergency channel and tell the crew medical officer what is happening and where you are. Start the mission’s onboard emergency procedure.", "Alert crew now"),
            Step("Follow the onboard procedure", "Keep the crew medical officer informed. Repeat a reading only when the approved procedure or the officer directs it and the repeat will not delay urgent care.", "Follow approved checklist"),
            Step("Prepare a ground handoff", "When the crew medical officer directs, relay the symptoms, reading times, and actions taken through the approved channel. The onboard response continues during link loss.", "Record actions and times"),
        ),
    ),
    "sleep": Guide(
        "Sleep and fatigue check-in", "Report what you observed. Wearable estimates, when available, have their own source.",
        "NASA Sleep on Station", "https://www.nasa.gov/humans-in-space/science-in-space-week-of-sept-15-2023-sleep-on-station/",
        (
            Step("Log the sleep you got", "Estimate the time you slept for the reporting period. Note disruptions, shift changes, or naps as relevant to the mission’s logging procedure.", "Sleep log"),
            Step("Report current fatigue", "Choose the response that matches how you feel now. Use the notes field for context such as a schedule change.", "Current fatigue"),
            Step("Review the readings together", "Compare the check-in with your previous entries. If a follow-up is flagged, open the associated checklist and record the next action.", "Review trend and follow-up"),
        ),
    ),
}

BG = "#0a1a2b"
PANEL = "#122a41"
GRID = "#1b344b"
EDGE = "#32526b"
FG = "#e4f5fd"
MUTED = "#a9bfd5"
TEAL = "#65e6db"
AMBER = "#f9c782"
PINK = "#ff9b8e"
SKIN = "#e8af88"
SUIT = "#447b9c"


class GuideFrame(ttk.Frame):
    """Animated visual instructions with fixed, independently readable steps."""

    def __init__(self, parent):
        super().__init__(parent, padding=(16, 12))
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)
        self._key = "bp"
        self._step = 0
        self._phase = 0.0
        self._started = 0.0
        self._timer = None
        self._configure_pending = None

        self._selector = ttk.Combobox(self, state="readonly", values=[guide.title for guide in GUIDES.values()], width=31)
        self._selector.grid(row=0, column=0, columnspan=2, sticky="w")
        self._selector.bind("<<ComboboxSelected>>", self._select)
        self._scope = ttk.Label(self, wraplength=680)
        self._scope.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 8))
        self._canvas = tk.Canvas(self, height=234, background=BG, highlightthickness=0, takefocus=False)
        self._canvas.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self._canvas.bind("<Configure>", self._resize_scene)

        self._title = ttk.Label(self, font=("Segoe UI", 13, "bold"))
        self._title.grid(row=3, column=0, columnspan=2, pady=(9, 2), sticky="w")
        self._instruction = ttk.Label(self, wraplength=680, justify="left", font=("Segoe UI", 10))
        self._instruction.grid(row=4, column=0, columnspan=2, sticky="ew")

        controls = ttk.Frame(self)
        controls.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self._previous = ttk.Button(controls, text="Previous", command=lambda: self._change_step(-1))
        self._play = ttk.Button(controls, text="Play animation", width=16, command=self._toggle)
        self._next = ttk.Button(controls, text="Next", command=lambda: self._change_step(1))
        for button in (self._previous, self._play, self._next):
            button.pack(side="left", padx=(0, 8))
        self._source = ttk.Button(controls, command=self._open_source)
        self._source.pack(side="right")

        self.bind("<Configure>", self._wrap_text)
        self.bind("<Unmap>", self._on_unmap)
        self.bind("<Destroy>", self._on_destroy)
        self.show_guide("bp")

    def show_guide(self, key):
        """Open a guide by key, reset to its first step, and leave motion paused."""
        if key not in GUIDES:
            return
        self._key = key
        self._step = 0
        self._phase = 0.0
        guide = GUIDES[key]
        self._selector.set(guide.title)
        self._scope.configure(text=guide.scope)
        self._source.configure(text="Source: " + ("NASA" if guide.source_name.startswith("NASA") else guide.source_name))
        self._show_step()

    def _select(self, _event):
        selected = self._selector.current()
        if selected >= 0:
            self.show_guide(tuple(GUIDES)[selected])

    def _show_step(self):
        self._pause()
        steps = GUIDES[self._key].steps
        step = steps[self._step]
        self._title.configure(text=f"{self._step + 1} of {len(steps)}   {step.title}")
        self._instruction.configure(text=step.instruction)
        self._previous.state(["!disabled"] if self._step else ["disabled"])
        self._next.state(["!disabled"] if self._step < len(steps) - 1 else ["disabled"])
        self._draw()

    def _change_step(self, delta):
        next_step = self._step + delta
        if 0 <= next_step < len(GUIDES[self._key].steps):
            self._step = next_step
            self._phase = 0.0
            self._show_step()

    def _wrap_text(self, event):
        self._scope.configure(wraplength=max(240, event.width - 34))
        self._instruction.configure(wraplength=max(240, event.width - 34))

    def _resize_scene(self, _event):
        if self._configure_pending is not None:
            self.after_cancel(self._configure_pending)
        self._configure_pending = self.after_idle(self._draw_idle)

    def _draw_idle(self):
        self._configure_pending = None
        self._draw()

    def _toggle(self):
        if self._timer is not None:
            self._pause()
            return
        self._started = monotonic() - self._phase * 3.2
        self._play.configure(text="Pause animation")
        self._tick()

    def _tick(self):
        elapsed = (monotonic() - self._started) / 3.2
        self._phase = elapsed % 1.0
        self._draw()
        self._timer = self.after(60, self._tick)

    def _pause(self):
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None
        self._play.configure(text="Play animation")

    def _on_unmap(self, _event):
        self._pause()

    def _on_destroy(self, _event):
        if self._timer is not None:
            self.after_cancel(self._timer)
        if self._configure_pending is not None:
            self.after_cancel(self._configure_pending)

    def _open_source(self):
        webbrowser.open(GUIDES[self._key].source_url)

    def _draw(self):
        canvas = self._canvas
        height = canvas.winfo_height()
        width = canvas.winfo_width()
        if min(height, width) <= 1:
            return
        canvas.delete("all")
        self._scale = min(width / 640, height / 220)
        self._left = (width - 640 * self._scale) / 2
        self._top = (height - 220 * self._scale) / 2
        for x in range(16, 640, 32):
            self._line(x, 12, x, 207, color=GRID)
        for y in range(15, 215, 32):
            self._line(16, y, 624, y, color=GRID)
        self._label(25, 16, "REHEARSAL", MUTED, 10)
        self._label(25, 182, GUIDES[self._key].steps[self._step].cue, TEAL, 16)
        animations = {
            "bp": self._draw_bp,
            "pulse": self._draw_pulse,
            "temperature": self._draw_temperature,
            "ultrasound": self._draw_ultrasound,
            "urgent": self._draw_urgent,
            "sleep": self._draw_sleep,
        }
        animations[self._key]()

    def _transform(self, coordinates):
        return tuple(value * self._scale + (self._left if i % 2 == 0 else self._top)
                     for i, value in enumerate(coordinates))

    def _line(self, *coords, color=TEAL, width=1, **kwargs):
        self._canvas.create_line(*self._transform(coords), fill=color,
                                 width=max(1, width * self._scale), capstyle="round", **kwargs)

    def _rect(self, *coords, fill=PANEL, outline=EDGE, width=1):
        self._canvas.create_rectangle(*self._transform(coords), fill=fill, outline=outline,
                                      width=max(1, width * self._scale))

    def _oval(self, *coords, fill="", outline="", width=1):
        self._canvas.create_oval(*self._transform(coords), fill=fill, outline=outline,
                                 width=max(1, width * self._scale))

    def _polygon(self, *coords, fill, outline=""):
        self._canvas.create_polygon(*self._transform(coords), fill=fill, outline=outline)

    def _label(self, x, y, text, color=FG, size=12):
        self._canvas.create_text(*self._transform((x, y)), text=text, anchor="nw", fill=color,
                                 font=("Segoe UI", max(8, round(size * self._scale)), "bold"))

    def _halo(self, x, y, color=TEAL):
        radius = 13 + 8 * (sin(self._phase * 2 * pi) + 1) / 2
        self._oval(x-radius, y-radius, x+radius, y+radius, outline=color, width=2)

    def _draw_bp(self):
        self._line(94, 99, 96, 173, 184, 173, color=EDGE, width=6)
        self._oval(141, 45, 197, 102, fill=SKIN)
        self._polygon(150, 104, 198, 103, 229, 132, 203, 162, 122, 162, 127, 119, fill=SUIT)
        self._line(194, 120, 299, 140, 391, 140, color=SKIN, width=27)
        self._line(262, 156, 475, 156, color=EDGE, width=6)
        if self._step == 0:
            self._line(167, 127, 320, 127, color=TEAL, dash=(5, 5))
            self._halo(173, 127)
        else:
            self._polygon(227, 110, 269, 118, 263, 151, 222, 144, fill=TEAL)
            self._line(247, 117, 242, 145, color=BG, width=3)
            self._line(262, 146, 304, 169, 432, 172, 463, 132, 472, 116, color=MUTED, width=2, smooth=True)
            if self._step == 1:
                self._halo(246, 129)
        self._rect(444, 68, 579, 142)
        self._rect(456, 81, 567, 126, fill=BG, outline=GRID)
        if self._step == 2:
            self._label(470, 90, "SYS / DIA", TEAL, 13)
            self._line(467, 119, 468 + 94 * self._phase, 119, width=2)
        else:
            self._label(478, 90, "CUFF", MUTED, 13)

    def _draw_pulse(self):
        self._line(93, 128, 281, 128, color=SKIN, width=44)
        self._oval(254, 100, 348, 153, fill=SKIN)
        self._line(277, 111, 309, 79, color=SKIN, width=17)
        for i in range(4):
            self._line(302, 110+i*10, 369-i*3, 109+i*11, color=SKIN, width=8)
        if self._step == 0:
            self._line(126, 157, 276, 157, color=EDGE, width=4)
            self._halo(303, 126)
        else:
            shift = 9 * sin(pi * self._phase)
            self._line(221, 48-shift, 260, 87-shift, 267, 112-shift, color="#f7c79f", width=12)
            self._line(234, 44-shift, 274, 83-shift, 281, 109-shift, color="#f7c79f", width=12)
            self._halo(272, 115)
        self._rect(401, 65, 568, 154)
        self._label(419, 78, "COUNT EVERY BEAT" if self._step == 2 else "WRIST PULSE", MUTED, 10)
        if self._step == 2:
            self._line(420, 122, 451, 122, 459, 110, 467, 138, 480, 100, 490, 122, 546, 122, width=2)
            dot = 420 + 126 * self._phase
            self._oval(dot-3, 119, dot+3, 125, fill=FG)
        else:
            self._line(422, 124, 545, 124, color=EDGE, width=2)

    def _draw_temperature(self):
        if self._step == 1:
            self._draw_oral_example()
            return
        self._line(113, 112, 250, 112, color=MUTED, width=16)
        self._oval(104, 104, 122, 120, fill=TEAL)
        self._rect(246, 79, 505, 145, fill=SUIT, outline=MUTED, width=2)
        self._rect(268, 90, 402, 134, fill=BG, outline=GRID)
        self._oval(439, 100, 466, 127, fill=PANEL, outline=MUTED)
        self._label(280, 101, "READY" if self._step == 0 else "LOG VALUE", TEAL, 14)
        if self._step == 0:
            self._halo(451, 115)
        else:
            self._label(514, 104, "°C / °F", AMBER, 12)
            self._halo(470, 114)

    def _draw_oral_example(self):
        self._oval(134, 37, 261, 158, fill=SKIN)
        self._polygon(196, 83, 257, 77, 273, 108, 251, 111, 262, 119,
                      249, 134, 247, 149, 216, 158, 211, 175, 165, 173, fill=SKIN)
        self._line(216, 122, 254, 122, color=BG, width=2)
        self._line(219, 119, 242, 115, color=PINK, width=5, smooth=True)
        shift = 20 * (1 - self._phase)
        self._line(218+shift, 125, 325+shift, 125, color=MUTED, width=5)
        self._line(218+shift, 125, 226+shift, 125, color=TEAL, width=5)
        self._line(330+shift, 125, 397+shift, 125, color=SUIT, width=17)
        self._halo(222, 124)
        self._label(442, 116, "ORAL THERMOMETER", MUTED, 10)

    def _draw_ultrasound(self):
        self._rect(331, 47, 560, 163, outline=MUTED, width=2)
        self._rect(345, 60, 547, 145, fill=BG, outline=GRID)
        self._label(359, 69, "SCHEMATIC", MUTED, 10)
        self._line(164, 123, 178, 76, color=MUTED, width=24)
        self._line(152, 126, 183, 133, color=TEAL, width=9)
        self._line(179, 70, 208, 51, 279, 56, 331, 104, color=EDGE, width=4, smooth=True)
        self._line(86, 139, 185, 141, 248, 146, color=SKIN, width=5, smooth=True)
        if self._step == 0:
            self._halo(171, 104)
            self._label(365, 101, "SELECT EXAM", TEAL, 13)
        else:
            x = 423 + 38 * self._phase
            self._polygon(448, 88, 405, 129, 490, 129, fill=GRID, outline=EDGE)
            self._line(x, 103, x, 130, color=TEAL, width=2)
            if self._step == 2:
                self._label(471, 70, "SAVED", TEAL, 10)

    def _draw_urgent(self):
        for idx, (x, label) in enumerate(((137, "CREW"), (319, "PROCEDURE"), (501, "HANDOFF"))):
            color = PINK if idx == self._step else EDGE
            self._oval(x-25, 66, x+25, 116, fill=PANEL, outline=color, width=2)
            self._label(x-5, 81, str(idx + 1), FG, 15)
            self._label(x-39, 130, label, FG, 11)
            if idx < 2:
                self._line(x+30, 91, x+152, 91, color=EDGE, width=2, arrow="last")
            if idx == self._step:
                radius = 27 + 5 * self._phase
                self._oval(x-radius, 91-radius, x+radius, 91+radius, outline=PINK)

    def _draw_sleep(self):
        self._oval(119, 77, 193, 150, fill=TEAL)
        self._oval(149, 62, 201, 123, fill=BG)
        self._rect(268, 47, 556, 161, outline=MUTED, width=2)
        self._label(283, 59, ("DURATION", "SELF REPORT", "RECENT ENTRIES")[self._step], MUTED, 10)
        if self._step < 2:
            for i in range(3):
                x = 293 + i * 78
                self._rect(x, 94, x+57, 133, fill=PANEL, outline=TEAL if i == self._step else EDGE)
                self._label(x+11, 105, ("LOW", "MID", "HIGH")[i] if self._step else ("START", "WAKE", "NOTE")[i], FG, 9)
            self._halo(322 + self._step * 78, 113)
        else:
            values = (105, 97, 106, 120, 135)
            for i, y in enumerate(values):
                x = 288 + i * 58
                if i:
                    self._line(x-58, values[i-1], x, y, width=2)
                radius = 3 + (2 * sin(pi * self._phase) if i == len(values) - 1 else 0)
                self._oval(x-radius, y-radius, x+radius, y+radius, fill=TEAL)
