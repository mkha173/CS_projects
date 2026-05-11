#include <GL/glew.h>
#include <GLFW/glfw3.h>
#include <glm/glm.hpp>
#include <glm/gtc/matrix_transform.hpp>
#include <glm/gtc/type_ptr.hpp>

#include <stdio.h>
#include <stdlib.h>
#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <iostream>

void loadARGB_BMP(const char* imagepath, unsigned char** data,
                  unsigned int* width, unsigned int* height)
{
    unsigned char header[54];
    unsigned int dataPos, imageSize;

    FILE* file = fopen(imagepath, "rb");
    if (!file) { printf("Cannot open %s\n", imagepath); return; }
    if (fread(header, 1, 54, file) != 54) { printf("Bad BMP\n"); fclose(file); return; }
    if (header[0]!='B' || header[1]!='M') { printf("Not BMP\n"); fclose(file); return; }
    if (*(int*)&(header[0x1E]) != 3)       { printf("Not 32bpp\n"); fclose(file); return; }

    dataPos   = *(int*)&(header[0x0A]);
    imageSize = *(int*)&(header[0x22]);
    *width    = *(int*)&(header[0x12]);
    *height   = *(int*)&(header[0x16]);

    if (imageSize == 0) imageSize = (*width) * (*height) * 4;
    if (dataPos   == 0) dataPos   = 54;

    *data = new unsigned char[imageSize];
    if (dataPos != 54) fread(header, 1, dataPos - 54, file);
    fread(*data, 1, imageSize, file);
    fclose(file);
}

struct VertexData {
    float x=0,y=0,z=0;
    float nx=0,ny=0,nz=0;
    float r=1,g=1,b=1;
    float u=0,v=0;
};

struct TriData {
    unsigned int idx[3];
};

void readPLYFile(const std::string& fname,
                 std::vector<VertexData>& vertices,
                 std::vector<TriData>& faces)
{
    std::ifstream f(fname);
    if (!f.is_open()) { std::cerr << "Cannot open " << fname << "\n"; return; }

    std::string line;
    int numVerts = 0, numFaces = 0;

    std::vector<std::string> props;

    while (std::getline(f, line)) {
        std::istringstream ss(line);
        std::string token;
        ss >> token;

        if (token == "element") {
            std::string kind; int count;
            ss >> kind >> count;
            if (kind == "vertex") numVerts = count;
            else if (kind == "face") numFaces = count;
        } else if (token == "property") {
            std::string type, name;
            ss >> type >> name;
            if (type != "list") props.push_back(name);
        } else if (token == "end_header") {
            break;
        }
    }

    vertices.resize(numVerts);
    for (int i = 0; i < numVerts; i++) {
        std::getline(f, line);
        std::istringstream ss(line);
        for (const auto& p : props) {
            float val; ss >> val;
            if      (p=="x")     vertices[i].x  = val;
            else if (p=="y")     vertices[i].y  = val;
            else if (p=="z")     vertices[i].z  = val;
            else if (p=="nx")    vertices[i].nx = val;
            else if (p=="ny")    vertices[i].ny = val;
            else if (p=="nz")    vertices[i].nz = val;
            else if (p=="red")   vertices[i].r  = val/255.f;
            else if (p=="green") vertices[i].g  = val/255.f;
            else if (p=="blue")  vertices[i].b  = val/255.f;
            else if (p=="u")     vertices[i].u  = val;
            else if (p=="v")     vertices[i].v  = val;
        }
    }

    faces.resize(numFaces);
    for (int i = 0; i < numFaces; i++) {
        std::getline(f, line);
        std::istringstream ss(line);
        int count; ss >> count;
        ss >> faces[i].idx[0] >> faces[i].idx[1] >> faces[i].idx[2];
    }
}

static const char* VS_SRC = R"(
#version 330 core
layout(location=0) in vec3 aPos;
layout(location=1) in vec2 aUV;
out vec2 vUV;
uniform mat4 MVP;
void main(){
    gl_Position = MVP * vec4(aPos, 1.0);
    vUV = aUV;
}
)";

