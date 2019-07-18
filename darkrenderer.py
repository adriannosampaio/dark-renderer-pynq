import os
import sys
import json
import socket
import struct
import logging as log
from application.parser import Parser
import darknode, darkclient

def main():
	log.basicConfig(
		level=log.DEBUG, 
		format='%(levelname)s: [%(asctime)s] - %(message)s', 
		datefmt='%d-%b-%y %H:%M:%S'
	)
	parser = Parser()
	config = json.load(open("settings/default.json"))
	
	if parser.args.mode == 'client':
		input_filename = parser.args.f
		output_filename = parser.args.o
		client = darkclient.DarkRendererClient(input_filename, output_filename, config)
		client.run()
	elif parser.args.mode == 'edge':
		use_python = parser.args.use_python
		dark_node = darknode.DarkRendererNode(config, use_python)
		try:
		    dark_node.start()
		finally:
		    dark_node.cleanup()


if __name__ == '__main__':
	main()