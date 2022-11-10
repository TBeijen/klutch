import http.server
import logging
import threading
import time
from datetime import datetime
from queue import Empty
from queue import SimpleQueue
from typing import List
from typing import Optional

from kubernetes import client  # type: ignore

from klutch import actions
from klutch.config import KlutchConfig
from klutch.status import HpaStatus
from klutch.status import sequence_status_from_cm
from klutch.status import SequenceStatus


class BaseThread(threading.Thread):

    tick_interval = 1

    def __init__(self, queue: SimpleQueue, is_active_event: threading.Event, config: KlutchConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.full_name = "{cls} ({thr})".format(cls=self.__class__.__name__, thr=self.name)
        self.should_stop = False
        self.queue = queue
        self.is_active_event = is_active_event
        self.config = config
        self.logger = logging.getLogger(self.full_name)
        self.logger.info(f"Started")

    def run(self):
        try:
            while True:
                if self.should_stop:
                    self.logger.info("Stopping")
                    return
                self.logger.debug("Running")
                time.sleep(self.tick_interval)
        finally:
            self.logger.info("Stopped")

    def stop(self):
        self.logger.info("Received stop")
        self.should_stop = True

    def _trigger(self):
        self.logger.info("Triggering")
        self.queue.put(self.full_name)

    def _is_active(self) -> bool:
        """Return True if a scaling sequence is active."""
        return self.is_active_event.is_set()


class ProcessScaler(BaseThread):

    """
    Main process.

    Responds to trigger, scales up. Scales down after certain duration,
    On startup will scan for status configmap which indicates klutch restart (e.g. re-scheduled)
    while in midst of scale-up/down cycle.
    """

    status_cm: Optional[client.models.v1_config_map.V1ConfigMap]

    sequence_status: Optional[SequenceStatus]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue_wait = 5
        self.scale_duration = self.config.common.duration
        self.reconcile_interval = self.config.common.reconcile_interval

    def run(self):
        self._start_up()
        try:
            while True:
                if self._is_active():
                    if self._is_status_duration_expired():
                        self._end_sequence()
                    else:
                        self._continue_sequence()
                    time.sleep(self.reconcile_interval)
                else:
                    try:
                        payload = self.queue.get(block=True, timeout=self.queue_wait)
                        self.logger.info(f"Received trigger {payload}")
                        self._start_sequence()
                    except Empty:
                        self.logger.debug("No trigger fired, starting next cycle.")

                if self.should_stop:
                    self.logger.info("Stopping")
                    return
        finally:
            self.logger.info("Stopped")

    def _start_up(self):
        """Startup: Find any scaling status ConfigMap that might exist and resume if found."""
        status_cm_list = actions.find_cm_status(self.config)
        if not status_cm_list:
            self.logger.info("Startup: No status for ongoing scaling sequence found.")
            return
        status_cm = status_cm_list.pop(0)

        # Store retrieved status
        self._set_active(sequence_status_from_cm(status_cm))
        self.logger.info("Startup: Found status for ongoing scaling sequence. Resuming.")

        # cleanup excess statuses (should not happen)
        if status_cm_list:
            self.logger.warning(
                "Startup: Found multiple statuses for ongoing scaling sequence. Deleting all but newest."
            )
            for s in status_cm_list:
                actions.delete_cm_status(s)

    def _start_sequence(self):
        """Start scaling sequence: Find HPAs, scale up and write status."""
        status_list = []
        hpas = actions.find_hpas(self.config)
        for hpa in hpas:
            try:
                hpa_status, patched_hpa = actions.scale_hpa(self.config, hpa, self.logger)
                status_list.append(hpa_status)
            except Exception as e:
                self.logger.exception()
        status_cm = actions.create_cm_status(self.config, status_list)
        self._set_active(sequence_status_from_cm(status_cm))

    def _continue_sequence(self):
        """While active: Clear any additional triggers from queue, reconcile HPAs."""
        self.logger.debug(f"Continuing scaling sequence.")
        for status in self.sequence_status.status_list:
            actions.reconcile_hpa(self.config, status, self.logger)
        self._clear_all_triggers()

    def _end_sequence(self):
        """End sequence: Revert HPAs, clear status."""
        self.logger.info(f"Ending scaling sequence.")
        for status in self.sequence_status.status_list:
            actions.revert_hpa(self.config, status, self.logger)
        self._clear_all_triggers()
        self._set_inactive()

    def _is_status_duration_expired(self) -> bool:
        """Return True if duration of scaling sequence has expired."""
        if not self.sequence_status:
            return False
        now = datetime.now().timestamp()
        return self.sequence_status.started_at_ts + self.config.common.duration < now

    def _clear_all_triggers(self):
        """Clear any triggers added to the queue."""
        while not self.queue.empty():
            ignored_payload = self.queue.get(block=False)
            self.logger.info(f"Ignoring trigger {ignored_payload} while scaling sequence is active.")

    def _set_active(self, sequence_status: SequenceStatus):
        """Set global active flag and store HpaStatus list."""
        self.is_active_event.set()
        self.sequence_status = sequence_status

    def _set_inactive(self):
        """Clear global active flag and clear HpaStatus list."""
        self.is_active_event.clear()
        actions.delete_cm_status(self.config, self.logger)
        self.sequence_status = None


class TriggerConfigMap(BaseThread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tick_interval = self.config.trigger_config_map.scan_interval

    def run(self):
        try:
            while True:
                if self.should_stop:
                    self.logger.info("Stopping")
                    return

                self.logger.debug("Looking for trigger ConfigMap objects.")
                trigger_cm_list = actions.find_cm_triggers(self.config)

                if trigger_cm_list:
                    trigger_cm = trigger_cm_list.pop(0)
                    # validate
                    if actions.validate_cm_trigger(self.config, trigger_cm):
                        self._trigger()
                    else:
                        self.logger.warning(
                            "Trigger ConfigMap (name={}, uid={}) is not valid (expired) and has been deleted.".format(
                                trigger_cm.metadata.name,
                                trigger_cm.metadata.uid,
                            )
                        )
                    # cleanup
                    actions.delete_cm_trigger(trigger_cm)
                    if trigger_cm_list:
                        self.logger.warning("More than one trigger found. Using most recent. Removing others.")
                        for t in trigger_cm_list:
                            actions.delete_cm_trigger(t)
                else:
                    self.logger.debug("No triggers found")

                time.sleep(self.tick_interval)
        finally:
            self.logger.info("Stopped")


class TriggerWebHook(BaseThread):
    def run(self):
        _queue = self.queue
        _logger = self.logger
        _trigger = self._trigger

        class Handler(http.server.BaseHTTPRequestHandler):
            queue = _queue
            logger = _logger
            trigger = _trigger

            error_message_format: str = "%(code)d: %(message)s"

            def do_POST(self):
                self.trigger()

                body = "OK"
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))

            def log_message(self, format, *args):
                self.logger.info(format % args)

        server_address = (self.config.trigger_web_hook.address, self.config.trigger_web_hook.port)
        httpd = http.server.ThreadingHTTPServer(server_address, Handler)

        def start_threaded(httpd):
            httpd.serve_forever()

        self.logger.info(f"Starting webserver at {server_address}")
        thread = threading.Thread(target=start_threaded, args=(httpd,))
        thread.start()

        try:
            while True:
                if self.should_stop:
                    self.logger.info("Stopping")
                    httpd.shutdown()
                    return
                self.logger.debug("Running")
                time.sleep(self.tick_interval)
        finally:
            self.logger.info("Stopped")
