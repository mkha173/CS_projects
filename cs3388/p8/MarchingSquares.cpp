// Include standard headers
#include <stdio.h>
#include <stdlib.h>
#include <cmath>

#include <GL/glew.h>

// Include GLFW
#include <GLFW/glfw3.h>
GLFWwindow* window;

#include <iostream>
#include <vector>

#define TOP_LEFT     8
#define TOP_RIGHT    4
#define BOTTOM_RIGHT 2
#define BOTTOM_LEFT  1

typedef float (*scalar_field_2d)(float, float);

int marching_squares_lut[16][4] = {
	{-1, -1, -1, -1},  // case 0:  no corners inside
	{2, 3, -1, -1},    // case 1:  BL only
	{1, 2, -1, -1},    // case 2:  BR only
	{1, 3, -1, -1},    // case 3:  BR + BL
	{0, 1, -1, -1},    // case 4:  TR only
	{0, 1, 2, 3},      // case 5:  TR + BL (ambiguous saddle)
	{0, 2, -1, -1},    // case 6:  TR + BR
	{0, 3, -1, -1},    // case 7:  TR + BR + BL
	{0, 3, -1, -1},    // case 8:  TL only
	{0, 2, -1, -1},    // case 9:  TL + BL
	{0, 3, 1, 2},      // case 10: TL + BR (ambiguous saddle)
	{0, 1, -1, -1},    // case 11: TL + BR + BL
	{1, 3, -1, -1},    // case 12: TL + TR
	{1, 2, -1, -1},    // case 13: TL + TR + BL
	{2, 3, -1, -1},    // case 14: TL + TR + BR
	{-1, -1, -1, -1}   // case 15: all corners inside
};

// Colors for each of the 16 cases
float case_colors[16][3] = {
	{0.15f, 0.15f, 0.20f},  // case 0:  empty          - dark background
	{0.80f, 0.20f, 0.20f},  // case 1:  BL             - red
	{0.20f, 0.80f, 0.20f},  // case 2:  BR             - green
	{0.80f, 0.80f, 0.00f},  // case 3:  BR+BL          - yellow
	{0.20f, 0.20f, 0.90f},  // case 4:  TR             - blue
	{0.80f, 0.40f, 0.00f},  // case 5:  TR+BL saddle   - orange (ambiguous)
	{0.00f, 0.70f, 0.70f},  // case 6:  TR+BR          - cyan
	{0.60f, 0.00f, 0.80f},  // case 7:  TR+BR+BL       - purple
	{0.90f, 0.40f, 0.70f},  // case 8:  TL             - pink
	{0.40f, 0.80f, 0.40f},  // case 9:  TL+BL          - light green
	{0.90f, 0.10f, 0.50f},  // case 10: TL+BR saddle   - magenta (ambiguous)
	{0.20f, 0.60f, 0.80f},  // case 11: TL+BR+BL       - steel blue
	{0.80f, 0.60f, 0.20f},  // case 12: TL+TR          - gold
	{0.50f, 0.80f, 0.60f},  // case 13: TL+TR+BL       - mint
	{0.80f, 0.50f, 0.50f},  // case 14: TL+TR+BR       - salmon
	{0.30f, 0.30f, 0.35f},  // case 15: full           - dark grey
};

// Edge midpoint positions expressed as fractions of cell width/height.
// Index: 0=top edge, 1=right edge, 2=bottom edge, 3=left edge
//   fx = fraction of stepx,  fy = fraction of stepy
float g_verts_fx[4] = { 0.5f, 1.0f, 0.5f, 0.0f };
float g_verts_fy[4] = { 1.0f, 0.5f, 0.0f, 0.5f };

float f1(float x, float y) { return x*x + y*y; }
float f2(float x, float y) { return sin(x*y); }
float f3(float x, float y) { return sin(x)*cos(y); }

// -----------------------------------------------------------------------
// Cell stores separate stepx / stepy for rectangular cells
// -----------------------------------------------------------------------
struct Cell {
	int   caseIndex;
	float x, y;    // bottom-left corner (world space)
	float stepx;   // cell width
	float stepy;   // cell height
};

// Build all rectangular cells
std::vector<Cell> build_cells(scalar_field_2d f, float isoval,
                               float minx, float maxx,
                               float miny, float maxy,
                               float stepx, float stepy)
{
	std::vector<Cell> cells;

	for (float y = miny; y < maxy; y += stepy) {
		for (float x = minx; x < maxx; x += stepx) {
			float tl = (*f)(x,         y + stepy);
			float tr = (*f)(x + stepx, y + stepy);
			float br = (*f)(x + stepx, y);
			float bl = (*f)(x,         y);

			int which = 0;
			if (tl < isoval) which |= TOP_LEFT;
			if (tr < isoval) which |= TOP_RIGHT;
			if (br < isoval) which |= BOTTOM_RIGHT;
			if (bl < isoval) which |= BOTTOM_LEFT;

			cells.push_back({which, x, y, stepx, stepy});
		}
	}
	return cells;
}

// -----------------------------------------------------------------------
// Compute world-space position of edge midpoint for a rectangular cell.
// Multiplies x-fraction by stepx and y-fraction by stepy independently.
// -----------------------------------------------------------------------
inline void edge_midpoint(const Cell& c, int edge, float& wx, float& wy) {
	wx = c.x + c.stepx * g_verts_fx[edge];
	wy = c.y + c.stepy * g_verts_fy[edge];
}

// Draw filled quad (color = case)
void draw_cell_fill(const Cell& c) {
	const float* col = case_colors[c.caseIndex];
	glColor4f(col[0], col[1], col[2], 1.0f);
	glBegin(GL_QUADS);
		glVertex2f(c.x,           c.y);
		glVertex2f(c.x + c.stepx, c.y);
		glVertex2f(c.x + c.stepx, c.y + c.stepy);
		glVertex2f(c.x,           c.y + c.stepy);
	glEnd();
}

