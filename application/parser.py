class Parser:
    def __init__(self, *args, **kwargs):
        import argparse

        self.parser = argparse.ArgumentParser(
            description='Request Ray-Triangle computations to the Fog.')

        self.parser.add_argument(
            '--mode', 
            choices=['client', 'edge', 'cloud', 'shutdown_edge', 'shutdown_all'],
            help='File containing the ray geometric information')

        self.parser.add_argument(
            '--res',
            type=int,
            nargs=2,
            help='Resolution of the final image')

        self.parser.add_argument(
            '--psize',
            type=float,
            help='Pixel size')

        self.parser.add_argument(
            '--task-size',
            type=int,
            help='Maximum size of an edge task')

        self.parser.add_argument(
            '--task-chunk-size',
            type=int,
            help='Number of simultaneous tasks to be processed on the cloud')

        self.parser.add_argument(
            '--multiqueue',
            action='store_true',
            help='Use multiple queues on the edge')

        self.parser.add_argument(
            '--send-cam',
            action='store_true',
            help='Send camera to the edge instead of the rays')

        self.parser.add_argument(
            '--config',
            type=str,
            help='Name of a configuration json file. [default.json if empty]')

        self.args = self.parser.parse_args()
