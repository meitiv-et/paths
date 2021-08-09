#include "csv.h"
#include <unordered_map>
#include <map>
#include <set>
#include <list>
#include <cmath>
#include <vector>
#include <string>
#include <fstream>
#include <iostream>
#include <functional>
#include <boost/lexical_cast.hpp>
#include <boost/filesystem.hpp>
#include <boost/algorithm/string.hpp>
#include <boost/iostreams/filtering_stream.hpp>
#include <boost/iostreams/filter/bzip2.hpp>
#include <boost/functional/hash.hpp>

using namespace std;
using namespace io;
using namespace boost;
using namespace boost::iostreams;

struct VolumeBin {
  int intervalID;
  int speed;
  int vehType;
  int fromNodeID;
  int toNodeID;
};

class volHash {
public: 
  size_t operator()(const VolumeBin& v) const {
    size_t result = 0;
    hash_combine(result,v.intervalID);
    hash_combine(result,v.speed);
    hash_combine(result,v.vehType);
    hash_combine(result,v.fromNodeID);
    hash_combine(result,v.toNodeID);
    return result;
  }
};

class volEq {
public: 
  bool operator()(const VolumeBin& v1,const VolumeBin& v2) const {
    return v1.intervalID == v2.intervalID && v1.speed == v2.speed && \
      v1.vehType == v2.vehType && v1.fromNodeID == v2.fromNodeID && \
      v1.toNodeID == v2.toNodeID;
  }
};

struct LinkBin {
  int fromNodeID;
  int toNodeID;
  int vehType;
};

class linkHash {
public: 
  size_t operator()(const LinkBin& l) const {
    size_t result = 0;
    hash_combine(result,l.fromNodeID);
    hash_combine(result,l.toNodeID);
    hash_combine(result,l.vehType);
    return result;
  }
};

class linkEq {
public: 
  bool operator()(const LinkBin& l1,const LinkBin& l2) const {
    return l1.fromNodeID == l2.fromNodeID && \
      l1.toNodeID == l2.toNodeID && l1.vehType == l2.vehType;
  }
};

typedef unordered_map<VolumeBin,double,volHash,volEq> volMap;
typedef unordered_map<LinkBin,double,linkHash,linkEq> linkDataMap;
typedef map<pair<int,int>,double> linkMap;

string cut(string &line,int start,int length) {
  string text = line.substr(start,length);
  trim(text);
  return text;
}

