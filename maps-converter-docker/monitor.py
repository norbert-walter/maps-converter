import time
import psutil
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import request, g
from collections import deque
from datetime import datetime, timedelta
from flask import session
request_timestamps = deque(maxlen=1000)
session_times = {}


# Create logs folder
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "metrics.log")

logger = logging.getLogger("metrics")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5)
logger.addHandler(handler)

# Function for server monitoring
def init_monitoring(app, cache):
    @app.before_request
    def start_timer():
        g.start = time.time()

    # Build metrics
    @app.after_request
    def log_metrics(response):
        duration = time.time() - g.start
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        try:
            cache_size = cache.volume() / 1024 / 1024  # Size in MB
        except:
            cache_size = 0.0

        now = time.time()
        request_timestamps.append(now)

        rps = sum(1 for t in request_timestamps if now - t <= 10) / 10.0

        sid = session.get("sid")
        if not sid:
            sid = os.urandom(8).hex()
            session["sid"] = sid
        session_times[sid] = datetime.utcnow()

        active_sessions = [s for s, t in session_times.items() if datetime.utcnow() - t < timedelta(minutes=10)]

        logger.info(f"{time.time()},{duration:.3f},{cpu},{mem},{cache_size:.2f},{rps:.2f},{len(active_sessions)}")

        return response
