#!/usr/bin/env python3
"""Privacy Architect — Scanner (Tk-native version).

One-click privacy scanner for Android. Runs entirely locally on the
user's machine. Zero network calls, zero persistence (nothing written
until the user clicks "Save"), read-only by design.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import queue
import threading
import json
from datetime import datetime

from core.theme import THEME
from ui import GradientBanner, Card, ThemedButton, LogText
from core.app_scan import get_device_info, get_installed_apps, build_permission_index
from core.tracker_scan import (
    load_tracker_database, pull_apk, scan_apk, cleanup_apk,
    get_all_cached_results, save_cached_result)
from core.report import build_report_html

# ------------------------------------------------------------------
#  Scan orchestration (worker thread)
# ------------------------------------------------------------------

def scan_stream(serial):
    """Generator of JSON events. Same contract as the HTTP version.

    Emits: {'event': 'phase'|'detail'|'done'|'error', ...}
    Progress runs 0→100% across four phases.
    """
    try:
        # Phase 1: device (0→5%)
        yield {'event': 'phase', 'label': 'Connessione al dispositivo',
               'progress': 2}
        device = get_device_info(serial)
        yield {'event': 'detail', 'text': (
            f"Dispositivo: {device['model']} "
            f"({device['brand']}, Android {device['android_version']})"),
               'progress': 5}

        # Phase 2: apps (5→10%)
        yield {'event': 'phase', 'label': 'Lettura app e permessi',
               'progress': 8}
        apps = get_installed_apps(serial, include_system=True)
        user_apps = [a for a in apps
                     if not a.is_system and a.is_active]
        yield {'event': 'detail', 'text': (
            f'{len(apps)} app totali ({len(user_apps)} utente)'),
               'progress': 10}

        # Phase 3: trackers (10→95%)
        yield {'event': 'phase', 'label': 'Analisi tracker',
               'progress': 10}
        db = load_tracker_database()
        if not db:
            yield {'event': 'detail', 'text': (
                'ATTENZIONE: database firme non trovato'),
                   'progress': 10}
        unscanned = []
        total = len(user_apps) or 1
        for i, app in enumerate(user_apps):
            pct = 10 + int(85 * (i + 1) / total)
            yield {'event': 'detail', 'text': (
                f'Analisi {i + 1}/{len(user_apps)}: {app.package_name}'),
                   'progress': pct}
            cached = get_all_cached_results().get(
                f'{app.package_name}_{app.version_code}')
            if cached and cached.get('trackers'):
                continue
            paths, _err = pull_apk(serial, app.package_name)
            if not paths:
                unscanned.append(app.package_name)
                continue
            try:
                hits = scan_apk(paths, db)
                save_cached_result(
                    app.package_name, app.version_code, hits, 0)
            finally:
                cleanup_apk(paths)

        # Phase 4: report (95→100%)
        yield {'event': 'phase', 'label': 'Generazione report',
               'progress': 97}
        html = build_report_html(device, apps, get_all_cached_results(),
                                 unscanned, len(db))
        n_tracked = len([k for k, v in
                         get_all_cached_results().items()
                         if v.get('trackers')])
        yield {'event': 'done', 'progress': 100,
               'html': html,
               'summary': {'app_tot': len(apps),
                           'app_utente': len(user_apps),
                           'app_con_tracker': n_tracked,
                           'non_scansionabili': len(unscanned)}}

    except FileNotFoundError:
        yield {'event': 'error',
               'message': ('ADB non trovato. Installa i '
                           'platform-tools di Android')}
    except Exception as exc:
        yield {'event': 'error',
               'message': f'Errore durante la scansione: {exc}'}

# ------------------------------------------------------------------
#  Main application
# ------------------------------------------------------------------

class ScannerApp:
    def __init__(self):
        self.serial = None
        self.stop_scan = threading.Event()
        self.queue = queue.Queue()
        self.worker = None
        self.html_cache = None

        self.root = tk.Tk()
        self.root.title('Privacy Architect — Scanner')
        self.root.geometry('540x740')
        self.root.geometry('580x720')
        self.root.resizable(True, True)
        self._build_ui()
        self.root.protocol('WM_DELETE_WINDOW', self._quit)
        self.root.after(100, self._poll_queue)

    def _build_ui(self):
        self.root.geometry('540x740')
        self.root.configure(bg=THEME['bg_light'])
        self.root.minsize(460, 560)

        # Blue progress bar (ttk style, like the site's --accent-blue)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            'PA.Horizontal.TProgressbar',
            troughcolor=THEME['bg_gradient_start'],
            background=THEME['accent_blue'],
            bordercolor=THEME['border_color'],
            lightcolor=THEME['accent_blue'],
            darkcolor=THEME['accent_blue'],
            thickness=10)

        # Header banner
        banner = GradientBanner(
            self.root,
            title='Privacy Architect',
            subtitle='Scansione privacy del tuo dispositivo')
        banner.pack(fill='x', padx=16, pady=(16, 8))

        # Intro text
        intro = tk.Label(
            self.root,
            text='Tutta l\'analisi avviene su questo computer: '
                 'nessun dato viene inviato online né salvato. '
                 'Collega il telefono via USB e autorizza il computer.',
            wraplength=400, justify='center',
            bg=THEME['bg_light'],
            fg=THEME['text_medium'])
        intro.pack(padx=16, pady=(0, 12))

        # Scan button
        self.scan_btn = ThemedButton(
            self.root, text='Avvia scansione',
            command=self._start_scan,
            pady=12, padx=36, font=('Helvetica', 12, 'bold'))
        self.scan_btn.pack(pady=8)

        # Progress bar (flexible width — no fixed length)
        self.progress = ttk.Progressbar(
            self.root, style='PA.Horizontal.TProgressbar',
            maximum=100)
        self.progress.pack(fill='x', padx=24, pady=(12, 2))
        self.pct_label = tk.Label(
            self.root, text='', font=('Helvetica', 9),
            bg=THEME['bg_light'],
            fg=THEME['text_light'])
        self.pct_label.pack()

        # Log area
        log_frame = Card(self.root)
        log_frame.pack(fill='both', expand=True,
                       padx=16, pady=(12, 0))

        self.log = LogText(log_frame, height=14)
        self.log.pack(fill='both', expand=True, padx=6, pady=6)

        # Summary card
        self.summary_card = Card(self.root)
        self.summary_card.pack_forget()

        self.summary_title = tk.Label(
            self.summary_card,
            text='Scansione completata',
            font=('Helvetica', 12, 'bold'),
            bg=THEME['bg_white'],
            fg=THEME['text_dark'])
        self.summary_title.pack(anchor='w', padx=16, pady=(12, 0))

        self.summary_body = tk.Label(
            self.summary_card,
            text='', wraplength=400, justify='left',
            bg=THEME['bg_white'],
            fg=THEME['text_medium'])
        self.summary_body.pack(anchor='w', padx=16, pady=(6, 0))

        self.save_btn = ThemedButton(
            self.summary_card, text='Salva report',
            command=self._save_report, pady=8, padx=24)
        self.save_btn.pack(anchor='w', padx=16, pady=(10, 14))

    def _start_scan(self):
        # Detect device once at scan start
        if not self.serial:
            try:
                from core.adb import ADB_PATH, TIMEOUTS
                import subprocess
                result = subprocess.run(
                    [ADB_PATH, 'devices'],
                    capture_output=True, text=True,
                    timeout=TIMEOUTS['devices_list'])
                serials = []
                for line in (result.stdout or '').strip().splitlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == 'device':
                        serials.append(parts[0])
                if not serials:
                    messagebox.showerror(
                        'Nessun dispositivo',
                        'Nessun telefono connesso. '
                        'Collega via USB e autorizza.')
                    return
                self.serial = serials[0]
            except Exception:
                messagebox.showerror(
                    'ADB non trovato',
                    'ADB non è raggiungibile. '
                    'Assicurati che platform-tools sia installato.')
                return

        # Disable button, clear log, start worker
        self.scan_btn.configure(state='disabled')
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')
        self.summary_card.pack_forget()
        self.progress['value'] = 0
        self.pct_label.configure(text='')

        self.worker = threading.Thread(
            target=self._run_scan, daemon=True)
        self.worker.start()

    def _run_scan(self):
        for event in scan_stream(self.serial):
            self.queue.put(event)
            if self.stop_scan.is_set():
                break

    def _poll_queue(self):
        try:
            while True:
                event = self.queue.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _handle_event(self, event):
        kind = event.get('event')
        progress = event.get('progress')

        if progress is not None:
            self.progress['value'] = progress
            self.pct_label.configure(
                text=f'{round(progress)}%')

        if kind == 'phase':
            self.log.append('— ' + event['label'], 'phase')
        elif kind == 'detail':
            self.log.append(event['text'], 'detail')
        elif kind == 'done':
            self.html_cache = event['html']
            summ = event['summary']
            self.log.append('Report generato', 'success')
            self._show_summary(summ)
        elif kind == 'error':
            self.log.append(event['message'], 'error')
            self.scan_btn.configure(state='normal')

    def _show_summary(self, summ):
        self.scan_btn.configure(state='normal')
        txt = (f'{summ["app_tot"]} app totali, '
               f'{summ["app_utente"]} app utente scansionate, '
               f'{summ["app_con_tracker"]} con tracker noti, '
               f'{summ["non_scansionabili"]} non scansionabili.')
        self.summary_body.configure(text=txt)
        self.summary_card.pack(fill='x', padx=24, pady=(16, 0))
        # Grow the window if the summary card doesn't fit
        self.root.update_idletasks()
        card_bottom = (self.summary_card.winfo_rooty()
                       + self.summary_card.winfo_reqheight())
        win_bottom = (self.root.winfo_rooty()
                      + self.root.winfo_height())
        if card_bottom > win_bottom:
            grow = card_bottom - win_bottom + 12
            self.root.geometry(
                f'{self.root.winfo_width()}x'
                f'{self.root.winfo_height() + grow}')

    def _save_report(self):
        if not self.html_cache:
            return
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'report_privacy_{stamp}.html'

        path = self._choose_save_path(filename)
        if not path:
            return
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.html_cache)
        messagebox.showinfo('Salvato', f'Report salvato:\n{path}')

    def _choose_save_path(self, suggested):
        """Native save dialog via zenity; Tk fallback otherwise.

        Tk's built-in Unix dialog is a Motif-era widget whose
        directory chooser needs press-and-hold. Zenity gives Linux
        users the modern desktop dialog instead.
        """
        try:
            import subprocess
            result = subprocess.run(
                ['zenity', '--file-selection', '--save',
                 '--confirm-overwrite', '--filename', suggested],
                capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                return result.stdout.strip() or None
            return None   # user cancelled
        except FileNotFoundError:
            # zenity missing — classic Tk dialog as fallback
            return filedialog.asksaveasfilename(
                defaultextension='.html',
                initialfile=suggested,
                filetypes=[('HTML file', '*.html')],
                title='Salva report')

    def _quit(self):
        self.stop_scan.set()
        self.root.destroy()

if __name__ == '__main__':
    ScannerApp().root.mainloop()
