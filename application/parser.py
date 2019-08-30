class Parser:
    def __init__(self, *args, **kwargs):
        import argparse

        self.parser = argparse.ArgumentParser(
            description='Request Ray-Triangle computations to the Fog.')

        self.parser.add_argument(
            '--mode', 
            choices=['client', 'edge', 'cloud', 'shutdown'],
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
            help='Maximum size for processing tasks')

        self.parser.add_argument(
            '--config',
            type=str,
            help='Name of a configuration json file. [default.json if empty]')

        self.args = self.parser.parse_args()
