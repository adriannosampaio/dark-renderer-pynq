class Counter():
    next_id = 0
    def __init__(self):
        self.id = type(self).next_id
        type(self).next_id += 1

    def reset_counter(self):
        type(self).next_id = 0

class Task(Counter):
    def __init__(self, ray_data, task_id=None):
        self.ray_data = ray_data
        if task_id is not None:
            self.id = task_id
        else:
            super().__init__()

    def __len__(self):
        return len(self.ray_data)//6

class TaskResult():
    """docstring for Result"""
    def __init__(self, task_id, triangles_hit, intersections):
        super().__init__()
        self.task_id = task_id
        self.triangles_hit = triangles_hit
        self.intersections = intersections
        self.ray_number = len(triangles_hit)


class TracerSummary():
    def __init__(self, tracer):
        self.tasks_processed = 0
        self.tracer_type = type(tracer).__name__

    def increment(self):
        self.tasks_processed += 1

    def __str__(self):
        ret = f'{self.tracer_type} processed '
        ret += f'{self.tasks_processed} tasks'
        return ret