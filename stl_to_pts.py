#!/usr/bin/env python

import sys
import json
import math
import time

def solid_to_triangles(fp):
    name_line = fp.readline()
    if name_line == "":
        return (None, None)
    
    name = name_line.strip().split(" ", 1)[1]
    tris = []
    while True:
        l = fp.readline()
        if l.strip().startswith("endsolid"):
            break
        elif l.strip().startswith("vertex"):
            x = tuple([ float(i) for i in l.strip().split(" ")[1:]])
            l = fp.readline()
            y = tuple([ float(i) for i in l.strip().split(" ")[1:]])
            l = fp.readline()
            z = tuple([ float(i) for i in l.strip().split(" ")[1:]])
            tris.append((x,y,z))
    return (name, tris)

def stl_to_triangles(fp):
    tris = []
    solid_name, solid_tris = solid_to_triangles(fp)
    while solid_name is not None:
        tris.extend(solid_tris)
        solid_name, solid_tris = solid_to_triangles(fp)
    return tris

def vsub(u, v):
    return tuple([i-j for i,j in zip(u,v)])

def l2_norm(v):
    return math.sqrt(sum([i*i for i in v]))

def max_edge_norm(Tri):
    return max([
        l2_norm(vsub(Tri[0], Tri[1])),
        l2_norm(vsub(Tri[1], Tri[2])),
        l2_norm(vsub(Tri[0], Tri[2]))
    ])

def mean(v):
    if len(v) > 0:
        return sum(v) / len(v)
    else:
        raise ValueError('Cannot compute mean of zero-length vector.')

def vmean(Pts):
    return [mean([ p[i] for p in Pts ]) for i in range(len(Pts[0]))]

def hexsect_tri(Tri):
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
    return tuple([ int(round(p / Resolution)) for p in Point ])

def split_tris(Primitives, Resolution):
    tris = []
    for p in Primitives:
        tris.extend(split_tri(p, Resolution))
    pts = list(set([ rescale_round_point(t[i], Resolution) for i in range(3) for t in tris ]))
    return pts

if len(sys.argv) < 3:
    print "Usage: stl_to_pts.py <Path to STL file> <Spatial sampling resolution>"
    exit(1)

t0 = time.time()
# Get the triangles
with open(sys.argv[1],'r') as fp:
    tris = stl_to_triangles(fp)

pts = split_tris(tris, float(sys.argv[2]))
for p in pts:
    sys.stdout.write("{:d},{:d},{:d}\n".format(p[0],p[1],p[2]))
sys.stderr.write("Converted %d triangles to %d points\n" % (len(tris), len(pts)))
sys.stderr.write("Operation took %f seconds\n" % (time.time() - t0))
