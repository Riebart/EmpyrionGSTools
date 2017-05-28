#!/usr/bin/env python
"""
More complex script that converts locations in 3D space into a Blueprint
dense filled matrix/block types.
For now, only a Steel cube block is used.

Also implements reading from STL files, and performing the point refinement.
"""

import os
import sys
import math
import time
import struct
import StringIO
import zipfile
import multiprocessing
from copy import copy

# Maximum number of points to attempt to generate per process, for memory bounding
# purposes.
MAX_POINTS_PER_PROCESS = 2000.0

# Build the list of unit vetors
UNIT_VECTORS = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0,-1)]
# Valid slopes, expressed as 1/m = the number of blocks required to complete the slope.
VALID_SLOPES = [1, 2]

TUPLE_DOT = lambda t1, t2: sum([a * b for a, b in zip(t1, t2)])
TUPLE_ADD = lambda t1, t2: (t1[0] + t2[0], t1[1] + t2[1], t1[2] + t2[2])
TUPLE_SUB = lambda t1, t2: (t1[0] - t2[0], t1[1] - t2[1], t1[2] - t2[2])
TUPLE_MUL = lambda t1, t2: (t1[0] * t2[0], t1[1] * t2[1], t1[2] * t2[2])
TUPLE_LE = lambda t1, t2: (t1[0] < t2[0]) and (t1[1] < t2[1]) and (t1[2] < t2[2])
TI = lambda a, t: a[t[0]][t[1]][t[2]]
TUPLE_SCALE = lambda a, t: (a * t[0], a * t[1], a * t[2])

SIGN_S = lambda s: -1 if s < 0 else 1 if s > 0 else 0
SIGN_V = lambda v: tuple([SIGN_S(c) for c in v])

def leq(a, b):
    """
    Given two values, return a boolean or None, depending on whether a < b, 
    with a == b returning None.
    """
    if a < b:
        return True
    elif a > b:
        return False
    else:
        return None

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

    def __repr__(self):
        return str(self)

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

    def shift(self, offset):
        self.x = Triple(*TUPLE_ADD(self.x, offset))
        self.y = Triple(*TUPLE_ADD(self.y, offset))
        self.z = Triple(*TUPLE_ADD(self.z, offset))

    def reflect(self, dim):
        scalar = [1 if i != dim else -1 for i in range(1, 3+1)]
        if isinstance(self.x, Triple):
            return Triple(
                Triple(*TUPLE_MUL(self.x, scalar)),
                Triple(*TUPLE_MUL(self.y, scalar)),
                Triple(*TUPLE_MUL(self.z, scalar))
            )
        else:
            return Triple(*TUPLE_MUL((self.x, self.y, self.x), scalar))


