import cProfile
import pstats
import io

def profile_function(func):
    """Decorator to profile specific functions and hunt down latency bottlenecks."""
    def wrapper(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        result = func(*args, **kwargs)
        pr.disable()
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        ps.print_stats(20) # Print top 20 time-consuming operations
        print(s.getvalue())
        return result
    return wrapper
