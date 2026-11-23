"""Local Go2 test console. Hardware actions reuse the bounded SDK launchers."""
import csv
from dataclasses import dataclass, field
from datetime import datetime
import fcntl
import ipaddress
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from a2_policy import POLICY_UPDATES

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'pruebas'
DIRECTIONS = {
    'Avance': ('forward', 'forward'), 'Retroceso': ('reverse', 'reverse'),
    'Lateral izquierda': ('lateral', 'left'), 'Giro': ('yaw', 'yaw'),
}
MODES = {
    'MuJoCo · política GRU': 'sim',
    'Go2 · comprobar telemetría': 'observe',
    'Go2 · GRU en sombra': 'shadow',
    'Go2 · pulso con Sport': 'sport',
    'Go2 · pulso GRU en banco': 'bench',
}
INFO = {
    'sim': 'Ejecuta el GRU por DDS local y guarda el movimiento simulado.',
    'observe': 'Comprueba rt/lowstate por Ethernet y registra sensores.',
    'shadow': 'Calcula y registra los objetivos del GRU. Solo lee del robot.',
    'sport': 'Pulso de 0,5 s con el controlador de fábrica. Requiere Go2 de pie y mando listo.',
    'bench': 'Pulso GRU de hasta 0,5 s con Sport desactivado. Go2 sostenido, patas libres y perfil verificado.',
}
BG, INK, MUTED, ACCENT = '#eef3f6', '#10283e', '#425a6a', '#0d675d'
SIM_COMMANDS = {'Avance': (.3, 0.), 'Retroceso': (-.2, 0.),
                'Lateral izquierda': (0., .2), 'Giro': (0., 0.)}
WALL_SECONDS = {'sim': 80, 'observe': 25, 'shadow': 25, 'sport': 20, 'bench': 20}


def wired_interfaces():
    return sorted(p.name for p in Path('/sys/class/net').iterdir()
                  if (p / 'device').exists() and not (p / 'wireless').exists()
                  and not (p / 'phy80211').exists() and (p / 'type').read_text().strip() == '1')


def network_state(iface):
    if iface not in wired_interfaces():
        return False, 'Selecciona la Ethernet conectada al Go2.'
    try:
        result = subprocess.run(['ip', '-j', '-4', 'addr', 'show', 'dev', iface], text=True,
                                capture_output=True, check=True, timeout=2)
        devices = json.loads(result.stdout)
        device = devices[0]
        addresses = [entry['local'] + '/' + str(entry['prefixlen'])
                     for entry in device.get('addr_info', []) if entry['scope'] == 'global']
        if 'LOWER_UP' not in device['flags']:
            return False, f'{iface} · sin enlace físico'
        if not addresses:
            return False, f'{iface} · configura la Ethernet (red estándar: 192.168.123.99/24)'
        standard = any(ipaddress.ip_interface(addr).ip in ipaddress.ip_network('192.168.123.0/24')
                       for addr in addresses)
        suffix = '' if standard else ' · comprueba la subred personalizada'
        return True, f'{iface} · {", ".join(addresses)}{suffix}'
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError):
        return False, f'{iface} · no se pudo leer el estado de red'


def job_commands(mode, direction, iface, profile, csv, view, policy_update=2000):
    command, sport = DIRECTIONS[direction]
    policy = ['--policy-update', str(policy_update)]
    if mode == 'sim':
        bridge = ['a2_sim.py', 'bridge', '--csv', str(csv)]
        if view:
            bridge += ['--view']
        return [bridge, ['a2_sim.py', 'policy', '--command', command, *policy]]
    common = ['--iface', iface, '--csv', str(csv)]
    if mode == 'sport':
        return [['robot.py', *common, '--seconds', '0.5', '--pulse', sport, '--arm']]
    args = ['a2_robot.py', mode, *common, '--seconds', '0.5' if mode == 'bench' else '10']
    if mode in ('bench', 'shadow'):
        args += ['--command', command, *policy]
    if mode == 'bench':
        args += ['--bench-profile', str(profile)]
    return [args]


