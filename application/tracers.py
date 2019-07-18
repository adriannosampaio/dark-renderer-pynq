import numpy as np 

class TracerPYNQ:
    MAX_DISTANCE = 1e9
    EPSILON = 1.0e-5
    def compute(self, rays, tri_ids, tris):
        raise Exception('ERROR: Using abstract class')

class TracerARM(TracerPYNQ):
    def __init__(
        self,
        use_python=False,
        use_multicore=False,
        use_fpga=False
    ):
        self.use_python = use_python
        self.use_fpga = False
        self.use_multicore = False

    def compute(self, rays, tri_ids, tris):
        ''' Call the ray-triangle intersection calculation
            method and convert the triangle indentifiers to 
            global

            P.S.: Maybe it's not necessary, since in a CPU is
            faster to pass the ids to the lower level method,
            but I'll change it later
        '''
        intersects, ids = [], []
        if not self.use_python:
            ids, intersects = self._computeCPP(
                rays,
                tri_ids,
                tris)
        else:
            ids, intersects = self._computeCPU(
                np.array(rays), 
                np.array(tris))
            print(ids)
            intersects = intersects.tolist()
            ids = list(map(lambda x : tri_ids[x] if x != -1 else -1, ids))

        return {
            'intersections' : intersects,
            'triangles_hit' : ids
        } 
        
    def _computeCPP(self, rays, tri_ids, tris):
        import platform
        platform = platform.architecture()[0]
        if platform == '64bit':
            import application.bindings.x64.tracer as cpp_tracer
        elif platform == 'ARM':
            import application.bindings.ARM.tracer as cpp_tracer
        else:
            raise Exception('Platform not currently supported')
        return cpp_tracer.compute(rays, tri_ids, tris)

    def _computeCPU(self, rays, triangles):
        ''' Compute the intersection of a set of rays against
            a set of triangles
        '''
        # data structures info
        ray_attrs = 6
        num_rays = len(rays) // ray_attrs
        tri_attrs = 9
        num_tris = len(triangles) // tri_attrs
        # output array
        out_inter = np.full(num_rays, 1.0e9)
        out_ids   = np.full(num_rays, -1)
        # for each ray
        for ray in range(num_rays):
            # select ray
            ray_base = ray * ray_attrs
            closest_tri, closest_dist = -1, self.MAX_DISTANCE
            ray_data = rays[ray_base : ray_base + ray_attrs]

            for tri in range(num_tris):
                tri_base = tri * tri_attrs
            
                tri_data = triangles[tri_base : tri_base + tri_attrs]
            
                dist = self._intersect(ray_data, tri_data)
            
                if dist is not None and dist < closest_dist:
                    closest_dist = dist
                    closest_tri  = tri

            out_inter[ray] = closest_dist
            out_ids[ray]   = closest_tri

        return (out_ids, out_inter)
    
    def _intersect(self, ray, tri):
        ''' Implementation of the Möller algorithm for
            ray-triangle intersection calculation
        '''
        origin, direction = np.array(ray[:3]), np.array(ray[3:6])
        v0, v1, v2 = (np.array(tri[3*x: 3*x+3]) for x in range(3))

        edge1 = v1 - v0
        edge2 = v2 - v0

        h = np.cross(direction, edge2)
        a = np.dot(edge1, h)

        if -self.EPSILON < a < self.EPSILON:
            return None

        f = 1.0 / a
        s = origin - v0
        u = f * np.dot(s, h)

        if not 0.0 <= u <= 1.0:
            return None

        q = np.cross(s, edge1)
        v = f * np.dot(direction, q)

        if v < 0.0 or u + v > 1.0:
            return None

        t = f * np.dot(edge2, q)

        if self.EPSILON < t < 1e9:
            return t
