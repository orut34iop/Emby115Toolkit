import threading

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QGroupBox, QProgressBar, QTextEdit, QVBoxLayout


class _TaskSignals(QObject):
    finished = pyqtSignal(str)


class BackgroundTaskMixin:
    """Shared UI behavior for tabs that run cancellable background work."""

    def _init_task_state(self):
        self._active_task = None
        self._active_workers = []
        self._task_buttons = []
        self.progress_bar = None
        self.btn_stop = None
        self._task_signals = _TaskSignals()
        self._task_signals.finished.connect(self._on_background_task_finished)

    def _create_progress_group(self):
        progress_group = QGroupBox("进度")
        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        progress_group.setLayout(progress_layout)
        return progress_group

    def _create_log_group(self):
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        return log_group

    def _register_task_buttons(self, *buttons):
        self._task_buttons.extend(button for button in buttons if button is not None)

    def _track_worker(self, worker):
        if worker is not None:
            self._active_workers.append(worker)
        return worker

    def is_task_running(self):
        return bool(self._active_task and self._active_task.is_alive())

    def _set_task_running(self, running):
        for button in self._task_buttons:
            button.setEnabled(not running)
        if self.btn_stop is not None:
            self.btn_stop.setEnabled(running)
        if self.progress_bar is not None:
            if running:
                self.progress_bar.setRange(0, 0)
            else:
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(0)

    def _start_background_task(self, task_name, task):
        if self.is_task_running():
            self.logger.warning("已有任务正在运行，请等待完成后再试")
            return None

        self._active_workers = []
        self._set_task_running(True)
        self.logger.info(f"{task_name}已在后台启动，界面可继续响应")

        def run_task():
            try:
                task()
            except Exception as exc:
                self.logger.exception(f"{task_name}执行异常: {exc}")
            finally:
                self._task_signals.finished.emit(task_name)

        self._active_task = threading.Thread(target=run_task, daemon=True)
        self._active_task.start()
        return self._active_task

    def stop_background_task(self):
        if not self.is_task_running():
            self.logger.warning("当前没有正在运行的任务")
            return

        stopped_any = False
        for worker in list(self._active_workers):
            if hasattr(worker, "request_stop"):
                worker.request_stop()
                stopped_any = True
            elif hasattr(worker, "stop_flag"):
                worker.stop_flag.set()
                stopped_any = True

        if self.btn_stop is not None:
            self.btn_stop.setEnabled(False)

        if stopped_any:
            self.logger.info("正在停止任务，请等待当前步骤结束...")
        else:
            self.logger.info("已请求停止任务，当前步骤可能需要完成后才会结束")

    def _on_background_task_finished(self, task_name):
        self._active_task = None
        self._active_workers = []
        self._set_task_running(False)
        self.logger.info(f"{task_name}后台任务结束")
