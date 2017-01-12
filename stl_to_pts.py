#!/usr/bin/env python
"""
Given an STL mesh, refine the triangles and smooth with sloped blocks.
"""

import sys
import math
import multiprocessing

# Build the list of unit vetors
UNIT_VECTORS = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
# Valid slopes, expressed as 1/m = the number of blocks required to complete the slope.
VALID_SLOPES = [1, 2]

tuple_dot = lambda t1, t2: sum([a*b for a,b in zip(t1,t2)])
tuple_add = lambda t1, t2: (t1[0]+t2[0],t1[1]+t2[1],t1[2]+t2[2])
tuple_scale = lambda a, t: (a*t[0],a*t[1],a*t[2])

class Triple(object):
    """
    Represents a triple of any object type. Is used to represent a point as well
    as a triangle of points.
    """
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

    def hexsect(self):
        """
        Given a triangle, partition it into six new triangles using the midpoints
        of each edge and the centroid as new vertices.
        """
        centroid = vmean3(self.x, self.y, self.z)
        mp1 = vmean2(self.x, self.y)
        mp2 = vmean2(self.x, self.z)
        mp3 = vmean2(self.y, self.z)
        return [
            Triple(self.x, mp1, centroid),
            Triple(mp1, self.y, centroid),
            Triple(self.x, mp2, centroid),
            Triple(mp2, self.z, centroid),
            Triple(self.y, mp3, centroid),
            Triple(mp3, self.z, centroid),
        ]


class STLFile(object):
    """
    Represents basic knowledge of the STL file format.
    """

    @staticmethod
    def read_solids(file_descriptor):
        """
        Convert a single 'solid' section of an STL file into triangles.
        Ignores normal verctor information.
        """
        _solids = []
        solid_name, solid_triangles = STLFile.solid_to_triangles(file_descriptor)
        while solid_name is not None:
            sys.stderr.write("Reading solid: %s\n" % solid_name)
            _solids.append((solid_name, solid_triangles))
            solid_name, solid_triangles = STLFile.solid_to_triangles(file_descriptor)

        return _solids

    @staticmethod
    def solid_to_triangles(file_descriptor):
        """
        Read through a Solid section of an STL file and extract all triangles as
        Triples of Triples
        """
        # Read in the 'solid' line, getting the name (which may be an empty string)
        name_line = file_descriptor.readline()
        if name_line == "":
            return (None, None)

        name = name_line.strip().split(" ", 1)[1]
        triangles = []
        # Can't mix iteration and .readline(), which made conditionally reading
        # multiple lines awkward, so the infinite while loop and break is used.
        while True:
            line = file_descriptor.readline()

            # If the end of the solid is reached, leave.
            if line.strip().startswith("endsolid"):
                break
            # Otherwise, if it's a vertex line (skipping the loop/endloop lines
            # completely)
            elif line.strip().startswith("vertex"):
                triangles.append(
                    Triple(
                        Triple(*[float(i) for i in
                                 line.strip().split(" ")[1:]]),
                        Triple(*[float(i) for i in
                                 file_descriptor.readline().strip().split(" ")[1:]]),
                        Triple(*[float(i) for i in
                                 file_descriptor.readline().strip().split(" ")[1:]])
                    )
                )
        return (name, triangles)

def triangle_list_bounds(tris):
    """
    Given a list of triangles, find the minimum and maximum bounds in each
    dimension.
    """
    bounds = []
    for i in range(3):
        coords = [a[b][i] for a in tris for b in range(3)]
        bounds.append((min(coords), max(coords)))

    return bounds

def vsub(u, v):
    """
    Vector subtraction.
    """
    return Triple(u.x - v.x, u.y - v.y, u.z - v.z)
    #return tuple([i-j for i,j in zip(u,v)])


def l2_norm(v):
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)
    #return math.sqrt(sum([i*i for i in v]))


