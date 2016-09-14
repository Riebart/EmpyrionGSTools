#!/usr/bin/env python

import sys
import json
import math
import time

class Triple(object):
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __getitem__(self, i):
        if i == 0:
            return self.x
        if i == 1:
            return self.y
        if i == 2:
            return self.z
    
    def __str__(self):
        return "<%s,%s,%s>" % (str(self.x), str(self.y), str(self.z))

def solid_to_triangles(fp):
    """
    Convert a single 'solid' section of an STL file into triangles.
    Ignores normal verctor information.
    """

    # Read in the 'solid' line, getting the name (which may be an empty string)
    name_line = fp.readline()
    if name_line == "":
        return (None, None)
    
    name = name_line.strip().split(" ", 1)[1]
    tris = []
    # Can't mix iteration and .readline(), which made conditionally reading
    # multiple lines awkward, so the infinite while loop and break is used. 
    while True:
        l = fp.readline()

        # If the end of the solid is reached, leave.
        if l.strip().startswith("endsolid"):
            break
        # Otherwise, if it's a vertex line (skipping the loop/endloop lines
        # completely)
        elif l.strip().startswith("vertex"):
            x = Triple(*[ float(i) for i in l.strip().split(" ")[1:]])
            l = fp.readline()
            y = Triple(*[ float(i) for i in l.strip().split(" ")[1:]])
            l = fp.readline()
            z = Triple(*[ float(i) for i in l.strip().split(" ")[1:]])
            tris.append(Triple(x,y,z))
    return (name, tris)

def stl_to_triangles(fp):
    """
    Convert an STL, and all solids in it, into a single list of triangles.
    This merges the triangles of all solids in the file, ignoring the STL named
    separation.
    """

    tris = []
    solid_name, solid_tris = solid_to_triangles(fp)
    # Just iterate through the solids in an STL file.
    while solid_name is not None:
        tris.extend(solid_tris)
        solid_name, solid_tris = solid_to_triangles(fp)

    return tris

def vsub(u, v):
    """
    Vector subtraction.
    """
    return Triple(u.x-v.x,u.y-v.y,u.z-v.z)
    #return tuple([i-j for i,j in zip(u,v)])

def l2_norm(v):
    return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
    #return math.sqrt(sum([i*i for i in v]))

def max_edge_norm(Tri):
    """
    Given an triangle, find length of the longest edge.
    """
    return max(
        l2_norm(vsub(Tri.x, Tri.y)),
        l2_norm(vsub(Tri.y, Tri.z)),
        l2_norm(vsub(Tri.x, Tri.z))
    )

def mean(v):
    """
    Find the mean of all elements of a triple.
    """
    if len(v) > 0:
        return (v.x+v.y+v.z) / 3.0
    else:
        raise ValueError('Cannot compute mean of zero-length vector.')

def vmean2(P1, P2):
    return Triple(
        (P1.x+P2.x)/2.0,
        (P1.y+P2.y)/2.0,
        (P1.z+P2.z)/2.0
    )

def vmean3(P1, P2, P3):
    return Triple(
        (P1.x+P2.x+P3.x)/3.0,
        (P1.y+P2.y+P3.y)/3.0,
        (P1.z+P2.z+P3.z)/3.0
    )

def hexsect_tri(Tri):
    """
    Given a triangle, partition it into six new triangles using the midpoints
    of each edge and the centroid as new vertices.
    """
    centroid = vmean3(Tri.x, Tri.y, Tri.z)
    mp1 = vmean2(Tri.x, Tri.y)
    mp2 = vmean2(Tri.x, Tri.z)
    mp3 = vmean2(Tri.y, Tri.z)
    return [
        Triple(Tri.x, mp1, centroid),
        Triple(mp1, Tri.y, centroid),
        Triple(Tri.x, mp2, centroid),
        Triple(mp2, Tri.z, centroid),
        Triple(Tri.y, mp3, centroid),
        Triple(mp3, Tri.z, centroid),
    ]

def split_tri(Tri, Resolution):
    """
    Given a single triangle and a spatial resolution, iteratively hexsect the triangles
    so that no subtriangle has an edge length longer than the given resolution.

    Recursive might have been nicer to look at, but this has efficiency benefits for
    large triangles 
    """
    small = []
    large = [Tri]
    while len(large) > 0:
        tris = []
        for t in large:
            tris.extend(hexsect_tri(t))
        large = []
        for t in tris:
            if max_edge_norm(t) > Resolution:
                large.append(t)
            else:
                small.append(t)
    return small

def rescale_round_point(Point, Resolution):
    """
    Transform a point to the nearest lattice point that lies on a grid with
    the specified resolution.

    Returned as a tuple for use in a set() for reduction to unique points only.
    """
    return (
        int(round(Point.x / Resolution)),
        int(round(Point.y / Resolution)),
        int(round(Point.z / Resolution))
    )

def split_tris(Primitives, Resolution, BatchSize=100):
    """
    Given a list of triangles, split all triangles to the given resolution, and
    flatten the resulting list of triangles to a list of points with duplicates removed.

    Consider batches of triangles together, aggregating the batches of partitioned triangles
    into the cumulative points list, removing duplicates with progression through the
    triangle list. This limits the growth rate of the point and triangle list, significantly
    improving memory consumption.
    """
    pts = []
    tris = []
    i = 0
    for p in Primitives:
        tris.extend(split_tri(p, Resolution))
        # For memory efficiency, perform batch-frequency flatten/union operations, to keep
        # the list of points at any given point in time bounded and reasonable.
        i += 1
        if (i % BatchSize) == 0:
            pts.extend([ rescale_round_point(t[i], Resolution) for i in range(3) for t in tris ])
            pts = list(set(pts))
            tris = []
    
    # One final round of flatten/union
    pts.extend([ rescale_round_point(t[i], Resolution) for i in range(3) for t in tris ])
    pts = list(set(pts))

    # LEGACY: Super slow on pypy (2x CPython), included for posterity and entertainment.
    #pts = list(set([ rescale_round_point(t[i], Resolution) for i in range(3) for t in tris ]))
    return pts

if len(sys.argv) < 3:
    print "Usage: stl_to_pts.py <Path to STL file> <Spatial sampling resolution>"
    exit(1)

t0 = time.time()
# Convert the STL to a list of triangles. 
with open(sys.argv[1],'r') as fp:
    tris = stl_to_triangles(fp)

sys.stderr.write("Identified %d triangles in the STL file.\n" % len(tris))

# Convert the polygonal representation of a 2D surface in 3D space into
# a cloud of points where no point is more than the given resolution away
# from a neighbour.
pts = split_tris(tris, float(sys.argv[2]))

# Print out the points as a CSV.
for p in pts:
    sys.stdout.write("{:d},{:d},{:d}\n".format(p[0],p[1],p[2]))
sys.stderr.write("Converted %d triangles to %d points\n" % (len(tris), len(pts)))
sys.stderr.write("Operation took %f seconds\n" % (time.time() - t0))
