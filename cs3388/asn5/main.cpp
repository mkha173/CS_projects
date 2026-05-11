#include <GL/glew.h>
#include <GLFW/glfw3.h>

#include <glm/glm.hpp>
#include <glm/gtc/matrix_transform.hpp>
#include <glm/gtc/type_ptr.hpp>

#include <cmath>
#include <functional>
#include <iostream>
#include <string>
#include <vector>

#include "MarchingCubes.h"

static int WIN_W = 900, WIN_H = 900;

static float camR     = 8.6603f;
static float camTheta = glm::radians(45.0f);
static float camPhi   = glm::radians(54.7356f);

static bool   mouseDown = false;
static double lastMouseX = 0.0, lastMouseY = 0.0;

static const float MOUSE_SENS = 0.005f;
static const float R_STEP     = 0.3f;
static const float R_MIN      = 0.5f;

static int activeMesh = 0;

static glm::vec3 camPosition() {
    float sinPhi = sinf(camPhi);
    float cosPhi = cosf(camPhi);
    float sinTh  = sinf(camTheta);
    float cosTh  = cosf(camTheta);
    return { camR * sinPhi * cosTh,
             camR * cosPhi,
             camR * sinPhi * sinTh };
}

static void cb_mouseButton(GLFWwindow*, int btn, int action, int) {
    if (btn == GLFW_MOUSE_BUTTON_LEFT)
        mouseDown = (action == GLFW_PRESS);
}

static void cb_cursorPos(GLFWwindow*, double x, double y) {
    if (mouseDown) {
        double dx = x - lastMouseX;
        double dy = y - lastMouseY;
        camTheta += (float)(dx * MOUSE_SENS);
        camPhi   -= (float)(dy * MOUSE_SENS);
        const float EPS = 0.01f;
        camPhi = glm::clamp(camPhi, EPS, (float)M_PI - EPS);
    }
    lastMouseX = x;
    lastMouseY = y;
}

static void cb_key(GLFWwindow* w, int key, int, int action, int) {
    if (action == GLFW_PRESS || action == GLFW_REPEAT) {
        if (key == GLFW_KEY_UP)
            camR = std::max(R_MIN, camR - R_STEP);
        if (key == GLFW_KEY_DOWN)
            camR += R_STEP;
        if (key == GLFW_KEY_TAB) {
            activeMesh = 1 - activeMesh;
            std::cout << "Showing field " << (activeMesh + 1) << "\n";
        }
        if (key == GLFW_KEY_ESCAPE)
            glfwSetWindowShouldClose(w, GLFW_TRUE);
    }
}

static void cb_resize(GLFWwindow*, int w, int h) {
    WIN_W = w; WIN_H = h;
    glViewport(0, 0, w, h);
}

static GLuint compileShader(GLenum type, const char* src) {
    GLuint s = glCreateShader(type);
    glShaderSource(s, 1, &src, nullptr);
    glCompileShader(s);
    GLint ok; glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char buf[1024]; glGetShaderInfoLog(s, 1024, nullptr, buf);
        std::cerr << "Shader compile error:\n" << buf << "\n";
    }
    return s;
}

static GLuint linkProgram(const char* vsrc, const char* fsrc) {
    GLuint p = glCreateProgram();
    GLuint v = compileShader(GL_VERTEX_SHADER,   vsrc);
    GLuint f = compileShader(GL_FRAGMENT_SHADER, fsrc);
    glAttachShader(p, v); glAttachShader(p, f);
    glLinkProgram(p);
    GLint ok; glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) {
        char buf[1024]; glGetProgramInfoLog(p, 1024, nullptr, buf);
        std::cerr << "Program link error:\n" << buf << "\n";
    }
    glDeleteShader(v); glDeleteShader(f);
    return p;
}

static const char* VS_PHONG = R"GLSL(
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNorm;

uniform mat4 MVP;
uniform mat4 V;
uniform vec3 LightDir;

out vec3 vNormal_cam;
out vec3 vEyeDir_cam;
out vec3 vLightDir_cam;

void main() {
    gl_Position = MVP * vec4(aPos, 1.0);

    mat3 normalMat = mat3(transpose(inverse(V)));
    vNormal_cam = normalize(normalMat * aNorm);

    vec3 pos_cam = vec3(V * vec4(aPos, 1.0));

    vEyeDir_cam   = normalize(-pos_cam);

    vLightDir_cam = normalize(mat3(V) * normalize(LightDir));
}
)GLSL";

static const char* FS_PHONG = R"GLSL(
#version 330 core
in vec3 vNormal_cam;
in vec3 vEyeDir_cam;
in vec3 vLightDir_cam;