class STLFile(object):
    """
    Represents basic knowledge of the STL file format.
    """

    @staticmethod
    def read_binary_stl(file_descriptor):
        """
        Read all triangles from a binary STL file.
        """
        _ = file_descriptor.read(80)  # Read the global file header
        ntris = struct.unpack("<L", file_descriptor.read(4))[0]

        tris = []
        for _ in range(ntris):
            _ = struct.unpack("<fff", file_descriptor.read(4 * 3))  # Normal
            v1 = struct.unpack("<fff", file_descriptor.read(4 * 3))
            v2 = struct.unpack("<fff", file_descriptor.read(4 * 3))
            v3 = struct.unpack("<fff", file_descriptor.read(4 * 3))
            _ = struct.unpack("<H", file_descriptor.read(2))  # Attributes
            tris.append(Triple(Triple(*v1), Triple(*v2), Triple(*v3)))
        return tris

    @staticmethod
    def read_ascii_stl(file_descriptor):
        """
        Reads a single solid section from an ASCII STL file, returning a list
        marging the triangles from all solids found in the file.
        """
        _solids = []
        solid_name, solid_triangles = STLFile.solid_to_triangles(
            file_descriptor)
        while solid_name is not None:
            sys.stderr.write("Reading solid: %s\n" % solid_name)
            _solids.append((solid_name, solid_triangles))
            solid_name, solid_triangles = STLFile.solid_to_triangles(
                file_descriptor)

        triangles = [e for s in _solids for e in s[1]]
        return triangles

    @staticmethod
    def read_triangles(file_descriptor):
        """
        Given a STL file, determine if it is ASCII or binary, and return a list
        of triangles representing all triangles in the file. For ACSII files,
        the triangles of all solids in the file.
        """
        # First, determine the file is binary or ASCII. Do this by reading the
        # first 5 bytes and if those are 'solid', then assume it is ASCII. Seek
        # back to the start after reading the header.
        is_ascii = (file_descriptor.read(5) == 'solid')
        file_descriptor.seek(0)

        if is_ascii:
            return STLFile.read_ascii_stl(file_descriptor)
        else:
            return STLFile.read_binary_stl(file_descriptor)

    @staticmethod
    def solid_to_triangles(file_descriptor):
        """
        Read through a Solid section of an STL file and extract all triangles as
        Triples of Triples
        """
        # Read in the 'solid' line, getting the name (which may be an empty string)
        # If there's a null in the name, then this is a binary file, and it should
        # be discarded and ignored.
        name_line = file_descriptor.readline()
        if name_line == "" or '\0' in name_line:
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
                        Triple(
                            * [float(i) for i in line.strip().split(" ")[1:]]),
                        Triple(* [
                            float(i)
                            for i in file_descriptor.readline().strip().split(
                                " ")[1:]
                        ]),
                        Triple(* [
                            float(i)
                            for i in file_descriptor.readline().strip().split(
                                " ")[1:]
                        ])))
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
    """
    Return the L2 norm of the vector.
    """
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
    # For the number of jobs per process, look the bounds, the primitive count,
    # and the resolution. Create process that will have an approximate bound
    # on the number of points generated.
    size = [i[1] - i[0] for i in triangle_list_bounds(Primitives)]
    # Primitives per unit cube of volume, approximately.
    prims_per_unit3 = len(Primitives) / (size[0] * size[1] * size[2])
    # Resolution is essentially units-per-point, so dimensional analysis gives...
    points_per_prim = 1.0 / math.pow((Resolution**3 * prims_per_unit3),
                                     1.0 / 3)
    prims_per_process = int(
        math.ceil(MAX_POINTS_PER_PROCESS / points_per_prim))

    # The prims_per_process should be at most enough so that there are more
    # processes than CPUs.
    prims_per_process = min(
        int(math.floor(len(Primitives) / (3 * multiprocessing.cpu_count()))),
        prims_per_process)
    sys.stderr.write("Approximate number of points generated per process: %s\n"
                     % (points_per_prim * prims_per_process))

    primitive_chunks = [
        Primitives[i:i + prims_per_process]
        for i in xrange(0, len(Primitives), prims_per_process)
    ]
    output_queue = multiprocessing.Queue()
    procs = [
        multiprocessing.Process(
            target=split_tris,
            args=(chunk, Resolution, BatchSize, output_queue))
        for chunk in primitive_chunks
    ]
    sys.stderr.write("Prepared %d processes of work\n" % len(procs))

    # First, start cpu_count() processes.
    running_procs = procs[:multiprocessing.cpu_count()]
    for p in running_procs:
        p.start()
    queued_procs = [p for p in procs if p not in running_procs]
    finished_procs = 0

    pts = set()
    # As long as there's a running process, keep cycling.
    while len(running_procs) > 0:
        # Attempt to join all running processes.
        for p in running_procs:
            p.join(0.0)

        while not output_queue.empty():
            pipe_pts = output_queue.get()
            finished_procs += 1
            sys.stderr.write("%d (%d/%d) " %
                             (len(pipe_pts), finished_procs, len(procs)))
            pts.update(pipe_pts)

        # Rebuild the running processes list to only include those still alive
        running_procs = [p for p in running_procs if p.is_alive()]

        # If there are fewer running processes than available CPUs, start some more.
        pending_procs = queued_procs[:multiprocessing.cpu_count() - len(
            running_procs)]
        for p in pending_procs:
            p.start()
        # Once started, add them to the pending procs, and remove them from the
        # list of queued processes.
        running_procs += pending_procs
        queued_procs = [p for p in queued_procs if p not in running_procs]

        # Give the processes another second to do some work before checking on them.
        # Prevents a certain amount of busywaiting.
        time.sleep(1.0)

    while not output_queue.empty():
        pts.update(output_queue.get())
        finished_procs += 1
        sys.stderr.write("%d (%d/%d) " %
                         (len(pipe_pts), finished_procs, len(procs)))
    sys.stderr.write("\n")

    return list(pts)


def split_tris(Primitives, Resolution, BatchSize=100, OutputQueue=None):
    """
    Given a list of triangles, split all triangles to the given resolution, and
    flatten the resulting list of triangles to a list of points with duplicates removed.

    Consider batches of triangles together, aggregating the batches of partitioned triangles
    into the cumulative points list, removing duplicates with progression through the
    triangle list. This limits the growth rate of the point and triangle list, significantly
    improving memory consumption.
    """
    start_time = time.time()
    last_print_time = time.time()
    pts = set()
    tris = []
    tris_handled = 0
    for p in Primitives:
        tris.extend(split_tri(p, Resolution))
        # For memory efficiency, perform batch-frequency flatten/union operations, to keep
        # the list of points at any given point in time bounded and reasonable.
        tris_handled += 1
        if (tris_handled % BatchSize) == 0:
            if OutputQueue is None and time.time() - last_print_time > 0.5:
                last_print_time = time.time()
                sys.stderr.write("%d/%d (ETA: %f)\n" % 
                (
                    tris_handled,
                    len(Primitives),
                    (len(Primitives) - tris_handled) * (time.time() - start_time) / tris_handled
                )
            )
            # sys.stderr.write("Batch done (%d)\n" % tris_handled)
            pts.update([
                rescale_round_point(t[i], Resolution)
                for i in range(3) for t in tris
            ])
            tris = []

    # sys.stderr.write("Final round (%d)\n" % tris_handled)
    # One final round of flatten/union
    pts.update([
        rescale_round_point(t[i], Resolution) for i in range(3) for t in tris
    ])
    pts_l = list(pts)

    # LEGACY: Super slow on pypy (2x CPython), included for posterity and entertainment.
    #pts = list(set([ rescale_round_point(t[i], Resolution) for i in range(3) for t in tris ]))
    if OutputQueue is not None:
        OutputQueue.put(pts_l)
    return pts_l


