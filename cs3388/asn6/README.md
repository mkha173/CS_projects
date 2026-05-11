# CS3388 Assignment 6 - Unity Water Scene

## How to run

1. Open the project in Unity 2022 LTS (Built-in Render Pipeline).
2. Open Assets/Scenes/WaterScene.unity.
3. Press Play.

## Scene setup (if building from scratch)

1. Create an empty GameObject named WaterRoot. Add MeshFilter, MeshRenderer, GridMeshGenerator, WaterController. Assign the water material.
2. Set WaterController's Target Renderer to the same MeshRenderer.
3. Add a Directional Light rotated around (-50, 30, 0).
4. Create a floating object (e.g. a capsule). Add FloatingObjectController and drag WaterRoot into the Water field.
5. Add a camera with CameraController attached. Set Target to WaterRoot.

## Controls

- Orbit rotate: hold right mouse + move
- Orbit zoom: scroll wheel
- Free fly move: WASD
- Free fly up/down: E / Q
- Free fly sprint: hold Left Shift
- Free fly look: hold right mouse + move

## What each script does

GridMeshGenerator - builds a flat grid mesh at runtime over the XZ plane. Resolution, size, and UV scale are set in the Inspector.

WaterController - stores four Gerstner wave definitions and evaluates them on both the CPU (for the floating object) and GPU (via MaterialPropertyBlock sent to the shader each frame). Also handles the detail texture scroll parameters.

FloatingObjectController - each frame samples the same wave function as the shader to get the water height at the object's position, then lerps the object up/down and tilts it to match the surface normal.

CameraController - provided script. Supports orbit mode and free-fly mode.

Water.shader - vertex stage displaces the mesh using Gerstner waves and a scrolling detail texture. Fragment stage runs ambient + diffuse + specular lighting with depth-based colour blending and a fresnel alpha boost.

## OpenGL to Unity mapping

- Tessellation -> dense procedural mesh from GridMeshGenerator
- Geometry shader displacement -> vertex shader in Water.shader
- Displacement mapping -> scrolling noise texture sampled in vertex stage
- Normal recalculation -> finite difference normal in vertex shader
- Phong lighting -> ambient + diffuse + specular in fragment shader
- Camera -> CameraController (orbit and free-fly modes)