class Vehicle {
  int upstreamNode; // A node of the origin link
  double originLinkFrac;
  vector<int> trajectory; // nodeIDs
  double startTime; // in min from midnight
  vector<double> nodeArrivalTimes,signalDelays,tolls;
public:
  int vehType;
  int ID;
  string text;
  void parseVehicleHeader(string &line) {
    ID = lexical_cast<int>(cut(line,0,9));
    originLinkFrac = lexical_cast<double>(cut(line,95,12));
    vehType = lexical_cast<int>(cut(line,37,6));
    startTime = lexical_cast<double>(cut(line,23,8));
    upstreamNode = lexical_cast<int>(cut(line,9,7));
  }
  void parseTrajBlock(list<string> &lines,bool incomplete) {
    // parser the header
    string line = lines.front();
    lines.pop_front();
    int traversedNodes = lexical_cast<int>(cut(line,161,4));
    if (incomplete && traversedNodes == 1) return;

    // split the rest of the data -- the number of lines can be
    // variable; put all tokens into a single vector and discard the
    // unreached node if incomplete
    vector<string> allVals,tokens;
    for (auto line : lines) {
      trim(line);
      split(tokens,line,is_any_of("\t "),token_compress_on);
      // discard the empty string at the beginning
      allVals.insert(allVals.end(),tokens.begin(),tokens.end());
    }

    // decrement traversedNodes by 1 and discard unreached node ID if
    // incomplete
    if (incomplete) {
      --traversedNodes;  
      allVals.erase(allVals.begin() + traversedNodes);
    }

    // sanity check
    if (allVals.size() % traversedNodes != 0) {
      cerr << "Inconsistet block size " << allVals.size()
	   << " traversedNodes = " << traversedNodes
	   << " for vehicle " << ID << endl;
    }
    
    // assign the trajectory, nodeArrivalTimes, delay and tolls
    for (int i = 0; i < traversedNodes; ++i) {
      trajectory.push_back(lexical_cast<int>(allVals[i]));
      double time = lexical_cast<double>(allVals[i + traversedNodes]);
      nodeArrivalTimes.push_back(startTime + time);
      double delay = lexical_cast<double>(allVals[i + 3*traversedNodes]);
      double prevdelay;
      if (signalDelays.empty()) {
	signalDelays.push_back(delay);
      } else {
	signalDelays.push_back(delay - prevdelay);
	prevdelay = delay;
      }
    }
    // parse toll if exists
    if (allVals.size()/traversedNodes == 5) {
      for (int i = 0; i < traversedNodes; ++i) {
	double toll = lexical_cast<double>(allVals[i + 4*traversedNodes]);
	tolls.push_back(toll);
      }
    }
  }
  volMap mapToLinks(linkMap& lnkLen,double aggint,int speedBin) {
    VolumeBin bin;
    bin.vehType = vehType;
    volMap volumes;
    double frac = originLinkFrac;
    int Anode = upstreamNode;
    int Bnode;
    double start = startTime - 0.00001; // startTime is > 0
    int startHourID = 1 + int(start/aggint);
    // cerr << "Mapping vehicle " << ID << endl;
    for (int i = 0; i < trajectory.size(); ++i) {
      Bnode = trajectory[i];
      bin.fromNodeID = Anode;
      bin.toNodeID = Bnode;
      double end = nodeArrivalTimes[i] - 0.00001;
      double duration = end - start;
      // skip 0 duration traversals
      if (duration == 0) {
	Anode = Bnode;
	frac = 1.;
	continue;
      }
      int maxBin = 80/speedBin;
      bin.speed = ceil(60*frac*lnkLen[make_pair(Anode,Bnode)]/(speedBin*duration));
      // because time resolution is limited, the speed can be very
      // wrong for short links, map to max speed bin
      if (bin.speed > maxBin) bin.speed = maxBin;
      int endHourID = 1 + int(end/aggint);
      // parse the volume into the intervalIDs that span it
      double lower = start;
      // cerr << Anode << " -> " << Bnode << "   "
      // 	   << start << " " << end << endl;
      for (int intervalID = startHourID; intervalID <= endHourID; ++intervalID) {
	double upper = min(end,intervalID*aggint);
	double volumeFraction = (upper - lower)/duration;
	lower = upper;
	bin.intervalID = intervalID;
	// cerr << bin.intervalID << " "
	//      << bin.fromNodeID << " "
	//      << bin.toNodeID << " "
	//      << bin.speed << " "
	//      << bin.vehType << " "
	//      << frac*volumeFraction << endl;
	volumes[bin] += volumeFraction*frac;
      }
      // prepare for the next iteration
      start = end;
      Anode = Bnode;
      frac = 1.;
      startHourID = endHourID;
    }
    return volumes;
  }
  int numberOfLinks() {
    return trajectory.size();
  }
  void output() {
    cerr << ID << " " << trajectory.size() << " "
	 << upstreamNode << ":" << startTime;
    for (int i = 0; i < trajectory.size(); ++i) {
      cerr << " " << trajectory[i] << ":" << nodeArrivalTimes[i];
    }
    cerr << endl;
  }
  linkDataMap mapVMT(linkMap& lnkLen) {
    linkDataMap vmt;
    double frac = originLinkFrac;
    int Anode = upstreamNode;
    LinkBin lb;
    lb.vehType = vehType;
    for (auto& Bnode : trajectory) {
      lb.fromNodeID = Anode;
      lb.toNodeID = Bnode;
      vmt[lb] += lnkLen[make_pair(Anode,Bnode)]*frac;
      frac = 1.;
      Anode = Bnode;
    }
    return vmt;
  }
  linkDataMap mapSignalDelay() {
    linkDataMap sigDelay;
    int Anode = upstreamNode;
    LinkBin lb;
    lb.vehType = vehType;
    for (int i = 0; i < trajectory.size(); ++i) {
      int Bnode = trajectory[i];
      if (signalDelays[i] > 0.) {
	lb.fromNodeID = Anode;
	lb.toNodeID = Bnode;
	sigDelay[lb] = signalDelays[i];
      }
      Anode = Bnode;
    }
    return sigDelay;
  }
  linkDataMap mapTolls() {
    linkDataMap toll;
    if (tolls.size() == trajectory.size()) {
      int Anode = upstreamNode;
      LinkBin lb;
      lb.vehType = vehType;
      for (int i = 0; i < trajectory.size(); ++i) {
	int Bnode = trajectory[i];
	if (tolls[i] > 0.) {
	  lb.fromNodeID = Anode;
	  lb.toNodeID = Bnode;
	  toll[lb] = tolls[i];
	}
	Anode = Bnode;
      }
    }
    return toll;
  }
  linkDataMap mapDelay(linkMap& lnkFFT) {
    linkDataMap delay;
    double start = startTime;
    double frac = originLinkFrac;
    int Anode = upstreamNode;
    LinkBin lb;
    lb.vehType = vehType;
    for (int i = 0; i < trajectory.size(); ++i) {
      int Bnode = trajectory[i];
      double end = nodeArrivalTimes[i];
      double linkDelay = frac*(end - start - \
			       lnkFFT[make_pair(Anode,Bnode)]);
      if (linkDelay > 0.) {
	lb.fromNodeID = Anode;
	lb.toNodeID = Bnode;
	delay[lb] = linkDelay;
      }
      start = end;
      Anode = Bnode;
      frac = 1.;
    }
    return delay;
  }
};

