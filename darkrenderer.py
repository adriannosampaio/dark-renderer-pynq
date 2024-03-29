import json
import socket
import struct
import sys
import logging as log
from time import time
from application.parser import Parser
from darkclient import DarkRendererClient
from darkedge import DarkRendererEdge
from darkcloud import DarkRendererCloud
import multiprocessing as mp

parser = Parser()

def run_client(config):
	import numpy as np
	from PIL import Image
	from application.raytracer.scene import Scene
	from application.raytracer.geometry import Intersection

	hres, vres = parser.args.res
	psize = parser.args.psize
	
	client = DarkRendererClient(config=config)
	image_name = config['client']['output']
	object_file = config['client']['mesh']
	
	ti = time()
	scene = Scene(object_file)
	scene.set_camera(
		(hres, vres), 
		np.array([0.0, 5.0, 5.0]),
		np.array([0.0, 0.0, 0.3]),
		np.array([0.0, 0.0, 1.0]),
		200, psize)
	log.warning(f'Setup time: {time() - ti} seconds')

	ti = time()
	res = json.loads(
		client.compute_scene(
			scene, 
			parser.args.task_size,
			parser.args.task_chunk_size,
			parser.args.multiqueue,
			parser.args.send_cam,
			parser.args.task_stealing,
			parser.args.cloud_streaming,
		)
	)
	log.warning(f'Intersection time: {time() - ti} seconds')
	
	ti = time()
	final_img = Image.new('RGB', (scene.camera.hres, scene.camera.vres), (0,0,0))
	pix = final_img.load()
	for i, tid in enumerate(res['triangles_hit']):
		x, y = i%scene.camera.hres, i//scene.camera.hres
		pix[x,y] = (0, 0, 0)
		if tid != -1:
			ray = scene.camera.get_ray(x, y)
			it = Intersection(
				ray,
				scene.triangles[tid],
				res['intersections'][i])
			col = (scene.materials[0].shade(it, scene.lights))
			col = tuple((col*255).astype('int32'))
			pix[x,y] = col
	
	log.info(f'Saving {image_name}')
	final_img.save(image_name)
	log.warning(f'Shading time: {time() - ti} seconds')

def run_edge(config):
	edge = DarkRendererEdge(config)
	try:
		edge.start()
	finally:
		edge.close()


def run_cloud(config):
	dark_cloud = DarkRendererCloud(config)
	try:
		dark_cloud.start()
	finally:
		dark_cloud.close()

import sys

def setup_logger(mode):
	
	log.basicConfig(
		stream=sys.stdout,
		level=log.WARNING, 
		datefmt='%d-%b-%y %H:%M:%S')
	
	logFormatter = log.Formatter(
		'%(levelname)s: [%(asctime)s] - %(message)s')
	
	rootLogger = log.getLogger()

	fileHandler = log.FileHandler(mode + '.log')
	fileHandler.setFormatter(logFormatter)
	rootLogger.addHandler(fileHandler)

	consoleHandler = log.StreamHandler()
	consoleHandler.setFormatter(logFormatter)
	rootLogger.addHandler(consoleHandler)

def main():
	mp.freeze_support()
	mode = parser.args.mode
	setup_logger(mode)

	config_filename = None
	if 'shutdown' in mode:
		config_filename = "settings/client.json"
	else:
		config_filename = f"settings/{mode}.json"
	
	config = json.load(
		open(
			config_filename
			if parser.args.config is None
			else parser.args.config
		)
	)

	log.info(f'Starting in {parser.args.mode} mode')
	if mode == 'client':
		ti = time()
		run_client(config)
		log.warning(f'Client time: {time() - ti} seconds')
	elif mode == 'edge':
		run_edge(config)
	elif mode == 'cloud':
		run_cloud(config)
	elif 'shutdown' in mode:
		client = DarkRendererClient(config=config)
		if mode == 'shutdown_all':
			client.shutdown_all()
		if mode == 'shutdown_edge':
			client.shutdown_edge()


if __name__ == '__main__':
	main()