import numpy as np 
import logging as log
from time import time, sleep
from .scheduling import TaskResult, TracerSummary, SuperTask
from .connection import ClientTCP

class TracerPYNQ:
    MAX_DISTANCE = 1e9
    EPSILON = 1.0e-5
    def __init__(self, tracer_id):
        self.tracer_id = tracer_id

    def set_scene(self, tri_ids, triangles):
         self.tri_ids = tri_ids
         self.tris = triangles
         self.active_queues = []

    def compute(self, rays):
        raise Exception('ERROR: Using abstract class')

    def steal_task(self, task_queues):
        task = None
        for i, q in enumerate(task_queues):
            if self.active_queues[i]: 
                task = task_queues[i].get()
            
            if task is None: 
                self.active_queues[i] = False
            else:
                print(f'{type(self).__name__}: Stealing task {task.id} from queue {i}')
                break
        return task 


    def get_task(self, task_queues, main_queue, allow_stealing):
        task = None
        # if the main queue is active, get task from there
        if self.active_queues[main_queue]:
            task = task_queues[main_queue].get()
            if task is None:
                self.active_queues[main_queue] = False
            else:
                print(f'{type(self).__name__}: Processing task {task.id}')
                pass

        # if stealing is not active, return anyway
        if allow_stealing and task is None:
            # if stealing is active and the task obtained is None
            # start scanning other queues
            task = self.steal_task(task_queues)
        
        return task

    def start(self, result_queue, task_queues, main_queue_id, allow_stealing=False, report_queue=None):
        self.active_queues= [True for _ in task_queues]
        task = self.get_task(task_queues, main_queue_id, allow_stealing)
        report = TracerSummary(self)
        while task is not None:
            report.increment()
            out_ids, out_inter = self.compute(list(map(float,task.ray_data)))
            result = TaskResult(task.id, list(map(str,out_ids)), list(map(str,out_inter)))
            result_queue.put(result)
            task = self.get_task(task_queues, main_queue_id, allow_stealing)
        if report_queue is not None: report_queue.put(report)
        result_queue.put(None)


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
        log.info(f'{self.name}: Allocating shared input arrays')
        
        self._tids = self.xlnk.cma_array(
            shape=(self.num_tris,), 
            dtype=np.int32)
        
        self._tris = self.xlnk.cma_array(
            shape=(self.num_tris*9,), 
            dtype=np.float64)

        ti = time()
        log.info(f'{self.name}: Filling input memory arrays')
        for t in range(self.num_tris):
            self._tids[t] = tri_ids[t]
            for i in range(9):
                self._tris[t*9+i] = tris[t*9+i]
        log.info(f'{self.name}: Triangle arrays filled in {time() - ti} seconds')

        log.info(f'{self.name}: Setting accelerator input triangle data addresses')
        
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

        log.info(f'{self.name}: Allocating shared input array')
        self._rays = self.xlnk.cma_array(shape=(num_rays*6,), dtype=np.float64)

        log.info(f'{self.name}: Allocating shared output arrays')
        self._out_ids   = self.xlnk.cma_array(shape=(num_rays,), dtype=np.int32)
        self._out_inter = self.xlnk.cma_array(shape=(num_rays,), dtype=np.float64)

        log.info(f'{self.name}: Setting task data physical addresses')
        self.intersect_ip.write(self.ADDR_I_RNUMBER_DATA, num_rays)
        self.intersect_ip.write(self.ADDR_I_RDATA_DATA, self._rays.physical_address)
        
        self.intersect_ip.write(self.ADDR_O_TIDS_DATA, self._out_ids.physical_address)
        self.intersect_ip.write(self.ADDR_O_TINTERSECTS_DATA, self._out_inter.physical_address)

        ti = time()
        for i, r in enumerate(rays):
            self._rays[i] = r
        log.info(f'{self.name}: Ray arrays filled in {time() - ti} seconds')

        log.info(f'Starting co-processor {self.name}')
        self.intersect_ip.write(0x00, 1)

    def get_results(self):
        return (self._out_ids.tolist(), self._out_inter.tolist())