def p_norm(coords, p):
    """
    Return the p-norm of the list.
    """
    return math.pow(sum([math.pow(c, p) for c in coords]), 1.0 / p)


def integral_ball(radius, norm=lambda x, y, z: p_norm((x, y, z), 2)):
    """
    Given a radius, find all integer coordinates within that radius of the origin
    in three dimensional Euclidean space (by default).
    """
    coord_range = range(-radius, radius + 1)
    brush = [(x, y, z)
             for x in coord_range for y in coord_range for z in coord_range
             if norm(x, y, z) <= radius]
    return brush


def parallel():
    shm_stat = None
    try:
        shm_stat = os.stat('/dev/shm')
    except OSError as e:
        if e.errno != 2:
            raise e
    return shm_stat is not None


def parallel_hollow(pts, radius=1):
    """
    Perform model hollowing in parallel across cpu_count() processes.
    """
    return list_parallelize(pts, (radius, pts), hollow)


def hollow(pts, radius=1, all_pts=None, output_queue=None):
    """
    Perform inverted morphological erosion, by keeping all blocks that would have
    failed the erosion test, and discarding all blocks that would have passed the
    erosion test.
    """
    if all_pts is None:
        all_pts = pts

    brush = integral_ball(radius)
    if len(brush) == 1:
        return pts

    start_time = time.time()
    last_print_time = time.time()
    npts = 0
    orig_pts = dict([(p, False) for p in all_pts])
    for p in orig_pts.keys():
        for b in brush:
            t = TUPLE_ADD(p, b)
            if t not in orig_pts:
                orig_pts[p] = True
                break
        npts += 1
        if output_queue is None and time.time() - last_print_time > 0.5:
            last_print_time = time.time()
            sys.stderr.write("%d/%d (ETA: %f)\n" % (
                npts,
                len(pts),
                (len(pts) - npts) * (time.time() - start_time) / npts
            ))

    ret = [p for p, c in orig_pts.iteritems() if c]
    if output_queue is not None:
        output_queue.put(ret)
    return ret


def list_parallelize(items, args, func):
    """
    Given a list of items, some additional arguments, and a function to call,
    call that function like map but with chosen arguments using Process()
    objects. Assume that the function given takes in a Queue() as a final argument.
    """
    items_per_proc = int(
        math.ceil(1.0 * len(items) / multiprocessing.cpu_count()))
    item_chunks = [
        items[i:i + items_per_proc]
        for i in xrange(0, len(items), items_per_proc)
    ]
    output_queue = multiprocessing.Queue()
    procs = [
        multiprocessing.Process(
            target=func, args=(chunk, ) + args + (output_queue, ))
        for chunk in item_chunks
    ]

    for p in procs:
        p.start()
    running_procs = [p for p in procs]

    ret = set()
    while len(running_procs) > 0:
        for p in running_procs:
            p.join(0.0)
        while not output_queue.empty():
            ret.update(output_queue.get())
        time.sleep(0.25)
        running_procs = [p for p in running_procs if p.is_alive()]

    while not output_queue.empty():
        ret.update(output_queue.get())

    return list(ret)


def parallel_morphological_dilate(pts, radius=2):
    """
    Perform morphological dilation in parallel across cpu_count() processes.
    """
    return list_parallelize(pts, (radius, ), morphological_dilate)


def parallel_morphological_erode(pts, radius=2):
    """
    Perform morphological erosion in parallel across cpu_count() processes.
    """
    return list_parallelize(pts, (radius, pts), morphological_erode)


def morphological_dilate(pts, radius=2, output_queue=None):
    """
    Given a list of tuples of integer coordinates, all of the same dimension,
    dilate the list of points to include all points within the given radius of
    a point in the input list.
    """
    brush = integral_ball(radius)
    if len(brush) == 1:
        return pts
    new_pts = set()

    start_time = time.time()
    last_print_time = time.time()
    npts = 0
    for p in pts:
        for b in brush:
            t = TUPLE_ADD(p, b)
            new_pts.update([t])
        npts += 1
        if output_queue is None and time.time() - last_print_time > 0.5:
            last_print_time = time.time()
            sys.stderr.write("%d/%d (ETA: %f)\n" % (
                npts,
                len(pts),
                (len(pts) - npts) * (time.time() - start_time) / npts
            ))

    new_pts.update(pts)
    ret = list(new_pts)
    if output_queue is not None:
        output_queue.put(ret)
    return ret


