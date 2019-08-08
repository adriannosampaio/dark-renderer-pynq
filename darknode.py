import json
import numpy as np
import logging as log
import struct
import application.tracers as tracer
from application.parser import Parser

def save_intersections(filename, ids, intersects):
    with open(filename, 'w') as file:
        for tid, inter in zip(ids, intersects):
            file.write(f'{tid} {inter}\n')

class DarkRendererNode():

    def __init__(self, 
        config, 
        use_python=False, 
        use_multicore=False, 
        use_fpga=False, 
        use_multi_fpga=False,
        use_heterogeneous=True,
        fpga_load_fraction=0.5
        ):        
        
        import socket as sk
        self.sock = sk.socket(sk.AF_INET, sk.SOCK_STREAM)
        self.config = config

        # Getting the current ip for binding
        ip   = config['edge']['ip']
        port = config['edge']['port']
        self.addr = (ip, port)
        self.sock.bind(self.addr)


        self.use_python = use_python
        self.use_multicore = use_multicore
        self.use_fpga = use_fpga
        self.use_multi_fpga = use_multi_fpga
        self.use_heterogeneous = use_heterogeneous
        self.fpga_load_fraction = fpga_load_fraction

        self.cpu_tracer = tracer.TracerCPU(
            use_multicore=use_multicore,
            use_python=use_python)

        self.fpga_tracer = tracer.TracerFPGA(
            '/home/xilinx/adrianno/intersect_fpga_x2.bit',
            use_multi_fpga=use_multi_fpga)

        # IP address of the cloud application
        # cloud_ip   = config['cloud']['ip']
        # cloud_port = config['cloud']['port']
        # self.cloud_addr = (cloud_ip, cloud_port)
        
        self.connection = None
        self.client_ip = None
        
        self.triangles    = []
        self.triangle_ids = []
        self.rays         = []
        
    def cleanup(self):
        self.sock.close()
        
    def start(self):
        from time import time

        log.info("Waiting for client connection")
        self._await_connection()
        
        log.info("Receiving scene file")
        ti = time()
        scene_data = self._receive_scene_data()
        tf = time()
        log.info(f'Finished receiving data in {tf - ti} seconds')

        log.info('Parsing scene data')
        ti = time()
        self._parse_scene_data(scene_data)
        tf = time()
        log.info(f'Finished parsing scene data in {tf - ti} seconds')

        log.info('Computing intersection')
        ti = time()
        result = self._compute()
        tf = time()
        log.info(f'Finishing intersection calculation in {tf - ti} seconds')

        log.info('Preparing and sending results')
        ti = time()
        result = json.dumps(result)
        size = len(result)
        msg = struct.pack('>I', size) + result.encode()
        self.connection.send(msg)
        tf = time()
        log.info(f'Finished sending results in {tf - ti} seconds')

    def _compute(self):
        import numpy as np
        log.info('Starting edge computation')
        intersects, ids = [], []
        if self.use_heterogeneous: # currently balancing 50%-50%
            log.info('Computing in heterogenous mode')
            num_rays = len(self.rays) // 6      

            log.info(f'FPGA processing {self.fpga_load_fraction*100}% (self.fpga_load_fraction)')
            fpga_load = int(np.floor(num_rays * self.fpga_load_fraction))
            log.info(f'FPGA load is {fpga_load}/{num_rays} rays')

            self.fpga_tracer.compute(
                self.rays[:fpga_load*6],
                self.triangle_ids,
                self.triangles)

            cpu_ids, cpu_inter = self.cpu_tracer.compute(
                self.rays[fpga_load*6:],
                self.triangle_ids,
                self.triangles)

            while not self.fpga_tracer.is_done(): pass
            fpga_ids, fpga_inter = self.fpga_tracer.get_results()
            #print(fpga_ids, fpga_inter, cpu_ids, cpu_inter)

            ids = fpga_ids + cpu_ids
            intersects = fpga_inter + cpu_inter
            save_intersections('heterogenous.txt', ids, intersects)

        elif self.use_fpga:
            log.info('Computing in fpga-only mode')
            self.fpga_tracer.compute(
                self.rays,
                self.triangle_ids,
                self.triangles)

            while not self.fpga_tracer.is_done(): 
                pass
            ids, intersects = self.fpga_tracer.get_results()
            save_intersections(f'fpga_multi_{self.use_multi_fpga}.txt', ids, intersects)
        else:
            log.info('Computing in cpu-only mode')
            ids, intersects = self.cpu_tracer.compute(
                self.rays,
                self.triangle_ids,
                self.triangles)
            save_intersections('cpu.txt', ids, intersects)

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
        
        CHUNK_SIZE = 256
        full_data = b''
        while len(full_data) < size:
            packet = self.connection.recv(CHUNK_SIZE)
            if not packet:
                break
            full_data += packet
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
        self.rays         = list(map(float, task_data[tri_end : ]))

def main():
    
    parser = Parser()
    log.basicConfig(
        level=log.DEBUG, 
        format='%(levelname)s: [%(asctime)s] - %(message)s', 
        datefmt='%d-%b-%y %H:%M:%S'
    )
    config = json.load(open("settings/default.json"))
    use_python = parser.args.use_python
    dark_node = DarkRendererNode(config, use_python)
    try:
        dark_node.start()
    finally:
        dark_node.cleanup()

if __name__ == '__main__':
    main()