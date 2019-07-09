import json
import numpy as np
import logging as log
import struct

IDLE                = 0
WAITING_SIZE        = 1
WAITING_SCENE       = 2
WAITING_RAY_TASK    = 3
COMPUTING           = 4
FINISHED            = 5

class Parser:
    def __init__(self, *args, **kwargs):
        import argparse

        self.parser = argparse.ArgumentParser(
            description='Request Ray-Triangle computations to the Fog.')

        self.parser.add_argument(
            '-f', 
            type=str,
            help='File containing the scene information')

        self.parser.add_argument(
            '-o', 
            type=str,
            help='Output file')

        self.parser.add_argument(
            '--mode', 
            choices=['client', 'edge', 'master', 'node'],
            help='File containing the ray geometric information')

        self.args = self.parser.parse_args()


class TracerPYNQ:
    MAX_DISTANCE = 1e9
    EPSILON = 1.0e-5
    def compute(self, rays, tri_ids, tris):
        raise Exception('ERROR: Using abstract class')

class TracerARM(TracerPYNQ):
    def compute(self, rays, tri_ids, tris):
        ''' Call the ray-triangle intersection calculation
            method and convert the triangle indentifiers to 
            global

            P.S.: Maybe it's not necessary, since in a CPU is
            faster to pass the ids to the lower level method,
            but I'll change it later
        '''
        intersects, ids = self._computeCPU(
            np.array(rays), 
            np.array(tris))
        ids = list(map(lambda x : tri_ids[x], ids))
        
        return {
            'intersections' : intersects.tolist(),
            'triangles_hit' : ids
        } 
        
    def _computeCPU(self, rays, triangles):
        ''' Compute the intersection of a set of rays against
            a set of triangles
        '''
        # data structures info
        ray_attrs = 6
        num_rays = len(rays) // ray_attrs
        tri_attrs = 9
        num_tris = len(triangles) // tri_attrs
        # output array
        out_inter = np.full(num_rays, 1.0e9)
        out_ids   = np.full(num_rays, -1)
        # for each ray
        for ray in range(num_rays):
            # select ray
            ray_base = ray * ray_attrs
            closest_tri, closest_dist = -1, self.MAX_DISTANCE
            ray_data = rays[ray_base : ray_base + ray_attrs]

            for tri in range(num_tris):
                tri_base = tri * tri_attrs
            
                tri_data = triangles[tri_base : tri_base + tri_attrs]
            
                dist = self._intersect(ray_data, tri_data)
            
                if dist is not None and dist < closest_dist:
                    closest_dist = dist
                    closest_tri  = tri

            out_inter[ray] = closest_dist
            out_ids[ray]   = closest_tri

        return (out_inter, out_ids)
    
    def _intersect(self, ray, tri):
        ''' Implementation of the Möller algorithm for
            ray-triangle intersection calculation
        '''
        origin, direction = np.array(ray[:3]), np.array(ray[3:6])
        v0, v1, v2 = (np.array(tri[3*x: 3*x+3]) for x in range(3))

        edge1 = v1 - v0
        edge2 = v2 - v0

        h = np.cross(direction, edge2)
        a = np.dot(edge1, h)

        if -self.EPSILON < a < self.EPSILON:
            return None

        f = 1.0 / a
        s = origin - v0
        u = f * np.dot(s, h)

        if not 0.0 <= u <= 1.0:
            return None

        q = np.cross(s, edge1)
        v = f * np.dot(direction, q)

        if v < 0.0 or u + v > 1.0:
            return None

        t = f * np.dot(edge2, q)

        if self.EPSILON < t < 1e9:
            return t



class Task(object):
    """docstring for Task"""
    def __init__(self, scene_size, ray_task_size, target='edge'):
        self.scene_size = scene_size
        self.ray_task_size = ray_task_size
        self.target = target
        

class DarkRendererNode():

    def __init__(self, config, isEdge=True, cloud_addr=None):        
        import socket as sk
        self.sock = sk.socket(sk.AF_INET, sk.SOCK_STREAM)
        self.config = config

        # Getting the current ip for binding
        ip   = config['edge']['ip']
        port = config['edge']['port']
        self.addr = (ip, port)
        self.sock.bind(self.addr)

        self.cpu_tracer = TracerARM()

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
        self.num_tris = int(size[0])
        self.num_rays = int(size[1])
        print("Task size received:")
        print('Number of triangles:', self.num_tris)
        print('Number of rays:', self.num_rays)

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
    log.basicConfig(level=log.INFO)
    config = json.load(open("settings/default.json"))
    dark_node = DarkRendererNode(config)
    try:
        dark_node.start()
    finally:
        dark_node.cleanup()

if __name__ == '__main__':
    main()