def morphological_erode(pts, radius=2, all_pts=None, output_queue=None):
    """
    Given a list of tyuples of integer coordinates, all of the same dimension,
    erode the list of points to include only those points that include every
    point within radius units of it.
    """
    if all_pts is None:
        all_pts = pts

    brush = integral_ball(radius)
    if len(brush) == 1:
        return pts

    start_time = time.time()
    last_print_time = time.time()
    npts = 0
    orig_pts = dict([(p, True) for p in all_pts])
    for p in pts:
        for b in brush:
            t = TUPLE_ADD(p, b)
            if t not in orig_pts:
                orig_pts[p] = False
                break
        npts += 1
        if output_queue is None and time.time() - last_print_time > 0.5:
            last_print_time = time.time()
            sys.stderr.write("%d/%d (ETA: %f)\n" % (
                npts,
                len(pts),
                (len(pts) - npts) * (time.time() - start_time) / npts
            ))

    ret = [p for p in pts if orig_pts[p]]
    if output_queue is not None:
        output_queue.put(ret)
    return ret


def adjacency_vectors(position, forward, points):
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
        if TUPLE_DOT(forward, v) != 0:
            continue
        else:
            p = TUPLE_ADD(position, v)
            if p in points and points[p] == 0:
                adj.append(v)
    return [(vec, [v for v in UNIT_VECTORS if TUPLE_DOT(v, vec) == -1][0]) for vec in adj]

def slope_check_single(position, forward, points, aggressive=False, dim_weight=[1,2,4]):
    """
    Given a single point and a forward direction, determine whether a slope is suitable
    in the given forward direction, and if so, what slope value. Add the resulting values
    to the points dictionary
    """
    # In the case that the adjacency is ambiguous, try them all.
    adjacencies = adjacency_vectors(TUPLE_ADD(position, forward), forward, points)
    
    # If we're not aggressively smoothing, and there's more than one adjacency, skip them
    # as this is an interior corner.
    if not aggressive and len(adjacencies) > 1:
        return

    for down_vec, up_vec in adjacencies:
        perpendicular_vectors = [
            v for v in UNIT_VECTORS if TUPLE_DOT(v, forward) == 0 and v != down_vec
        ]

        # For each unit vector that is perpendicular to the forward vector, move up
        # to the maximum slope length along the forward vector, checking all around
        viable_slope = 0
        for slope_length in range(1, max(VALID_SLOPES) + 1):
            # The 'base' position along the forward vector from the starting position
            p = TUPLE_ADD(position, TUPLE_SCALE(slope_length, forward))

            # If there's no longer a full block adjacent to this position, break.
            a = TUPLE_ADD(p, down_vec)
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
                c = TUPLE_ADD(p, v)

                # If a neighbouring point is a slope, ignore it only consider full
                # blocks to cause interior corner issues.
                if c in points and points[c] == 0:
                    interior = True
                    break

            # if this is an interior point, then the viable slope is one less than
            # as far as we've gone. Otherwise, the viable slope is as far as we've
            # gone
            if interior and not aggressive:
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
            chosen_slope = max([
                slope_length for slope_length in VALID_SLOPES
                if slope_length <= viable_slope
            ])
            # Now, for each block along the forward vector, find if this chosen slope
            # conflicts with any other sloped blocks that exist along the forward
            # vector
            for i in range(1, chosen_slope + 1):
                p = TUPLE_ADD(position, TUPLE_SCALE(i, forward))
                # Gentler slopes take precendence, so if one is encountered, reduce
                # the viable slope length by one and try again. If this reduces it
                # below 1, then no slope is added.
                #
                # Perfer slopes away from the origin over slopes toward the origin.
                # In the event that two slopes slope away from the origin in the same
                # number of components, consider the dim_weight passed in.

                # If a slope block already exists, only overwrite it if:
                # - Ours points more away from the origin (forward)
                # - Ours faces more away from the origin (up)
                # - Ours is gentler

                # If the location we're considering is occupied...
                if p in points and points[p] is not None:
                    # If the one that exists is gentler than we are, we don't want to clobber it
                    test_slope = leq(points[p][0][0], chosen_slope)

                    if dim_weight is not None:
                        p_weight = TUPLE_MUL(SIGN_V(p), dim_weight)
                        # Only consider placing slopes that are at least as 'pointing away' as any
                        # that already exist. This is True if ours points 'more away' than the other
                        test_forward = leq(TUPLE_DOT(p_weight, points[p][1][0]),
                                           TUPLE_DOT(p_weight, forward))
                        test_up = leq(TUPLE_DOT(p_weight, points[p][1][1]),
                                      TUPLE_DOT(p_weight, up_vec))
                    else:
                        test_forward = None
                        test_up = None

                    # If all values are equal delete the block and return a non-clear path as this
                    # clearly can't be decided.
                    if test_forward is None and test_up is None and test_slope is None:
                        points[p] = None
                        chosen_slope -= 1
                        viable_slope = chosen_slope
                        clear_path = False
                        break
                    # If this one is more forward, replace it.
                    # If this one is 'just as' forward, but more up, replace it.
                    # If this one is just as forward and up, but gentler, replace it.
                    elif test_slope or \
                        (test_slope is None and test_forward) or \
                        (test_slope is None and test_forward is None and test_up):
                        clear_path = True
                    else:
                        chosen_slope -= 1
                        viable_slope = chosen_slope
                        clear_path = False
                        break
                else:
                    clear_path = True

        # sys.stderr.write("%d\n" % chosen_slope)
        # Now that the slope has been chosen, fill in the appropriate parts of the
        # points dict.
        for i in range(1, chosen_slope + 1):
            p = TUPLE_ADD(position, TUPLE_SCALE(i, forward))
            points[p] = ((chosen_slope, i), (forward, up_vec))

    return points


