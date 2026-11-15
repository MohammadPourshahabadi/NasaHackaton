"""Offline software-rendered 3D crew assistant for the Aboard desktop app."""

from dataclasses import dataclass
from functools import lru_cache
from math import cos, pi, sin, sqrt
from random import Random
from time import monotonic
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk


MODE_COLORS = {
    "idle": (88, 224, 233),
    "listening": (128, 242, 200),
    "thinking": (179, 165, 255),
    "speaking": (109, 218, 255),
}
DEEP = (19, 36, 60)
PORCELAIN = (204, 224, 237)
SUIT = (117, 147, 178)
SEAM = (70, 99, 134)
VISOR = (21, 47, 76)
GOLD = (245, 174, 74)
CYAN = (98, 227, 238)
CHEST = (26, 53, 82)


@dataclass(frozen=True)
class Face:
    corners: tuple
    normal: tuple
    color: tuple
    group: str
    finish: str


def normalized(vector):
    length = sqrt(sum(component * component for component in vector))
    return tuple(component / length for component in vector)


def ellipsoid(center, radii, color, group, finish="matte", detail=(24, 12)):
    """Generate outward quads for an ellipsoid with a per-face normal."""
    longitude, latitude = detail
    cx, cy, cz = center
    rx, ry, rz = radii
    rows = []
    for j in range(latitude + 1):
        pitch = -pi / 2 + pi * j / latitude
        row = []
        for i in range(longitude + 1):
            yaw = 2 * pi * i / longitude
            row.append((cx + rx * cos(pitch) * sin(yaw),
                        cy + ry * sin(pitch),
                        cz + rz * cos(pitch) * cos(yaw)))
        rows.append(row)
    for y in range(latitude):
        for x in range(longitude):
            corners = (rows[y][x], rows[y][x+1], rows[y+1][x+1], rows[y+1][x])
            mid = tuple(sum(point[i] for point in corners) * 0.25 for i in range(3))
            normal = normalized(((mid[0]-cx)/rx**2, (mid[1]-cy)/ry**2, (mid[2]-cz)/rz**2))
            yield Face(corners, normal, color, group, finish)


def faceplate():
    """A continuous tapered visor, including the trim around its glass."""
    sections = (
        (.00, .708, VISOR, "glass"), (.17, .705, VISOR, "glass"),
        (.34, .695, VISOR, "glass"), (.52, .676, VISOR, "glass"),
        (.69, .647, VISOR, "glass"), (.83, .613, VISOR, "glass"),
        (.95, .565, VISOR, "glass"), (1.00, .538, VISOR, "glass"),
        (1.02, .529, CYAN, "satin"), (1.07, .509, DEEP, "satin"),
        (1.17, .466, SEAM, "satin"), (1.20, .430, DEEP, "matte"),
    )
    sides = 42
    angles = [i * 2 * pi / sides for i in range(sides+1)]

    def ring(radius, z):
        return [(radius * .519 * cos(a), .266 + radius * .327 * sin(a), z) for a in angles]

    previous_radius, previous_z, _, _ = sections[0]
    inner = ring(previous_radius, previous_z)
    for radius, z, color, finish in sections[1:]:
        outer = ring(radius, z)
        angle_slope = (previous_z - z) / (radius - previous_radius)
        for i in range(sides):
            angle = (angles[i] + angles[i+1]) / 2
            normal = normalized((angle_slope * cos(angle) / .519,
                                 angle_slope * sin(angle) / .327, 1))
            yield Face((inner[i], outer[i], outer[i+1], inner[i+1]), normal, color, "head", finish)
        inner = outer
        previous_radius, previous_z = radius, z


