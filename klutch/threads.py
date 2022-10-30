import http.server
import logging
import threading
import time
from queue import Empty
from queue import Queue

from klutch import actions


class BaseThread(threading.Thread):

    tick_interval = 1

    def __init__(self, queue: Queue, config, name_suffix="", *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.full_name = "{cls} ({thr})".format(cls=self.__class__.__name__, thr=self.name)
        self.should_stop = False
        self.queue = queue
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

    def trigger(self):
        self.logger.info("Triggering")
        self.queue.put(self.full_name)


class ProcessScaler(BaseThread):

    """
    Main process.

    Responds to trigger, scales up. Scales down after certain duration,
    On startup will scan for status configmap which indicates klutch restart (e.g. re-scheduled)
    while in midst of scale-up/down cycle.
    """

    status = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue_wait = 5
        self.is_active = False
        self.scale_duration = self.config.common.duration
        self.reconcile_interval = self.config.common.reconcile_interval

    def run(self):
        self._start_up()
        try:
            while True:
                if self.status:
                    if actions.is_status_duration_expired(self.status):
                        self._end_sequence()
                    else:
                        self._continue_sequence()
                    time.sleep(self.queue_wait)
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
        statuses = actions.find_status(self.config)

        if not statuses:
            self.logger.info("Startup: No status for ongoing scaling sequence found.")
            return

        self.status = statuses.pop(0)
        self.logger.info("Startup: Found status for ongoing scaling sequence. Resuming.")

        if statuses:
            self.logger.warning(
                "Startup: Found multiple statuses for ongoing scaling sequence. Deleting all but newest."
            )
            for s in statuses:
                actions.delete_status(s)

    def _start_sequence(self):
        pass

    def _continue_sequence(self):
        pass

    def _end_sequence(self):
        pass


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
                        self.trigger()
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
        _trigger = self.trigger

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