def max_edge_norm(Tri):
    """
    Given an triangle, find length of the longest edge.
    """
    return max(
        l2_norm(vsub(Tri.x, Tri.y)),
        l2_norm(vsub(Tri.y, Tri.z)), l2_norm(vsub(Tri.x, Tri.z)))


def mean(v):
    """
    Find the mean of all elements of a triple.
    """
    if len(v) > 0:
        return (v.x + v.y + v.z) / 3.0
    else:
        raise ValueError('Cannot compute mean of zero-length vector.')


def vmean2(P1, P2):
    return Triple((P1.x + P2.x) / 2.0, (P1.y + P2.y) / 2.0,
                  (P1.z + P2.z) / 2.0)


def vmean3(P1, P2, P3):
    return Triple((P1.x + P2.x + P3.x) / 3.0, (P1.y + P2.y + P3.y) / 3.0,
                  (P1.z + P2.z + P3.z) / 3.0)


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
            tris.extend(t.hexsect())
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
    return (int(round(Point.x / Resolution)), int(round(Point.y / Resolution)),
            int(round(Point.z / Resolution)))

def parallel_split_tris(Primitives, Resolution, BatchSize=100):
    """
    Perform the split_tris() operation on chunks of primitives in parallel, and
    recombine at the end.
    """
    n = int(math.ceil(1.0*len(Primitives)/(2*multiprocessing.cpu_count())))
    primitive_chunks = [Primitives[i:i + n] for i in xrange(0, len(Primitives), n)]
    output_queue = multiprocessing.Queue()
    procs = [multiprocessing.Process(target=split_tris,
                                     args=(chunk, Resolution, BatchSize, output_queue))
             for chunk in primitive_chunks]
    sys.stderr.write("Prepared %d processes of work\n" % len(procs))
    
    for p in procs:
        p.start()
    
    pts = []
    while len(procs) > 0:
        for p in procs:
            p.join(1.0)
            while not output_queue.empty():
                pipe_pts = output_queue.get()
                sys.stderr.write("Pulled %d pts from the pipe\n" % len(pipe_pts))
                pts.extend(pipe_pts)
        procs = [p for p in procs if p.is_alive()]

    while not output_queue.empty():
        pts.extend(output_queue.get())
    
    pts = list(set(pts))

    return pts

def split_tris(Primitives, Resolution, BatchSize=100, OutputQueue=None):
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
    tris_handled = 0
    for p in Primitives:
        tris.extend(split_tri(p, Resolution))
        # For memory efficiency, perform batch-frequency flatten/union operations, to keep
        # the list of points at any given point in time bounded and reasonable.
        tris_handled += 1
        if (tris_handled % BatchSize) == 0:
            # sys.stderr.write("Batch done (%d)\n" % tris_handled)
            pts.extend([
                rescale_round_point(t[i], Resolution)
                for i in range(3) for t in tris
            ])
            pts = list(set(pts))
            tris = []

    # sys.stderr.write("Final round (%d)\n" % tris_handled)
    # One final round of flatten/union
    pts.extend([
        rescale_round_point(t[i], Resolution) for i in range(3) for t in tris
    ])
    pts = list(set(pts))

    # LEGACY: Super slow on pypy (2x CPython), included for posterity and entertainment.
    #pts = list(set([ rescale_round_point(t[i], Resolution) for i in range(3) for t in tris ]))
    if OutputQueue is not None:
        OutputQueue.put(pts)
    return pts

def adjacency_vector(position, forward, points):
    """
    Return the vector that points out of what should be the bottom of any
    sloped blocks placed.
    """
    # To start, for each unit vector that is perpendicular to the forward vector,
    # check to see if there is a block 'next' to the path. If there is precisely
    # one vector for which this is true, take the director that dots to -1 with
    # the vector satisfying this criteria
    adj = []
    for v in UNIT_VECTORS:
        if tuple_dot(forward, v) != 0:
            continue
        else:
            p = tuple_add(position, v)
            if p in points and points[p] == 0:
                adj.append(v)
    if len(adj) == 1:
        # return [v for v in UNIT_VECTORS if tuple_dot(v, adj[0]) == -1]
        return adj[0]
    else:
        return None

