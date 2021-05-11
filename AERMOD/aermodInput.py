#!/usr/bin/env python3

import pandas as pd
import geopandas as gpd
import networkx as nx
from shapely.geometry import Point,LineString
from shapely.wkt import loads
from shapely.strtree import STRtree
import math
import argparse
import multiprocessing as mp
from itertools import chain
import hashlib
import os
from aermodConst import *

home = os.path.dirname(__file__)
aermodTemplate = open(os.path.join(home,'AERMOD_input_template.txt')).read()

# functions for parallel receptor checking
output = mp.SimpleQueue()

def checkReceptorGroup(tree,data):
    indices = []
    for idx,row in data.iterrows():
        if tree.nearest(row.location).contains(row.location):
            print('Dropping',row.receptorID)
            indices.append(idx)
    output.put(indices)


def checkAllReceptors(tree,receptors,numGroups = None):
    numReceptors = receptors.index.size
    if numGroups is None: numGroups = mp.cpu_count()
    groupSize = 1 + int(numReceptors/numGroups)
    args = []
    for start in range(0,numReceptors,groupSize):
        if start >= numReceptors: break
        stop = start + groupSize
        if stop > numReceptors: stop = numReceptors
        args.append((tree,receptors.iloc[range(start,stop)]))
        
    procs = [mp.Process(target = checkReceptorGroup,args = arg)
             for arg in args]
    
    for p in procs: p.start()
    for p in procs:
        if p.is_alive():
            print('Joining',p.name)
            p.join(timeout = 10)
            
    indices = [output.get() for p in procs]
    return list(chain(*indices))


