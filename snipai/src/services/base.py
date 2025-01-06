from loguru import logger
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Thread
from PyQt6.QtCore import QObject, pyqtSignal


class BaseService(QObject):
    """Base class for all services"""

    error_occurred = pyqtSignal(str, str)  # Signal for error handling

    def __init__(self):
        super().__init__()
        self._queue = Queue()
        self._running = False
        self._worker_thread = None
        self.executor = ThreadPoolExecutor(max_workers=10)

    def start(self):
        """Start the service worker thread"""
        if self._running:
            return
        self._running = True
        self._worker_thread = Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()

    def stop(self):
        """Stop the service"""
        self._running = False
        self._queue.put(None)  # Sentinel to stop the thread
        if self._worker_thread:
            self._worker_thread.join()
        self.executor.shutdown()

    def _process_queue(self):
        """Process items in the queue"""
        while self._running:
            item = self._queue.get()
            if item is None:  # Stop sentinel
                break
            try:
                self._process_item(item)
            except Exception as e:
                logger.exception(e)
                self.error_occurred.emit(str(e), "")
            self._queue.task_done()

    def _process_item(self, item):
        """Override this method to process queue items"""
        raise NotImplementedError
