import sys
import json

def is_close(a, b, tol):
	return abs(a - b) < tol

def compare(filename1, filename2):
	expected_file = open(filename1, 'r')
	obtained_file = open(filename2, 'r')

	expected_values = json.load(expected_file)
	obtained_values = json.load(obtained_file)

	expected_inter	= expected_values['intersections']
	expected_ids	= expected_values['triangles_hit']
	obtained_inter	= obtained_values['intersections']
	obtained_ids	= obtained_values['triangles_hit']

	data = zip(
		expected_inter, 
		expected_ids,
		obtained_inter, 
		obtained_ids)	

	error_count = 0
	ray_id = 0
	for exp_int, exp_id, ob_int, ob_id in data:
		if exp_id != ob_id:
			print(f'At ray {ray_id}: obtained id ({ob_id}) is different from  expected id ({exp_id})')
			error_count+=1
		elif not is_close(exp_int, ob_int, 1e-3):
			print(f'At ray {ray_id}: obtained intersection ({ob_int}) is not close enough to expected ({exp_int})')
			error_count+=1
		ray_id += 1
	return error_count == 0

if __name__ == '__main__':
	if len(sys.argv) != 3:
		print('Error: Incorrect arguments')
		print('Usage: convert.py <intersects-file> <json-file>')
		sys.exit(1)
	sys.exit(compare(sys.argv[1], sys.argv[2]))