class AermodScenario(object):

    def __init__(self,epsg,laneWidth):
        self.pollutantID = 110
        self.pollutant = 'PM25 H1H'
        self.epsg = 3665 if epsg is None else epsg
        self.laneWidth = 3.6576 if laneWidth is None else laneWidth*feet2meters

        # init dataframes
        self.lineSources = pd.DataFrame(
            columns = ['sourceID','x1','y1','x2','y2','flux','width','geometry','buffers']
        )
        
    def getLinkGeometries(self,linksPath):
        # read the links
        self.scenarioGDF = gpd.read_file(linksPath)
        # project
        self.scenarioGDF = self.scenarioGDF.to_crs(epsg = self.epsg)
        # define the study area
        self.studyArea = self.scenarioGDF.unary_union.convex_hull.buffer(receptorSpacing)


    def constructNetwork(self):
        # add the links to a DiGraph() object for easier retrieval
        self.network = nx.DiGraph()
        for idx,row in self.scenarioGDF.iterrows():
            self.network.add_edge(
                row.A_NODE,row.B_NODE,
                geometry = row.geometry,
                width = row['#LANES']*self.laneWidth
            )

                
    def mergeEmissionRate(self,emissionsPath):
        # read the total_emissions.csv from S3 and add the g/(s*m^2)
        # emissionFlux for each link
        emissions = pd.read_csv(emissionsPath)

        # filter on and pollutant
        emissions = emissions.query(f'pollutantID == {self.pollutantID}')

        # aggregate to link
        emissions = emissions.groupby('linkID').emquant.sum().reset_index()

        # iterate and add the emission flux to every link
        for idx,row in emissions.iterrows():
            a,b = map(int,row['linkID'].split('-'))
            link = self.network[a][b]
            area = link['geometry'].length*link['width']
            link['flux'] = row['emquant']/(area*secondsInDay)
            

    def makeSources(self):
        # for every link that has non-zero emissions, decompose it
        # into straight line segments, assign these segments new IDs
        # and save them in a dataframe
        numLinks = len(self.network.edges)
        rows = []
        for a,b,link in self.network.edges(data = True):
            flux = link.get('flux')
            if not flux: continue
            points = [Point(p) for p in link['geometry'].coords]
            for index in range(len(points) - 1):
                sourceID = f'{a}_{b}_{index}'
                start = points[index]
                end = points[index + 1]
                # discard very short (< 1 meter) segments
                if start.distance(end) < 1: continue
                geom = LineString((start,end))
                # print('Adding source',sourceID)
                rows.append({
                    'sourceID':sourceID,
                    'x1':start.x,'y1':start.y,
                    'x2':end.x,'y2':end.y,
                    'flux':flux,
                    'width':link['width'],
                    'geometry':geom,
                    'buffers':geom.buffer(0.5*link['width'])
                })

        # make the geopandas dataframe with all line source buffers
        self.lineSources = gpd.GeoDataFrame(
            rows,geometry = 'geometry',crs = f'epsg:{self.epsg}'
        )
        
        # make the R-tree of all buffers
        self.tree = STRtree(self.lineSources.buffers)

        # add the UID column that is the 12 character hash of the
        # sourceID
        self.lineSources['UID'] = self.lineSources.sourceID.apply(
            lambda ID: hashlib.md5(ID.encode()).hexdigest()[:12]
        )
            
        print('Finished making sources')


    def addReceptorLayers(self,source):
        # link length and number of receptors along the link
        length = source.geometry.length
        numReceptors = int(length/receptorSpacing) + 1
        # starting position of receptors along the link
        startPos = 0.5*(length - receptorSpacing*(numReceptors - 1))
        receptors = []
        for layerID,scale in enumerate(receptorLayerScales): 
            # receptor distance from link centerline
            dist = scale + 0.5*source.width

            print('Adding',numReceptors,'for layer',layerID,
                  'source',source.sourceID)


            # the link shifted normally to itself on either side
            offsets = [source.geometry.parallel_offset(dist),
                       source.geometry.parallel_offset(-dist)]

            for receptorIdx in range(numReceptors):
                # generate equidistant points along the parallel offsets
                for offsetIdx,offset in enumerate(offsets):
                    location = offset.interpolate(
                        startPos + receptorIdx*receptorSpacing
                    )

                    receptorID = '{}_{}_{}_{}'.format(
                        source.sourceID,
                        layerID,
                        receptorIdx,
                        offsetIdx
                    )

                    receptors.append({
                        'receptorID':receptorID,
                        'location':location
                    })

        return receptors
    

    def makeGridReceptors(self):
        # add gridded receptors with xy spacing of receptorSpacing
        xmin,ymin,xmax,ymax = self.studyArea.bounds
        numX = int((xmax - xmin)/receptorSpacing) + 1
        numY = int((ymax - ymin)/receptorSpacing) + 1
        xoffset = 0.5*(xmax - xmin - receptorSpacing*(numX - 1))
        yoffset = 0.5*(ymax - ymin - receptorSpacing*(numY - 1))
        receptors = []
        for xIdx in range(numX):
            x = xmin + xoffset + xIdx*receptorSpacing
            for yIdx in range(numY):
                y = ymin + yoffset + yIdx*receptorSpacing
                location = Point((x,y))
                # skip if the receptor is outside the study area
                if not self.studyArea.contains(location):
                    continue

                # add otherwise
                receptorID = f'grid_{xIdx}_{yIdx}'
                print('adding grid receptor',receptorID)
                receptors.append({
                    'receptorID':receptorID,
                    'location':location
                })

        self.receptors = self.receptors.append(
            receptors,ignore_index = True
        )


    def makeLinkReceptors(self):
        numSources = len(self.lineSources)
        receptors = []
        for idx,(sourceID,source) in enumerate(self.lineSources.iterrows()):
            print('Processing source',idx,'out of',numSources)
            receptors.extend(self.addReceptorLayers(source))

        self.receptors = pd.DataFrame(
            receptors,
            columns = ['receptorID','geometry']
        )

        
    def makeSourceReceptors(self):
        # iterate over the links that have an emission rate; compute
        # the number of receptor layers using the log scale of the
        # link areal emissions rate.  The links with the maxFlux
        # should have 3 layers.  The distances of the receptor layers
        # from the roadway are defined in aermodConst.py
        maxLogFlux = math.log(self.lineSources.flux.max())
        minLogFlux = math.log(self.lineSources.flux.min())
        logFluxDiff = maxLogFlux - minLogFlux

        numSources = len(self.lineSources)
        receptors = []
        for idx,(sourceID,source) in enumerate(self.lineSources.iterrows()):
            print('Processing source',idx + 1,'out of',numSources)
            logFlux = math.log(source.flux)
            numReceptorLayers = 1 + int(
                len(receptorLayerScales)*(logFlux - minLogFlux)/logFluxDiff
            )
            if numReceptorLayers > len(receptorLayerScales):
                numReceptorLayers = len(receptorLayerScales)
                
            # print('Processing source',idx+1,'out of',numSources,
            #       numReceptorLayers,'layers')
            receptors.extend(self.addReceptorLayers(source))

        self.receptors = pd.DataFrame(
            receptors,columns = ['receptorID','geometry']
        )


    def dropReceptorsInSources(self):
        idsToDrop = set(checkAllReceptors(self.tree,self.receptors))
        # remove the receptors that fall into sources
        self.receptors = self.receptors[
            ~self.receptors.receptorID.isin(idsToDrop)
        ]


    def saveReceptors(self):
        # make a GeoDataFrame        
        receptorGDF = gpd.GeoDataFrame(
            self.receptors,geometry = 'geometry'
        )
        # set crs
        receptorGDF.crs = f'epsg:{self.epsg}'
        # drop duplicate receptors
        receptorGDF = receptorGDF.loc[
            receptorGDF.geometry.apply(
                lambda geom: geom.wkb
            ).drop_duplicates().index
        ]
        # save it
        receptorGDF.to_file(
            'receptors.geojson',driver='GeoJSON',index = False
        )


    def saveSources(self):
        # transform the 'buffers column to wkb'
        self.lineSources['buffers'] = [
            g.wkt for g in self.lineSources.buffers
        ]
        # save
        self.lineSources.to_file(
            'sources.geojson',driver='GeoJSON',index = False
        )
        
        
    def readSources(self):
        try:
            self.lineSources = gpd.read_file('sources.geojson')
            self.lineSources = self.lineSources.to_crs(
                epsg = self.epsg
            )
            # load the buffers from wkb
            self.lineSources['buffers'] = [
                loads(poly) for poly in self.lineSources.buffers
            ]
            
            # make the R-tree of the buffers
            self.tree = STRtree(self.lineSources.buffers)
            
            # make the study area
            self.studyArea = self.lineSources.unary_union.convex_hull.buffer(
                receptorSpacing
            )
            print('Read sources.geojson')
            return True
        except:
            return False


    def readReceptors(self):
        try:
            self.receptors = gpd.read_file('receptors.geojson')
            self.receptors = self.receptors.to_crs(
                epsg = self.epsg
            )
            print('Read receptors.geojson')
            return True
        except:
            return False

        
    def constructSourceLocation(self,subset):
        return '\n'.join(
            'SO LOCATION ' + 
            subset.UID +
            ' LINE ' +
            subset.x1.astype(str) + ' ' +
            subset.y1.astype(str) + ' ' +
            subset.x2.astype(str) + ' ' +
            subset.y2.astype(str)
        )
            

    def constructSourceParam(self,subset):
        return '\n'.join(
            'SO SRCPARAM ' +
            subset.UID + ' ' +
            subset.flux.astype(str) +
            f' {sourceHeight} ' + 
            subset.width.astype(str)
        )

    def constructReceptorCoords(self):
        return '\n'.join(
            'RE DISCCART' + self.receptors.geometry.apply(
                lambda p: f' {round(p.x,5)} {round(p.y,5)}'
            ) + ' ' + str(receptorHeight)
        )


    def processAERMETfiles(self,aermetDir):
        self.aermetDir = aermetDir
        self.stanumSurf = open(os.path.join(
            aermetDir,'bestSurfaceStation.txt'
        )).read()
        self.stanumAir = open(os.path.join(
            aermetDir,'bestUpperStation.txt'
        )).read()
        self.profbase = float(open(os.path.join(
            aermetDir,'bestSurfElev.txt'
        )).read())
        upperData = pd.read_csv(
            os.path.join(aermetDir,'AERMETUPPER.PFL'),
            sep = '\s+',header = None
        )
        self.year = set(upperData[0]).pop()
        self.month = set(upperData[1]).pop()

        
    def constructAermodInputs(self,title,groupSize,population,day):
        self.population = population
        self.day = day
        self.title = title
        # bundle groupSize sources together
        
        # write the receptors text to a file to be later imported into
        # the .inp file at run time
        with open('receptors.txt','w') as f:
            f.write(self.constructReceptorCoords())
        
        numSources = len(self.lineSources)
        numGroups = 1 + int(numSources/groupSize)
        for groupIdx in range(numGroups):
            start = groupIdx*groupSize
            end = start + groupSize
            self.assembleAndWriteInput(start,end)


    def assembleAndWriteInput(self,start,end):
        prefix = f'{self.title}_{start}-{end}'
        subset = self.lineSources.iloc[start:end]
        aermodInput = aermodTemplate.format(
            title = prefix,
            population = self.population,
            pollutant = self.pollutant,
            sourceLocation = self.constructSourceLocation(subset),
            sourceParam = self.constructSourceParam(subset),
            urbanSource = '\n'.join('SO URBANSRC ' + subset['UID']),
            receptorCoords = f'   INCLUDED receptors.txt',
            stanumSurf = self.stanumSurf,
            stanumAir = self.stanumAir,
            profbase = self.profbase,
            pathToSurf = os.path.join(self.aermetDir,'AERMETSURFACE.SFC'),
            pathToUpper = os.path.join(self.aermetDir,'AERMETUPPER.PFL'),
            year = '20' + str(self.year),
            month = self.month,
            day = self.day,
            postfile = f'{prefix}.out'
        )

        with open(f'{prefix}.inp','w') as f:
            f.write(aermodInput)
