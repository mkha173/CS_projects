Muhammad Saad Khan 251309919
cs 3388 asn 5
----------------------------------------------------------------------------------------------------

What's Implemented:

Marching Cubes– iterates a voxel grid over [min, max]³, evaluates a scalar field at each cube's 8 corners, and creates triangles via edge interpolation and a triangle lookup table.
Normal Computation – per triangle face normals via cross product, same normal assigned to all 3 vertices.
*PLY Export – ASCII PLY with vertex positions, normals, and face indices.
Camera – spherical coordinates (r, θ, φ), initially positioned at (5, 5, 5).
Phong Shading – ambient + diffuse + specular (shininess = 64), cyan model colour.
Wireframe Overlay – white bounding box, RGB axis lines.

Controls:

left-click + drag = rotate camera
arrow up = zoom in
arrow down = zoom out
tab = switch between fields
esc = quit

Dependencies: GLEW, GLFW3, GLM, CMake ≥ 3.15, C++17

Building instructions:
make
./a5

The two PLY files (`field1.ply`, `field2.ply`) are written to the working
directory when the program starts.

---

Scalar Fields Used

| Field | Function | Isovalue |
|---|---|---|
| 1 | y − sin(x)cos(z) | 0 |
| 2 | x² − y² − z² − z | −1.5 |

Grid: [−2.5, 2.5]³, step = 0.05.
