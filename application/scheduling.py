class Counter():
    next_id = 0
    def __init__(self):
        self.id = type(self).next_id
        type(self).next_id += 1

    def reset_counter(self):
        type(self).next_id = 0

class Task(Counter):
    def __init__(self, ray_data):
        super().__init__()
        self.ray_data = ray_data

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
