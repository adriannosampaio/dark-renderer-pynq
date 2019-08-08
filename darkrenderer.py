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
		from time import time
		input_filename = parser.args.f
		output_filename = parser.args.o
		#for i in range(3):
		client = darkclient.DarkRendererClient(input_filename, output_filename, config)
		log.info('Preparing to offload computation to edge node')
		initial_time = time()
		client.run()
		log.info(f'Received result in {time() - initial_time} seconds')
	elif parser.args.mode == 'edge':
		use_python = parser.args.use_python
		use_multicore = parser.args.use_multicore
		use_fpga = parser.args.use_fpga
		use_multi_fpga = parser.args.use_multi_fpga
		use_heterogeneous = parser.args.use_heterogeneous
		
		arg_load = parser.args.fpga_load_fraction
		fpga_load_fraction = 0.5 if arg_load is None else arg_load
		
		dark_node = darknode.DarkRendererNode(
			config, 
			use_python,
			use_multicore,
			use_fpga,
			use_multi_fpga,
			use_heterogeneous,
			fpga_load_fraction)
		try:
		    dark_node.start()
		finally:
		    dark_node.cleanup()


if __name__ == '__main__':
	main()