def fill_corners(Points):
    """
    For a given set of points (dictionary mapping coordinates to block type), find all unambiguous
    places to place corner blocks.
    """
    corner_mapping = {
        ((1, 1), (1, 1)): 'Corner'
    }
    # For a location to be valid for a corner filling, there needs to be exactly
    # two adjacent blocks with appropriate orientations that are the same time.
    offsets = [(i, j, k)
               for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)
               if abs(i) + abs(j) + abs(k) == 2]

    # Iterate over all blocks in the object at this point, only considering slant
    # blocks, and identify any where there is a candidate nearby.
    corners = dict()
    for coord, block in Points.iteritems():
        # If it is a plain cube, skip it.
        if block == 0:
            continue

        # Otherwise, look at all of the midpoints of the edges of the cube centred
        # on this location for a block that is the same as this.
        for offset in offsets:
            other_coord = TUPLE_ADD(coord, offset)
            other_block = Points.get(other_coord, None)
            # If this point isn't there, or it is a cube, then move to the next offset.
            if other_block is None or other_block == 0:
                continue

            # Otherwise, check to see that the slope type and the slope part
            # match. Then check that the up vectors match. Then check that the
            # forward vectors are perpendicular and cross to 
            if block[0] == other_block[0] and \
                block[1][1] == other_block[1][1] and \
                TUPLE_DOT(block[1][0], other_block[1][0]) == 0:
                corner_type = None
                corner_coord = None
                # Additional check for an interior closed-off corner:
                #  - The two slopes need to have position+forward be equal.
                if TUPLE_ADD(coord, block[1][0]) == TUPLE_ADD(other_coord, other_block[1][0]):
                    corner_type = 'CutCorner'
                    # For a closed off interior corner, the corner coordiante
                    # is the position of one slope MINUS the forward direction
                    # of the other slope.
                    corner_coord = TUPLE_SUB(coord, other_block[1][0])

                # Additional check for simple corner:
                #  - The two slopes need to have position-forward be equal.
                if TUPLE_SUB(coord, block[1][0]) == TUPLE_SUB(other_coord, other_block[1][0]):
                    corner_type = ('Corner', block[0])
                    # For a normal interior corner, the corner coordinate is
                    # the position of one of the slopes plus the forward of
                    # the other slope.
                    corner_coord = TUPLE_ADD(coord, other_block[1][0])

                # If neither corner type was found, then do nothing.
                if corner_type is None:
                    continue
                # If a corner type was found, ensure that the space is empty in
                # the existing point set.
                elif corner_coord not in Points:
                    corners[corner_coord] = (
                        corner_type,
                        block[1]
                    )

    Points.update(corners)
    return Points


def smooth_pts(PointTriples, aggressive=False):
    """
    Given a collection of points (assumed to be cubic voxels), identify and build
    the list of slanted/sloped voxel elements that will help smooth out the voxel
    surface while remaining, locally, within the convex hull of the voxel surface.
    """
    # First, create a dict that maps from the points to the slope values
    pts = dict([(p, 0) for p in PointTriples])

    start_time = time.time()
    last_print_time = time.time()
    npts = 0
    # For each point check along each unit vector to see if there are any blocks
    # that would make that direction an interior corner.
    for p in pts.keys():
        for v in UNIT_VECTORS:
            slope_check_single(p, v, pts, aggressive)
        npts += 1
        if time.time() - last_print_time > 0.5:
            last_print_time = time.time()
            sys.stderr.write("%d/%d (ETA: %f)\n" % (
                npts,
                len(pts),
                (len(pts) - npts) * (time.time() - start_time) / npts
            ))

    # Throw away any points with a value of None
    pts = dict([(k, v) for k, v in pts.iteritems() if v is not None])
    return pts


