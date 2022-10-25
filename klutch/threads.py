import http.server
import logging
import threading
import time

from klutch import actions


class BaseThread(threading.Thread):

    tick_interval = 1

    def __init__(self, queue, config, name_suffix="", *args, **kwargs):
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
                trigger_cm_list = actions.find_triggers(self.config)

                if trigger_cm_list:
                    trigger_cm = trigger_cm_list.pop(0)
                    # validate
                    if actions.validate_trigger(self.config, trigger_cm):
                        self.trigger()
                    else:
                        self.logger.warning(
                            "Trigger ConfigMap (name={}, uid={}) is not valid (expired) and has been deleted.".format(
                                trigger_cm.metadata.name,
                                trigger_cm.metadata.uid,
                            )
                        )
                    # cleanup
                    actions.delete_trigger(trigger_cm)
                    if trigger_cm_list:
                        self.logger.warning("More than one trigger found. Using most recent. Removing others.")
                        for t in trigger_cm_list:
                            actions.delete_trigger(t)
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
