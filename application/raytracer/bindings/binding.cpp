#include "pybind11/pybind11.h"
#include "pybind11/stl.h"
#include "utils.hpp"

namespace py = pybind11;

PYBIND11_MODULE(utils, m) {
	m.doc() = "Utility functions for ray-tracing"; // optional module docstring
	m.def("generate_rays", &generate_primary_rays, 
        "A function to generate the primary rays "
        "based on a camera specification");
}