def map_to_empyrion_codes(points):
    block_type_mapping = {
        0: 0x0,
        (1, 1): 0x14,
        'CutCorner': 0x02,
        ('Corner', (1, 1)): 0x0c,
        (2, 1): 0x12,
        (2, 2): 0x10,
        ('Corner', (2, 1)): 0x08,
        ('Corner', (2, 2)): 0x0a
    }
    slope_code_mapping = {
        177: ((0, 0, -1), (1, 0, 0)),
        9: ((1, 0, 0), (0, 1, 0)),
        137: ((1, 0, 0), (0, 0, -1)),
        89: ((1, 0, 0), (0, 0, 1)),
        33: ((0, 0, 1), (0, -1, 0)),
        1: ((0, 0, 1), (0, 1, 0)),
        97: ((0, 0, 1), (-1, 0, 0)),
        81: ((0, -1, 0), (0, 0, 1)),
        41: ((-1, 0, 0), (0, -1, 0)),
        185: ((0, 1, 0), (1, 0, 0)),
        105: ((0, 1, 0), (-1, 0, 0)),
        129: ((0, 1, 0), (0, 0, -1)),
        161: ((0, 0, 1), (1, 0, 0)),
        25: ((-1, 0, 0), (0, 1, 0)),
        153: ((-1, 0, 0), (0, 0, -1)),
        73: ((-1, 0, 0), (0, 0, 1)),
        49: ((0, 0, -1), (0, -1, 0)),
        17: ((0, 0, -1), (0, 1, 0)),
        113: ((0, 0, -1), (-1, 0, 0)),
        65: ((0, 1, 0), (0, 0, 1)),
        57: ((1, 0, 0), (0, -1, 0)),
        169: ((0, -1, 0), (1, 0, 0)),
        121: ((0, -1, 0), (-1, 0, 0)),
        145: ((0, -1, 0), (0, 0, -1))
    }
    slope_orientation_mapping = dict(
        [(v, k) for k, v in slope_code_mapping.iteritems()])

    blocks = []
    for position, block in points.iteritems():
        blocks.append(position + (block_type_mapping[block[
            0] if block != 0 else 0], slope_orientation_mapping[block[1]]
                                  if block != 0 else 1))
    return blocks


def blocks_to_csv(blocks):
    return [
        "{:d},{:d},{:d},{:d},{:d}".format(b[0], b[1], b[2], b[3], b[4])
        for b in blocks
    ]


def dbm_bitmask(dbm, block_type="\x87"):
    block_strings = ""
    bm = []

    # Current mask, and the bit being twiddled.
    # When this rolls over, it gets appended to the bm list.
    cm = 0
    cb = 1

    for i in range(len(dbm)):
        x = dbm[i]
        for j in range(len(x)):
            y = x[j]
            for k in range(len(y)):
                z = y[k]
                if z != False:
                    #block_strings += "\x87\x01\x00\x00"
                    block_strings += block_type + \
                                     (chr(z[1]) if len(z) > 1 else chr(1)) + \
                                     chr(0) + \
                                     (chr(z[0]) if len(z) > 0 else chr(0))
                    cm += cb
                cb *= 2
                if cb > 128:
                    bm.append(cm)
                    cb = 1
                    cm = 0
    if cb > 1:
        bm.append(cm)
    return (bm, block_strings)


def sparse_to_dense(positions, meta, l, w, h):
    # Map the numeric axes, in terms of the major-ordering of the arrays, to the named axes
    Z = (l, 0)
    Y = (w, 1)
    X = (h, 2)

    a = [[[False for _ in range(Z[0])] for _ in range(Y[0])]
         for _ in range(X[0])]

    for p, m in zip(positions, meta):
        P = [p[X[1]], p[Y[1]], p[Z[1]]]
        a[P[0]][P[1]][P[2]] = m

    return a


def list_subtract(l1, l2):
    return [l1[i] - l2[i] for i in range(len(l1))]


def bounding_box(positions):
    m = [min([p[i] for p in positions]) for i in range(3)]
    M = [max([p[i] for p in positions]) for i in range(3)]
    return (m, M)

def iterative_flood_fill(dbm, start, VisitedType):
    """
    Use a manual stack context to iteratively flood-fill the volume around the hull.
    """
    M = (len(dbm), len(dbm[0]), len(dbm[0][0]))
    directions = UNIT_VECTORS

    cur_pos = start
    # Each item in the rail is a position, and the directions we have left to try starting at that
    # position.
    trail = [(cur_pos, copy(UNIT_VECTORS))]

    # Prime the pump by testing the start, which is guaranteed to be in-bounds, but not guaranteed
    # to be unoccupied or unvisited. If the position has been visited, but is unoccupied, then the
    # value will be changed from False to None. If the position is occupied, then it will have a
    # value that is neither False nor None.
    if dbm[cur_pos[0]][cur_pos[1]][cur_pos[2]] == None:
        return 0
    elif isinstance(dbm[cur_pos[0]][cur_pos[1]][cur_pos[2]], VisitedType):
        return 0
    elif dbm[cur_pos[0]][cur_pos[1]][cur_pos[2]] != False:
        dbm[cur_pos[0]][cur_pos[1]][cur_pos[2]] = VisitedType(
            dbm[cur_pos[0]][cur_pos[1]][cur_pos[2]])
        return 1

    n_visits = 0
    # While the trail still has items in it...
    while len(trail) > 0:
        # If the current position has no more places to move to, pop it off (we're done with it),
        # move back to the previous position, and continue.
        if len(trail[-1][1]) == 0:
            trail.pop()
            if len(trail) > 0:
                cur_pos = trail[-1][0]
        # If there are still directions to try from the current position...
        else:
            # Pop a direction
            d = trail[-1][1].pop()
            next_pos = TUPLE_ADD(cur_pos, d)

            # Check to see if the next position is one of the following:
            # - Is out of bounds in any component (in which case we do nothing and iterate)
            if not TUPLE_LE((-1, -1, -1), next_pos) or not TUPLE_LE(next_pos, M):
                pass
            # - Is empty, but has been visited (in which case we don't move there): None
            elif dbm[next_pos[0]][next_pos[1]][next_pos[2]] is None:
                pass
            # - Is occupied and has been visited (in which case we do nothing and iterate): (True,)
            elif isinstance(dbm[next_pos[0]][next_pos[1]][next_pos[2]], VisitedType):
                pass
            # - Is occupied, but has not been visited (in which case we dont move there, and mark
            #   if as occupied and visited): True
            elif dbm[next_pos[0]][next_pos[1]][next_pos[2]] == False:
                # If the tests pass, this becomes the new current position, so push it, and a
                # fresh set of directions to try at this new position.
                trail.append((next_pos, copy(UNIT_VECTORS)))
                cur_pos = next_pos

                # If we reach this point, then the current position should be marked as having been
                # visited by the flood fill. This is distinguished from an unvisited location by
                # being set to None as opposed to False.
                #
                # This line will only execute when visiting valid new empty spaces.
                dbm[cur_pos[0]][cur_pos[1]][cur_pos[2]] = None
            else:
                n_visits += 1
                dbm[next_pos[0]][next_pos[1]][next_pos[2]] = VisitedType(
                    dbm[next_pos[0]][next_pos[1]][next_pos[2]])


    return n_visits


