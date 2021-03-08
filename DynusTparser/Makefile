CC = g++
CFLAGS=-I.
LIBS = -l boost_system -l boost_iostreams -l boost_filesystem -l pthread 
OBJ = computeVolumes.o
CPPS = computeVolumes.cpp

%.o: %.cpp
	$(CC) -std=c++1z -c -O2 -o $@ $< -I.

volumes: $(OBJ)
	$(CC) -O2 -o volumes.exe $(OBJ) $(LIBS)

debug: $(CPPS)
	$(CC) -std=c++0x -Wall -fPIC -I. -o volumes.exe -ggdb $(CPPS) $(LIBS)

clean:
	rm -f *.o *~
