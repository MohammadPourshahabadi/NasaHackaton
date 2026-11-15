"""Offline measurement tutorials with source links and animated checkpoints."""
from dataclasses import dataclass
from math import cos, pi
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageOps, ImageTk
from ai_label import ai_tag
from nasa_reference import CALF_US_SOURCE, EYE_SOURCE


AHA = 'https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings/monitoring-your-blood-pressure-at-home'
APOLLO = 'https://ntrs.nasa.gov/citations/19760005591'
ISS_CARDIO = 'https://ntrs.nasa.gov/api/citations/20090014822/downloads/20090014822.pdf'
NASA_LAB = 'https://www.nasa.gov/hrp/research-operations-integration/sample-collection-and-portable-systems-and-blood-collection-data/'


@dataclass(frozen=True)
class Guide:
    label: str
    mode: str
    source: str
    steps: tuple
    row: int | None = None
    video: str | None = None


GUIDES = {
    'bp': Guide('Blood pressure', 'Earth practice • Automatic upper-arm cuff', AHA, (
        ('Prepare the cuff', 'Use a validated upper-arm monitor and the cuff size specified for your arm. Avoid exercise, smoking and caffeine for 30 minutes beforehand. Empty your bladder.'),
        ('Settle for five minutes', 'Sit with your back supported and both feet flat. Stay quiet for at least five minutes before starting.'),
        ('Fit the cuff', 'Wrap the cuff around your bare upper arm. Use the cuff’s placement markings and the device instructions to position it above the elbow.'),
        ('Support the arm and start', 'Rest your arm on a surface with the cuff at heart level. Press Start and stay still and quiet until the display settles.'),
        ('Repeat and record both values', 'Wait at least one minute, then repeat using the same arm and posture. Record both systolic/diastolic pairs in mmHg.'),
    ), 0, 'https://www.youtube.com/watch?v=TLiD3vh_X8o'),
    'orbit_bp': Guide('Blood pressure', 'Spacecraft • Mission-approved cuff', ISS_CARDIO, (
        ('Confirm the session', 'Open the onboard procedure for the assigned cuff and measurement session. Check whether it calls for a spot reading or scheduled ambulatory monitoring.'),
        ('Set up the cuff', 'Use its placement markings and the crew procedure for cuff size, arm, routing and body stabilization in microgravity.'),
        ('Acquire the reading', 'Follow the onboard procedure for rest and body position. Keep the arm still during inflation and wait for the completed reading.'),
        ('Check and log the result', 'If the device reports an error, follow its procedure for troubleshooting and repetition. Record systolic and diastolic in mmHg with time, posture and session type.'),
    )),
    'pulse': Guide('Resting heart rate', 'Spacecraft • Mission-approved HR / ECG monitor', ISS_CARDIO, (
        ('Choose a resting session', 'Use the assigned heart-rate or ECG monitor. Follow the crew protocol for the resting period and body position, and note any recent activity.'),
        ('Fit the sensor', 'Use the onboard placement diagram for your device. Verify sensor contact and secure leads if your monitor uses them.'),
        ('Wait for a usable signal', 'Keep still until the monitor completes the recording. Check for signal or motion warnings before accepting the value.'),
        ('Log the resting rate', 'Enter the device’s resting value in beats per minute (bpm). Save the time, body position and method so the next reading can be taken under comparable conditions.'),
    )),
    'sleep': Guide('Sleep duration', 'Spacecraft • Wrist actigraphy or sleep log',
                   'https://www.nasa.gov/humans-in-space/wearable-tech-for-space-station-research/', (
        ('Prepare the wearable or log', 'If your mission assigns an actigraph, check that it is recording and wear it on the wrist specified by the study. Use the mission time convention in your log.'),
        ('Capture the sleep episode', 'Keep the device on during the scheduled recording window. Log attempted sleep time, wake time and any periods when the device was off your wrist.'),
        ('Check the episode after waking', 'Find the matching sleep episode in the device export or official report. Check its date and whether it includes a nap or incomplete recording.'),
        ('Log the source and duration', 'Enter total sleep time in hours. Label wearable estimates and self-reported values separately. If flagged, verify the episode and log the next planned sleep period.'),
    ), 1, 'https://www.youtube.com/watch?v=fYX6Jq9Z7E8'),
    'sleep_review': Guide('Review the sleep log', 'Spacecraft • Recorded sleep episode',
                         'https://www.nasa.gov/humans-in-space/wearable-tech-for-space-station-research/', (
        ('Find the entry', 'Open the matching sleep episode in the wearable report or crew sleep log. Check its start and end time.'),
        ('Check what the duration covers', 'Identify whether the value came from the full sleep period, a nap or an incomplete wearable recording.'),
        ('Plan the next check', 'Check your alertness before critical tasks. Record the next planned sleep episode in the journal.'),
    ), 1),
    'calf': Guide('Calf isometric torque', 'Ground research • Operator-supervised dynamometer',
                  'https://journals.physiology.org/doi/abs/10.1152/japplphysiol.91578.2008', (
        ('Book a matched test', 'Use the research or clinical dynamometer with a trained operator. Confirm the test leg, the static test mode and the study protocol.'),
        ('Align and stabilize', 'The operator positions the leg, secures the foot to the plate and checks that the ankle is neutral, with the foot at 90° to the lower leg.'),
        ('Press against the fixed plate', 'On the operator’s cue, press as directed while the plate stays fixed. Follow the operator’s timing and rest instructions for every trial.'),
        ('Save the verified torque', 'Record the operator’s reported isometric torque in N·m, with side and setup. Arrange a supervised repeat if the first result is flagged.'),
    )),
    'calf_us': Guide('Calf muscle ultrasound', 'ISS • Teleguided panoramic ultrasound', CALF_US_SOURCE, (
        ('Set up the guided scan', 'Use the assigned onboard ultrasound and leg guide with a trained sonographer. Confirm the leg and scan landmark from the reference session.'),
        ('Sweep across the marked site', 'Follow the sonographer’s directions for positioning, coupling and sweep. Have the sonographer check image quality and repeat the sweep if requested.'),
        ('Record cross-sectional area', 'Use the specialist’s medial gastrocnemius cross-sectional area in cm². Match the same side and scan site when reviewing change.'),
    )),
    'oct': Guide('Peripapillary retinal thickness', 'ISS • Clinician-reviewed OCT', EYE_SOURCE, (
        ('Set up the onboard OCT', 'Use the assigned optical coherence tomography instrument and crew procedure. Select the optic nerve head scan and verify the correct eye.'),
        ('Capture and verify the scan', 'Follow the onboard alignment and fixation procedure. Have the specialist verify scan quality, registration and segmentation before accepting the report.'),
        ('Record TRT250 in µm', 'Enter the reviewed total retinal thickness from the 0–250 µm annulus outside the Bruch membrane opening. Use the matching eye field.'),
    )),
}

