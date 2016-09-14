#!/usr/bin/env python

import sys
import json
import math
import time

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
            x = [ float(i) for i in l.strip().split(" ")[1:]]
            l = fp.readline()
            y = [ float(i) for i in l.strip().split(" ")[1:]]
            l = fp.readline()
            z = [ float(i) for i in l.strip().split(" ")[1:]]
            tris.append([x,y,z])
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
    return tuple([i-j for i,j in zip(u,v)])

def l2_norm(v):
    return math.sqrt(sum([i*i for i in v]))

def max_edge_norm(Tri):
    """
    Given an triangle, find length of the longest edge.
    """
    return max([
        l2_norm(vsub(Tri[0], Tri[1])),
        l2_norm(vsub(Tri[1], Tri[2])),
        l2_norm(vsub(Tri[0], Tri[2]))
    ])

def mean(v):
    """
    Find the mean of all elements of a vector.
    """
    if len(v) > 0:
        return sum(v) / len(v)
    else:
        raise ValueError('Cannot compute mean of zero-length vector.')

def vmean(Pts):
    """
    Given a 2D matrix in row-major form, compute the mean along each column.  
    No distinction is made between row and columns, but the mean is computed along
    the minor dimension, so the row/column language is used as a convenience.
    """
    return [mean([ p[i] for p in Pts ]) for i in range(len(Pts[0]))]

def hexsect_tri(Tri):
    """
    Given a triangle, partition it into six new triangles using the midpoints
    of each edge and the centroid as new vertices.
    """
    centroid = vmean(Tri)
    mp1 = vmean([Tri[0], Tri[1]])
    mp2 = vmean([Tri[0], Tri[2]])
    mp3 = vmean([Tri[1], Tri[2]])
    return [
        [Tri[0], mp1, centroid],
        [mp1, Tri[1], centroid],
        [Tri[0], mp2, centroid],
        [mp2, Tri[2], centroid],
        [Tri[1], mp3, centroid],
        [mp3, Tri[2], centroid],
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
    return tuple([ int(round(p / Resolution)) for p in Point ])

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
    
    #One final round of flatten/union
    pts.extend([ rescale_round_point(t[i], Resolution) for i in range(3) for t in tris ])
    pts = list(set(pts))

    # LEGACY: Super slow on pypy (2x CPython), included for posterity and entertainment.
    # pts = list(set([ rescale_round_point(t[i], Resolution) for i in range(3) for t in tris ]))
    return pts

if len(sys.argv) < 3:
    print "Usage: stl_to_pts.py <Path to STL file> <Spatial sampling resolution>"
    exit(1)

t0 = time.time()
# Convert the STL to a list of triangles. 
with open(sys.argv[1],'r') as fp:
    tris = stl_to_triangles(fp)

# Convert the polygonal representation of a 2D surface in 3D space into
# a cloud of points where no point is more than the given resolution away
# from a neighbour.
pts = split_tris(tris, float(sys.argv[2]))

# Print out the points as a CSV.
for p in pts:
    sys.stdout.write("{:d},{:d},{:d}\n".format(p[0],p[1],p[2]))
sys.stderr.write("Converted %d triangles to %d points\n" % (len(tris), len(pts)))
sys.stderr.write("Operation took %f seconds\n" % (time.time() - t0))