@lru_cache(maxsize=1)
def astronaut_mesh():
    """Meshes for the pressure suit, layered helmet, and face insert."""
    forms = (
        ((0, -.91, -.11), (.85, .57, .47), SUIT, "body", "matte"),
        ((-.68, -.75, -.06), (.37, .39, .43), SEAM, "body", "matte"),
        ((.68, -.75, -.06), (.37, .39, .43), SEAM, "body", "matte"),
        ((-.72, -.70, .02), (.33, .33, .41), PORCELAIN, "body", "matte"),
        ((.72, -.70, .02), (.33, .33, .41), PORCELAIN, "body", "matte"),
        ((-.84, -.67, .393), (.15, .055, .02), GOLD, "body", "satin"),
        ((.82, -.67, .396), (.16, .052, .020), CYAN, "body", "satin"),
        ((0, -.87, .22), (.69, .39, .28), PORCELAIN, "body", "matte"),
        ((0, -.43, -.02), (.51, .13, .43), DEEP, "body", "satin"),
        ((0, -.37, -.02), (.47, .075, .40), SUIT, "body", "satin"),
        ((0, -.35, -.02), (.44, .063, .38), CYAN, "body", "satin"),
        ((0, -.318, -.02), (.44, .056, .38), DEEP, "body", "satin"),
        ((0, -.91, .46), (.36, .205, .10), SEAM, "body", "satin"),
        ((0, -.907, .525), (.327, .177, .065), CHEST, "body", "satin"),
        ((-.153, -.906, .579), (.057, .06, .017), CYAN, "body", "glow"),
        ((-.004, -.906, .594), (.038, .043, .012), GOLD, "body", "glow"),
        ((.118, -.906, .587), (.075, .019, .010), SUIT, "body", "satin"),
        ((.118, -.953, .583), (.063, .016, .010), SUIT, "body", "satin"),
        ((-.53, .315, -.01), (.24, .27, .32), DEEP, "head", "matte"),
        ((.53, .315, -.01), (.24, .27, .32), DEEP, "head", "matte"),
        ((-.595, .322, .022), (.19, .215, .285), SEAM, "head", "satin"),
        ((.595, .322, .022), (.19, .215, .285), SEAM, "head", "satin"),
        ((-.726, .328, .05), (.049, .103, .159), GOLD, "head", "satin"),
        ((.726, .328, .05), (.049, .103, .159), GOLD, "head", "satin"),
        ((0, .34, -.015), (.66, .68, .55), PORCELAIN, "head", "satin"),
        ((0, .798, .343), (.113, .043, .018), SEAM, "head", "matte"),
        ((0, .8, .365), (.068, .023, .013), CYAN, "head", "glow"),
    )
    mesh = list(faceplate())
    for center, radii, color, group, finish in forms:
        detail = (24, 12) if max(radii) > .35 else (14, 7)
        mesh.extend(ellipsoid(center, radii, color, group, finish, detail))
    return tuple(mesh)