def slope_check_single(position, forward, points):
    """
    Given a single point and a forward direction, determine whether a slope is suitable
    in the given forward direction, and if so, what slope value. Add the resulting values
    to the points dictionary
    """
    down_vec = adjacency_vector(tuple_add(position, forward), forward, points)
    if down_vec is None:
        return
    else:
        up_vec = [v for v in UNIT_VECTORS if tuple_dot(v, down_vec) == -1][0]

    perpendicular_vectors = [v for v in UNIT_VECTORS if
                             tuple_dot(v, forward) == 0 and v != down_vec]
    # sys.stderr.write("%s %s %s    %s\n" % (str(position), str(forward), str(down_vec), str(perpendicular_vectors)))

    # For each unit vector that is perpendicular to the forward vector, move up
    # to the maximum slope length along the forward vector, checking all around
    viable_slope = 0
    for slope_length in range(1, max(VALID_SLOPES)+1):
        # The 'base' position along the forward vector from the starting position
        p = tuple_add(position, tuple_scale(slope_length, forward))

        # If there's no longer a full block adjacent to this position, break.
        a = tuple_add(p, down_vec)
        if a not in points or points[a] != 0:
            viable_slope = slope_length - 1
            break

        # If the position along the forward vector we're considering adding a block
        # to is already filled with a full block (slope 0), then exit the loop and
        # and see how far we got.
        # Otherwise, if it's filled with a sloped block, keep going
        if p in points and points[p] == 0:
            viable_slope = slope_length - 1
            break

        # Is the position along the forward vector an interior position? Let's find out!
        interior = False

        # For each unit vector that is perpendicular to the forward vector...
        for v in perpendicular_vectors:
            # The position to check is the position along the forward vector
            # plus the unit vector 'away'.
            c = tuple_add(p, v)
            
            # If a neighbouring point is a slope, ignore it only consider full
            # blocks to cause interior corner issues.
            if c in points and points[c] == 0:
                interior = True
                break

        # if this is an interior point, then the viable slope is one less than
        # as far as we've gone. Otherwise, the viable slope is as far as we've
        # gone
        if interior:
            viable_slope = slope_length - 1
            break
        else:
            viable_slope = slope_length

    # Once here, check the viable slope length, and find the longest slope
    # in the VALID_SLOPES list that is no longer than this. If the viable slope
    # isn't at least 1, then there's nothing to do.
    chosen_slope = viable_slope
    clear_path = False
    while viable_slope > 0 and not clear_path:
        chosen_slope = max([slope_length for slope_length in VALID_SLOPES
                            if slope_length <= viable_slope])
        # Now, for each block along the forward vector, find if this chosen slope
        # conflicts with any other sloped blocks that existing along the forward
        # vector
        for i in range(1, chosen_slope+1):
            p = tuple_add(position, tuple_scale(i, forward))
            # Gentler slopes take precendence, so if one is encountered, reduce
            # the viable slope length by one and try again. If this reduces it
            # below 1, then no slope is added.
            if p in points and points[p][0][0] > chosen_slope:
                chosen_slope -= 1
                viable_slope = chosen_slope
                clear_path = False
                break
            else:
                clear_path = True

    # sys.stderr.write("%d\n" % chosen_slope)
    # Now that the slope has been chosen, fill in the appropriate parts of the
    # points dict.
    for i in range(1,chosen_slope+1):
        p = tuple_add(position, tuple_scale(i, forward))
        points[p] = ((chosen_slope, i), (forward, up_vec))

    return points

def smooth_pts(PointTriples):
    """
    Given a collection of points (assumed to be cubic voxels), identify and build
    the list of slanted/sloped voxel elements that will help smooth out the voxel
    surface while remaining, locally, within the convex hull of the voxel surface.
    """
    # First, create a dict that maps from the points to the slope values
    pts = dict([(p, 0) for p in PointTriples])

    # For each point check along each unit vector to see if there are any blocks
    # that would make that direction an interior corner.
    for p in pts.keys():
        for v in UNIT_VECTORS:
            slope_check_single(p, v, pts)

    return pts

