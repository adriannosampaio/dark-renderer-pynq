#ifndef _TRACER_H_
#define _TRACER_H_



#ifdef DEBUG
#include <iostream>
#define PRINT_VAR(V) std::cout << #V << " = " << V << '\n'
#define PRINT_VEC3(VEC)  			\
	std::cout << #VEC << " = (";	\
	for(int i=0;i<3;i++) 			\
		std::cout << VEC[i] << " "; \
	std::cout << #VEC << ")\n" 		\
#else
#define PRINT_VAR(V)
#define PRINT_VEC3(VEC)
#endif

#define EPSILON 1.0e-6
#define INFINITY 1.0e9
#define TRIANGLE_ATTR_NUMBER 9
#define RAY_ATTR_NUMBER 6

#define COORDS 3
#define VEC3(NAME) double NAME[COORDS]
#define ASSIGN(VL, VR) (VL)[0] = (VR)[0]; (VL)[1] = (VR)[1]; (VL)[2] = (VR)[2]
#define DOT(V1, V2) (V1[0]*V2[0] + V1[1]*V2[1] + V1[2]*V2[2])
#define CROSS(VR, V1, V2) \
	VR[0] = V1[1] * V2[2] - V1[2] * V2[1], \
	VR[1] = V1[2] * V2[0] - V1[0] * V2[2], \
	VR[2] = V1[0] * V2[1] - V1[1] * V2[0]
#define SUB(VR, V1, V2) 	\
	VR[0] = V1[0] - V2[0]; 	\
	VR[1] = V1[1] - V2[1]; 	\
	VR[2] = V1[2] - V2[2]

#define SUM(VR, V1, V2) 	\
	VR[0] = V1[0] + V2[0]; 	\
	VR[1] = V1[1] + V2[1]; 	\
	VR[2] = V1[2] + V2[2]

#define SCALAR_MULTIPLY(V, C) \
     V[0]*= C;  \
     V[1]*= C;  \
     V[2]*= C

std::vector<double> generate_primary_rays(
    std::vector<int> resolution,
    std::vector<double> eye_point,
    std::vector<double> look_point,
    std::vector<double> up_vector,
    double distance,
    double pixel_size);
#endif