import sys
import json

if len(sys.argv) != 3:
	print('Error: Incorrect arguments')
	print('Usage: convert.py <intersects-file> <json-file>')
	sys.exit(1)

input_file = sys.argv[1]
output_file = sys.argv[2]

out = {}
out['intersections'] = []
out['triangles_hit'] = []

with open(input_file, 'r') as file:
	for line in file:
		tid, tint = line.split()
		out['intersections'].append(float(tint))
		out['hit_triangles'].append(int(tid))

with open(output_file, 'w') as file:
	file.write(json.dumps(out))