LAB_TESTS = {
    'serum_sodium': ('Serum sodium', 'mEq/L', 'Verify that the report row is sodium (Na) and the specimen is serum.'),
    'serum_potassium': ('Serum potassium', 'mEq/L', 'Verify that the row is potassium (K). If the report flags the sample as hemolyzed or unsuitable, ask the medical officer to review it before entry.'),
    'serum_creatinine': ('Serum creatinine', 'mg/dL', 'Verify that the row is serum creatinine. Check the units and use the measured concentration from the report.'),
    'serum_glucose': ('Serum glucose', 'mg/dL', 'Verify that the row is serum glucose and note the fasting or meal timing recorded by the team. Follow their preparation instructions.'),
}

for key, (label, unit, check) in LAB_TESTS.items():
    GUIDES[key] = Guide(label, 'Crew medical officer • Verified serum report', NASA_LAB, (
        ('Confirm the order', f'Ask the crew medical officer to confirm the order for {label.lower()}, specimen requirements and collection timing.'),
        ('Follow the assigned workflow', 'A trained operator follows the approved collection, processing and storage procedure. Confirm whether the mission can analyze this specimen onboard or must send it for later analysis.'),
        ('Verify the result', f'{check} Check the sample date, identification and the final report status.'),
        ('Enter the verified value', f'Use the confirmed value in {unit}. Ask the medical officer to verify or order a repeat if the result is flagged. Use the Apollo reference for comparable preflight serum only.'),
    ), 2, 'https://www.youtube.com/watch?v=KQ9Nj-L-mK0')


