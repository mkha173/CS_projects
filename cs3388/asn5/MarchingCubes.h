#pragma once
#include <functional>
#include <vector>
#include <string>

std::vector<float> marching_cubes(
    std::function<float(float,float,float)> f,
    float isovalue,
    float min,
    float max,
    float stepsize);

std::vector<float> compute_normals(const std::vector<float>& verts);

void writePLY(const std::vector<float>& verts,
              const std::vector<float>& normals,
              const std::string& fileName);