def flood_hollow_dbm(dbm, positions, test=lambda _: False):
    """
    Given a dense boolean matrix of which positions are filled, and the positions mapping, perform
    a flood fill from every point on the exterior of the bounding box, and remove all positions
    that aren't touched by the flood.
    """
    class __VisitedPosition:
        def __init__(self, val):
            self.val = val

    # For each positions on the edge of the bounding box, start to run a flood.
    # If the starting position is occupied, do nothing and move to the next.
    # If the starting position has been filled by a previous flood, do nothing and move on.
    x = len(dbm)
    y = len(dbm[0])
    z = len(dbm[0][0])

    starting_positions = [
        t for u in [[(0, j, k), (x-1, j, k)] for j in range(y) for k in range(z)] for t in u
    ]
    starting_positions += [
        t for u in [[(i, 0, k), (i, y-1, k)] for i in range(x) for k in range(z)] for t in u
    ]
    starting_positions += [
        t for u in [[(i, j, 0), (i, j, z-1)] for i in range(x) for j in range(y)] for t in u
    ]
    starting_positions = list(set(starting_positions))

    for start in starting_positions:
        iterative_flood_fill(dbm, start, __VisitedPosition)

    # Now that we've flooded the exterior, go through and prune anything that wasn't touched in the
    # flood. Also reset any point that was flooded but not originally filled to empty.
    pruned_positions = set()
    for i in range(x):
        for j in range(y):
            for k in range(z):
                # Visited locations that were occupied will be set to (True, <original_value>), and
                # this is exactly the set of locations that should be set to True; all others
                # should be set to False
                if isinstance(dbm[i][j][k], __VisitedPosition):
                    dbm[i][j][k] = dbm[i][j][k].val
                # The exception tot he above rule is the test parameter. If this evaluates to True
                # on the value of a given position, then that position should be spared.
                elif test(dbm[i][j][k]):
                    pass
                else:
                    # If the position is True, then it was set, but not visited and should be
                    # deleted.
                    if dbm[i][j][k] not in (None, False):
                        pruned_positions.add((k, j, i))
                    dbm[i][j][k] = False

    if isinstance(positions, list):
        return dbm, [pos for pos in positions if tuple(pos) not in pruned_positions]
    elif isinstance(positions, dict):
        return dbm, dict([(pos, positions[pos]) for
                          pos in [p for p in positions.keys() if p not in pruned_positions]])

