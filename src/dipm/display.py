"""Physical display sizes from the OS, for 1:1 real-size viewing (docs/gui.md §8.2 3E.8, §8.3
item 12; tolerance-uncertainty.md §4 item 2).

Browsers do not expose a screen's physical size (CSS `mm` is a fixed 96 px/in convention),
so the local engine asks the OS:

* **macOS:** CoreGraphics through ctypes: `CGGetActiveDisplayList`, `CGDisplayScreenSize`
  (mm), `CGDisplayPixelsWide/High` (points of the current mode, the same units as the
  browser's CSS px at 100 % zoom, also under scaled resolutions), `CGDisplayIsBuiltin`,
  `CGDisplayBounds` (position in the global space).  The name comes from AppKit's
  `NSScreen.localizedName` through the Objective-C runtime when that works, else
  "Built-in display" / "Display <id>".
* **Windows / Linux:** not implemented in this iteration (EDID parsing is not
  straightforward to do portably): `source: "unknown"` with no displays, so the GUI falls back
  to credit-card calibration.

Tests and e2e runs replace the OS with a stub: `DIPM_DISPLAY_STUB` (a JSON list of displays,
or `{"displays": [...]}`) or `set_provider(fn)`.

`match()` picks the display the browser is on from what the page reports (CSS px screen
size, devicePixelRatio, and on Chromium the Window Management API's label / isInternal /
position).  CSS px per mm = screen width in CSS px ÷ physical width in mm (the GUI computes
it; browser zoom scales both the CSS px and the reported screen width together).
"""
from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import sys
from typing import Callable

_provider: Callable[[], dict] | None = None


def set_provider(fn: Callable[[], dict] | None) -> None:
    """Replace the OS query (tests).  `fn() -> {"source", "displays": [...]}`."""
    global _provider
    _provider = fn


def _plausible(d: dict) -> tuple[bool, str]:
    w, h = d.get("mm") or (0, 0)
    pw, ph = d.get("px") or (0, 0)
    if not w or not h or w <= 0 or h <= 0:
        return False, "the OS reports no physical size"
    if not (40 <= w <= 3000 and 25 <= h <= 2000):
        return False, f"{w:g} × {h:g} mm is outside 40–3000 mm"
    if pw and ph:
        ar_mm, ar_px = w / h, pw / ph
        if abs(ar_mm - ar_px) / ar_px > 0.08:
            return False, f"aspect ratio {ar_mm:.3f} (mm) disagrees with {ar_px:.3f} (px)"
        ppm = pw / w
        if not (1.0 <= ppm <= 40.0):
            return False, f"{ppm:.2f} px/mm is implausible"
    return True, ""


def _finish(raw: dict) -> dict:
    out = []
    for d in raw.get("displays") or []:
        d = dict(d)
        d.setdefault("name", "Built-in display" if d.get("builtin") else f"Display {d.get('id', '?')}")
        ok, why = _plausible(d)
        d["plausible"], d["implausible_reason"] = ok, why
        out.append(d)
    return {"source": raw.get("source", "unknown"), "displays": out, "platform": sys.platform}


def displays() -> dict:
    """{"source": "coregraphics" | "stub" | "unknown", "displays": [{id, name, builtin, mm: [w, h],
    px: [w, h] (points), origin: [x, y], scale (backing pixels per point), main, plausible,
    implausible_reason}], "platform"}."""
    if _provider is not None:
        return _finish(_provider())
    stub = os.environ.get("DIPM_DISPLAY_STUB")
    if stub:
        data = json.loads(stub)
        return _finish({"source": "stub", "displays": data if isinstance(data, list) else data.get("displays", [])})
    if sys.platform == "darwin":
        try:
            return _finish(_coregraphics())
        except Exception as e:   # noqa: BLE001 - fall back to calibration
            return {"source": "unknown", "displays": [], "platform": sys.platform, "error": f"{type(e).__name__}: {e}"}
    return {"source": "unknown", "displays": [], "platform": sys.platform,
            "note": "physical display size is only read on macOS in this iteration; use calibration"}


# ---------------------------------------------------------------- macOS

class _CGSize(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]


class _CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class _CGRect(ctypes.Structure):
    _fields_ = [("origin", _CGPoint), ("size", _CGSize)]


