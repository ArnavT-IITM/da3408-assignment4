from contextlib import contextmanager
from time import perf_counter

import psutil
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, Summary, start_http_server


class Metrics:
    def __init__(self):
        self.registry = CollectorRegistry()
        self.requests = Counter("caption_requests", "Generate button clicks", ["mode"], registry=self.registry)
        self.images = Counter("caption_images", "Image attempts by outcome and session", ["mode", "session", "outcome"], registry=self.registry)
        self.failures = Counter("caption_request_failures", "Requests that could not complete", ["mode"], registry=self.registry)
        self.active = Gauge("caption_active_requests", "Requests in progress, including model loading and waiting", ["mode"], registry=self.registry)
        self.latency = Histogram("caption_image_seconds", "Image decode and caption time, including inference lock wait", ["mode", "outcome"], buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60), registry=self.registry)
        self.duration = Summary("caption_request_seconds", "Total request time including model loading", ["mode"], registry=self.registry)
        self.batch_size = Histogram("caption_batch_images", "Supported image entries per accepted ZIP", buckets=(1, 5, 10, 20, 50, 100), registry=self.registry)
        self.memory = Gauge("caption_process_memory_bytes", "App process resident memory, not model-only memory", registry=self.registry)
        self.memory.set_function(lambda: psutil.Process().memory_info().rss)
        for mode in ("single", "bulk"):
            self.requests.labels(mode)
            self.failures.labels(mode)
            self.active.labels(mode)
            self.duration.labels(mode)
            for outcome in ("success", "failure"):
                self.latency.labels(mode, outcome)

    def start(self):
        return start_http_server(18000, registry=self.registry)

    @contextmanager
    def request(self, mode):
        self.requests.labels(mode).inc()
        with self.active.labels(mode).track_inprogress(), self.duration.labels(mode).time():
            try:
                yield
            except Exception:
                self.failures.labels(mode).inc()
                raise

    @contextmanager
    def image(self, mode, session):
        start = perf_counter()
        outcome = "success"
        try:
            yield
        except Exception:
            outcome = "failure"
            raise
        finally:
            self.images.labels(mode, session, outcome).inc()
            self.latency.labels(mode, outcome).observe(perf_counter() - start)