@dataclass
class Job:
    mode: str
    direction: str
    csv: Path
    deadline: float
    processes: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    stopping: str = ''


class Panel:
    def __init__(self, root, python=sys.executable):
        self.python = python
        self.root = root
        self.job = None
        self.closing = False
        self.profile = None
        self.mode = tk.StringVar(value=next(iter(MODES)))
        self.direction = tk.StringVar(value=next(iter(DIRECTIONS)))
        self.policy_update = tk.StringVar(value='student')
        self.iface = tk.StringVar()
        self.view = tk.BooleanVar(value=True)
        self.description = tk.StringVar()
        self.net_text = tk.StringVar()
        self.status = tk.StringVar(value='Listo')
        self.profile_label = tk.StringVar(value='Perfil de banco pendiente')
        root.title('Unitree Go2 — Panel local')
        root.configure(bg=BG)
        root.geometry('860x660')
        root.minsize(690, 610)
        root.protocol('WM_DELETE_WINDOW', self.close)

        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', font=('DejaVu Sans', 10), background=BG, foreground=INK)
        style.configure('Card.TFrame', background='#ffffff')
        style.configure('Card.TLabel', background='#ffffff', foreground=INK)
        style.configure('Muted.TLabel', foreground=MUTED)
        style.configure('Title.TLabel', font=('DejaVu Sans', 24, 'bold'), foreground=INK)
        style.configure('TButton', padding=(12, 7))
        style.configure('Start.TButton', background=ACCENT, foreground='#ffffff')
        style.map('Start.TButton', background=[('disabled', '#79958d'), ('active', '#0b554e')])
        style.configure('Stop.TButton', foreground='#9b302c')
        style.configure('TCombobox', padding=5)

        frame = ttk.Frame(root, padding=(24, 18))
        frame.pack(fill='both', expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)
        header = ttk.Frame(frame)
        header.grid(row=0, column=0, sticky='ew', pady=(0, 14))
        ttk.Label(header, text='Unitree Go2', style='Title.TLabel').pack(anchor='w')
        ttk.Label(header, text='A2/P0  ·  GRU 128',
                  style='Muted.TLabel').pack(anchor='w')

        card = ttk.Frame(frame, style='Card.TFrame', padding=(16, 12))
        card.grid(row=1, column=0, sticky='ew')
        card.columnconfigure(1, weight=1)
        self.mode_box = self.combo(card, 0, 'Prueba', self.mode, tuple(MODES))
        self.direction_box = self.combo(card, 1, 'Movimiento', self.direction, tuple(DIRECTIONS))
        self.iface_box = self.combo(card, 2, 'Ethernet', self.iface, wired_interfaces())
        self.policy_box = self.combo(card, 3, 'Checkpoint GRU', self.policy_update, POLICY_UPDATES)
        self.net_btn = ttk.Button(card, text='Actualizar', command=self.refresh_net)
        self.net_btn.grid(row=2, column=2, padx=(12, 0))
        ttk.Label(card, textvariable=self.net_text, style='Card.TLabel', wraplength=560).grid(
            row=4, column=1, columnspan=2, sticky='w', pady=(2, 8))
        self.options = ttk.Frame(card, style='Card.TFrame')
        self.options.grid(row=5, column=1, columnspan=2, sticky='w')
        self.view_button = ttk.Checkbutton(self.options, text='Abrir visor MuJoCo', variable=self.view)
        self.profile_button = ttk.Button(self.options, text='Elegir perfil', command=self.choose_profile)
        self.profile_text = ttk.Label(self.options, textvariable=self.profile_label, style='Card.TLabel')
        ttk.Label(card, textvariable=self.description, style='Card.TLabel', wraplength=615).grid(
            row=6, column=0, columnspan=3, sticky='w', pady=(10, 0))

        actions = ttk.Frame(frame)
        actions.grid(row=2, column=0, sticky='ew', pady=12)
        self.start_button = ttk.Button(actions, text='Iniciar prueba', style='Start.TButton', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(actions, text='Detener', style='Stop.TButton', command=self.stop)
        self.stop_button.pack(side='left', padx=8)
        ttk.Button(actions, text='Abrir resultados', command=self.open_results).pack(side='right')
        ttk.Label(actions, textvariable=self.status, wraplength=365).pack(side='left', padx=4)

        logpane = ttk.Frame(frame)
        logpane.grid(row=3, column=0, sticky='nsew')
        self.log = tk.Text(logpane, bg='#183043', fg='#eef5f6', padx=14, pady=12, relief='flat',
                           font=('DejaVu Sans Mono', 10), height=7, wrap='word', state='disabled')
        scroll = ttk.Scrollbar(logpane, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        self.mode_box.bind('<<ComboboxSelected>>', lambda _: self.update_controls())
        self.iface_box.bind('<<ComboboxSelected>>', lambda _: self.refresh_net())
        self.refresh_net()
        self.update_controls()

    @staticmethod
    def combo(parent, row, label, variable, values):
        ttk.Label(parent, text=label, style='Card.TLabel').grid(row=row, column=0, sticky='w', padx=(0, 14))
        box = ttk.Combobox(parent, textvariable=variable, values=values, state='readonly')
        box.grid(row=row, column=1, sticky='ew', pady=3)
        return box

    def refresh_net(self):
        choices = wired_interfaces()
        self.iface_box.configure(values=choices)
        if self.iface.get() not in choices:
            self.iface.set(choices[0] if choices else '')
        _, description = network_state(self.iface.get())
        self.net_text.set(description)

    def choose_profile(self):
        result = filedialog.askopenfilename(parent=self.root, title='Perfil verificado para el Go2',
                                            filetypes=[('Perfil JSON', '*.json')])
        if result:
            self.profile = Path(result)
            self.profile_label.set(self.profile.name)

    def open_results(self):
        try:
            subprocess.Popen(['xdg-open', str(OUTPUT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            messagebox.showinfo('Resultados', str(OUTPUT), parent=self.root)

    def update_controls(self):
        mode = MODES[self.mode.get()]
        self.description.set(INFO[mode])
        for widget in (self.view_button, self.profile_button, self.profile_text):
            widget.pack_forget()
        if mode == 'sim':
            self.view_button.pack(side='left')
        if mode == 'bench':
            self.profile_button.pack(side='left')
            self.profile_text.pack(side='left', padx=8)
        busy = self.job is not None
        self.mode_box.configure(state='disabled' if busy else 'readonly')
        self.direction_box.configure(state='disabled' if busy or mode == 'observe' else 'readonly')
        self.iface_box.configure(state='disabled' if busy or mode == 'sim' else 'readonly')
        self.policy_box.configure(state='disabled' if busy or mode in ('observe', 'sport') else 'readonly')
        self.net_btn.configure(state='disabled' if busy else 'normal')
        self.start_button.configure(state='disabled' if busy else 'normal')
        self.stop_button.configure(state='normal' if busy and not self.job.stopping else 'disabled')
        for button in (self.view_button, self.profile_button):
            button.configure(state='disabled' if busy else 'normal')

    def start(self):
        if self.job is not None or self.closing:
            return
        mode = MODES[self.mode.get()]
        direction = self.direction.get()
        policy_update = self.policy_update.get()
        iface = self.iface.get()
        if mode != 'sim':
            linked, label = network_state(iface)
            self.net_text.set(label)
            if not linked:
                messagebox.showwarning('Ethernet', label, parent=self.root)
                return
        if mode == 'bench' and (self.profile is None or not self.profile.is_file()):
            messagebox.showwarning('Perfil de banco', 'Selecciona el perfil verificado de tu Go2.', parent=self.root)
            return
        if mode in ('sport', 'bench'):
            control = {'sport': 'Sport de fábrica', 'bench': f'GRU A2/P0 · {policy_update}'}[mode]
            if not messagebox.askyesno('Confirmar movimiento físico',
                                       f'{direction} · {control} · hasta 0,5 s\n\n{INFO[mode]}\n\n'
                                       'Confirma que el operador puede accionar el paro físico.',
                                       default='no', parent=self.root):
                return
        started = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        suffix = f'-u{policy_update}' if mode in ('sim', 'shadow', 'bench') else ''
        csv = OUTPUT / f'{started}-{mode}{suffix}.csv'
        job = Job(mode, direction, csv, time.monotonic() + WALL_SECONDS[mode])
        self.job = job
        self.status.set(f'En curso · {direction}' if mode != 'observe' else 'Leyendo telemetría')
        self.write_log(csv.name)
        self.update_controls()
        commands = job_commands(mode, direction, iface, self.profile, csv, self.view.get(), policy_update)
        for index, argv in enumerate(commands):
            log_file = csv.with_suffix(f'.{index+1}.log')
            try:
                with log_file.open('xb') as log:
                    child = subprocess.Popen([self.python, '-u', *argv], cwd=ROOT, stdout=log,
                                             stderr=subprocess.STDOUT, start_new_session=True)
            except OSError as exc:
                self.stop('Error al iniciar')
                job.notes.append(f'Error al iniciar {argv[0]}: {exc}')
                break
            job.processes.append((child, log_file))
        self.tick()

    def write_log(self, text):
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.insert('end', text)
        self.log.see('end')
        self.log.configure(state='disabled')

    def tick(self):
        job = self.job
        out = [job.csv.name, *job.notes]
        for process, log in job.processes:
            try:
                with log.open('rb') as stream:
                    stream.seek(max(0, os.fstat(stream.fileno()).st_size - 3200))
                    out.append(stream.read(3200).decode('utf-8', errors='replace').strip())
            except OSError:
                out.append(f'Registro no disponible: {log.name}')
        codes = [process.poll() for process, _ in job.processes]
        if all(code is not None for code in codes):
            self.status.set(job.stopping or ('Prueba completada' if all(code == 0 for code in codes)
                                             else 'Prueba con error · revisa el registro'))
            if job.mode == 'sim' and not job.stopping and all(code == 0 for code in codes):
                try:
                    with job.csv.open(newline='') as stream:
                        rows = list(csv.DictReader(stream))
                    vx, vy = SIM_COMMANDS[job.direction]
                    error = math.sqrt(sum((float(row['vx_m_s'])-vx)**2 + (float(row['vy_m_s'])-vy)**2
                                          for row in rows) / len(rows))
                    out.append(f"{rows[-1]['t_s']} s simulados · error de velocidad {error:.4f} m/s")
                except (OSError, ValueError, KeyError, ZeroDivisionError):
                    out.append('Resumen no disponible. Revisa el CSV.')
            self.write_log('\n\n'.join(filter(None, out)))
            self.job = None
            self.update_controls()
            if self.closing:
                self.root.destroy()
            return
        self.write_log('\n\n'.join(filter(None, out)))
        if not job.stopping:
            if any(code not in (None, 0) for code in codes):
                self.stop('Prueba con error · revisa el registro')
            elif time.monotonic() >= job.deadline:
                self.stop('Tiempo de prueba agotado')
        self.root.after(180, self.tick)

    def stop(self, reason='Detenida por el operador'):
        job = self.job
        if job is None or job.stopping:
            return
        job.stopping = reason
        self.status.set('Deteniendo · confirma con el mando' if job.mode in ('sport', 'bench') else 'Deteniendo…')
        self.update_controls()
        for process, _ in job.processes:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

    def close(self):
        if self.job is None:
            self.root.destroy()
        else:
            self.closing = True
            self.stop()


def main():
    OUTPUT.mkdir(exist_ok=True)
    root = tk.Tk()
    with (OUTPUT / '.panel.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            root.withdraw()
            messagebox.showwarning('Unitree Go2', 'Ya hay un panel abierto.', parent=root)
            root.destroy()
            return
        Panel(root)
        root.mainloop()


if __name__ == '__main__':
    main()
