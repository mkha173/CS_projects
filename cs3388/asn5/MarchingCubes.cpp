
#include "MarchingCubes.h"
#include "TriTable.hpp"

#include <glm/glm.hpp>
#include <cmath>
#include <fstream>
#include <iostream>

static const int edgeTable[256] = {
0x000,0x109,0x203,0x30a,0x406,0x50f,0x605,0x70c,
0x80c,0x905,0xa0f,0xb06,0xc0a,0xd03,0xe09,0xf00,
0x190,0x099,0x393,0x29a,0x596,0x49f,0x795,0x69c,
0x99c,0x895,0xb9f,0xa96,0xd9a,0xc93,0xf99,0xe90,
0x230,0x339,0x033,0x13a,0x636,0x73f,0x435,0x53c,
0xa3c,0xb35,0x83f,0x936,0xe3a,0xf33,0xc39,0xd30,
0x3a0,0x2a9,0x1a3,0x0aa,0x7a6,0x6af,0x5a5,0x4ac,
0xbac,0xaa5,0x9af,0x8a6,0xfaa,0xea3,0xda9,0xca0,
0x460,0x569,0x663,0x76a,0x066,0x16f,0x265,0x36c,
0xc6c,0xd65,0xe6f,0xf66,0x86a,0x963,0xa69,0xb60,
0x5f0,0x4f9,0x7f3,0x6fa,0x1f6,0x0ff,0x3f5,0x2fc,
0xdfc,0xcf5,0xfff,0xef6,0x9fa,0x8f3,0xbf9,0xaf0,
0x650,0x759,0x453,0x55a,0x256,0x35f,0x055,0x15c,
0xe5c,0xf55,0xc5f,0xd56,0xa5a,0xb53,0x859,0x950,
0x7c0,0x6c9,0x5c3,0x4ca,0x3c6,0x2cf,0x1c5,0x0cc,
0xfcc,0xec5,0xdcf,0xcc6,0xbca,0xac3,0x9c9,0x8c0,
0x8c0,0x9c9,0xac3,0xbca,0xcc6,0xdcf,0xec5,0xfcc,
0x0cc,0x1c5,0x2cf,0x3c6,0x4ca,0x5c3,0x6c9,0x7c0,
0x950,0x859,0xb53,0xa5a,0xd56,0xc5f,0xf55,0xe5c,
0x15c,0x055,0x35f,0x256,0x55a,0x453,0x759,0x650,
0xaf0,0xbf9,0x8f3,0x9fa,0xef6,0xfff,0xcf5,0xdfc,
0x2fc,0x3f5,0x0ff,0x1f6,0x6fa,0x7f3,0x4f9,0x5f0,
0xb60,0xa69,0x963,0x86a,0xf66,0xe6f,0xd65,0xc6c,
0x36c,0x265,0x16f,0x066,0x76a,0x663,0x569,0x460,
0xca0,0xda9,0xea3,0xfaa,0x8a6,0x9af,0xaa5,0xbac,
0x4ac,0x5a5,0x6af,0x7a6,0x0aa,0x1a3,0x2a9,0x3a0,
0xd30,0xc39,0xf33,0xe3a,0x936,0x835,0xb3f,0xa36,
0x53c,0x435,0x73f,0x636,0x13a,0x033,0x339,0x230,
0xe90,0xf99,0xc93,0xd9a,0xa96,0xb9f,0x895,0x99c,
0x69c,0x795,0x49f,0x596,0x29a,0x393,0x099,0x190,
0xf00,0xe09,0xd03,0xc0a,0xb06,0xa0f,0x905,0x80c,
0x70c,0x605,0x50f,0x406,0x30a,0x203,0x109,0x000
};

static glm::vec3 interpEdge(float iso,
                             glm::vec3 p1, float v1,
                             glm::vec3 p2, float v2)
{
    if (fabsf(v2 - v1) < 1e-8f) return p1;
    float t = (iso - v1) / (v2 - v1);
    return p1 + t * (p2 - p1);
}