class TracerCPU(TracerPYNQ):
    def __init__(self, tracer_id, use_multicore: bool):
        super().__init__(tracer_id)
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
            ids, intersects = cpp_tracer.computeParallel(
                rays, self.tri_ids, self.tris)
        else: 
            # CPP without parallelism
            ids, intersects = cpp_tracer.compute(
                rays, self.tri_ids, self.tris)

        return (ids, intersects)


class TracerFPGA(TracerPYNQ):
    def __init__(self, tracer_id, overlay_filename: str, use_multi_fpga: bool = False):
        super().__init__(tracer_id)
        from pynq import Overlay
        self.use_multi_fpga = use_multi_fpga
        self.accelerators = []

        #overlay = Overlay('/home/xilinx/adrianno/intersect_fpga_x2.bit')
        overlay = Overlay(overlay_filename)
        log.warning('Finished loading overlay')
        
        log.info('Initializing FPGA instances')
        self.accelerators.append(
            XIntersectFPGA(overlay.intersectFPGA_0, 'accel_0'))

        if use_multi_fpga:
            log.info('Using multi-accelerator mode')
            self.accelerators.append(
                XIntersectFPGA(overlay.intersectFPGA_1, 'accel_1'))


    def set_scene(self, tri_ids, tris):
        for accel in self.accelerators:
            accel.set_scene(tri_ids, tris)

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
                rays[ : 6*(num_rays//2)])

            self.accelerators[1].compute(
                rays[6*(num_rays//2) : ])
        else:
            self.accelerators[0].compute(rays)
        
        while not self.is_done():
            sleep(0.2)

        return self.get_results()



class TracerCloud(TracerPYNQ, ClientTCP):
    def __init__(self, tracer_id, cloud_addr, config):
        super().__init__(tracer_id)
        self.cloud_addr = cloud_addr
        self.config = config
        self.compression = config['networking']['compression']

        

    def shutdown(self):
        self.connect(self.cloud_addr)
        compression = self.config['networking']['compression']
        self.send_msg('EXIT', compression)


    def set_scene(self, tri_ids, triangles):
        self.connect(self.cloud_addr)
        scene = f'{len(tri_ids)}\n'
        scene += f"{' '.join(map(str, tri_ids))} "
        scene += f"{' '.join(map(str, triangles))}"
        self.send_msg(scene, self.compression)

    def send_task(self, task):
        task_msg = f'{task.id}\n'
        task_msg += f"{' '.join(task.ray_data)}"
        self.send_msg(task_msg, self.compression)

    def receive_result(self):
        res = self.recv_msg(self.compression).split()
        task_id = int(res[0])
        num_rays = int(res[1])
        out_ids = res[2:num_rays+2]
        out_inter = res[num_rays+2:]
        return TaskResult(task_id, out_ids, out_inter)

    def start(self, result_queue, task_queues, main_queue_id, allow_stealing=False, report_queue=None):
        report = TracerSummary(self)
        chunk_size = self.config['processing']['cloud']['task_chunk_size']
        self.active_queues= [True for _ in task_queues]
        finished, start_stealing = False, False
        while not finished:
            task_counter = 0
            print(*map(lambda x : x.qsize(), task_queues))
            super_task = SuperTask()
            for i in range(chunk_size):
                task = self.get_task(task_queues, main_queue_id, start_stealing)
                if task is not None:
                    report.increment()
                    super_task.add_task(task)
                    task_counter += 1
                else:
                    if not allow_stealing or not np.any(self.active_queues):
                        finished = True
                    else:
                        print(f'{type(self).__name__}: Start stealing...')
                        start_stealing = True
                    break
            self.send_task(super_task)
            result = super_task.separate_results(self.receive_result())
            for r in result:
                result_queue.put(r)
        self.send_msg('END', self.compression)
        if report_queue is not None: report_queue.put(report)
        result_queue.put(None)

