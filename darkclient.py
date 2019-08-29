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

	def compute_scene(self, scene):
		# connect to the edge node
		self.connect(self.edge_addr)

		# preparing scene to send
		ti = time()
		num_tris, num_rays = len(scene.triangles), scene.camera.vres * scene.camera.hres
		string_data  = f'{num_tris} {num_rays}\n' 
		string_data += f'{scene.get_triangles_string()}\n' 
		string_data += f'{scene.camera.get_string()}'
		tf = time()
		log.warning(f'Parse scene time: {tf - ti} seconds')

		# sending the scene	

		compress = self.config['networking']['compression']
		log.info('Waiting for results')
		ti = time()
		self.send_msg(string_data, compress)
		tf = time()
		log.warning(f'Recv time: {tf - ti} seconds')


		log.info('Waiting for results')
		ti = time()
		result = self.recv_msg(compress)
		tf = time()
		log.warning(f'Recv time: {tf - ti} seconds')

		self.close()
		return result

