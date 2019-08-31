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

	def compute_scene(self, scene, task_size=None):
		# connect to the edge node
		compression = self.config['networking']['compression']
		self.connect(self.edge_addr)

		if task_size is not None:
			config_msg = f'CONFIG TSIZE {task_size}'
			self.send_msg(config_msg, compression)

		# preparing scene to send
		ti = time()
		num_tris, num_rays = len(scene.triangles), scene.camera.vres * scene.camera.hres
		string_data  = f'{num_tris} {num_rays}\n' 
		string_data += f'{scene.get_triangles_string()}\n' 
		string_data += f'{scene.camera.get_string()}'
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

