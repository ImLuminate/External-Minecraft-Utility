import subprocess
import keyboard
from pymem import Pymem, exception
import ctypes
import re
import time
import threading

print("Launching Minecraft...")
subprocess.run(["explorer.exe", "minecraft:"])

PAGE_GUARD = 0x100
MEM_COMMIT = 0x1000

READABLE_PROTS = {
    0x02, 0x04, 0x20, 0x40, 0x08, 0x80
}

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_ulong),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_ulong),
        ("Protect", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
    ]

_pm = None
_cached_addr = None
toggle_state = False
stop_event = threading.Event()

def attach_process(proc_name="Minecraft.Windows.exe", retry=3, wait=1.0):
    global _pm
    if _pm is not None:
        try:
            _ = _pm.read_bytes(0x1000, 1)
            return _pm
        except Exception:
            try: _pm.close_process()
            except Exception: pass
            _pm = None

    for _ in range(retry):
        try:
            _pm = Pymem(proc_name)
            return _pm
        except exception.ProcessNotFound:
            time.sleep(wait)
        except Exception:
            time.sleep(wait)
    return None

def scan_memory(pm, pattern: bytes):
    k32 = ctypes.windll.kernel32
    mbi = MEMORY_BASIC_INFORMATION()
    address = 0
    tail = b""
    patlen = len(pattern)

    while k32.VirtualQueryEx(pm.process_handle,
                             ctypes.c_void_p(address),
                             ctypes.byref(mbi),
                             ctypes.sizeof(mbi)):
        try:
            if (mbi.State == MEM_COMMIT) and (mbi.Protect in READABLE_PROTS) and not (mbi.Protect & PAGE_GUARD):
                base = int(mbi.BaseAddress)
                size = int(mbi.RegionSize)
                chunk = pm.read_bytes(base, size)
                search_buf = tail + chunk
                m = re.search(re.escape(pattern), search_buf)
                if m:
                    offset = m.start()
                    if offset < len(tail):
                        return base - len(tail) + offset
                    else:
                        return base + (offset - len(tail))
                if patlen > 1:
                    tail = search_buf[-(patlen - 1):]
        except Exception:
            pass
        address += int(mbi.RegionSize)
    return None

def run_toggle():
    global _cached_addr, toggle_state

    pm = attach_process()
    if pm is None:
        print("[toggle] Can't attach to Minecraft (run as Admin, make sure it's open).")
        return

    if not _cached_addr:
        sig = b"\x00\x00\x80\x3F\x00\x00\x00\x3F\x6F\x12\x83\x3A\x00"
        print("[toggle] Scanning for signature...")
        addr = scan_memory(pm, sig)
        if addr is None:
            print("[toggle] Pattern not found.")
            return
        _cached_addr = addr
        print(f"[toggle] Found at {hex(addr)}")

    toggle_state = not toggle_state
    value = 9.0 if toggle_state else 1.0
    try:
        pm.write_float(_cached_addr, value)
        print(f"[toggle] Wrote {value} to {hex(_cached_addr)}")
    except Exception as e:
        print(f"[toggle] Failed to write: {e}")

def stop_script():
    print("[exit] Pause/Break pressed — exiting.")
    stop_event.set()

keyboard.add_hotkey("f9", run_toggle)
keyboard.add_hotkey("pause", stop_script)

print("Press F9 to toggle between 1.0 and 9.0.")
print("Press Pause/Break to quit.")
stop_event.wait()

try:
    if _pm: _pm.close_process()
except Exception:
    pass

print("Exited cleanly.")