std::vector<float> marching_cubes(
    std::function<float(float,float,float)> f,
    float isovalue,
    float mn, float mx, float stepsize)
{
    std::vector<float> result;
    result.reserve(1 << 18);

    for (float x = mn; x < mx - stepsize * 0.5f; x += stepsize) {
        for (float y = mn; y < mx - stepsize * 0.5f; y += stepsize) {
            for (float z = mn; z < mx - stepsize * 0.5f; z += stepsize) {

                float x1 = x + stepsize;
                float y1 = y + stepsize;
                float z1 = z + stepsize;

                glm::vec3 c[8] = {
                    {x,  y,  z },
                    {x1, y,  z },
                    {x1, y,  z1},
                    {x,  y,  z1},
                    {x,  y1, z },
                    {x1, y1, z },
                    {x1, y1, z1},
                    {x,  y1, z1}
                };
                float v[8];
                for (int i = 0; i < 8; i++)
                    v[i] = f(c[i].x, c[i].y, c[i].z);

                int cubeIdx = 0;
                for (int i = 0; i < 8; i++)
                    if (v[i] < isovalue) cubeIdx |= (1 << i);

                if (edgeTable[cubeIdx] == 0) continue;

                glm::vec3 ev[12];
                int et = edgeTable[cubeIdx];
                if (et & 0x001) ev[0]  = interpEdge(isovalue, c[0],v[0], c[1],v[1]);
                if (et & 0x002) ev[1]  = interpEdge(isovalue, c[1],v[1], c[2],v[2]);
                if (et & 0x004) ev[2]  = interpEdge(isovalue, c[2],v[2], c[3],v[3]);
                if (et & 0x008) ev[3]  = interpEdge(isovalue, c[3],v[3], c[0],v[0]);
                if (et & 0x010) ev[4]  = interpEdge(isovalue, c[4],v[4], c[5],v[5]);
                if (et & 0x020) ev[5]  = interpEdge(isovalue, c[5],v[5], c[6],v[6]);
                if (et & 0x040) ev[6]  = interpEdge(isovalue, c[6],v[6], c[7],v[7]);
                if (et & 0x080) ev[7]  = interpEdge(isovalue, c[7],v[7], c[4],v[4]);
                if (et & 0x100) ev[8]  = interpEdge(isovalue, c[0],v[0], c[4],v[4]);
                if (et & 0x200) ev[9]  = interpEdge(isovalue, c[1],v[1], c[5],v[5]);
                if (et & 0x400) ev[10] = interpEdge(isovalue, c[2],v[2], c[6],v[6]);
                if (et & 0x800) ev[11] = interpEdge(isovalue, c[3],v[3], c[7],v[7]);

                for (int i = 0; marching_cubes_lut[cubeIdx][i] != -1; i += 3) {
                    for (int j = 0; j < 3; j++) {
                        const glm::vec3& p = ev[marching_cubes_lut[cubeIdx][i + j]];
                        result.push_back(p.x);
                        result.push_back(p.y);
                        result.push_back(p.z);
                    }
                }
            }
        }
    }
    return result;
}

std::vector<float> compute_normals(const std::vector<float>& verts)
{
    std::vector<float> norms(verts.size(), 0.0f);
    int numTris = (int)verts.size() / 9;

    for (int i = 0; i < numTris; i++) {
        glm::vec3 a(verts[i*9+0], verts[i*9+1], verts[i*9+2]);
        glm::vec3 b(verts[i*9+3], verts[i*9+4], verts[i*9+5]);
        glm::vec3 c(verts[i*9+6], verts[i*9+7], verts[i*9+8]);

        glm::vec3 n = glm::normalize(glm::cross(b - a, c - a));

        for (int v = 0; v < 3; v++) {
            norms[i*9 + v*3 + 0] = n.x;
            norms[i*9 + v*3 + 1] = n.y;
            norms[i*9 + v*3 + 2] = n.z;
        }
    }
    return norms;
}

void writePLY(const std::vector<float>& verts,
              const std::vector<float>& normals,
              const std::string& fileName)
{
    int numVerts = (int)verts.size() / 3;
    int numFaces = numVerts / 3;

    std::ofstream f(fileName);
    if (!f) { std::cerr << "writePLY: cannot open " << fileName << "\n"; return; }

    f << "ply\n"
      << "format ascii 1.0\n"
      << "element vertex " << numVerts << "\n"
      << "property float x\n"
      << "property float y\n"
      << "property float z\n"
      << "property float nx\n"
      << "property float ny\n"
      << "property float nz\n"
      << "element face " << numFaces << "\n"
      << "property list uchar int vertex_indices\n"
      << "end_header\n";

    for (int i = 0; i < numVerts; i++) {
        f << verts[i*3+0]   << " " << verts[i*3+1]   << " " << verts[i*3+2]   << " "
          << normals[i*3+0] << " " << normals[i*3+1] << " " << normals[i*3+2] << "\n";
    }

    for (int i = 0; i < numFaces; i++) {
        f << "3 " << i*3 << " " << i*3+1 << " " << i*3+2 << "\n";
    }

    std::cout << "Wrote " << fileName
              << "  (" << numVerts << " verts, " << numFaces << " faces)\n";
}
