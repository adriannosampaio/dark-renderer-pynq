class Parser:
    def __init__(self, *args, **kwargs):
        import argparse

        self.parser = argparse.ArgumentParser(
            description='Request Ray-Triangle computations to the Fog.')

        self.parser.add_argument(
            '-f', 
            type=str,
            help='File containing the scene information')

        self.parser.add_argument(
            '-o', 
            type=str,
            help='Output file')

        self.parser.add_argument(
            '--fpga-load-fraction', 
            type=float,
            help='Workload fraction passed to the FPGA computation')

        self.parser.add_argument(
            '--mode', 
            choices=['client', 'edge', 'master', 'node'],
            help='File containing the ray geometric information')

        self.parser.add_argument(
            '--use-python',
            action='store_true')

        self.parser.add_argument(
            '--use-multicore',
            action='store_true')

        self.parser.add_argument(
            '--use-fpga',
            action='store_true')

        self.parser.add_argument(
            '--use-multi-fpga',
            action='store_true')

        self.parser.add_argument(
            '--use-heterogeneous',
            action='store_true')

        self.args = self.parser.parse_args()


    def _logic_validation(self):
        ag = self.args