static const char* FS_SRC = R"(
#version 330 core
in vec2 vUV;
out vec4 FragColor;
uniform sampler2D tex;
void main(){
    FragColor = texture(tex, vUV);
}
)";

GLuint compileShader(GLenum type, const char* src) {
    GLuint s = glCreateShader(type);
    glShaderSource(s, 1, &src, nullptr);
    glCompileShader(s);
    GLint ok; glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[512]; glGetShaderInfoLog(s, 512, nullptr, log);
        std::cerr << "Shader error: " << log << "\n";
    }
    return s;
}

GLuint buildProgram() {
    GLuint vs = compileShader(GL_VERTEX_SHADER,   VS_SRC);
    GLuint fs = compileShader(GL_FRAGMENT_SHADER, FS_SRC);
    GLuint prog = glCreateProgram();
    glAttachShader(prog, vs); glAttachShader(prog, fs);
    glLinkProgram(prog);
    glDeleteShader(vs); glDeleteShader(fs);
    return prog;
}

class TexturedMesh {
public:
    GLuint vboPos, vboUV, ebo, tex, vao, prog;
    int numIndices;

    TexturedMesh(const std::string& plyPath, const std::string& bmpPath) {
        std::vector<VertexData> verts;
        std::vector<TriData>    faces;
        readPLYFile(plyPath, verts, faces);

        numIndices = (int)faces.size() * 3;

        std::vector<float> positions, uvs;
        positions.reserve(verts.size()*3);
        uvs.reserve(verts.size()*2);
        for (auto& v : verts) {
            positions.push_back(v.x);
            positions.push_back(v.y);
            positions.push_back(v.z);
            uvs.push_back(v.u);
            uvs.push_back(v.v);
        }
        std::vector<unsigned int> indices;
        indices.reserve(numIndices);
        for (auto& t : faces) {
            indices.push_back(t.idx[0]);
            indices.push_back(t.idx[1]);
            indices.push_back(t.idx[2]);
        }

        prog = buildProgram();
        glGenVertexArrays(1, &vao);
        glBindVertexArray(vao);

        glGenBuffers(1, &vboPos);
        glBindBuffer(GL_ARRAY_BUFFER, vboPos);
        glBufferData(GL_ARRAY_BUFFER, positions.size()*sizeof(float), positions.data(), GL_STATIC_DRAW);
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, nullptr);
        glEnableVertexAttribArray(0);

        glGenBuffers(1, &vboUV);
        glBindBuffer(GL_ARRAY_BUFFER, vboUV);
        glBufferData(GL_ARRAY_BUFFER, uvs.size()*sizeof(float), uvs.data(), GL_STATIC_DRAW);
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 0, nullptr);
        glEnableVertexAttribArray(1);

        glGenBuffers(1, &ebo);
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo);
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.size()*sizeof(unsigned int), indices.data(), GL_STATIC_DRAW);

        glBindVertexArray(0);

        unsigned char* imgData = nullptr;
        unsigned int w = 0, h = 0;
        loadARGB_BMP(bmpPath.c_str(), &imgData, &w, &h);

        glGenTextures(1, &tex);
        glBindTexture(GL_TEXTURE_2D, tex);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S,     GL_REPEAT);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T,     GL_REPEAT);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);

        if (imgData) {
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_BGRA, GL_UNSIGNED_BYTE, imgData);
            glGenerateMipmap(GL_TEXTURE_2D);
            delete[] imgData;
        } else {
            std::cerr << "Failed to load texture: " << bmpPath << "\n";
        }
    }

    void draw(const glm::mat4& MVP) {
        glUseProgram(prog);
        glUniformMatrix4fv(glGetUniformLocation(prog, "MVP"), 1, GL_FALSE, glm::value_ptr(MVP));
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, tex);
        glUniform1i(glGetUniformLocation(prog, "tex"), 0);
        glBindVertexArray(vao);
        glDrawElements(GL_TRIANGLES, numIndices, GL_UNSIGNED_INT, nullptr);
        glBindVertexArray(0);
    }
};

glm::vec3 camPos(0.5f, 0.4f, 0.5f);
float     camYaw = 180.0f;