class Scenario {
  map<int,Vehicle*> vehicles; // map from ID to Vehicle pointers
  volMap volumes;
  linkDataMap vmt,delay,signalDelay,toll;
  linkMap lnkLen,lnkFFT;
  set<int> electrifiedIDs; 
public:
  void readElecIDs() {
    ifstream elecIDfile;
    elecIDfile.open("elecIDs.txt");
    int ID;
    while (elecIDfile >> ID) electrifiedIDs.insert(ID);
    elecIDfile.close();
  }
  void removeElecVeh() {
    for (auto ID : electrifiedIDs) vehicles.erase(ID);
  }      
  void parseVehicle() {
    // set up the bzip2 decompressor and parse vehicle.dat
    filtering_istream in;
    in.push(bzip2_decompressor());
    ifstream vehFile("output_vehicle.dat.bz2",ios_base::binary);
    in.push(vehFile);
    
    // read lines and parse the vehicles
    int lineNumber = 0;
    string line;
    while (getline(in,line)) {
      // skip the first two lines and odd lines
      if (lineNumber < 2 || lineNumber % 2 == 1) {
	++lineNumber;
	continue;
      }

      // make new vehicle and assign ID and originLinkFrac
      Vehicle* vehicle = new Vehicle();
      vehicle->parseVehicleHeader(line);
      vehicles[vehicle->ID] = vehicle;
      ++lineNumber;
    }
    // close the ifstream
    vehFile.close();
  }
  void parseVehTraj() {
    // set up the bzip2 decompressor and parse VehTrajectory.dat
    filtering_istream in;
    in.push(bzip2_decompressor());
    ifstream trajFile("VehTrajectory.dat.bz2",ios_base::binary);
    in.push(trajFile);
    
    // read lines and parse the blocks
    list<string> lines;
    bool skipVehicle = false;
    bool incomplete = false;
    bool reachedIncomplete = false;
    string line;
    int lineNumber = 0;
    int vehID = 0;
    while (getline(in,line)) {
      // skip the first 5 lines
      if (lineNumber < 6) {
	++lineNumber;
	continue;
      }
      
      // start of a new vehicle block
      if (line.compare(0,3,"Veh") == 0) {
	// parse the previous block if it has non-zero size and
	// skipVehicle is false
	if (vehID > 0 && !skipVehicle) {
	  auto vehicle = vehicles[vehID];
	  vehicle->parseTrajBlock(lines,incomplete);
	}

	// set the incomplete flag if reached the "in the network"
	// section
	if (reachedIncomplete) {
	  incomplete = true;
	  reachedIncomplete = false;
	}
	
	// empty the block
	lines.clear();
	// add the line to the block
	lines.push_back(line);
	  
	// parse out the vehicleID and set skipVehicle based on
	// whether or not the ID is in the vehicles map
	vehID = lexical_cast<int>(cut(line,5,9));
	if (vehicles.find(vehID) == vehicles.end()) {
	  skipVehicle = true;
	} else {
	  skipVehicle = false;
	}
      } else if (line.compare(1,3,"###") == 0) {
	reachedIncomplete = true; // don't add the line to the block
      } else {
	// add the line to the block
	lines.push_back(line);
      }
    }
    // parse the last block
    if (!skipVehicle) {
      auto vehicle = vehicles[vehID];
      vehicle->parseTrajBlock(lines,incomplete);
    }
    trajFile.close();
  }
  void readLinkInfo() {
    CSVReader<5, trim_chars<' '> > in("links.csv");
    in.read_header(ignore_extra_column,
		   "linkID","roadTypeID","countyID","length","speedLimit");
    int roadType;
    int fips;
    double length,speed;
    string linkID;
    vector<string> tokens;
    while (in.read_row(linkID,roadType,fips,length,speed)) {
      split(tokens,linkID,is_any_of("-"),token_compress_on);
      int aNode = lexical_cast<int>(tokens[0]);
      int bNode = lexical_cast<int>(tokens[1]);
      lnkLen[make_pair(aNode,bNode)] = length; // miles
      lnkFFT[make_pair(aNode,bNode)] = length/speed*60; // min
    }
  }
  void computeVolumes(double aggint,int speedBin) {
    for (auto& [ID,vehicle] : vehicles) {
      // cerr << endl << ID << ":\n";
      auto mappedVolumes = vehicle->mapToLinks(lnkLen,aggint,speedBin);
      for (auto [key,volume] : mappedVolumes) {
	// cerr << key.intervalID << " " << key.speed << " " << volume << endl;
	volumes[key] += volume;
      }
    }      
  }
  void computeLinkData() {
    for (auto& [ID,vehicle] : vehicles) {
      auto vehvmt = vehicle->mapVMT(lnkLen);
      for (auto [key,val] : vehvmt) vmt[key] += val;
      auto vehdelay = vehicle->mapDelay(lnkFFT);
      for (auto [key,val] : vehdelay) delay[key] += val;
      auto vehsigdelay = vehicle->mapSignalDelay();
      for (auto [key,val] : vehsigdelay) signalDelay[key] += val;
      auto vehtoll = vehicle->mapTolls();
      for (auto [key,val] : vehtoll) toll[key] += val;
    }
  }
  void outputLinkData() {
    ofstream fh("linkData.csv");
    fh << "linkID,vehType,metric,unit,value\n";
    // vmt
    for (auto [lb,val] : vmt) {
      fh << lb.fromNodeID << "-" << lb.toNodeID << "," << lb.vehType
	 << ",vmt,mile," << val << endl;
    }
    // delay
    for (auto [lb,val] : delay) {
      fh << lb.fromNodeID << "-" << lb.toNodeID << "," << lb.vehType
	 << ",delay,min," << val << endl;
    }
    // signalDelay
    for (auto [lb,val] : signalDelay) {
      fh << lb.fromNodeID << "-" << lb.toNodeID << "," << lb.vehType
	 << ",signalDelay,min," << val << endl;
    }
    for (auto [lb,val] : toll) {
      fh << lb.fromNodeID << "-" << lb.toNodeID << "," << lb.vehType
	 << ",toll,dollar," << val << endl;
    }
    fh.close();
  }
  void outputVolumes() {
    ofstream fh("linkVMT.csv");
    // write the header
    fh << "linkID,vehType,timeIntervalID,avgSpeedBinID,vmt\n";
    for (auto [bin,volume] : volumes) {
      fh << bin.fromNodeID << "-" << bin.toNodeID << "," << bin.vehType
	 << "," << bin.intervalID << "," << bin.speed << ","
	 << volume*lnkLen[make_pair(bin.fromNodeID,bin.toNodeID)] << endl;
    }
    fh.close();
  }
  void outputNumberOfTrips() {
    map<int,int> numberOfTrips;
    for (auto& [ID,vehicle] : vehicles) {
      ++numberOfTrips[vehicle->vehType];
    }
    ofstream fh;
    fh.open("numberOfTrips.csv");
    fh << "vehType,numTrips\n";
    for (auto [vehType,num] : numberOfTrips) {
      fh << vehType << "," << num << endl;
    }
    fh.close();
  }
};

int main(int argc,char **argv) {
  if (argc != 3) {
    cerr << "Usage: " << argv[0] << " aggInt speedBin\n";
    return 1;
  }
  double aggInt = lexical_cast<double>(argv[1]);
  int speedBin = lexical_cast<int>(argv[2]);
  Scenario scenario;
  cerr << "Reading link attributes\n";
  scenario.readLinkInfo();
  cerr << "Parsing output_vehicle.dat\n";
  scenario.parseVehicle();
  cerr << "Parsing VehTrajectory.dat\n";
  scenario.parseVehTraj();
  // if elecIDs.txt is present, remove vehIDs listed in it
  if (boost::filesystem::exists(boost::filesystem::path("elecIDs.txt"))) {
    cerr << "Removing electrified vehicles\n";
    scenario.readElecIDs();
    scenario.removeElecVeh();
  }
  cerr << "Computing link volumes\n";
  scenario.computeVolumes(aggInt,speedBin);
  cerr << "Writing volumes\n";
  scenario.outputVolumes();
  cerr << "Writing number of trips\n";
  scenario.outputNumberOfTrips();
  cerr << "Computing link attributes\n";
  scenario.computeLinkData();
  cerr << "Writing link attributes\n";
  scenario.outputLinkData();
}
