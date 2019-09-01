import json
import numpy as np
import logging as log
import struct
import application.tracers as tracer
from application.parser import Parser
from application.raytracer.scene import Camera
from application.scheduling import Task, TaskResult
from application.connection import ServerTCP
import multiprocessing as mp
from time import time, sleep
from sortedcontainers import SortedDict
from functools import reduce


class DarkRendererCloud(ServerTCP):
    def __init__(self, config):
        self.config = config
        super().__init__((
            config['cloud']['ip'], 
            config['cloud']['port']))

        self.num_tris = 0
        self.triangles = []
        self.triangle_ids = []

        self.task_queue = mp.Queue()
        self.result_queue = mp.Queue()

        processing = config['cloud']['processing']
        self.compression = self.config['networking']['compression']
        self.tracers = []
        cpu_mode = processing['cpu']['mode']
        use_multicore = (cpu_mode == 'multicore')
        self.tracers.append(
            tracer.TracerCPU(use_multicore))
    
    def task_receiver(self, task_queue):
        # Receive a task in the shape
        # <id> <ray 1> ... <ray n> where 
        # <ray i> = ox oy oz dx dy dz for every i
        
        msg = self.recv_msg(self.compression)
        while msg != 'END':
            msg = msg.split()
            task_id = int(msg[0])
            print(f'Stored task {task_id}')
            ray_data = list(map(float, msg[1:]))
            task_queue.put(Task(ray_data, task_id))
            msg = self.recv_msg(self.compression)

        # Adding close orders
        for _ in self.tracers:
            task_queue.put(None)

    def task_returner(self, result_queue):
        # return task results in the shape:
        # <id> <nrays> <ids> <intersects>
        tracers_finished = 0
        log.info(f'num tracers = {len(self.tracers)}')
        while tracers_finished < len(self.tracers):
            res = result_queue.get()
            if res is None:
                tracers_finished += 1
            else:
                print(f'Returning task {res.task_id}')
                task_result = f'{res.task_id} {len(res.triangles_hit)} ' 
                task_result += f"{' '.join(map(str, res.triangles_hit))}\n"
                task_result += f"{' '.join(map(str, res.intersections))}"
                self.send_msg(task_result, self.compression)
            


    def start(self):
        while True:
            log.info("Waiting for edge connection")
            self.listen()
            log.info("Receiving and Parsing scene file")
            ti = time()
            message = self.recv_msg(self.compression)
            if message == 'EXIT': break
            scene_data = message.split()
            self.num_tris = int(scene_data[0])
            self.triangle_ids = list(
                map(int, scene_data[1 : self.num_tris + 1]))
            self.triangles = list(
                map(float, scene_data[self.num_tris + 1 : ]))
            log.warning(f'Recv scene time: {time() - ti} seconds')

            log.info('Start receiving tasks')
            ti = time()
            self.start_processing()
            log.warning(f'Intersection time: {time() - ti} seconds')



    def start_processing(self):
        log.info('Starting cloud computation')

        processes = [
            mp.Process(
                target=self.task_receiver,
                args=(self.task_queue,))]

        for tracer in self.tracers:
            tracer.set_scene(
                self.triangle_ids,
                self.triangles)

            processes.append(
                mp.Process(
                    target=tracer.start, 
                    args=(self.task_queue, self.result_queue)
                )
            )

        for p in processes: p.start()

        self.task_returner(self.result_queue)

        for p in processes: p.join()



