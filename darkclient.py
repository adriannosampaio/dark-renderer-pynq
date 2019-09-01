import os
import sys
import json
import socket
import struct
import logging as log
from time import time
from application.connection import ClientTCP

class DarkRendererClient(ClientTCP):
	'''	Class responsible for the DarkRenderer client behavior.
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


		log.info('Waiting for results')
		ti = time()
		result = self.recv_msg(compression)
		tf = time()
		log.warning(f'Recv time: {tf - ti} seconds')

		self.close()
		return result

