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


class SuperTask(Counter):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.sizes = []
        self.ray_data = []

    def add_task(self, task):
        self.ids.append(task.id)
        self.sizes.append(len(task))
        self.ray_data += task.ray_data

    def separate_results(self, result):
        if result.task_id != self.id:
            raise Exception("Id ERROR")
        res = []
        ray_ptr = 0
        for i, sz in zip(self.ids, self.sizes):
            res.append(
                TaskResult(
                    i,
                    result.triangles_hit[ray_ptr : ray_ptr + sz],
                    result.intersections[ray_ptr : ray_ptr + sz] 
                ))
            ray_ptr += sz
        return res





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

def divide_tasks(rays, max_task_size):
    import numpy as np
    num_rays = len(rays)//6
    number_of_tasks = int(np.ceil(num_rays/max_task_size))
    ray_tasks = []
    for i in range(1, number_of_tasks+1):
        task_start = (i - 1) * max_task_size * 6
        task_data = []
        if i < number_of_tasks:
            task_end = task_start + (max_task_size*6)
            task_data = rays[task_start : task_end]
        else:
            task_data = rays[task_start : ]
        ray_tasks.append(Task(task_data))
    return ray_tasks