import time
from collections import defaultdict

REQUESTS = defaultdict(list)

MAX_REQUESTS = 600
WINDOW_SECONDS = 60

def rate_limiter(client_id: str):
    now = time.time()
    window_start = now - WINDOW_SECONDS

    REQUESTS[client_id] = [
        t for t in REQUESTS[client_id] if t > window_start
    ]

    if len(REQUESTS[client_id]) >= MAX_REQUESTS:
        return False

    REQUESTS[client_id].append(now)
    return True
