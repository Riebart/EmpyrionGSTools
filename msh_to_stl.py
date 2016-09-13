#!/usr/bin/env python

import sys
import math

def normalize(v):
    l = math.sqrt(sum([i*i for i in v]))
    return [ i/l for i in v ]

def triangle_normal(p1, p2, p3):
    return normalize([-(p1[2]*p2[1]) + p1[1]*p2[2] + p1[2]*p3[1] - p2[2]*p3[1] - \
            p1[1]*p3[2] + p2[1]*p3[2], p1[2]*p2[0] - p1[0]*p2[2] - p1[2]*p3[0] + \
            p2[2]*p3[0] + p1[0]*p3[2] - p2[0]*p3[2], -(p1[1]*p2[0]) + p1[0]*p2[1] \
            + p1[1]*p3[0] - p2[1]*p3[0] - p1[0]*p3[1] + p2[0]*p3[1]])

def bottom_corner(tris):
    # Step 1 is to find the min in each trignale, redusing the dimensionality by 1
    s1 = [[min([t[j][i] for j in range(3)]) for i in range(3)] for t in tris]
    # Step 2 is to min over this new 2D list.
    return [ min([ m[i] for m in s1 ]) for i in range(3) ]

def build_stl(tris):
    m = bottom_corner(tris)
    output = "solid Default\n"
    for t in tris:
        output += "  facet normal {:e} {:e} {:e}\n".format(*triangle_normal(t[0], t[1], t[2]))
        output += "    outer loop\n"
        for i in t:
            output += "      vertex {:e} {:e} {:e}\n".format(i[0]-m[0],
                                                             i[1]-m[1],
                                                             i[2]-m[2])
        output += "    endloop\n"
        output += "  endfacet\n"
    output += "endsolid Default"
    return output

def read_group(fp):
    # MATERIAL line
    fp.readline()
    # TEXTURE line
    fp.readline()
    #GEOM line
    l = sys.stdin.readline().strip()
    if not l.startswith("GEOM"):
        print "Expecting GEOM line, found: %s" % l
        exit(2)
    npts, ntris = [ int(i.strip()) for i in l.replace("\t"," ").split(" ", 3)[1:3] ]

    pts = []
    for i in xrange(npts):
        p = [ float(i) for i in sys.stdin.readline().strip().split(" ") ]
        pts.append(p)

    tris = []
    for i in xrange(ntris):
        t = [ pts[int(i)] for i in sys.stdin.readline().strip().split(" ") ]
        tris.append(t)

    return tris

fhdr = sys.stdin.readline().strip()
if fhdr != "MSHX1":
    print "Unknown file format"
    exit(1)

groups_line = sys.stdin.readline().strip()
if not groups_line.startswith("GROUPS"):
    print "Expecting number of groups, found: %s" % groups_line
    exit(2)

ngroups = int(groups_line.split(" ", 1)[1])

tris = [] 
for g in xrange(ngroups):
    tris.extend(read_group(sys.stdin))

print build_stl(tris)
