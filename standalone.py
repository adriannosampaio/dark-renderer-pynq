import numpy as np
import json
from PIL import Image
from application.raytracer.geometry import *
from application.raytracer.light import *
from application.raytracer.material import *

object_file = 'examples/bunny_2k.obj'

def read_obj(filename):
	triangles = []
	vertices = []
	with open(object_file, 'r') as file:
		tid = 0
		vcount = 0
		for line in file:
			line = line.split()
			data_type = line[0]
			data = line[1:]
			if data_type == 'v':
				vcount += 1
				vertices.append(np.array(list(map(float, data))))
			elif data_type == 'f':
				triangles.append(
					Triangle(
						vertices[int(data[0]) - 1],
						vertices[int(data[1]) - 1],
						vertices[int(data[2]) - 1])
					)
				triangles[tid].id = tid
				tid+=1
	return triangles


lights = [
	PointLight(
		np.array([50., 50., 50.]),
		np.array([1.0, 1.0, 1.0]),
		2.0),
	PointLight(
		np.array([-50., -50., 50.]),
		np.array([1.0, 1.0, 1.0]),
		1.0)]

materials = [Matte(np.array([1.0, 0.0, 1.0]), 0.7)]

class Scene():
	def __init__(self, filename):
		self.triangles = read_obj(filename)

	def get_triangles_string(self):
		ids = ''
		out = ''
		counter = 0
		for t in self.triangles:
			ids += f'{counter} '
			for p in t.pts:
				for c in p:
					out += f'{c} '
			out += '\n'
			counter += 1
		return ids + '\n' + out + '\n'

class Camera():
	def __init__(self, 
		res, eye_point, 
		look_point, up_vec, 
		dist, psize):

		self.hres, self.vres = res
		self.dist = dist
		self.psize = psize
		self.eye_point = eye_point
		self.look_point = look_point
		self.up_vec = up_vec

		self.w  = eye_point - look_point
		self.w /= np.linalg.norm(self.w)
		
		self.u = -np.cross(up_vec, self.w)
		self.u /= np.linalg.norm(self.u)

		self.v = np.cross(self.w, self.u)

	def get_ray(self, c, r):
		xv = self.psize*(c - self.hres/2),
		yv = self.psize*(r - self.vres/2);
		d = xv*self.u + yv*self.v - self.dist*self.w
		d /= np.linalg.norm(d)
		return Ray(self.eye_point, d)

	def get_rays_string(self):
		out = ''
		for r in range(self.vres):
			for c in range(self.hres):
				xv = self.psize*(c - self.hres/2),
				yv = self.psize*(r - self.vres/2);
				dir = xv*self.u + yv*self.v - self.dist*self.w
				dir /= np.linalg.norm(dir)

				for i in self.eye_point:
					out += f'{round(i, 6)} '
				for i in dir:
					out += f'{round(i, 6)} '
				out += '\n'
		return out


def main():
	import logging as log
	from darkclient import DarkRendererClient
	from application.parser import Parser
	log.basicConfig(
		level=log.DEBUG, 
		format='%(levelname)s: [%(asctime)s] - %(message)s', 
		datefmt='%d-%b-%y %H:%M:%S')
	#parser = Parser()
	from time import time
	ti = time()
	scene = Scene(object_file)
	camera = Camera(
		(125, 125), 
		np.array([0.0, 5.0, 5.0]),
		np.array([0.0, 0.0, 0.3]),
		np.array([0.0, 0.0, 1.0]),
		200, 0.4)
	num_tris, num_rays = len(scene.triangles), camera.vres * camera.hres

	data = f'{num_tris} {num_rays}\n{scene.get_triangles_string()}\n{camera.get_rays_string()}'
	log.info(f'Finished standalone setup in {time() - ti} seconds')
	config = json.load(open("settings/default.json"))
	client = DarkRendererClient(config=config)
	
	ti = time()
	res = json.loads(
		client.compute_string(
			(num_tris, num_rays, data)))
	log.info(f'Finished intersection calculations in {time() - ti} seconds')
	
	ti = time()
	final_img = Image.new('RGB', (camera.hres, camera.vres), (0,0,0))
	pix = final_img.load()
	for i, tid in enumerate(res['triangles_hit']):
		x, y = i%camera.hres, i//camera.hres
		pix[x,y] = (0, 0, 0)
		if tid != -1:
			ray = camera.get_ray(x, y)
			it = Intersection(
				ray,
				scene.triangles[tid],
				res['intersections'][i])
			col = (materials[0].shade(it, lights))
			col = tuple((col*255).astype('int32'))
			pix[x,y] = col
	#final_img.show()
	log.info('Saving visualization.jpg')
	final_img.save('visualization.jpg')
	log.info(f'Finished shading calculations in {time() - ti} seconds')
	
	#input("Press enter to continue...")

if __name__ == '__main__':
	main()

