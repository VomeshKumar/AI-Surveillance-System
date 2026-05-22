import time
import logging

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """Prevents continuous connection attempts to offline cameras."""
    def __init__(self, failure_threshold=5, cooldown_period=30):
        self.failure_threshold = failure_threshold
        self.cooldown_period = cooldown_period
        
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED" # CLOSED (normal), OPEN (broken), HALF_OPEN (testing)
        
    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning("Circuit breaker OPENED. Halting connection attempts.")
            
    def record_success(self):
        self.failures = 0
        self.state = "CLOSED"
        
    def allow_request(self) -> bool:
        if self.state == "CLOSED":
            return True
            
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.cooldown_period:
                self.state = "HALF_OPEN"
                return True
            return False
            
        # HALF_OPEN
        return True
