#include <cmath>
#include <vector>
#include <tuple>
#include <iostream>

#include "utils.hpp"


int normalize(double* vec){
    double norm = sqrt(DOT(vec, vec));
    vec[0] /= norm;
    vec[1] /= norm;
    vec[2] /= norm;
    return 0;
}

/** This free function is responsible for creating a list of
*   primary rays from given camera parameters.
*/
std::vector<double> generate_primary_rays(
    std::vector<int> resolution,
    std::vector<double> eye_point,
    std::vector<double> look_point,
    std::vector<double> up_vector,
    double distance,
    double pixel_size)
{
    double u[3], v[3], w[3];

    SUB(w, eye_point, look_point);
    normalize(w);

    CROSS(u, w, up_vector);
    normalize(u);

    CROSS(v, w, u);

    int number_of_rays = resolution[0] * resolution[1];

    int vres = resolution[0],
        hres = resolution[1];

    std::vector<double> result;
    result.reserve((number_of_rays) * RAY_ATTR_NUMBER);

    // Temporary vectors for the ray direction calculation
    double xvtu[3], yvtv[3], dstw[3], ray_dir[3];

    for (int r = 0; r < vres; r++) {
        for (int c = 0; c < hres; c++) {

            for (int i = 0; i < 3; i ++)
                result.push_back(eye_point[i]);

            double xv = pixel_size * double(c - (hres / 2));
            double yv = pixel_size * double(r - (vres / 2));
            
            ASSIGN(xvtu, u);
            ASSIGN(yvtv, v);
            ASSIGN(dstw, w);

            for (int i = 0; i < 3; i++){
                ray_dir[i] = xv*u[i] + yv*v[i] - distance*w[i];
            }

            normalize(ray_dir);

            for (double& i : ray_dir)
                result.push_back(i);
        }
    }
    return result;
}