"""Windows remote media tabs share the same cancellable worker lifecycle."""

import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from media_server.client import MediaServerClient
from utils.config import Config
from utils.logger import setup_logger
from utils.media_profiles import connection, get_media_profiles
from windows_gui.base_tab import BaseTab
from windows_gui.media_profiles import ProfilePicker


class MediaOperationTab(BaseTab):
    section = ''
    operation = ''
    method = ''

    def __init__(self, frame, log_dir):
        super().__init__(frame, log_dir)
        self.config = Config()
        self.profiles = get_media_profiles(self.config)
        self._profile_token = None
        self._cancel_event = None
        self.profile_picker = ProfilePicker(frame, self.profiles)
        self.profile_picker.pack(fill='x', padx=5, pady=5)
        self.scan_buttons = []
        if self.section != 'version_merge':
            modes = ttk.LabelFrame(frame, text='扫描模式', padding=8)
            modes.pack(fill='x', padx=5, pady=5)
            self.scan_mode_var = tk.StringVar(frame, value='incremental')
            for label, mode in [('快速增量（推荐）', 'incremental'), ('完整扫描修复', 'full')]:
                button = ttk.Radiobutton(
                    modes, text=label, variable=self.scan_mode_var, value=mode, command=self.save_config
                )
                button.pack(side='left', padx=5)
                self.scan_buttons.append(button)
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', padx=5, pady=5)
        self.start_button = ttk.Button(buttons, text='开始' + self.operation, command=self.start_operation)
        self.start_button.pack(side='left', padx=5)
        self.create_stop_button(buttons)
        self.register_task_buttons(self.start_button)
        self.progress_frame, self.progress_bar = self.create_progress_frame(frame)
        self.progress_frame.pack(fill='x', padx=5, pady=5)
        self.log_frame, self.log_text = self.create_log_frame(frame)
        self.log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        self.logger = setup_logger(self.section, self.log_text, os.path.join(log_dir, self.section + '.log'))
        unsubscribe = self.profiles.subscribe(self.load_config)
        frame.bind('<Destroy>', lambda e: unsubscribe() if e.widget is frame else None, add='+')
        self.load_config()

    def load_config(self):
        self.start_button.configure(state='normal' if self.profiles.active and not self.profiles.busy else 'disabled')
        if self.scan_buttons:
            self.scan_mode_var.set(self.profiles.settings(self.section).get('scan_mode', 'incremental'))
            for button in self.scan_buttons:
                button.configure(state='disabled' if self.profiles.busy or not self.profiles.active else 'normal')

    def save_config(self):
        try:
            self.profiles.set_scan_mode(self.section, self.scan_mode_var.get())
        except (ValueError, OSError) as exc:
            messagebox.showerror('保存失败', str(exc), parent=self.frame)
            self.load_config()

    def start_operation(self):
        if self._task_thread is not None:
            return
        try:
            token, snapshot = self.profiles.begin_task(self.section)
        except (ValueError, OSError) as exc:
            messagebox.showwarning('无法开始', str(exc), parent=self.frame)
            return
        self._profile_token = token
        profile = snapshot['profile']
        settings = profile.get('settings', {}).get(self.section, {})
        self.logger.info(f"{self.operation} → {profile['name']} ({profile['server_type']}, {profile['server_url']})")

        cancel_event = self._cancel_event = threading.Event()

        def task():
            if cancel_event.is_set():
                return
            client = self.track_worker(
                MediaServerClient(**connection(profile), logger=self.logger, cancel_event=cancel_event)
            )
            kwargs = {}
            if self.section != 'version_merge':
                kwargs = dict(
                    full_scan=settings.get('scan_mode') == 'full',
                    sync_state=settings.get('sync_state', {}),
                    state_callback=lambda state: self.profiles.save_task_state(token, state),
                )
            worker = getattr(client, self.method)(self.logger.info, **kwargs)
            if worker:
                worker.join()

        try:
            return self.start_background_task(self.operation, task)
        except Exception:
            self._task_thread = None
            self.set_task_running(False)
            self.profiles.end_task(token)
            self._profile_token = None
            self.logger.exception('无法启动媒体任务')
            return None

    def finish_background_task(self, task_name):
        super().finish_background_task(task_name)
        token, self._profile_token = self._profile_token, None
        if token:
            self.profiles.end_task(token)

    def stop_background_task(self):
        if self._cancel_event is not None:
            self._cancel_event.set()
        super().stop_background_task()