@lru_cache(maxsize=5)
def backdrop(width, height):
    small = Image.new("RGB", (128, 128))
    pixels = []
    for y in range(128):
        for x in range(128):
            distance = sqrt(((x - 64) / 67)**2 + ((y - 58) / 70)**2)
            glow = max(0, 1 - distance) ** 1.7
            pixels.append((9 + int(12*glow), 19 + int(34*glow), 33 + int(54*glow)))
    small.putdata(pixels)
    image = small.resize((width, height), Image.Resampling.BICUBIC)
    draw = ImageDraw.Draw(image)
    rng = Random(415)
    for _ in range(72):
        x, y = rng.randrange(width), rng.randrange(height)
        offset = rng.randrange(15, 49)
        draw.point((x, y), fill=(25 + offset//3, 53 + offset, 79 + offset))
    scale = min(width, height)
    for ratio, strength in ((.71, 1), (.80, 0)):
        radius = scale * ratio / 2
        x, y = width * .5, height * .47
        bounds = (x-radius, y-radius, x+radius, y+radius)
        draw.arc(bounds, 20, 160, fill=(28, 55+strength*13, 72+strength*18), width=1)
        draw.arc(bounds, 200, 340, fill=(28, 55+strength*13, 72+strength*18), width=1)
    return image


def shade(color, normal, finish, accent):
    nx, ny, nz = normal
    key = max(0, -.42*nx + .55*ny + .72*nz)
    fill = max(0, .72*nx + .26*ny + .57*nz)
    power = (.37 + .56*key + .16*fill)
    high = 0
    if finish in ("satin", "glass"):
        high = max(0, -.30*nx + .45*ny + .84*nz)**16 * (27 if finish == "satin" else 19)
    if finish == "glass":
        power = .60 + .57*max(0, -.54*nx + .54*ny + .64*nz)
        high += .18 * (1 - nz)**2 * 100
    if finish == "glow":
        return tuple(int(.65 * value + .35 * tint) for value, tint in zip(color, accent))
    rim = max(0, nx - .25*nz) * 12
    return tuple(min(255, int(value * power + high + rim * factor))
                 for value, factor in zip(color, (.15, .52, 1)))


def rigid_rotation(yaw, pitch, roll):
    cy, sy, cx, sx, cz, sz = cos(yaw), sin(yaw), cos(pitch), sin(pitch), cos(roll), sin(roll)
    return (
        (cz*cy - sz*sx*sy, -sz*cx, cz*sy + sz*sx*cy),
        (sz*cy + cz*sx*sy, cz*cx, sz*sy - cz*sx*cy),
        (-cx*sy, sx, cx*cy),
    )


def transform(vector, matrix):
    x, y, z = vector
    a, b, c = matrix
    return (a[0]*x + a[1]*y + a[2]*z,
            b[0]*x + b[1]*y + b[2]*z,
            c[0]*x + c[1]*y + c[2]*z)


def make_expression(seconds, mode):
    blink_phase = (seconds + 1.3) % 4.6
    blink = .13 + .87 * min(1, abs(blink_phase - 2.6) / .133)
    energy = abs(sin(seconds * 13)) * (.6 + .4*sin(seconds*3.4)**2)
    open_mouth = .014 if mode == "listening" else .003
    if mode == "speaking":
        open_mouth = .022 + .041 * energy
    return blink, open_mouth


def render_avatar(width, height, seconds=0, mode="idle", yaw=None, pitch=None):
    """Render a single perspective view from solid 3D geometry."""
    image = backdrop(width, height).copy()
    draw = ImageDraw.Draw(image)
    accent = MODE_COLORS[mode]
    scale = min(width, height) * .313
    horizon = min(width, height)
    radius = horizon * .378
    ring_x, ring_y = width * .5, height * .47
    ring = (ring_x-radius, ring_y-radius, ring_x+radius, ring_y+radius)
    sweep = seconds * (49 if mode == "thinking" else 12)
    restrained = tuple(int(value*.54) for value in accent)
    for offset in (31, 211):
        draw.arc(ring, sweep + offset, sweep + offset + 30, fill=restrained, width=2)
    if mode != "idle":
        pulse = seconds * (1.8 if mode == "listening" else 1.1) % 1
        echo = radius + horizon * .075 * pulse
        fade = tuple(int(value * (.16 + .26*(1-pulse))) for value in accent)
        draw.ellipse((ring_x-echo, ring_y-echo, ring_x+echo, ring_y+echo), outline=fade)
    lift = .018*sin(seconds*2.3)
    yaw = .17*sin(seconds*.82) if yaw is None else yaw
    pitch = -.04 + .032*sin(seconds*1.3) if pitch is None else pitch
    head_matrix = rigid_rotation(yaw, pitch, .023*sin(seconds*1.06))
    body_matrix = rigid_rotation(.25*yaw, .02, 0)
    center_x, center_y = width * .5, height * .436

    def project(point):
        x, y, z = point
        depth = 4.6 / (4.6 - z)
        return center_x + scale*x*depth, center_y - scale*(y+lift)*depth, z

    def head_point(point):
        x, y, z = point
        px, py, pz = transform((x, y-.30, z), head_matrix)
        return px, py+.30, pz

    def body_point(point):
        return transform(point, body_matrix)

    stack = []
    for face in astronaut_mesh():
        in_head = face.group == "head"
        normal = transform(face.normal, head_matrix if in_head else body_matrix)
        if normal[2] < -.025:
            continue
        world = head_point if in_head else body_point
        polygon = [project(world(corner)) for corner in face.corners]
        depth = sum(item[2] for item in polygon) * .25
        stack.append((depth, [point[:2] for point in polygon], shade(face.color, normal, face.finish, accent)))

    for _, points, color in sorted(stack, key=lambda item: item[0]):
        draw.polygon(points, fill=color)

    # The expression follows the curved visor as the helmet turns.
    def panel_point(x, y):
        sag = (x/.519)**2 + ((y-.266)/.327)**2
        z = .485 + .221*sqrt(max(0, 1-sag)) + .007
        return project(head_point((x, y, z)))[:2]

    blink, open_mouth = make_expression(seconds, mode)
    eye_center_y = .35 if mode != "thinking" else .375
    for x in (-.218, .218):
        gaze = x + (.026 if mode == "thinking" else 0)
        squint = blink * (.93 if mode == "listening" else 1)

        def eye(half_width, half_height):
            return [panel_point(gaze+half_width*cos(i*pi/14),
                                eye_center_y+half_height*sin(i*pi/14))
                    for i in range(28)]

        ambient = tuple(int(value*.32) for value in accent)
        soft = tuple(int(value*.60) for value in accent)
        draw.polygon(eye(.124, .095*squint+.007), fill=ambient)
        draw.polygon(eye(.100, .076*squint+.003), fill=soft)
        draw.polygon(eye(.085, .064*squint+.002), fill=accent)
        if squint > .25:
            draw.polygon(eye(.046, .041*squint), fill=(207, 248, 255))

    smile = [(x*.013, .184 + .00043*x*x) for x in range(-9, 10)]
    mouth = [panel_point(x, y + open_mouth*(1-(x/.131)**2)) for x, y in smile]
    mouth.extend(panel_point(x, y - open_mouth*(1-(x/.131)**2)) for x, y in reversed(smile))
    if open_mouth >= .010:
        draw.polygon(mouth, fill=tuple(int(value*.26) for value in accent))
    draw.line(mouth, fill=accent, width=max(2, round(scale*.016)), joint="curve")

    for side in (-1, 1):
        x = side * .366
        draw.line((panel_point(x, .253), panel_point(x+.043*side, .258)),
                  fill=(54, 117, 148), width=max(1, int(scale*.012)))

    if mode in ("listening", "speaking"):
        current = seconds * (8 if mode == "listening" else 14)
        bar_x, bar_y = round(width * .5), round(height * .94)
        gap = max(3, int(horizon*.014))
        for index in range(-5, 6):
            envelope = 1 - abs(index)*.13
            level = (0.37 + .63 * abs(sin(current + index * .72))) * envelope
            half = max(1, round(horizon * .021 * level))
            x = bar_x + index * gap
            draw.line((x, bar_y-half, x, bar_y+half), fill=restrained, width=max(1, gap//3))
    return image


class AvatarCanvas(tk.Canvas):
    """Responsive avatar canvas. Drag left or right to explore the 3D view."""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("width", 390)
        kwargs.setdefault("height", 385)
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("background", "#091321")
        super().__init__(master, **kwargs)
        self.mode = "idle"
        self.started = monotonic()
        self._frame = None
        self._photo = None
        self._image_item = self.create_image(0, 0, anchor="center")
        self._orbit = None
        self._drag = None
        self.bind("<Map>", self._resume, add=True)
        self.bind("<Unmap>", self._pause, add=True)
        self.bind("<Destroy>", self._pause, add=True)
        self.bind("<ButtonPress-1>", self._start_drag, add=True)
        self.bind("<B1-Motion>", self._move_drag, add=True)
        self.bind("<ButtonRelease-1>", self._stop_drag, add=True)

    def set_mode(self, mode):
        if mode not in MODE_COLORS:
            raise ValueError("Unknown avatar mode: " + str(mode))
        self.mode = mode

    def _resume(self, _event=None):
        if self._frame is None:
            self._frame = self.after(0, self._tick)

    def _pause(self, _event=None):
        if self._frame is not None:
            self.after_cancel(self._frame)
            self._frame = None

    def _start_drag(self, event):
        self._drag = (event.x, event.y)
        self._orbit = (0.0, -.04)

    def _move_drag(self, event):
        if self._drag:
            dx, dy = event.x - self._drag[0], event.y - self._drag[1]
            self._orbit = (max(-.46, min(.46, dx/180)),
                           max(-.24, min(.24, -.04+dy/180)))

    def _stop_drag(self, _event):
        self._drag = None
        self._orbit = None

    def _tick(self):
        self._frame = None
        width, height = self.winfo_width(), self.winfo_height()
        if width > 20 and height > 20:
            scale = min(1, 560 / max(width, height))
            yaw, pitch = self._orbit if self._orbit is not None else (None, None)
            image = render_avatar(int(width*scale), int(height*scale),
                                  monotonic()-self.started, self.mode, yaw=yaw, pitch=pitch)
            if scale < 1:
                image = image.resize((width, height), Image.Resampling.BILINEAR)
            self._photo = ImageTk.PhotoImage(image, master=self)
            self.itemconfigure(self._image_item, image=self._photo)
            self.coords(self._image_item, width/2, height/2)
        self._frame = self.after(42, self._tick)