glm::vec3 camForward() {
    float rad = glm::radians(camYaw);
    return glm::normalize(glm::vec3(sin(rad), 0.f, cos(rad)));
}

bool keys[GLFW_KEY_LAST+1] = {};

void keyCallback(GLFWwindow* win, int key, int scancode, int action, int mods) {
    if (key >= 0 && key <= GLFW_KEY_LAST) {
        if      (action == GLFW_PRESS)   keys[key] = true;
        else if (action == GLFW_RELEASE) keys[key] = false;
    }
    if (key == GLFW_KEY_ESCAPE && action == GLFW_PRESS)
        glfwSetWindowShouldClose(win, GLFW_TRUE);
}

int main() {
    if (!glfwInit()) { std::cerr << "GLFW init failed\n"; return -1; }
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);

    GLFWwindow* window = glfwCreateWindow(1024, 768, "CS3388 A4 – Link's House", nullptr, nullptr);
    if (!window) { std::cerr << "Window creation failed\n"; glfwTerminate(); return -1; }
    glfwMakeContextCurrent(window);
    glfwSetKeyCallback(window, keyCallback);

    glewExperimental = GL_TRUE;
    if (glewInit() != GLEW_OK) { std::cerr << "GLEW init failed\n"; return -1; }

    glEnable(GL_DEPTH_TEST);
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);

    std::string dir = "LinksHouse/";

    std::vector<TexturedMesh*> opaque;
    opaque.push_back(new TexturedMesh(dir+"Floor.ply",        dir+"floor.bmp"));
    opaque.push_back(new TexturedMesh(dir+"Walls.ply",        dir+"walls.bmp"));
    opaque.push_back(new TexturedMesh(dir+"Table.ply",        dir+"table.bmp"));
    opaque.push_back(new TexturedMesh(dir+"Patio.ply",        dir+"patio.bmp"));
    opaque.push_back(new TexturedMesh(dir+"WoodObjects.ply",  dir+"woodobjects.bmp"));
    opaque.push_back(new TexturedMesh(dir+"Bottles.ply",      dir+"bottles.bmp"));
    opaque.push_back(new TexturedMesh(dir+"WindowBG.ply",     dir+"windowbg.bmp"));

    std::vector<TexturedMesh*> transparent;
    transparent.push_back(new TexturedMesh(dir+"DoorBG.ply",       dir+"doorbg.bmp"));
    transparent.push_back(new TexturedMesh(dir+"MetalObjects.ply", dir+"metalobjects.bmp"));
    transparent.push_back(new TexturedMesh(dir+"Curtains.ply",     dir+"curtains.bmp"));

    glm::mat4 proj = glm::perspective(glm::radians(45.f), 1024.f/768.f, 0.01f, 100.f);

    double prevTime = glfwGetTime();

    while (!glfwWindowShouldClose(window)) {
        double now  = glfwGetTime();
        float  dt   = (float)(now - prevTime);
        prevTime    = now;

        glfwPollEvents();


        const float MOVE_SPEED = 1.5f;
        const float ROT_SPEED  = 90.f;

        if (keys[GLFW_KEY_UP])    camPos += camForward() * MOVE_SPEED * dt;
        if (keys[GLFW_KEY_DOWN])  camPos -= camForward() * MOVE_SPEED * dt;
        if (keys[GLFW_KEY_LEFT])  camYaw -= ROT_SPEED * dt;
        if (keys[GLFW_KEY_RIGHT]) camYaw += ROT_SPEED * dt;

        glm::vec3 target = camPos + camForward();
        glm::mat4 view   = glm::lookAt(camPos, target, glm::vec3(0,1,0));
        glm::mat4 VP     = proj * view;

        glClearColor(0.1f, 0.1f, 0.15f, 1.f);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

        glDepthMask(GL_TRUE);
        for (auto* m : opaque)      m->draw(VP);

        glDepthMask(GL_FALSE);
        for (auto* m : transparent) m->draw(VP);
        glDepthMask(GL_TRUE);

        glfwSwapBuffers(window);
    }

    glfwTerminate();
    return 0;
}
