import http.server
import logging
import threading
import time


class TriggerConfigMap(threading.Thread):
    logger = None

    def __init__(self, queue, config, name_suffix=""):
        super().__init__()
        name = self.__class__.__name__ + name_suffix

        self.should_stop = False
        self.name = name
        self.queue = queue
        self.config = config
        self.logger = logging.getLogger(name)
        self.logger.info(f"Started {name}")

    def run(self):
        try:
            while True:
                if self.should_stop:
                    self.logger.info("stopping")
                    return
                self.logger.info("running")
                time.sleep(1)
        finally:
            self.logger.info("ended")

    def stop(self):
        self.logger.info("Received stop()")
        self.should_stop = True


class TriggerWebHook(threading.Thread):
    logger = None

    def __init__(self, queue, config, name_suffix=""):
        super().__init__()
        name = self.__class__.__name__ + name_suffix

        self.server_thread = None
        self.should_stop = False
        self.name = name
        self.queue = queue
        self.config = config
        self.logger = logging.getLogger(name)
        self.logger.info(f"Started {name}")

    def run(self):

        # handler = http.server.BaseHTTPRequestHandler()

        server_address = ("", 8123)
        httpd = http.server.ThreadingHTTPServer(server_address, http.server.BaseHTTPRequestHandler)

        def start_threaded(httpd):
            httpd.serve_forever()

        # while True:
        self.logger.info(f"starting webserver on port {server_address}")
        thread = threading.Thread(target=start_threaded, args=(httpd,))
        thread.start()
        # httpd.serve_forever()
        # httpd.handle_request()

        try:
            while True:
                if self.should_stop:
                    self.logger.info("stopping")
                    httpd.shutdown()
                    return
                self.logger.info("running")
                time.sleep(1)
        finally:
            self.logger.info("ended")

    def stop(self):
        self.logger.info("Received stop()")
        self.should_stop = True


# import CGIHTTPServer
# import BaseHTTPServer

# KEEP_RUNNING = True

# def keep_running():
#     return KEEP_RUNNING

# class Handler(CGIHTTPServer.CGIHTTPRequestHandler):
#     cgi_directories = ["/cgi-bin"]

# httpd = BaseHTTPServer.HTTPServer(("", 8000), Handler)

# while keep_running():
#     httpd.handle_request()
