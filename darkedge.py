import json
import numpy as np
import logging as log
import struct
import application.tracers as tracer
from application.parser import Parser
from application.raytracer.scene import Camera
from application.scheduling import Task, TaskResult
import multiprocessing as mp
from time import time

def save_intersections(filename, ids, intersects):
    with open(filename, 'w') as file:
        for tid, inter in zip(ids, intersects):
            file.write(f'{tid} {inter}\n')

class DarkRendererEdge():

    def __init__(self, config):        
        
        import socket as sk
        self.sock = sk.socket(sk.AF_INET, sk.SOCK_STREAM)
        self.config = config

        # Getting the current ip for binding
        ip   = config['edge']['ip']
        port = config['edge']['port']
        self.addr = (ip, port)
        self.sock.bind(self.addr)
        
        self.connection = None
        self.client_ip = None
        
        self.triangles    = []
        self.triangle_ids = []
        self.rays         = []
        self.camera       = None

        self.task_queue = mp.Queue()
        self.result_queue = mp.Queue()

        processing = config['processing']
        mode = processing['mode']
        self.heterogeneous_mode = (mode == 'heterogeneous')
        self.cpu_active = mode in ['cpu', 'heterogeneous']
        self.fpga_active = mode in ['fpga', 'heterogeneous']
        
        if self.heterogeneous_mode:
            self.fpga_load_fraction = processing['heterogeneous']['fpga-load']

        self.tracers = []

        if self.cpu_active:
            cpu_mode = processing['cpu']['mode']    
            use_python = (cpu_mode == 'python')
            use_multicore = (cpu_mode == 'multicore')
            self.cpu_tracer = tracer.TracerCPU(
                use_multicore=use_multicore)
            self.tracers.append(self.cpu_tracer)
            # self.tracers.append(tracer.TracerCPU(
                # use_multicore=use_multicore))

        if self.fpga_active:
            fpga_mode = processing['fpga']['mode']
            use_multi_fpga = (fpga_mode == 'multi')
            self.fpga_tracer = tracer.TracerFPGA(
                config['edge']['bitstream'],
                use_multi_fpga=use_multi_fpga)
            self.tracers.append(self.fpga_tracer)
        
    def cleanup(self):
        self.sock.close()
        
    def start(self):

        log.info("Waiting for client connection")
        self._await_connection()
        
        log.info("Receiving scene file")
        ti = time()
        scene_data = self._receive_scene_data()
        tf = time()
        log.warning(f'Recv time: {tf - ti} seconds')

        log.info('Parsing scene data')
        ti = time()
        self._parse_scene_data(scene_data)
        tf = time()
        log.warning(f'Parse time: {tf - ti} seconds')

        log.info('Computing intersection')
        ti = time()
        result = self._compute()
        tf = time()
        log.warning(f'Intersection time: {tf - ti} seconds')

        log.info('Preparing and sending results')
        ti = time()
        result = json.dumps(result)
        size = len(result)
        msg = struct.pack('>I', size) + result.encode()
        self.connection.send(msg)
        tf = time()
        log.warning(f'Send time: in {tf - ti} seconds')

    def _compute(self):
        import numpy as np
        log.info('Starting edge computation')

        processes = []
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

        for p in processes:
            p.start()

        tracers_finished = 0
        from sortedcontainers import SortedDict
        from functools import reduce
        ids_dict = SortedDict()
        intersect_dict = SortedDict() 

        print(f'num tracers = {len(self.tracers)}')
        while tracers_finished < len(self.tracers):
            res = self.result_queue.get()
            if res is None:
                tracers_finished += 1
            else:
                task_id = res.task_id 
                ids_dict[task_id] = res.triangles_hit
                intersect_dict[task_id] = res.intersections

        for p in processes:
            p.join()

        ids = reduce(
            lambda x, y : x + y,
            ids_dict.values())

        intersects = reduce(
            lambda x, y : x + y,
            intersect_dict.values())

        return {
            'intersections' : intersects,
            'triangles_hit' : ids
        } 

    def _await_connection(self):
        self.sock.listen()
        print('Waiting for connection...')
        self.connection, self.current_client = self.sock.accept()
        print(f"Connection with {self.current_client[0]}:{self.current_client[1]}")

    def _receive_scene_data(self):
        log.info("Start reading scene file content")
        raw_size = self.connection.recv(4)
        size = struct.unpack('>I', raw_size)[0]
        log.info(f'Finishing receiving scene file size: {size}B')
        
        CHUNK_SIZE = self.config['networking']['recv_buffer_size']
        full_data = b''
        while len(full_data) < size:
            packet = self.connection.recv(min(CHUNK_SIZE, size))
            if not packet:
                break
            full_data += packet
        
        if self.config['networking']['compression']:
            import zlib

            ti = time()
            full_data = zlib.decompress(full_data)
            log.warning(f'Compression time: {time() - ti} seconds')

        return full_data.decode()

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
        print(f'Created {len(tasks)} tasks')
        print(f'len(task 0) = {len(tasks[0])}')
        for t in tasks:
            self.task_queue.put(t)
            print(t.id, len(t))

        for _ in self.tracers:
            self.task_queue.put(None)



    def divide_tasks(self, rays):
        num_rays = len(rays)//6
        max_task_size = self.config['processing']['task_size']
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
        print(*map(len, ray_tasks), sep=', ')
        return ray_tasks