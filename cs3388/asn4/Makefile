CXX      = g++
CXXFLAGS = -std=c++17 -Wall -O2
LIBS     = -lGL -lGLEW -lglfw -lm

TARGET = a4_linkshouse

all: $(TARGET)

$(TARGET): main.cpp
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LIBS)

clean:
	rm -f $(TARGET)
