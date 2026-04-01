import logging
import queue
import threading
import time
from src.llm.sentence import sentence
from src import utils

class sentence_queue:
    POLL_INTERVAL: float = 0.1  # seconds between poll attempts
    GET_TIMEOUT: float = 30.0   # total timeout for get_next_sentence
    __logging_level = 42
    __should_log = False

    def __init__(self) -> None:
        self.__queue: queue.Queue[sentence] = queue.Queue()
        self.__is_more_to_come: bool = False
        self.__cancel_event: threading.Event = threading.Event()

    @property
    def is_more_to_come(self) -> bool:
        return self.__is_more_to_come

    @is_more_to_come.setter
    def is_more_to_come(self, value: bool):
        self.__is_more_to_come = value
        if value:
            self.__cancel_event.clear()

    @utils.time_it
    def get_next_sentence(self) -> sentence | None:
        """Retrieves the next sentence from the queue, polling with short waits.
        Returns None if cancelled, timed out, or no more sentences are expected.
        No locks are held during the wait — clear() and cancel_get() wake this instantly.
        """
        deadline = time.time() + self.GET_TIMEOUT
        while True:
            if self.__cancel_event.is_set():
                self.log("get_next_sentence cancelled")
                return None
            try:
                retrieved_sentence = self.__queue.get_nowait()
                self.log(f"Retrieved '{retrieved_sentence.text}'")
                return retrieved_sentence
            except queue.Empty:
                pass
            if not self.__is_more_to_come:
                self.log("Nothing more to come, returning None")
                return None
            if time.time() >= deadline:
                logging.warning(f"sentence_queue.get_next_sentence() timed out after {self.GET_TIMEOUT}s waiting for a sentence. Generation may be hung.")
                return None
            self.__cancel_event.wait(timeout=self.POLL_INTERVAL)

    @utils.time_it
    def put(self, new_sentence: sentence):
        self.log(f"Putting '{new_sentence.text}'")
        self.__queue.put(new_sentence)

    @utils.time_it
    def put_at_front(self, new_sentence: sentence):
        """Prepends a sentence to the front of the queue.
        Only called after generation is stopped, so no concurrent put() calls.
        """
        items: list[sentence] = []
        try:
            while True:
                items.append(self.__queue.get_nowait())
        except queue.Empty:
            pass
        self.__queue.put_nowait(new_sentence)
        for s in items:
            self.__queue.put_nowait(s)

    @utils.time_it
    def clear(self):
        """Clears the queue and wakes any blocked consumer instantly."""
        self.__cancel_event.set()
        try:
            while True:
                self.__queue.get_nowait()
        except queue.Empty:
            pass
        self.log("Queue cleared")

    def cancel_get(self):
        """Wake any consumer blocked in get_next_sentence without draining the queue."""
        self.__cancel_event.set()

    @utils.time_it
    def log(self, text: str):
        if(self.__should_log):
            logging.log(self.__logging_level, text)
