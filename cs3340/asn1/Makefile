CXX = g++
CXXFLAGS = -O2 -Wall

all: asn1_a asn1_b

asn1_a: fib_naive.o
	$(CXX) $(CXXFLAGS) -o asn1_a fib_naive.o

asn1_b: fib_fast.o
	$(CXX) $(CXXFLAGS) -o asn1_b fib_fast.o

fib_naive.o: fib_naive.cpp
	$(CXX) $(CXXFLAGS) -c fib_naive.cpp

fib_fast.o: fib_fast.cpp
	$(CXX) $(CXXFLAGS) -c fib_fast.cpp

clean:
	rm -f *.o asn1_a asn1_b