// Draw grid outline for the rectangular cell
void draw_cell_grid(const Cell& c) {
	glColor4f(0.45f, 0.45f, 0.50f, 1.0f);
	glBegin(GL_LINE_LOOP);
		glVertex2f(c.x,           c.y);
		glVertex2f(c.x + c.stepx, c.y);
		glVertex2f(c.x + c.stepx, c.y + c.stepy);
		glVertex2f(c.x,           c.y + c.stepy);
	glEnd();
}

// Draw contour line segments — edge midpoints use stepx AND stepy separately
void draw_cell_lines(const Cell& c) {
	int* v = marching_squares_lut[c.caseIndex];
	if (v[0] < 0) return;

	float ax, ay, bx, by;
	glColor4f(1.0f, 1.0f, 1.0f, 1.0f);
	glBegin(GL_LINES);
		edge_midpoint(c, v[0], ax, ay);  glVertex2f(ax, ay);
		edge_midpoint(c, v[1], bx, by);  glVertex2f(bx, by);
		if (v[2] >= 0) {
			edge_midpoint(c, v[2], ax, ay);  glVertex2f(ax, ay);
			edge_midpoint(c, v[3], bx, by);  glVertex2f(bx, by);
		}
	glEnd();
}

// Draw a small dot at each corner that is inside the isosurface
void draw_inside_corners(const Cell& c) {
	float corners[4][2] = {
		{c.x,           c.y + c.stepy},  // TL
		{c.x + c.stepx, c.y + c.stepy},  // TR
		{c.x + c.stepx, c.y},            // BR
		{c.x,           c.y}             // BL
	};
	int masks[4] = { TOP_LEFT, TOP_RIGHT, BOTTOM_RIGHT, BOTTOM_LEFT };
	float r = 0.10f * fminf(c.stepx, c.stepy);

	for (int i = 0; i < 4; i++) {
		if (c.caseIndex & masks[i]) {
			glColor4f(0.2f, 1.0f, 0.3f, 1.0f);
			glBegin(GL_TRIANGLE_FAN);
				glVertex2f(corners[i][0], corners[i][1]);
				for (int seg = 0; seg <= 12; seg++) {
					float ang = seg * 2.0f * (float)M_PI / 12.0f;
					glVertex2f(corners[i][0] + r * cosf(ang),
					           corners[i][1] + r * sinf(ang));
				}
			glEnd();
		}
	}
}

//////////////////////////////////////////////////////////////////////////////
// Main
//////////////////////////////////////////////////////////////////////////////

int main(int argc, char* argv[])
{
	float screenW = 1400;
	float screenH = 900;
	float stepx   = 0.5f;   // horizontal step size (cell width)
	float stepy   = 0.5f;   // vertical   step size (cell height)
	float xmin    = -5;
	float xmax    =  5;
	float isoval  =  1;

	// Argument order: width height stepx stepy xmin xmax isoval
	if (argc > 1) screenW = atoi(argv[1]);
	if (argc > 2) screenH = atoi(argv[2]);
	if (argc > 3) stepx   = atof(argv[3]);
	if (argc > 4) stepy   = atof(argv[4]);   // separate vertical step
	if (argc > 5) xmin    = atof(argv[5]);
	if (argc > 6) xmax    = atof(argv[6]);
	if (argc > 7) isoval  = atof(argv[7]);

	float ymin = xmin;
	float ymax = xmax;

	if (!glfwInit()) {
		fprintf(stderr, "Failed to initialize GLFW\n");
		getchar();
		return -1;
	}

	glfwWindowHint(GLFW_SAMPLES, 4);

	window = glfwCreateWindow((int)screenW, (int)screenH,
	                          "Marching Rectangles – Grid Overlay", NULL, NULL);
	if (!window) {
		fprintf(stderr, "Failed to open GLFW window.\n");
		getchar();
		glfwTerminate();
		return -1;
	}
	glfwMakeContextCurrent(window);

	glewExperimental = true;
	if (glewInit() != GLEW_OK) {
		fprintf(stderr, "Failed to initialize GLEW\n");
		getchar();
		glfwTerminate();
		return -1;
	}

	glfwSetInputMode(window, GLFW_STICKY_KEYS, GL_TRUE);
	glClearColor(0.12f, 0.12f, 0.18f, 0.0f);

	glMatrixMode(GL_PROJECTION);
	glLoadIdentity();
	glOrtho(xmin, xmax, ymin, ymax, -1, 1);

	printf("\nMarching Rectangles  |  stepx=%.3f  stepy=%.3f  isoval=%.2f\n",
	       stepx, stepy, isoval);
	printf("Usage: ./MarchingSquares width height stepx stepy xmin xmax isoval\n\n");

	std::vector<Cell> cells = build_cells(f1, isoval,
	                                       xmin, xmax, ymin, ymax,
	                                       stepx, stepy);
	do {
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

		// Pass 1: colored cell fills
		for (const Cell& c : cells)
			draw_cell_fill(c);

		// Pass 2: grid outlines
		glLineWidth(1.0f);
		for (const Cell& c : cells)
			draw_cell_grid(c);

		// Pass 3: inside-corner dots
		for (const Cell& c : cells)
			draw_inside_corners(c);

		// Pass 4: contour lines
		glLineWidth(2.5f);
		for (const Cell& c : cells)
			draw_cell_lines(c);

		glfwSwapBuffers(window);
		glfwPollEvents();

	} while (glfwGetKey(window, GLFW_KEY_ESCAPE) != GLFW_PRESS &&
	         glfwWindowShouldClose(window) == 0);

	glfwTerminate();
	return 0;
}