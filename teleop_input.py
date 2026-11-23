"""Bounded motion requests shared by the simulator and read-only SSH shadow."""

import os
import select

STOP = "stop"
LEASE_SECONDS = .25
VELOCITIES = {
    STOP: (0., 0., 0.),
    "w": (.30, 0., 0.),
    "s": (-.20, 0., 0.),
    "a": (0., .20, 0.),
    "d": (0., -.20, 0.),
    "q": (0., 0., .30),
    "e": (0., 0., -.30),
}


class CommandLease:
    def __init__(self):
        self.clear()

    def clear(self):
        self.key = STOP
        self.expires = 0.

    def renew(self, request, now):
        if request in VELOCITIES and request != STOP:
            self.key = request
            self.expires = now + LEASE_SECONDS
        else:
            self.clear()

    def sample(self, now):
        if now >= self.expires:
            self.clear()
        return self.key


class StdinCommands:
    """Read short newline-delimited key names from a supervised input pipe."""

    def __init__(self, fd):
        self.fd = fd
        self.lease = CommandLease()
        self.pending = b""
        self.closed = False

    def sample(self, now):
        if not self.closed and select.select([self.fd], [], [], 0)[0]:
            chunk = os.read(self.fd, 256)
            if not chunk:
                self.closed = True
                self.lease.clear()
            else:
                *complete, self.pending = (self.pending + chunk).split(b"\n")
                if len(self.pending) > 16:
                    self.closed = True
                    self.lease.clear()
                elif complete:
                    self.lease.renew(complete[-1].decode("ascii", errors="replace"), now)
        return self.lease.sample(now)


class KeyboardWindow:
    """Track physical release and disarm on loss of focus."""

    def __init__(self, title):
        import tkinter as tk

        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry("550x215")
        self.keys = set()
        self.releases = {}
        self.running = True
        tk.Label(self.root, text="Mando Go2", font=("Sans", 18, "bold")).pack(pady=(18, 10))
        tk.Label(self.root, text="Mantén Espacio y una tecla. Suelta Espacio para parar.").pack()
        tk.Label(self.root, text="W / S · avance y retroceso     A / D · lateral     Q / E · giro").pack(pady=8)
        self.status = tk.StringVar(value="Parado")
        tk.Label(self.root, textvariable=self.status).pack()
        self.root.bind("<KeyPress>", self.press)
        self.root.bind("<KeyRelease>", self.release)
        self.root.bind("<FocusOut>", lambda _: self.disarm())
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def press(self, event):
        key = event.keysym.lower()
        if key in self.releases:
            self.root.after_cancel(self.releases.pop(key))
        if key == "escape":
            self.close()
        elif key in VELOCITIES or key == "space":
            self.keys.add(key)

    def release(self, event):
        key = event.keysym.lower()
        if key in self.keys and key not in self.releases:
            def released():
                self.releases.pop(key)
                self.keys.discard(key)

            # X11 auto-repeat can queue a release/press pair for one held key.
            self.releases[key] = self.root.after_idle(released)

    def disarm(self):
        self.keys.clear()

    def close(self):
        self.disarm()
        self.running = False

    def poll(self):
        self.root.update()
        directions = self.keys.intersection(VELOCITIES) - {STOP}
        key = next(iter(directions)) if self.running and "space" in self.keys and len(directions) == 1 else STOP
        self.status.set("Parado" if key == STOP else f"Orden activa · {key.upper()}")
        return key

    def destroy(self):
        self.root.destroy()
