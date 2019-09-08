import numpy as np


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
        from pynq import Xlnk
        self.xlnk = Xlnk()
        self.intersect_ip = intersect_ip
        self.name = name
        self.num_tris = 0
        self._out_ids   = None
        self._out_inter = None
        self._tids = None
        self._tris = None
        self._rays = None

    def set_scene(self, tri_ids, tris):
        from pynq import Xlnk
        self.num_tris = len(tri_ids)

        self._tids = self.xlnk.cma_array(
            shape=(self.num_tris,), 
            dtype=np.int32)
        
        self._tris = self.xlnk.cma_array(
            shape=(self.num_tris*9,), 
            dtype=np.float64)

        ti = time()
        for t in range(self.num_tris):
            self._tids[t] = tri_ids[t]
            for i in range(9):
                self._tris[t*9+i] = tris[t*9+i]

        self.intersect_ip.write(
            self.ADDR_I_TNUMBER_DATA, 
            self.num_tris)
        
        self.intersect_ip.write(
            self.ADDR_I_TDATA_DATA, 
            self._tris.physical_address)
        
        self.intersect_ip.write(
            self.ADDR_I_TIDS_DATA, 
            self._tids.physical_address)

    def is_done(self):
        return self.intersect_ip.read(0x00) == 4

    def compute(self, rays):
        num_rays = len(rays) // 6

        self._rays = self.xlnk.cma_array(shape=(num_rays*6,), dtype=np.float64)

        self._out_ids   = self.xlnk.cma_array(shape=(num_rays,), dtype=np.int32)
        self._out_inter = self.xlnk.cma_array(shape=(num_rays,), dtype=np.float64)

        self.intersect_ip.write(self.ADDR_I_RNUMBER_DATA, num_rays)
        self.intersect_ip.write(self.ADDR_I_RDATA_DATA, self._rays.physical_address)
        
        self.intersect_ip.write(self.ADDR_O_TIDS_DATA, self._out_ids.physical_address)
        self.intersect_ip.write(self.ADDR_O_TINTERSECTS_DATA, self._out_inter.physical_address)

        ti = time()
        for i, r in enumerate(rays):
            self._rays[i] = r

        log.info(f'Starting co-processor {self.name}')
        self.intersect_ip.write(0x00, 1)

    def get_results(self):
        return (self._out_ids.tolist(), self._out_inter.tolist())