uniform vec3 modelColor;

out vec4 fragColour;

void main() {
    vec3 ambientColor  = vec3(0.2, 0.2, 0.2);
    vec3 specularColor = vec3(1.0, 1.0, 1.0);
    float shininess    = 64.0;

    vec3 N = normalize(vNormal_cam);
    vec3 L = normalize(vLightDir_cam);
    vec3 E = normalize(vEyeDir_cam);
    vec3 R = reflect(-L, N);

    float diff = max(dot(N, L), 0.0);
    float spec = pow(max(dot(E, R), 0.0), shininess);

    vec3 colour = ambientColor  * modelColor
                + diff          * modelColor
                + spec          * specularColor;

    fragColour = vec4(colour, 1.0);
}
)GLSL";

static const char* VS_FLAT = R"GLSL(
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aColour;
uniform mat4 MVP;
out vec3 vColour;
void main() {
    gl_Position = MVP * vec4(aPos, 1.0);
    vColour = aColour;
}
)GLSL";

static const char* FS_FLAT = R"GLSL(
#version 330 core
in vec3 vColour;
out vec4 fragColour;
void main() { fragColour = vec4(vColour, 1.0); }
)GLSL";

struct Mesh {
    GLuint vao = 0, vbo = 0;
    int    count = 0;
    glm::vec3 colour{0.0f, 0.8f, 0.8f};
};

static void uploadMesh(Mesh& m,
                       const std::vector<float>& verts,
                       const std::vector<float>& norms)
{
    int n = (int)verts.size() / 3;
    std::vector<float> buf;
    buf.reserve(n * 6);
    for (int i = 0; i < n; i++) {
        buf.push_back(verts[i*3+0]); buf.push_back(verts[i*3+1]); buf.push_back(verts[i*3+2]);
        buf.push_back(norms[i*3+0]); buf.push_back(norms[i*3+1]); buf.push_back(norms[i*3+2]);
    }
    if (m.vao == 0) { glGenVertexArrays(1, &m.vao); glGenBuffers(1, &m.vbo); }
    glBindVertexArray(m.vao);
    glBindBuffer(GL_ARRAY_BUFFER, m.vbo);
    glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)(buf.size() * sizeof(float)), buf.data(), GL_STATIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)(3 * sizeof(float)));
    glBindVertexArray(0);
    m.count = n;
}

struct Lines {
    GLuint vao = 0, vbo = 0;
    int count = 0;
};

static void uploadLines(Lines& L, const std::vector<float>& data) {
    if (L.vao == 0) { glGenVertexArrays(1, &L.vao); glGenBuffers(1, &L.vbo); }
    glBindVertexArray(L.vao);
    glBindBuffer(GL_ARRAY_BUFFER, L.vbo);
    glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)(data.size() * sizeof(float)), data.data(), GL_STATIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)(3 * sizeof(float)));
    glBindVertexArray(0);
    L.count = (int)data.size() / 6;
}

static std::vector<float> buildWireframe(float mn, float mx) {
    std::vector<float> v;

    auto pt = [&](float x, float y, float z, float r, float g, float b) {
        v.insert(v.end(), {x, y, z, r, g, b});
    };
    auto edge = [&](float ax,float ay,float az,
                    float bx,float by,float bz,
                    float r, float g, float b) {
        pt(ax,ay,az, r,g,b);
        pt(bx,by,bz, r,g,b);
    };

    edge(mn,mn,mn,  mx,mn,mn,  1,1,1);
    edge(mx,mn,mn,  mx,mn,mx,  1,1,1);
    edge(mx,mn,mx,  mn,mn,mx,  1,1,1);
    edge(mn,mn,mx,  mn,mn,mn,  1,1,1);
    edge(mn,mx,mn,  mx,mx,mn,  1,1,1);
    edge(mx,mx,mn,  mx,mx,mx,  1,1,1);
    edge(mx,mx,mx,  mn,mx,mx,  1,1,1);
    edge(mn,mx,mx,  mn,mx,mn,  1,1,1);
    edge(mn,mn,mn,  mn,mx,mn,  1,1,1);
    edge(mx,mn,mn,  mx,mx,mn,  1,1,1);
    edge(mx,mn,mx,  mx,mx,mx,  1,1,1);
    edge(mn,mn,mx,  mn,mx,mx,  1,1,1);

    float len = mx - mn;
    edge(mn,mn,mn,  mn+len,mn,mn,  1,0,0);
    edge(mn,mn,mn,  mn,mn+len,mn,  0,1,0);
    edge(mn,mn,mn,  mn,mn,mn+len,  0,0,1);

    return v;
}

