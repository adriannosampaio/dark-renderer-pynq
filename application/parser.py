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
            '--mode', 
            choices=['client', 'edge', 'master', 'node'],
            help='File containing the ray geometric information')

        self.args = self.parser.parse_args()