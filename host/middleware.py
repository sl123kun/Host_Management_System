import logging
import time

logger = logging.getLogger("host.request_time")


class RequestDurationMiddleware:
    """
    记录每次HTTP请求的耗时
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response["X-Request-Duration-Ms"] = f"{elapsed_ms:.2f}"
        logger.info("%s %s status=%s duration_ms=%.2f", request.method,
                    request.path, response.status_code, elapsed_ms)
        return response
