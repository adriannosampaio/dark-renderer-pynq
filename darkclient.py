import os
import sys
import json
import socket
import struct
import logging as log
from time import time
from application.connection import ClientTCP
from application.scheduling import TaskResult

class DarkRendererClient(ClientTCP):
    ''' Class responsible for the DarkRenderer client behavior.
        This includes the TCP requests to the Fog/Cloud, task 
        sending and receiving the results.
    '''
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        edge_ip   = config['edge']['ip']
        edge_port = config['edge']['port']
        self.edge_addr = (edge_ip, edge_port)

    def shutdown_edge(self):
        self.connect(self.edge_addr)
        compression = self.config['networking']['compression']
        self.send_msg('EXIT_EDGE', compression)
    
    def shutdown_all(self):
        self.connect(self.edge_addr)
        compression = self.config['networking']['compression']
        self.send_msg('EXIT_ALL', compression)

    def compute_scene(self, scene, 
        task_size, task_chunk_size, 
        multiqueue, send_cam,
        task_stealing):
        # connect to the edge node
        compression = self.config['networking']['compression']
        self.connect(self.edge_addr)

        config_msg = 'CONFIG '
        if task_size is not None:
            config_msg += f'TSIZE {task_size} '
        if task_chunk_size is not None:
            config_msg += f'TCHUNKSIZE {task_chunk_size} '
        if multiqueue is not None:
            config_msg += f'MULTIQUEUE {int(multiqueue)} '
        if task_stealing is not None:
            config_msg += f'STEAL {int(task_stealing)} '
        print(config_msg)
        self.send_msg(config_msg, compression)

        # preparing scene to send
        ti = time()
        num_tris, num_rays = len(scene.triangles), scene.camera.vres * scene.camera.hres
        string_data  = f'{num_tris} {num_rays}\n' 
        string_data += f'{scene.get_triangles_string()}\n' 
        if send_cam:
            string_data += f'CAM {scene.camera.get_string()}'
        else:
            rays = scene.camera.get_rays(cpp_version=True)
            string_data += f'{" ".join(map(str, rays))}'

        tf = time()
        log.warning(f'Parse scene time: {tf - ti} seconds')

        # sending the scene 

        log.info('Waiting for results')
        ti = time()
        self.send_msg(string_data, compression)
        tf = time()
        log.warning(f'Send time: {tf - ti} seconds')


        #log.info('Waiting for results')
        ti = time()
        import numpy as np
        results = []
        task_number = np.ceil(float(num_rays/task_size))
        for i in range(int(task_number)):
            res_msg = self.recv_msg(compression).split()
            task_id = int(res_msg[0])
            log.debug(f'Receiving result {task_id}')
            task_sz = int(res_msg[1])
            out_ids = list(map(int, res_msg[2:2+task_sz]))
            out_its = list(map(float, res_msg[2+task_sz:]))
            results.append(TaskResult(task_id, out_ids, out_its))

        triangles_hit = []
        intersections = []
        for res in sorted(results, key=lambda x : x.task_id):
            triangles_hit += res.triangles_hit
            intersections += res.intersections

        log.warning(f'Edge report:\n{self.recv_msg(compression)}')

        self.close()
        return json.dumps({
            'intersections' : intersections,
            'triangles_hit' : triangles_hit})

