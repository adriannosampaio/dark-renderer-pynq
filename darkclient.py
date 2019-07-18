import os
import sys
import json
import socket
import struct
import logging as log
from application.parser import Parser

class Session:
	def __init__(self, input_filename, output_filename):
		self.input_filename = input_filename
		self.output_filename = output_filename
		self.input_file = open(input_filename, 'r')
		line = self.input_file.readline().split()
		self.num_tris = int(line[0])
		self.num_rays = int(line[1])

	def get_tris(self):
		for i in range(self.num_tris):
			yield self.input_file.readline()

	def get_rays(self):
		for i in range(self.num_rays):
			yield self.input_file.readline()

class DarkRendererClient:
	'''	Class responsible for the DarkRenderer client behavior.
		This includes the TCP requests to the Fog/Cloud, task 
		sending and receiving the results.
	'''
	def __init__(self, input_filename, output_filename, config):
		self.sock = socket.socket(
			socket.AF_INET, 
			socket.SOCK_STREAM)
		self.config = config
		
		edge_ip   = config['edge']['ip']
		edge_port = config['edge']['port']
		self.edge_addr = (edge_ip, edge_port)

		print(f"Reading filename {input_filename}")
		self.session = Session(input_filename, output_filename)
		self.num_tris = self.session.num_tris
		self.num_rays = self.session.num_rays

	def _connect(self):
		log.info(f'Connecting to edge node {self.edge_addr[0]}:{self.edge_addr[1]}')
		self.sock.connect(self.edge_addr)

	def _cleanup(self):
		self.sock.close()

	def _send(self, data):
		print("Sending:", data)
		self.sock.send(data)

	def _recv(self, size):
		msg = self.sock.recv(size)
		print("Received:", msg)
		return msg

	def run(self):
		# connect to the edge node
		self._connect()
		# send the task size
		self._send_task_size()
		# sending the scene	
		self._send_scene_file()
		log.info('Waiting for results')
		result = self._receive_results()
		log.info('Results received')
		print(result)
		with open(self.session.output_filename, 'w') as output_file:
			output_file.write(result)
		self._cleanup()

	def _receive_results(self):
		log.info("Start receiving results")

		raw_size = self.sock.recv(4)
		size = struct.unpack('>I', raw_size)[0]
		log.info(f'Finishing receiving scene file size: {size}B')

		CHUNK_SIZE = 256
		full_data = b''
		while len(full_data) < size:
			packet = self._recv(CHUNK_SIZE)
			if not packet:
				break
			full_data += packet
		return full_data.decode()

	def _send_task_size(self):
		log.info('Sending task size to the Edge')
		size_msg = f'{self.num_tris} {self.num_rays}'
		log.debug(f'Sent: "{size_msg}"')
		self._send(size_msg.encode())
		# receive confirmation from the edge
		ans = b'OK'# self._recv(16)
		# when the edge confirms
		if ans != b'OK': # send the scene
			raise Exception('Edge Task refused...')
		else:
			print('Task size is OK')

	def _send_scene_file(self):
		log.info('Sending configuration file')
		with open(self.session.input_filename, 'r') as input_file:
			file = input_file.read()
			size = len(file)
			msg = struct.pack('>I', size) + file.encode()
			self._send(msg)
		log.info("Configuration file sent")


def main():
	log.basicConfig(
		level=log.DEBUG, 
		format='%(levelname)s: [%(asctime)s] - %(message)s', 
		datefmt='%d-%b-%y %H:%M:%S'
	)
	parser = Parser()
	input_filename = parser.args.f
	output_filename = parser.args.o
	config = json.load(open("settings/default.json"))
	client = DarkRendererClient(input_filename, output_filename, config)
	client.run()


if __name__ == '__main__':
	main()