import multiprocessing
from multiprocessing import Manager
import time


class MultiProcesser:
    def __init__(self, num_processes):
        self.num_processes = num_processes
        self.pool = multiprocessing.Pool(processes=num_processes)
        self.results = []

    def submit_task(self, func, *args, **kwargs):
        result = self.pool.apply_async(func, args=args, kwds=kwargs)
        self.results.append(result)

    def wait_for_completion(self, timeout=None):
        self.pool.close()
        self.pool.join()
        results = []
        for i, result in enumerate(self.results):
            try:
                if timeout:
                    results.append(result.get(timeout=timeout))
                else:
                    results.append(result.get())
            except Exception as e:
                print(f"Error getting result {i}: {e}")
                results.append(None) 
        return results

    def __del__(self):
        if self.pool:
            self.pool.terminate()


class DynamicMultiProcesser:
    """
    Dynamic process pool manager.

    Always keeps up to ``num_processes`` active tasks running.
    When one task finishes, a new task is automatically started.
    """
    def __init__(self, num_processes, verbose=False):
        self.num_processes = num_processes
        # Create a pool sized to num_processes; we will run at most num_processes tasks concurrently.
        self.pool = multiprocessing.Pool(processes=num_processes)
        self.pending_tasks = []  # Pending task queue
        self.active_results = []  # Active task AsyncResult objects
        self.completed_results = []  # Completed task results
        self.manager = Manager()
        self.global_lock = self.manager.Lock()  # Global lock protecting shared state
        self.verbose = verbose

    def submit_task(self, func, *args, **kwargs):
        """Submit a task to the pending queue."""
        with self.global_lock:
            self.pending_tasks.append((func, args, kwargs))
            if self.verbose:
                print(f"Task submitted. Pending: {len(self.pending_tasks)}, Active: {len(self.active_results)}")

    def _get_next_task(self):
        """Thread-safely fetch the next pending task."""
        with self.global_lock:
            if self.pending_tasks:
                task = self.pending_tasks.pop(0)
                if self.verbose:
                    print(f"Retrieved task. Pending: {len(self.pending_tasks)}, Active: {len(self.active_results)}")
                return task
            return None

    def _submit_next_task(self):
        """Submit the next pending task to the process pool."""
        task = self._get_next_task()
        if task:
            func, args, kwargs = task
            result = self.pool.apply_async(func, args=args, kwds=kwargs)
            with self.global_lock:
                self.active_results.append(result)
                if self.verbose:
                    print(f"Task submitted to pool. Active: {len(self.active_results)}")
            return True
        return False

    def _check_completed_tasks(self):
        """Check and process completed tasks."""
        completed_indices = []
        completed_count = 0

        with self.global_lock:
            # Copy active results to avoid mutating while iterating.
            active_copy = list(enumerate(self.active_results))

        for i, result in active_copy:
            if result.ready():
                try:
                    result_value = result.get(timeout=1.0)  # Add a timeout to avoid blocking
                    with self.global_lock:
                        self.completed_results.append(result_value)
                        completed_indices.append(i)
                        completed_count += 1
                    if self.verbose:
                        print(f"Task completed successfully. Total completed: {len(self.completed_results)}")
                except Exception as e:
                    if self.verbose:
                        print(f"Task failed with error: {e}")
                    with self.global_lock:
                        completed_indices.append(i)

        # Remove completed tasks (delete from the end to keep indices valid).
        with self.global_lock:
            for i in reversed(completed_indices):
                if i < len(self.active_results):
                    del self.active_results[i]

        return completed_count

    def _fill_active_slots(self):
        """Fill available active task slots."""
        submitted_count = 0
        with self.global_lock:
            active_count = len(self.active_results)
            pending_count = len(self.pending_tasks)

        while active_count + submitted_count < self.num_processes and pending_count - submitted_count > 0:
            if self._submit_next_task():
                submitted_count += 1
            else:
                break

        if self.verbose and submitted_count > 0:
            print(f"Filled {submitted_count} active slots")

        return submitted_count

    def process_all_tasks(self):
        """
        Process all tasks while dynamically maintaining the number of active tasks.

        Returns a list of completed results.
        """
        if self.verbose:
            print(f"Starting dynamic processing with {self.num_processes} processes")

        # Start initial tasks (up to pool capacity).
        initial_count = 0
        with self.global_lock:
            available_slots = min(self.num_processes, len(self.pending_tasks))

        for _ in range(available_slots):
            if self._submit_next_task():
                initial_count += 1

        if self.verbose:
            print(f"Initial {initial_count} tasks submitted")

        # Continuously monitor and refill active slots.
        while True:
            with self.global_lock:
                has_active = len(self.active_results) > 0
                has_pending = len(self.pending_tasks) > 0

            if not has_active and not has_pending:
                break

            # Check completed tasks.
            completed = self._check_completed_tasks()

            # Submit new tasks into active slots.
            submitted = self._fill_active_slots()

            # If there are active tasks but nothing changed, wait a bit longer.
            if has_active and submitted == 0 and completed == 0:
                if self.verbose:
                    print("Waiting for tasks to complete...")
                time.sleep(0.5)  # Wait a bit longer
            elif has_active:
                time.sleep(0.2)  # Slight delay while work is ongoing
            else:
                time.sleep(0.1)  # Poll faster when idle

        if self.verbose:
            print(f"All tasks completed. Total results: {len(self.completed_results)}")

        # Close the pool.
        self.pool.close()
        self.pool.join()

        return self.completed_results

    def __del__(self):
        if self.pool:
            self.pool.terminate()


def test_func(a, b):
    sum_result = a + b
    product_result = a * b
    return sum_result, product_result


def slow_task(task_id, duration):
    """Simulate a slow task (must be defined at module scope for pickling)."""
    import time
    print(f"Task {task_id} started, will run for {duration}s")
    time.sleep(duration)
    result = f"Task {task_id} completed after {duration}s"
    print(result)
    return result


def test_dynamic_processor():
    """Test the dynamic process manager."""
    print("Testing DynamicMultiProcesser...")

    processor = DynamicMultiProcesser(num_processes=3, verbose=True)

    tasks = [
        (slow_task, 1, 2),
        (slow_task, 2, 1),
        (slow_task, 3, 3),
        (slow_task, 4, 1),
        (slow_task, 5, 2),
        (slow_task, 6, 1),
    ]

    for task in tasks:
        processor.submit_task(*task)

    results = processor.process_all_tasks()

    print(f"\nAll tasks completed! Results: {len(results)}")
    for result in results:
        print(f"Result: {result}")

