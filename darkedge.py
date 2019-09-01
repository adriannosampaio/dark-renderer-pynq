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

        self.task_queues = []

        processing = config['processing']
        self.cpu_active = processing['cpu']['active']
        self.fpga_active = processing['fpga']['active']
        self.cloud_active = processing['cloud']['active']
        
        self.tracers = []
        self.tracer_fractions = []

        self.multiqueue = processing['multiqueue']


        if self.cloud_active:
            cloud_addr = (
                processing['cloud']['ip'], 
                processing['cloud']['port'])
            if self.multiqueue:
                self.tracer_fractions.append(
                    self.config['processing']['cloud']['factor'])

            self.tracers.append(
                tracer.TracerCloud(
                    cloud_addr,
                    config
                )
            )

        if self.cpu_active:
            cpu_mode = processing['cpu']['mode']
            use_multicore = (cpu_mode == 'multicore')

            if self.multiqueue:
                self.tracer_fractions.append(
                    self.config['processing']['cpu']['factor'])

            self.cpu_tracer = tracer.TracerCPU(
                use_multicore=use_multicore)

            self.tracers.append(self.cpu_tracer)

        if self.fpga_active:
            fpga_mode = processing['fpga']['mode']
            use_multi_fpga = (fpga_mode == 'multi')

            if self.multiqueue:
                self.tracer_fractions.append(
                    self.config['processing']['fpga']['factor'])

            self.fpga_tracer = tracer.TracerFPGA(
                config['edge']['bitstream'],
                use_multi_fpga=use_multi_fpga)
            
            self.tracers.append(self.fpga_tracer)

        if self.multiqueue:
            if not np.isclose(np.sum(self.tracer_fractions), 1.0):
                log.warning("The processing percentage does not amount to 100%")

        
    def start(self):
        while True:
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
                        value = int(config_msg[i + 1])
                        self.config['processing']['task_size'] = value
                    elif param == 'TCHUNKSIZE':
                        value = int(config_msg[i + 1])
                        self.config['processing']['cloud']['task_chunk_size'] = value
                    elif param == 'MULTIQUEUE':
                        value = bool(int(config_msg[i + 1]))
                        print(value)
                        self.config['processing']['multiqueue'] = value
                        self.multiqueue = value

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

            # for q in self.task_queues:
            #     while not q.empty():
            #         q.get() 

    def _compute(self):
        import numpy as np
        log.info('Starting edge computation')

        processes = []
        for tracer_id, tracer in enumerate(self.tracers):
            tracer.set_scene(
                self.triangle_ids,
                self.triangles)

            processes.append(
                mp.Process(
                    target=tracer.start, 
                    args=(
                        self.task_queues[tracer_id if self.multiqueue else 0], 
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

        summ_message = f'Processing report: '
        while not self.report_queue.empty():
            summ = self.report_queue.get()
            summ_message += f'{str(summ)} | '
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
        if cam_data[0] == 'CAM':
            print(*cam_data)
            cam_data = cam_data[1:]
            res = (int(cam_data[0]), int(cam_data[1]))
            float_data = list(map(float, cam_data[2:])) 
            self.camera = Camera(res, 
                np.array(float_data[:3]),
                np.array(float_data[3:6]),
                np.array(float_data[6:9]),
                float_data[9], float_data[10])
            self.rays = self.camera.get_rays(cpp_version=True)
        else:
            self.rays = list(map(float, cam_data[1:]))

        Task.next_id = 0
        tasks = self.divide_tasks(self.rays)

        task_pointer = 0
        number_of_tasks = len(tasks)

        self.task_queues.clear()
        if self.multiqueue:
            for _ in self.tracers:
                self.task_queues.append(mp.Queue())
            for tid, t in enumerate(tasks):
                queue_id = tid % len(self.tracers)
                self.task_queues[queue_id].put(t)
        else:
            self.task_queues.append(mp.Queue())
            for t in tasks:
                self.task_queues[0].put(t)
        
        for q in self.task_queues:
            for _ in self.tracers:
                q.put(None)

        setup_report = 'Setup report:'
        setup_report += f'Generated {len(tasks)} tasks | '
        setup_report += f'Using {len(self.task_queues)} queue(s)'
        log.info(setup_report)



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