def generate_blocks(positions, meta, flood_hollow):
    # The string used for each block, corresponds to a steel cube.
    # The four bytes are (in order):
    # - Block type
    #  > 0x87 = Steel-Small
    #  > 0x8a = Hardened Steel
    #  > 0x9c = CombatSteel-Large
    # - Rotation (Code, Forward, Up) with vectors as (x, y, z)
    #  > 0x01, +y, +z
    #  > 0x09, +x, +z
    #  > 0x11, -y, +z
    #  > 0x19, -x, +z
    #  > 0x21, +y, +x
    #  > 0x29, +z, +x
    #  > 0x31, -y, +x
    #  > 0x39, -z, +x
    #  > 0x41, -y, -z
    #  > 0x49, -x, -z
    #  > 0x51, +y, -z
    #  > 0x59, +x, -z
    #  > 0x61, +y, -x
    #  > 0x69, +z, -x
    #  > 0x71, -y, -x
    #  > 0x79, -z, -x
    #  > 0x81, +z, -y
    #  > 0x89, +x, -y
    #  > 0x91, -z, -y
    #  > 0x99, -x, -y
    #  > 0xA1, -x, +y
    #  > 0xA9, -z, +y
    #  > 0xB1, +x, +y
    #  > 0xB9, +z, +y
    # - 0x00 ???
    # - Blocktype variant
    #  > 0x14 = Slope 1:1 Solid
    #  > 0x12 = Slope 1:2 Top Solid
    #  > 0x10 = Slope 1:2 Bottom Solid
    #  > 0x0c = Corner
    #  > 0x0a = Corner D
    #  > 0x08 = Corner C
    #  > 0x06 = Corner B
    #  > 0x04 = Corner A
    #  > 0x02 = Cut Corner
    #  > 0x00 = Full Cube
    block_type = "\x87"
    block_rotation = "\x01"
    block_shape = "\x00"
    #block_string = "\x87\x01\x00\x00"

    # Step 1: Figure out how big the bounding box is, calculate the two opposing corners.
    m, M = bounding_box(positions)

    # Step 2: Move all positions by the minimal corner, putting one corner at the origin,
    # and move the maximal corner
    length, width, height = list_subtract(M, m)
    length += 1
    width += 1
    height += 1
    sys.stderr.write("Dimensions of resulting blueprint: %d %d %d\n" %
                     (length, width, height))
    positions = [list_subtract(p, m) for p in positions]
    #sys.stderr.write(repr(positions) + "\n")

    # Step 3: Now that we have the size of the object, calculate the header
    n_hdr_bytes = int(math.ceil(length * width * height / 8.0))
    sys.stderr.write("Model requires %d header bytes\n" % n_hdr_bytes)
    output = struct.pack("<L", n_hdr_bytes)

    # Step 3: Given the positions of the blocks, derive the cuboid-filling bit mask
    # for block/space. This is equivalent to convert a sparse 1-0 matrix to a dense matrix
    #
    # This just returns a dense True/False matrix, which needs to be serialized into a bitmask.
    dense_boolean_matrix = sparse_to_dense(positions, meta, length, width,
                                           height)
    if flood_hollow:
        sys.stderr.write("Performing flood-fill hollowing pass 2 (removing internal slopes).\n")
        t0 = time.time()
        n_positions = len(positions)
        (dense_boolean_matrix,
         positions) = flood_hollow_dbm(dense_boolean_matrix, positions,
                                       lambda v: isinstance(v, tuple) and v == (0, 1))
        t1 = time.time()
        sys.stderr.write("Reduced from %d to %d blocks in %f seconds.\n" % (
            n_positions, len(positions), t1 - t0))

    bm_list, block_strings = dbm_bitmask(dense_boolean_matrix, block_type)
    output += "".join([struct.pack('B', bm) for bm in bm_list])
    set_bits = 0
    for b in bm_list:
        for i in range(8):
            if b & (1 << i):
                set_bits += 1
    sys.stderr.write("%d bits set in header bytes for %d blocks.\n" %
                     (set_bits, len(positions)))

    # Step 4: Fill in the body/footer with steel blocks and whatever the footer represents.
    # We need to build a mapping of positions to order to look up the positions and
    # place the right block at the right positions in the Blueprint.
    output += block_strings

    # Step 5: Fill in the footer, which we'll just ignore ... ???
    # There are four 'section', each with the same format as the block type header,
    # probably representing rotation, texture, symbol, and symbol somehow.
    output += "\x01\x7f"
    for i in xrange(4):
        output += struct.pack("<L", n_hdr_bytes)
        output += "\x00" * n_hdr_bytes

    #sys.stderr.write(output.encode("hex") + "\n")
    return (output, length, width, height)


def csv_to_array(csv):
    return [[int(float(i)) for i in l.strip().split(",")]
            for l in csv.strip().split("\n")]


def build_new_bp(bp_body, positions, bp_class, flood_hollow):
    blueprint_class_mapping = {
        "CV": chr(8),
        "BA": chr(2),
        "HV": chr(16),
        "SV": chr(4)
    }

    new_blocks, length, width, height = generate_blocks(
        [tuple(p[:3]) for p in positions], [tuple(p[3:]) for p in positions], flood_hollow)

    sso = StringIO.StringIO()
    zf = zipfile.ZipFile(sso, 'w', zipfile.ZIP_DEFLATED)
    zf.writestr('0', new_blocks)
    zf.close()

    # The Empyrion Blueprints don't include the first PK, so don't read that.
    sso.seek(2)
    new_zip = sso.read()

    # Write out:
    # - The initial global header
    #  > Byte 0x08: 00=UNKNOWN, 02=BA, 04=SV, 08=CV, 16=HV
    # - Rebuild the dimensions
    # - The device groupings from the original BP
    # - Replace the zip section with our newly built one

    if bp_class is None:
        header = bp_body[:9]
    else:
        header = bp_body[:8]
        class_code = blueprint_class_mapping[bp_class]
        header += class_code

    new_bp = header + \
    struct.pack("<LLL", int(length), int(width), int(height)) + \
    bp_body[21:bp_body.rfind('\x03\x04\x14\x00\x00\x00\x08\x00')] + \
    new_zip

    return new_bp
