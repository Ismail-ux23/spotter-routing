import os

bind = "0.0.0.0:" + os.environ.get("PORT", "8000")
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
threads = 4
timeout = 240
accesslog = "-"
errorlog = "-"
capture_output = True
