import json
import numpy as np
import logging as log
import struct
import application.tracers as tracer
from application.parser import Parser
from application.raytracer.scene import Camera
from application.scheduling import Task
from application.connection import ServerTCP
import multiprocessing as mp
from time import time

def save_intersections(filename, ids, intersects):
    with open(filename, 'w') as file:
        for tid, inter in zip(ids, intersects):
            file.write(f'{tid} {inter}\n')

class DarkRendererEdge(ServerTCP):
    def __init__(self, config):
        self.config = config
        super().__init__(
            (config['edge']['ip'], 
            config['edge']['port']))

        self.triangles    = []
        self.triangle_ids = []
        self.rays         = []
        self.camera       = None

        self.task_queue = mp.Queue()
        self.result_queue = mp.Queue()
        self.report_queue = mp.Queue()

        processing = config['processing']
        self.cpu_active = processing['cpu']['active']
        self.fpga_active = processing['fpga']['active']
        self.cloud_active = processing['cloud']['active']
        
        self.tracers = []

        if self.cloud_active:
            cloud_addr = (
                processing['cloud']['ip'], 
                processing['cloud']['port'])

            self.tracers.append(
                tracer.TracerCloud(
                    cloud_addr,
                    config
                )
            )

        if self.cpu_active:
            cpu_mode = processing['cpu']['mode']
            use_multicore = (cpu_mode == 'multicore')
            self.cpu_tracer = tracer.TracerCPU(
                use_multicore=use_multicore)
            self.tracers.append(self.cpu_tracer)

        if self.fpga_active:
            fpga_mode = processing['fpga']['mode']
            use_multi_fpga = (fpga_mode == 'multi')
            self.fpga_tracer = tracer.TracerFPGA(
                config['edge']['bitstream'],
                use_multi_fpga=use_multi_fpga)
            self.tracers.append(self.fpga_tracer)
        
    def start(self):
        finished = False
        while not finished:
            log.info("Waiting for client connection")
            self.listen()
            
            compression = self.config['networking']['compression']
            log.info("Receiving scene file")
            ti = time()
            message = self.recv_msg(compression)
            if 'EXIT' in message: 
                if message == 'EXIT_ALL':
                    for tr in self.tracers:
                        if type(tr) == tracer.TracerCloud:
                            tr.shutdown()

                break

            elif 'CONFIG' in message:
                config_msg = message.split()[1:]
                params = {}
                for i, param in enumerate(config_msg):
                    if param == 'TSIZE':
                        self.config['processing']['task_size'] = int(config_msg[i + 1])
                message = self.recv_msg(compression)
            log.warning(f'Recv time: {time() - ti} seconds')

            log.info('Parsing scene data')
            ti = time()
            self._parse_scene_data(message)
            log.warning(f'Parse time: {time() - ti} seconds')

            log.info('Computing intersection')
            ti = time()
            result = self._compute()
            log.warning(f'Intersection time: {time() - ti} seconds')

            log.info('Preparing and sending results')
            ti = time()
            result = json.dumps(result)
            self.send_msg(result, compression)
            log.warning(f'Send time: in {time() - ti} seconds')

    def _compute(self):
        import numpy as np
        log.info('Starting edge computation')

        processes = []
        for counter, tracer in enumerate(self.tracers):
            tracer.set_scene(
                self.triangle_ids,
                self.triangles)

            processes.append(
                mp.Process(
                    target=tracer.start, 
                    args=(self.task_queue, 
                        self.result_queue,
                        self.report_queue)
                )
            )

        for p in processes: p.start()

        tracers_finished = 0
        results = []

        log.info(f'Number of tracers = {len(self.tracers)}')
        while tracers_finished < len(self.tracers):
            res = self.result_queue.get()
            if res is None:
                tracers_finished += 1
            else:
                results.append(res)

        for p in processes: p.join()

        triangles_hit = []
        intersections = []
        for res in sorted(results, key=lambda x : x.task_id):
            triangles_hit += res.triangles_hit
            intersections += res.intersections

        summ_message = f'Processing summary:\n'
        while not self.report_queue.empty():
            summ = self.report_queue.get()
            summ_message += f'\t- {str(summ)}\n'
        log.warning(summ_message)

        return {
            'intersections' : intersections,
            'triangles_hit' : triangles_hit,
        } 

    NUM_TRIANGLE_ATTRS = 9
    NUM_RAY_ATTRS = 6

    def _parse_scene_data(self, scene_data):
        data = scene_data.split()
        task_data = data[2:]
        self.num_tris = int(data[0])
        self.num_rays = int(data[1])
        tri_end = self.num_tris * (self.NUM_TRIANGLE_ATTRS+1)
        self.triangle_ids = list(map(int, task_data[: self.num_tris]))
        self.triangles    = list(map(float, task_data[self.num_tris : tri_end]))
        
        cam_data = task_data[tri_end : ]
        res = (int(cam_data[0]), int(cam_data[1]))
        float_data = list(map(float, cam_data[2:])) 
        self.camera = Camera(res, 
            np.array(float_data[:3]),
            np.array(float_data[3:6]),
            np.array(float_data[6:9]),
            float_data[9], float_data[10])
        self.rays = self.camera.get_rays(cpp_version=True)

        Task.next_id = 0
        tasks = self.divide_tasks(self.rays)
        for t in tasks:
            self.task_queue.put(t)
        for _ in self.tracers:
            self.task_queue.put(None)



    def divide_tasks(self, rays):
        num_rays = len(rays)//6
        max_task_size = self.config['processing']['task_size']
        log.info(f'Maximum task size: {max_task_size}')
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