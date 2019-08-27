import numpy as np 
import logging as log
from time import time

class TracerPYNQ:
    MAX_DISTANCE = 1e9
    EPSILON = 1.0e-5

    def set_scene(self, tri_ids, triangles):
         self.tri_ids = tri_ids
         self.tris = triangles

    def compute(self, rays):
        raise Exception('ERROR: Using abstract class')

class XIntersectFPGA():
    
    ADDR_AP_CTRL            = 0x00
    ADDR_I_TNUMBER_DATA     = 0x10
    ADDR_I_TDATA_DATA       = 0x18
    ADDR_I_TIDS_DATA        = 0x20
    ADDR_I_RNUMBER_DATA     = 0x28
    ADDR_I_RDATA_DATA       = 0x30
    ADDR_O_TIDS_DATA        = 0x38
    ADDR_O_TINTERSECTS_DATA = 0x40

    def __init__(self, intersect_ip, name):
        self.intersect_ip = intersect_ip
        self.name = name
        self._out_ids   = None
        self._out_inter = None
        self._tids = None
        self._tris = None
        self._rays = None

    def is_done(self):
        return self.intersect_ip.read(0x00) == 4

    def compute(self, rays, tri_ids, tris):
        from pynq import Xlnk
        xlnk = Xlnk()
        num_tris = len(tris) // 9
        num_rays = len(rays) // 6

        log.info(f'{self.name}: Allocating shared input arrays')
        self._tids = xlnk.cma_array(shape=(num_tris,), dtype=np.int32)
        self._tris = xlnk.cma_array(shape=(num_tris*9,), dtype=np.float64)
        self._rays = xlnk.cma_array(shape=(num_rays*6,), dtype=np.float64)

        log.info(f'{self.name}: Allocating shared output arrays')
        self._out_ids   = xlnk.cma_array(shape=(num_rays,), dtype=np.int32)
        self._out_inter = xlnk.cma_array(shape=(num_rays,), dtype=np.float64)

        log.info(f'{self.name}: Setting accelerator input physical addresses')
        self.intersect_ip.write(self.ADDR_I_TNUMBER_DATA, num_tris)
        self.intersect_ip.write(self.ADDR_I_TDATA_DATA, self._tris.physical_address)
        self.intersect_ip.write(self.ADDR_I_TIDS_DATA, self._tids.physical_address)

        self.intersect_ip.write(self.ADDR_I_RNUMBER_DATA, num_rays)
        self.intersect_ip.write(self.ADDR_I_RDATA_DATA, self._rays.physical_address)
        
        self.intersect_ip.write(self.ADDR_O_TIDS_DATA, self._out_ids.physical_address)
        self.intersect_ip.write(self.ADDR_O_TINTERSECTS_DATA, self._out_inter.physical_address)

        ti = time()
        log.info(f'{self.name}: Filling input memory arrays')
        for t in range(num_tris):
            self._tids[t] = tri_ids[t]
            for i in range(9):
                self._tris[t*9+i] = tris[t*9+i]
        log.info(f'{self.name}: Triangle arrays filled in {time() - ti} seconds')

        ti = time()
        for i, r in enumerate(rays):
            self._rays[i] = r
        log.info(f'{self.name}: Ray arrays filled in {time() - ti} seconds')

        log.info(f'Starting co-processor {self.name}')
        self.intersect_ip.write(0x00, 1)

    def get_results(self):
        return (self._out_ids.tolist(), self._out_inter.tolist())


class TracerCPU(TracerPYNQ):
    def __init__(self, use_multicore: bool = True):
        self.use_multicore = use_multicore

    def compute(self, rays):
        ''' Call the ray-triangle intersection calculation
            method and convert the triangle indentifiers to 
            global

            P.S.: Maybe it's not necessary, since in a CPU is
            faster to pass the ids to the lower level method,
            but I'll change it later
        '''
        intersects, ids = [], []
        import application.bindings.tracer as cpp_tracer
            if self.use_multicore: 
                # CPP Code with OpenMP parallelism
            ids, intersects = cpp_tracer.compute(
                rays, self.tri_ids, self.tris)
            else: 
                # CPP without parallelism
            ids, intersects = cpp_tracer.computeParallel(
                rays, self.tri_ids, self.tris)

        return (ids, intersects)


class TracerFPGA(TracerPYNQ):
    def __init__(self, overlay_filename: str, use_multi_fpga: bool = False):
        from pynq import Overlay
        self.use_multi_fpga = use_multi_fpga
        self.accelerators = []

        #overlay = Overlay('/home/xilinx/adrianno/intersect_fpga_x2.bit')
        overlay = Overlay(overlay_filename)
        log.info('Finished loading overlay')
        
        log.info('Initializing FPGA instances')
        self.accelerators.append(
            XIntersectFPGA(overlay.intersectFPGA_0, 'accel_0'))

        if use_multi_fpga:
            log.info('Using multi-accelerator mode')
            self.accelerators.append(
                XIntersectFPGA(overlay.intersectFPGA_1, 'accel_1'))


    def is_done(self):
        all_done = True
        for accel in self.accelerators:
            all_done = all_done and accel.is_done()
        return all_done

    def get_results(self):
        ids, intersects = [], []
        if self.use_multi_fpga:
            ids0, intersects0 = self.accelerators[0].get_results()
            ids1, intersects1 = self.accelerators[1].get_results()
            intersects = intersects0 + intersects1
            ids =  ids0 + ids1
        else:
            ids, intersects = self.accelerators[0].get_results()
        return (ids, intersects)

    def start_compute(self, rays):
        if self.use_multi_fpga:
            num_rays = len(rays) // 6
            self.accelerators[0].compute(
                rays[ : 6*(num_rays//2)], 
                self.tri_ids, 
                self.tris)

            self.accelerators[1].compute(
                rays[6*(num_rays//2) : ], 
                self.tri_ids, 
                self.tris)
        else:
            self.accelerators[0].compute(rays, tri_ids, tris)
        

    def compute(self, rays):
        ''' Call the ray-triangle intersection FPGA accelerator

            P.S.: This operation is non-blocking, so it's 
            required to check if the accelerator is finished
            and to get the results manually
        '''
        if self.use_multi_fpga:
            num_rays = len(rays) // 6
            self.accelerators[0].compute(
                rays[ : 6*(num_rays//2)], 
                self.tri_ids, 
                self.tris)

            self.accelerators[1].compute(
                rays[6*(num_rays//2) : ], 
                self.tri_ids, 
                self.tris)
        else:
            self.accelerators[0].compute(rays, tri_ids, tris)
        

        while not self.is_done():
            time.sleep(0.2)

        return self.get_results()