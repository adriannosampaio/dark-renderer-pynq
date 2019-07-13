import json
import numpy as np
import logging as log
import struct
import application.tracers as tracer
from application.parser import Parser

class DarkRendererNode():

    def __init__(self, config):        
        import socket as sk
        self.sock = sk.socket(sk.AF_INET, sk.SOCK_STREAM)
        self.config = config

        # Getting the current ip for binding
        ip   = config['edge']['ip']
        port = config['edge']['port']
        self.addr = (ip, port)
        self.sock.bind(self.addr)

        self.cpu_tracer = tracer.TracerARM()

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
        log.info("Waiting for client connection")
        self._await_connection()
        log.info("Receiving task size")
        self._receive_task_size()
        log.info("Receiving scene file")
        scene_data = self._receive_scene_data()
        log.info('Parsing scene data')
        self._parse_scene_data(scene_data)
        log.info('Computing intersection')
        result = self.cpu_tracer.compute(
                self.rays,
                self.triangle_ids,
                self.triangles)
        log.info('Finishing intersection calculation')

        result = json.dumps(result)
        size = len(result)
        msg = struct.pack('>I', size) + result.encode()
        self.connection.send(msg)

    def _await_connection(self):
        self.sock.listen()
        print('Waiting for connection...')
        self.connection, self.current_client = self.sock.accept()
        print(f"Connection with {self.current_client[0]}:{self.current_client[1]}")
        
    def _receive_task_size(self):
        size = self.connection.recv(32).split()
        log.debug(f'Received: {size}')
        self.num_tris = int(size[0])
        self.num_rays = int(size[1])
        log.debug("Task size received:")
        log.debug(f'Number of triangles: {self.num_tris}')
        log.debug(f'Number of rays: {self.num_rays}')

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
        task_data = scene_data.split()[2:]
        tri_end = self.num_tris * (self.NUM_TRIANGLE_ATTRS+1)
        self.triangle_ids = list(map(int, task_data[: self.num_tris]))
        self.triangles    = list(map(float, task_data[self.num_tris : tri_end]))
        self.rays         = list(map(float, task_data[tri_end : ]))

    def _confirm_task_size(self):
        is_scene_ok = False
        is_ray_task_ok = False
        
        if self.num_tris < 2000:
            is_scene_ok = True
        if self.num_rays < 1280*720:
            is_ray_task_ok = True        

        if is_scene_ok and is_ray_task_ok:
            self.connection.send(b'OK')
        else:
            self.connection.send(b'NOK')


def main():
    
    parser = Parser()
    log.basicConfig(
        level=log.DEBUG, 
        format='%(levelname)s: [%(asctime)s] - %(message)s', 
        datefmt='%d-%b-%y %H:%M:%S'
    )
    config = json.load(open("settings/default.json"))
    dark_node = DarkRendererNode(config)
    try:
        dark_node.start()
    finally:
        dark_node.cleanup()

if __name__ == '__main__':
    main()