def _coregraphics() -> dict:
    path = ctypes.util.find_library("CoreGraphics") or \
        "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
    cg = ctypes.CDLL(path)
    cg.CGGetActiveDisplayList.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32)]
    cg.CGGetActiveDisplayList.restype = ctypes.c_int32
    cg.CGDisplayScreenSize.argtypes = [ctypes.c_uint32]
    cg.CGDisplayScreenSize.restype = _CGSize
    cg.CGDisplayPixelsWide.argtypes = [ctypes.c_uint32]
    cg.CGDisplayPixelsWide.restype = ctypes.c_size_t
    cg.CGDisplayPixelsHigh.argtypes = [ctypes.c_uint32]
    cg.CGDisplayPixelsHigh.restype = ctypes.c_size_t
    cg.CGDisplayIsBuiltin.argtypes = [ctypes.c_uint32]
    cg.CGDisplayIsBuiltin.restype = ctypes.c_uint32
    cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
    cg.CGDisplayBounds.restype = _CGRect
    cg.CGMainDisplayID.restype = ctypes.c_uint32
    cg.CGDisplayCopyDisplayMode.argtypes = [ctypes.c_uint32]
    cg.CGDisplayCopyDisplayMode.restype = ctypes.c_void_p
    cg.CGDisplayModeGetPixelWidth.argtypes = [ctypes.c_void_p]
    cg.CGDisplayModeGetPixelWidth.restype = ctypes.c_size_t
    cg.CGDisplayModeRelease.argtypes = [ctypes.c_void_p]
    ids = (ctypes.c_uint32 * 16)()
    n = ctypes.c_uint32(0)
    err = cg.CGGetActiveDisplayList(16, ids, ctypes.byref(n))
    if err != 0:
        raise OSError(f"CGGetActiveDisplayList error {err}")
    if n.value == 0:
        # a sleeping display is not "active" (e.g. the lid is closed or the screen is asleep);
        # the online list still knows its size
        cg.CGGetOnlineDisplayList.argtypes = cg.CGGetActiveDisplayList.argtypes
        cg.CGGetOnlineDisplayList.restype = ctypes.c_int32
        cg.CGGetOnlineDisplayList(16, ids, ctypes.byref(n))
    names = _ns_screen_names()
    main = cg.CGMainDisplayID()
    out = []
    for i in range(n.value):
        did = int(ids[i])
        s = cg.CGDisplayScreenSize(did)
        r = cg.CGDisplayBounds(did)
        scale = None
        mode = cg.CGDisplayCopyDisplayMode(did)
        if mode:
            pxw = cg.CGDisplayModeGetPixelWidth(mode)
            cg.CGDisplayModeRelease(mode)
            pts = cg.CGDisplayPixelsWide(did)
            scale = round(pxw / pts, 4) if pts else None
        out.append({"id": did, "name": names.get(did) or ("Built-in display" if cg.CGDisplayIsBuiltin(did) else f"Display {did}"),
                    "builtin": bool(cg.CGDisplayIsBuiltin(did)), "main": did == main,
                    "mm": [round(s.width, 2), round(s.height, 2)],
                    "px": [int(cg.CGDisplayPixelsWide(did)), int(cg.CGDisplayPixelsHigh(did))],
                    "origin": [r.origin.x, r.origin.y], "scale": scale})
    return {"source": "coregraphics", "displays": out}


def _ns_screen_names() -> dict:
    """CGDirectDisplayID -> NSScreen.localizedName via the Objective-C runtime; {} on any failure."""
    try:
        objc = ctypes.CDLL(ctypes.util.find_library("objc"))
        ctypes.CDLL(ctypes.util.find_library("AppKit") or "/System/Library/Frameworks/AppKit.framework/AppKit")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        send = objc.objc_msgSend

        def msg(obj, sel, *args, restype=ctypes.c_void_p, argtypes=()):
            send.restype = restype
            send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, *argtypes]
            return send(obj, objc.sel_registerName(sel), *args)

        screens = msg(objc.objc_getClass(b"NSScreen"), b"screens")
        if not screens:
            return {}
        count = msg(screens, b"count", restype=ctypes.c_ulong)
        key = msg(objc.objc_getClass(b"NSString"), b"stringWithUTF8String:", b"NSScreenNumber",
                  argtypes=(ctypes.c_char_p,))
        out = {}
        for i in range(count):
            scr = msg(screens, b"objectAtIndex:", i, argtypes=(ctypes.c_ulong,))
            desc = msg(scr, b"deviceDescription")
            num = msg(desc, b"objectForKey:", key, argtypes=(ctypes.c_void_p,))
            did = msg(num, b"unsignedIntValue", restype=ctypes.c_uint32)
            name = msg(scr, b"localizedName")
            if not name:
                continue
            utf8 = msg(name, b"UTF8String", restype=ctypes.c_char_p)
            if utf8:
                out[int(did)] = utf8.decode("utf-8", "replace")
        return out
    except Exception:   # noqa: BLE001 - a name is a nicety
        return {}


# ---------------------------------------------------------------- matching the browser's screen

def match(info: dict, screen: dict) -> dict:
    """Which display the browser is on.  `screen`: {width, height (CSS px), dpr, label?,
    internal?, left?, top?} as the page reports it.  Returns {index, display, reason} (index
    None when nothing plausible matches)."""
    ds = [d for d in info.get("displays") or []]
    if not ds:
        return {"index": None, "display": None, "reason": "the OS reported no displays"}
    w, h = float(screen.get("width") or 0), float(screen.get("height") or 0)
    label = (screen.get("label") or "").strip().lower()
    best, why = None, ""
    scores = []
    for i, d in enumerate(ds):
        pw, ph = d.get("px") or (0, 0)
        s = 0.0
        notes = []
        if label and d.get("name", "").strip().lower() == label:
            s += 100
            notes.append("name matches")
        if screen.get("internal") is not None and bool(screen["internal"]) == bool(d.get("builtin")):
            s += 20
            notes.append("built-in flag matches")
        if w and h and pw and ph:
            ar = abs((w / h) - (pw / ph)) / (pw / ph)
            s += max(0.0, 30 - ar * 600)
            if abs(w - pw) < 1.5 and abs(h - ph) < 1.5:
                s += 40
                notes.append("size matches at 100 % zoom")
            elif ar < 0.01:
                notes.append("aspect ratio matches (browser zoom?)")
        if screen.get("left") is not None and d.get("origin") is not None:
            if abs(float(screen["left"]) - d["origin"][0]) < 2 and abs(float(screen.get("top") or 0) - d["origin"][1]) < 2:
                s += 25
                notes.append("position matches")
        if d.get("main"):
            s += 1
        scores.append((s, -i, i, notes))
    scores.sort(reverse=True)
    s, _, i, notes = scores[0]
    best = ds[i]
    why = ", ".join(notes) or ("only display" if len(ds) == 1 else "best guess")
    return {"index": i, "display": best, "reason": why, "score": s}
