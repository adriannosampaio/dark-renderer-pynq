import os
import sys
import json
import socket
import struct
import logging as log
from time import time

class DarkRendererClient:
	'''	Class responsible for the DarkRenderer client behavior.
		This includes the TCP requests to the Fog/Cloud, task 
		sending and receiving the results.
	'''
	def __init__(self, input_filename=None, output_filename=None, config=None):
		self.sock = socket.socket(
			socket.AF_INET, 
			socket.SOCK_STREAM)
		self.config = config
		
		#self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
		edge_ip   = config['edge']['ip']
		edge_port = config['edge']['port']
		self.edge_addr = (edge_ip, edge_port)

		log.info(f"Reading filename {input_filename}")
		if input_filename != None:
			self.session = Session(input_filename, output_filename)
			self.num_tris = self.session.num_tris
			self.num_rays = self.session.num_rays

	def _connect(self):
		log.info(f'Connecting to edge node {self.edge_addr[0]}:{self.edge_addr[1]}')
		self.sock.connect(self.edge_addr)

	def _cleanup(self):
		self.sock.close()

	def _send(self, data):
		self.sock.send(data)

	def _recv(self, size):
		msg = self.sock.recv(size)
		return msg

	def compute_scene(self, scene):
		# connect to the edge node
		self._connect()

		# preparing scene to send
		ti = time()
		num_tris, num_rays = len(scene.triangles), scene.camera.vres * scene.camera.hres
		string_data  = f'{num_tris} {num_rays}\n' 
		string_data += f'{scene.get_triangles_string()}\n' 
		string_data += f'{scene.camera.get_string()}'
		tf = time()
		log.warning(f'Parse scene time: {tf - ti} seconds')

		# sending the scene	
		self._send_scene_string(string_data)

		log.info('Waiting for results')
		ti = time()
		result = self._receive_results()
		tf = time()
		log.warning(f'Recv time: {tf - ti} seconds')

		self._cleanup()
		return result
		
	def _send_scene_string(self, string):
		import zlib, time
		log.info('Sending scene configuration')
		encoded_msg = string.encode()
		
		size_msg = len(encoded_msg)
		final_msg = encoded_msg
		
		if self.config['networking']['compression']:
			ti = time.time()
			final_msg = zlib.compress(encoded_msg)
			size_msg = len(final_msg)
			log.warning(f'Compression time: {time.time() - ti} seconds')
			log.warning(f'sizes\n\t- encoded: {len(encoded_msg)}\n\t- compressed: {len(final_msg)}')
		
		final_msg = struct.pack('>I', size_msg) + final_msg
		self._send(final_msg)
		log.info("Configuration file sent")

	def _receive_results(self):
		log.info("Start receiving results")
		raw_size = self.sock.recv(4)
		size = struct.unpack('>I', raw_size)[0]
		log.info(f'Finishing receiving scene file size: {size}B')

		# 256kB
		CHUNK_SIZE = self.config['networking']['recv_buffer_size']
		full_data = b''
		while len(full_data) < size:
			packet = self._recv(min(size, CHUNK_SIZE))
			if not packet:
				break
			full_data += packet
		return full_data.decode()

	def _send_scene_file(self):
		log.info('Sending configuration file')
		with open(self.session.input_filename, 'r') as input_file:
			file = input_file.read()
			size = len(file)
			msg = struct.pack('>I', size) + file.encode()
			self._send(msg)
		log.info("Configuration file sent")