int main() {
    if (!glfwInit()) {
        std::cerr << "GLFW init failed\n"; return 1;
    }
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
#ifdef __APPLE__
    glfwWindowHint(GLFW_OPENGL_FORWARD_COMPAT, GL_TRUE);
#endif

    GLFWwindow* win = glfwCreateWindow(WIN_W, WIN_H,
                                       "CS3388 A5 – Marching Cubes", nullptr, nullptr);
    if (!win) { std::cerr << "Window creation failed\n"; glfwTerminate(); return 1; }
    glfwMakeContextCurrent(win);

    glfwSetMouseButtonCallback(win, cb_mouseButton);
    glfwSetCursorPosCallback  (win, cb_cursorPos);
    glfwSetKeyCallback        (win, cb_key);
    glfwSetFramebufferSizeCallback(win, cb_resize);

    glewExperimental = GL_TRUE;
    if (glewInit() != GLEW_OK) {
        std::cerr << "GLEW init failed\n"; return 1;
    }
    glEnable(GL_DEPTH_TEST);

    GLuint phongProg = linkProgram(VS_PHONG, FS_PHONG);
    GLuint flatProg  = linkProgram(VS_FLAT,  FS_FLAT);

    auto field1 = [](float x, float y, float z) -> float {
        return y - sinf(x) * cosf(z);
    };
    auto field2 = [](float x, float y, float z) -> float {
        return x*x - y*y - z*z - z;
    };

    const float GRID_MIN  = -2.5f;
    const float GRID_MAX  =  2.5f;
    const float GRID_STEP =  0.05f;

    std::cout << "Running marching cubes for field 1 (y − sin(x)cos(z), iso=0)...\n";
    auto verts1 = marching_cubes(field1, 0.0f,  GRID_MIN, GRID_MAX, GRID_STEP);
    auto norms1 = compute_normals(verts1);
    writePLY(verts1, norms1, "field1.ply");

    std::cout << "Running marching cubes for field 2 (x²−y²−z²−z, iso=-1.5)...\n";
    auto verts2 = marching_cubes(field2, -1.5f, GRID_MIN, GRID_MAX, GRID_STEP);
    auto norms2 = compute_normals(verts2);
    writePLY(verts2, norms2, "field2.ply");

    Mesh mesh1, mesh2;
    mesh1.colour = glm::vec3(0.0f, 0.8f, 0.8f);
    mesh2.colour = glm::vec3(0.0f, 0.8f, 0.8f);
    uploadMesh(mesh1, verts1, norms1);
    uploadMesh(mesh2, verts2, norms2);

    Lines lines;
    auto wireData = buildWireframe(GRID_MIN, GRID_MAX);
    uploadLines(lines, wireData);

    glm::vec3 lightDir = glm::normalize(glm::vec3(1.0f, 2.0f, 1.0f));

    while (!glfwWindowShouldClose(win)) {
        glClearColor(0.16f, 0.15f, 0.22f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

        float aspect = (WIN_H > 0) ? (float)WIN_W / (float)WIN_H : 1.0f;
        glm::mat4 P   = glm::perspective(glm::radians(45.0f), aspect, 0.1f, 200.0f);
        glm::mat4 V   = glm::lookAt(camPosition(), glm::vec3(0,0,0), glm::vec3(0,1,0));
        glm::mat4 M   = glm::mat4(1.0f);
        glm::mat4 MVP = P * V * M;

        glUseProgram(phongProg);
        glUniformMatrix4fv(glGetUniformLocation(phongProg, "MVP"), 1, GL_FALSE, glm::value_ptr(MVP));
        glUniformMatrix4fv(glGetUniformLocation(phongProg, "V"),   1, GL_FALSE, glm::value_ptr(V));
        glUniform3fv(glGetUniformLocation(phongProg, "LightDir"),  1, glm::value_ptr(lightDir));

        Mesh& cur = (activeMesh == 0) ? mesh1 : mesh2;
        glUniform3fv(glGetUniformLocation(phongProg, "modelColor"), 1, glm::value_ptr(cur.colour));

        glBindVertexArray(cur.vao);
        glDrawArrays(GL_TRIANGLES, 0, cur.count);
        glBindVertexArray(0);

        glUseProgram(flatProg);
        glUniformMatrix4fv(glGetUniformLocation(flatProg, "MVP"), 1, GL_FALSE, glm::value_ptr(MVP));
        glBindVertexArray(lines.vao);
        glDrawArrays(GL_LINES, 0, lines.count);
        glBindVertexArray(0);

        glfwSwapBuffers(win);
        glfwPollEvents();
    }

    glfwDestroyWindow(win);
    glfwTerminate();
    return 0;
}