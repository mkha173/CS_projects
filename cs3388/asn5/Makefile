CXX      = g++
CXXFLAGS = -std=c++17 -O2
LIBS     = -lGL -lGLEW -lglfw

a5: main.cpp MarchingCubes.cpp MarchingCubes.h TriTable.hpp
	$(CXX) $(CXXFLAGS) main.cpp MarchingCubes.cpp -o a5 $(LIBS)

clean:
	rm -f a5 *.ply