def map_to_empyrion_codes(points):
    block_type_mapping = {
        0: 0,
        (2, 1): 18, (2, 2): 16, (1, 1): 20}
    slope_code_mapping = {
        177: ((0, 0, -1), (1, 0, 0)), 9: ((1, 0, 0), (0, 1, 0)), 137: ((1, 0, 0), (0, 0, -1)),
        89: ((1, 0, 0), (0, 0, 1)), 33: ((0, 0, 1), (0, -1, 0)), 1: ((0, 0, 1), (0, 1, 0)),
        97: ((0, 0, 1), (-1, 0, 0)), 81: ((0, -1, 0), (0, 0, 1)), 41: ((-1, 0, 0), (0, -1, 0)),
        185: ((0, 1, 0), (1, 0, 0)), 105: ((0, 1, 0), (-1, 0, 0)), 129: ((0, 1, 0), (0, 0, -1)),
        161: ((0, 0, 1), (1, 0, 0)), 25: ((-1, 0, 0), (0, 1, 0)), 153: ((-1, 0, 0), (0, 0, -1)),
        73: ((-1, 0, 0), (0, 0, 1)), 49: ((0, 0, -1), (0, -1, 0)), 17: ((0, 0, -1), (0, 1, 0)),
        113: ((0, 0, -1), (-1, 0, 0)), 65: ((0, 1, 0), (0, 0, 1)), 57: ((1, 0, 0), (0, -1, 0)),
        169: ((0, -1, 0), (1, 0, 0)), 121: ((0, -1, 0), (-1, 0, 0)), 145: ((0, -1, 0), (0, 0, -1))}
    slope_orientation_mapping = dict([(v, k) for k, v in slope_code_mapping.iteritems()])

    blocks = []
    for position, block in points.iteritems():
        blocks.append(position + (block_type_mapping[block[0] if block != 0 else 0],
                                  slope_orientation_mapping[block[1]] if block != 0 else 1))
    return blocks

def blocks_to_csv(blocks):
    return ["{:d},{:d},{:d},{:d},{:d}".format(b[0], b[1], b[2], b[3], b[4]) for b in blocks]

# if __name__ == "__main__":
#     if len(sys.argv) < 3:
#         print "Usage: stl_to_pts.py <Path to STL file> <Number of voxel elements in the longest dimension>"
#         exit(1)

#     t0 = time.time()
#     # Convert the STL to a list of triangles.
#     with open(sys.argv[1], 'r') as fp:
#         solids = STLFile.read_solids(fp)

#     triangles = [ e for s in solids for e in s[1] ]

#     sys.stderr.write("Identified %d triangles in the STL file.\n" % len(triangles))
#     bounds = triangle_list_bounds(triangles)
#     longest_dim = max([i[1]-i[0] for i in bounds])
#     resolution = longest_dim / float(sys.argv[2])
#     sys.stderr.write("STL bounds: %s\n" % str(bounds))

#     # Convert the polygonal representation of a 2D surface in 3D space into
#     # a cloud of points where no point is more than the given resolution away
#     # from a neighbour.
#     pts = parallel_split_tris(triangles, resolution)
#     smoothed_pts = smooth_pts(pts)
#     mapped_blocks = map_to_empyrion_codes(smoothed_pts)

#     # Print out the points as a CSV.
#     sys.stdout.write("\n".join(blocks_to_csv(mapped_blocks)))
#     # for b in mapped_blocks:
#     #     sys.stdout.write("{:d},{:d},{:d},{:d},{:d}\n".format(b[0], b[1], b[2], b[3], b[4]))
#     sys.stderr.write("Converted %d triangles to %d points\n" %
#                     (len(triangles), len(mapped_blocks)))
#     sys.stderr.write("Operation took %f seconds\n" % (time.time() - t0))
