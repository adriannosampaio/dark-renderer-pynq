import socket
import struct
import zlib

class TemplateTCP(object):
	"""docstring for TemplateTCP"""

	CHUNK_SIZE = 256*1024

	def __init__(self):
		self.socket = None

	def send_msg(self, string_msg : str, compress=True):
		msg = string_msg.encode()
		if compress:
			compressed_msg = zlib.compress(msg)
			msg = compressed_msg
		self.socket.send(
			struct.pack(
				'>I', len(msg)) + msg
			)

	def recv_msg(self, decompress=True):
		size_msg = self.socket.recv(4)
		size_msg = struct.unpack('>I', size_msg)[0]
		full_msg = b''
		while len(full_msg) < size_msg:
			packet = self.socket.recv(min(self.CHUNK_SIZE, size_msg))
			if not packet:
				break
			full_msg += packet

		if decompress:
			return zlib.decompress(full_msg).decode()
		else:
			return full_msg.decode()

	def close(self):
		self.socket.close()

class ClientTCP(TemplateTCP):
	
	def __init__(self):
		super().__init__()
		self.server_addr = None
		self.socket = None

	def connect(self, server_addr : tuple = ('localhost',1005)):
		self.server_addr = server_addr
		self.socket = socket.socket(
				socket.AF_INET, 
				socket.SOCK_STREAM)
		self.socket.connect(server_addr)

class ServerTCP(TemplateTCP):
	def __init__(self, bind_addr : tuple = ('localhost',1005)):
		super().__init__()
		self.bind_addr = bind_addr
		self.client_ip = None
		
		self.server_socket = socket.socket(
			socket.AF_INET, 
			socket.SOCK_STREAM)

		self.server_socket.bind(self.bind_addr)

	def close(self):
		super().close()
		self.server_socket.close()

	def listen(self):
		self.server_socket.listen()
		print('Waiting for connection...')
		self.socket, self.client_ip = self.server_socket.accept()
		