def supine_guide(kind):
    label = GUIDES[kind].label
    value = 'both pressure values in mmHg' if kind == 'bp' else 'the heart rate in bpm'
    return Guide(label, 'Ground comparison • Apollo AP005 supine conditions', APOLLO, (
        ('Set up the comparison', 'Confirm that you are collecting a ground reading under the AP005 comparison conditions. Use the monitor specified by the local procedure.'),
        ('Lie on your back and rest', 'Lie face up and remain quietly at rest for five minutes. Use the local procedure for cuff or sensor placement.'),
        ('Acquire and record the result', f'Follow the ground procedure to acquire the reading. Log {value}, the posture and the rest period.'),
        ('Match the setup when repeating', 'Recreate the same conditions if a repeat is requested. For an in-flight measurement, open the spacecraft guide instead.'),
    ))


KEY_GUIDES = {
    'sleep': 'sleep', 'pulse': 'pulse', 'systolic': 'bp', 'diastolic': 'bp',
    'calf_csa_left': 'calf_us', 'calf_csa_right': 'calf_us',
    'trt250_left': 'oct', 'trt250_right': 'oct', **{key: key for key in LAB_TESTS},
}


def equipment_photos(kind, guide, supine):
    if guide.row is not None:
        filename, cells = 'measurement-frames.png', [(guide.row, i) for i in range(3)]
    else:
        filename = 'equipment-atlas.png'
        layout = {'calf_us': (0, 0), 'oct': (1, 0), 'orbit_bp': (2, 0),
                  'pulse': (2, 1), 'supine': (2, 2)}
        if not supine and kind not in layout:
            return []
        row, column = layout['supine' if supine else kind]
        cells = [(row, i) for i in range(3)] if row < 2 else [(row, column)]
    path = Path(__file__).with_name(filename)
    if not path.is_file():
        return []
    with Image.open(path) as atlas:
        w,h=atlas.size
        return [atlas.crop((c*w//3+9,r*h//3+9,(c+1)*w//3-9,(r+1)*h//3-9))
                for r,c in cells]


def open_measurement(parent, kind, on_repeat=None, supine=False):
    supine = supine and kind in ('bp', 'pulse')
    guide = supine_guide(kind) if supine else GUIDES[kind]
    window = tk.Toplevel(parent)
    window.title(guide.label + ' | Measurement guide')
    window.transient(parent)
    previous_grab = parent.grab_current()
    panel = ttk.Frame(window, padding=18)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text=guide.label, style='Section.TLabel').pack(anchor='w')
    ttk.Label(panel, text=guide.mode).pack(anchor='w', pady=(0, 8))
    stage=tk.Frame(panel,bg='#203a3e',padx=10,pady=10)
    stage.pack(fill='x')
    photos=equipment_photos(kind,guide,supine)
    canvas=tk.Canvas(stage,width=284,height=284,bg='#152a2e',highlightthickness=0)
    if photos:
        canvas.pack(side='left',padx=(0,12))
    photo_item=canvas.create_image(0,0,anchor='nw')
    outline=tk.Frame(stage,bg='#203a3e')
    outline.pack(side='left',anchor='n',fill='x',expand=True,padx=8)
    steps=[]
    for number,(title,_) in enumerate(guide.steps,1):
        line=tk.Label(outline,text=f'{number:02}   {title}',font=('Segoe UI',10),
                      anchor='w',padx=9,pady=9)
        line.pack(fill='x',pady=2)
        steps.append(line)
    if photos:
        tk.Label(outline,text='Illustration · Follow the written procedure',bg='#203a3e',
                 fg='#b7cbc5',font=('Segoe UI',9),wraplength=240,justify='left').pack(
                     anchor='w',pady=(8,0))
    if kind in ('sleep','sleep_review'):
        timeline=tk.Canvas(outline,width=240,height=75,bg='#203a3e',highlightthickness=0)
        timeline.pack(anchor='w',pady=(5,0))
        timeline.create_line(22,42,217,42,fill='#71968c',width=2)
        timeline.create_line(42,42,191,42,fill='#a1e7cc',width=8,capstyle='round')
        timeline.create_text(42,62,text='Sleep start',fill='#d6eee5',font=('Segoe UI',9))
        timeline.create_text(191,62,text='Wake time',fill='#d6eee5',font=('Segoe UI',9))
        cursor=timeline.create_oval(36,36,48,48,fill='#effdf6',outline='')
    caption = ttk.Label(panel, wraplength=530, justify='left', padding=(0, 0, 0, 6))
    heading = ttk.Label(panel, style='Section.TLabel')
    heading.pack(anchor='w', pady=(8, 4))
    caption.pack(fill='x')
    caption.configure(width=68)
    controls = ttk.Frame(panel)
    controls.pack(fill='x', pady=(6, 8))
    index = 0
    frame = 0
    timer = None
    photo_steps = {'bp': (0, 0, 1, 2, 2), 'sleep': (0, 1, 2, 2),
                   'sleep_review': (2, 0, 1), 'oct': (0, 1, 0)}

    def render():
        if not photos:
            return
        if kind in ('sleep','sleep_review'):
            x=42+149*frame/43
            timeline.coords(cursor,x-6,36,x+6,48)
        image_index = 0 if len(photos)==1 else photo_steps.get(kind,(0,1,2,2))[index]
        zoom = 1 + .075*(1-cos(2*pi*frame/44))/2
        source=photos[image_index]
        enlarged=ImageOps.fit(source,(round(284*zoom),round(284*zoom)),Image.Resampling.LANCZOS)
        offset=(enlarged.width-284)//2
        canvas.photo=ImageTk.PhotoImage(ai_tag(enlarged.crop((offset,offset,offset+284,offset+284))),master=window)
        canvas.itemconfigure(photo_item,image=canvas.photo)

    def show():
        nonlocal frame
        frame = 0
        title, instructions = guide.steps[index]
        heading.configure(text=title)
        caption.configure(text=instructions)
        for number,line in enumerate(steps):
            selected=number==index
            line.configure(bg='#365650' if selected else '#203a3e',
                           fg='#d6fae9' if selected else '#b7cbc5',
                           font=('Segoe UI',10,'bold' if selected else 'normal'))
        back.state(['!disabled'] if index else ['disabled'])
        forward.state(['!disabled'] if index+1 < len(guide.steps) else ['disabled'])
        render()

    def jump(delta):
        nonlocal index
        index = max(0, min(len(guide.steps)-1, index+delta))
        show()

    def tick():
        nonlocal timer, frame
        frame = (frame+1) % 44
        render()
        timer = window.after(70, tick)

    back = ttk.Button(controls, text='Previous', command=lambda: jump(-1))
    back.pack(side='left')
    forward = ttk.Button(controls, text='Next step', command=lambda: jump(1))
    forward.pack(side='left', padx=6)
    footer = ttk.Frame(panel)
    footer.pack(fill='x')
    if kind in ('bp', 'orbit_bp') and not supine:
        other = 'orbit_bp' if kind == 'bp' else 'bp'
        label = 'See spacecraft cuff workflow' if kind == 'bp' else 'See Earth cuff demonstration'
        def switch():
            window.destroy()
            open_measurement(parent, other, on_repeat)
        ttk.Button(footer, text=label, command=switch).pack(side='left')
    if on_repeat:
        def repeat():
            window.destroy()
            on_repeat()
        ttk.Button(footer, text='Record repeat', style='Primary.TButton', command=repeat).pack(side='right')

    def cleanup(event):
        if event.widget is window:
            if timer is not None:
                window.after_cancel(timer)
            if previous_grab and previous_grab.winfo_exists():
                previous_grab.grab_set()

    window.bind('<Destroy>', cleanup)
    window.bind('<Left>', lambda event: jump(-1))
    window.bind('<Right>', lambda event: jump(1))
    window.bind('<Escape>', lambda event: window.destroy())
    show()
    if photos:
        timer = window.after(70, tick)
    if previous_grab:
        window.wait_visibility()
        window.grab_set()
    window.focus_set()
    return window
