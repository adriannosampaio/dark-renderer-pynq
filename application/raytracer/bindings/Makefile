CC=g++ -std=c++11
FLAGS=-shared -fPIC -fopenmp
INCLUDES=-I./deps/pybind11/include -I/usr/include/python3.6
FILES=utils.cpp binding.cpp
TARGET=utils.so
TEST_TARGET=

$(TARGET) : $(FILES)
	$(CC) $(FLAGS) $(INCLUDES) $(FILES) -o $(TARGET)
	

