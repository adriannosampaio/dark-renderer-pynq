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
        tracer_id = 0

        if self.cloud_active:
            cloud_addr = (
                processing['cloud']['ip'], 
                processing['cloud']['port'])

            if self.multiqueue:
                self.tracer_fractions.append(
                    self.config['processing']['cloud']['factor'])

            self.tracers.append(
                tracer.TracerCloud(
                    tracer_id,
                    cloud_addr,
                    config
                )
            )
            tracer_id += 1

        if self.cpu_active:
            cpu_mode = processing['cpu']['mode']
            use_multicore = (cpu_mode == 'multicore')

            if self.multiqueue:
                self.tracer_fractions.append(
                    self.config['processing']['cpu']['factor'])

            self.cpu_tracer = tracer.TracerCPU(
                tracer_id,
                use_multicore=use_multicore)

            tracer_id += 1

            self.tracers.append(self.cpu_tracer)

        if self.fpga_active:
            fpga_mode = processing['fpga']['mode']
            use_multi_fpga = (fpga_mode == 'multi')

            if self.multiqueue:
                self.tracer_fractions.append(
                    self.config['processing']['fpga']['factor'])

            self.fpga_tracer = tracer.TracerFPGA(
                tracer_id,
                config['edge']['bitstream'],
                use_multi_fpga=use_multi_fpga)
            tracer_id += 1
            self.tracers.append(self.fpga_tracer)

        if self.multiqueue:
            if not np.isclose(np.sum(self.tracer_fractions), 1.0):
                log.warning("The processing percentage does not amount to 100%")

        
    def start(self):
        while True:
            message=''
            log.info("Waiting for client connection")
            self.listen()
            
            compression = self.config['networking']['compression']
            self.compression = self.config['networking']['compression']
            self.config['processing']['cloud']['cloud_streaming'] = False
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
                    elif param == 'STEAL':
                        value = bool(int(config_msg[i + 1]))
                        print(value)
                        self.config['processing']['task_steal'] = value
                    elif param == 'STREAM':
                        self.config['processing']['cloud']['cloud_streaming'] = True

                message = self.recv_msg(compression)
            print('str', self.config['processing']['cloud']['cloud_streaming'])
            recv_report = f'Recv time: {time() - ti} seconds'
            log.warning(recv_report)

            log.info('Parsing scene data')
            ti = time()
            setup_report = self._parse_scene_data(message.split())
            message=''
            
            parse_report = f'Parse time: {time() - ti} seconds'
            log.warning(parse_report)

            log.info('Computing intersection')
            ti = time()
            tasks_report = self._compute()
            intersection_report = f'Intersection time: {time() - ti} seconds'
            log.warning(intersection_report)

            reports = '\n'.join([
                recv_report,
                parse_report,
                intersection_report,
                setup_report,
                tasks_report])

            self.send_msg(reports, compression)

    def send_result(self, result):
        message = f'{result.task_id} {len(result.triangles_hit)} '
        message += ' '.join(result.triangles_hit) + ' '
        message += ' '.join(result.intersections)
        self.send_msg(message, self.compression)


    def _compute(self):
        import numpy as np
        log.info('Starting edge computation')

        processes = []
        print(f"Use task stealing {self.config['processing']['task_steal']}")
        for tracer_id, tracer in enumerate(self.tracers):
            tracer.set_scene(
                self.triangle_ids,
                self.triangles)
            
            allow_stealing = self.config['processing']['task_steal']
            processes.append(
                mp.Process(
                    target=tracer.start, 
                    args=(
                        self.result_queue,
                        self.task_queues,
                        tracer_id if self.multiqueue else 0,
                        allow_stealing, 
                        self.report_queue,
                        self.config['processing']['cloud']['cloud_streaming'])
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
                self.send_result(res)

        for p in processes: p.join()

        summ_message = f'Processing report: | '
        while not self.report_queue.empty():
            summ = self.report_queue.get()
            summ_message += f'{str(summ)} | '
        log.warning(summ_message)
        return summ_message


    NUM_TRIANGLE_ATTRS = 9
    NUM_RAY_ATTRS = 6

    def _parse_scene_data(self, data):

        ti = time()
        self.num_tris = int(data[0])
        self.num_rays = int(data[1])
        task_data = data[2:]
        print(f'Split time: {time() - ti} seconds')
        data = None
        scene_data = None
        del data
        del scene_data

        tri_end = self.num_tris * (self.NUM_TRIANGLE_ATTRS+1)
        self.triangle_ids = list(map(int, task_data[: self.num_tris]))
        self.triangles    = list(map(float, task_data[self.num_tris : tri_end]))
        
        cam_data = task_data[tri_end : ]
        rays = []
        if cam_data[0] == 'CAM':
            cam_data = cam_data[1:]
            res = (int(cam_data[0]), int(cam_data[1]))
            float_data = list(map(float, cam_data[2:])) 
            self.camera = Camera(res, 
                np.array(float_data[:3]),
                np.array(float_data[3:6]),
                np.array(float_data[6:9]),
                float_data[9], float_data[10])
            rays = self.camera.get_rays(cpp_version=True)
        else:
            rays = cam_data

        ti = time()
        Task.next_id = 0
        from application.scheduling import divide_tasks
        tasks = divide_tasks(rays, self.config['processing']['task_size'])
        print(f'Tasks time: {time() - ti} seconds')

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

        setup_report = 'Setup report: | '
        setup_report += f'Generated {len(tasks)} tasks | '
        setup_report += f'Using {len(self.task_queues)} queue(s) |'
        log.info(setup_report)
        return setup_report
