#!/usr/bin/env python
"""
Implements a generic function that ingests either a text STL file on stdin,
or a Lambda event body, and performs the necessary functions.
"""

import sys
import json
import time
import base64
import urllib2
import StringIO
import threading

import empyrion


class StderrFlusher(threading.Thread):
    """
    Class that asynchronously flushes stderr ten times per second to ensure
    that output is emitted to the pipe in a timely fashion.
    """

    def __init__(self):
        threading.Thread.__init__(self)
        self.running = True

    def run(self):
        while self.running:
            sys.stderr.flush()
            time.sleep(0.1)


def lambda_handler(event, _):
    """
    Given a Lambda event body, ready the STL file and generate a new blueprint
    based on the parameters.
    """
    operation_start = time.time()
    stl_body = base64.b64decode(event['STLBody'])
    disable_smoothing = event.get('DisableSmoothing', False)
    corner_blocks = event.get('CornerBlocks', False)
    voxel_dimension = event.get('BlueprintSize', 25)
    dim_remap = event.get('DimensionRemap', [1, 2, 3])
    dim_mirror = event.get('DimensionMirror', [])
    bp_class = event.get('BlueprintClass', 'SV')
    morphological_factors = event.get('MorphologicalFactors', None)
    hollow_radius = event.get('HollowRadius', None)
    no_multithreading = event.get('NoMultithreading', False)

    with open('BlueprintBase/BlueprintBase.epb', 'r') as fp:
        bp_body = fp.read()

    ssi = StringIO.StringIO(stl_body)
    timer_start = time.time()
    triangles = empyrion.STLFile.read_triangles(ssi)
    sys.stderr.write("Reading model took %s seconds.\n" %
                     str(time.time() - timer_start))
    sys.stderr.write("Model has %d triangles\n" % len(triangles))

    if len(triangles) == 0:
        return ""

    bounds = empyrion.triangle_list_bounds(triangles)
    sys.stderr.write("Model bounds: %s\n" % str(bounds))

    # To assist with ensuring symmetry, shift the points so that the centroid
    # of the model is at the origin. Find the midpoint along each of dimensions
    # of the cube spanned by the bounds of the model, and subtract that midpoint
    # from each triangle coordinate.
    origin_offset = [-sum(b) / 2 for b in bounds]
    for t in triangles:
        t.shift(origin_offset)

    # For clarity, show the transpose model bounds, which should be symmetric.
    bounds = empyrion.triangle_list_bounds(triangles)
    sys.stderr.write("Translated model bounds: %s\n" % str(bounds))

    # First, see if the voxel_dimension is s list, and if it isn't use the
    # longest dimension.
    if isinstance(voxel_dimension, list):
        dim, size = voxel_dimension
        resolution = (bounds[dim - 1][1] - bounds[dim - 1][0]) / (size - 1)
    else:
        longest_dim = max([i[1] - i[0] for i in bounds])
        resolution = longest_dim / (abs(voxel_dimension) - 1)

    sys.stderr.write("Computed spatial resolution in model-space: %f\n" %
                     resolution)

    sys.stderr.write("Splitting triangles...\n")
    timer_start = time.time()
    if empyrion.parallel() and not no_multithreading:
        pts = empyrion.parallel_split_tris(triangles, resolution)
    else:
        pts = empyrion.split_tris(triangles, resolution)
    sys.stderr.write("Triangle to point refinement took %s seconds.\n" %
                     str(time.time() - timer_start))
    sys.stderr.write("Split %d triangles into %d points.\n" %
                     (len(triangles), len(pts)))

    # Mirror the dimensions listed. For each dimension, just negate the coordinates
    # of all points in that dimension
    timer_start = time.time()
    pts = [tuple([p[dim_remap[i] - 1] for i in range(3)]) for p in pts]
    tuple_mul = lambda t1, t2: (t1[0] * t2[0], t1[1] * t2[1], t1[2] * t2[2])
    dim_mirror_tuple = [-1 if i + 1 in dim_mirror else 1 for i in range(3)]
    pts = [tuple_mul(dim_mirror_tuple, p) for p in pts]
    sys.stderr.write("Dimension mirroring and remapping took %s seconds.\n" %
                     str(time.time() - timer_start))

    if morphological_factors is not None:
        sys.stderr.write("Dilating voxel cloud...\n")
        timer_start = time.time()
        if empyrion.parallel() and not no_multithreading:
            pts = empyrion.parallel_morphological_dilate(
                pts, morphological_factors[0])
        else:
            pts = empyrion.morphological_dilate(pts, morphological_factors[0])
        sys.stderr.write("Morphological dilation took %s seconds.\n" %
                         str(time.time() - timer_start))
        sys.stderr.write("Morphological dilation expanded to %d points.\n" %
                         len(pts))

        sys.stderr.write("Eroding voxel cloud...\n")
        timer_start = time.time()
        if empyrion.parallel() and not no_multithreading:
            pts = empyrion.parallel_morphological_erode(
                pts, morphological_factors[1])
        else:
            pts = empyrion.morphological_erode(pts, morphological_factors[1])
        sys.stderr.write("Morphological erosion took %s seconds.\n" %
                         str(time.time() - timer_start))
        sys.stderr.write("Morphological erosion reduced to %d points.\n" %
                         len(pts))

    if not disable_smoothing:
        sys.stderr.write("Smoothing voxel cloud...\n")
        timer_start = time.time()
        smoothed_pts = empyrion.smooth_pts(pts)
        sys.stderr.write("Voxel smoothing took %s seconds.\n" %
                         str(time.time() - timer_start))
        sys.stderr.write("Smoothed %d voxels into %d blocks.\n" %
                         (len(pts), len(smoothed_pts)))
    else:
        # Otherwise naively convert the list of coordinates into a mapping to
        # all cubes.
        smoothed_pts = dict([(p, 0) for p in pts])

    if corner_blocks:
        timer_start = time.time()
        pre_corner_count = len(smoothed_pts)
        smoothed_pts = empyrion.fill_corners(smoothed_pts)
        sys.stderr.write("Filled in %d corner blocks in %s seconds.\n" %
                         (len(smoothed_pts) - pre_corner_count,
                          str(time.time() - timer_start)))

    if hollow_radius is not None:
        sys.stderr.write("Hollowing voxel cloud...\n")
        timer_start = time.time()
        if empyrion.parallel() and not no_multithreading:
            passing_blocks = empyrion.hollow(smoothed_pts.keys(),
                                             hollow_radius)
        else:
            passing_blocks = empyrion.hollow(smoothed_pts, hollow_radius)
        # The passing blocks are all of the block coordinates we should keep
        smoothed_pts = dict([(c, smoothed_pts[c]) for c in passing_blocks])
        sys.stderr.write("Model hollowing took %s seconds.\n" %
                         str(time.time() - timer_start))
        sys.stderr.write("Hollowed down to %d blocks.\n" % len(smoothed_pts))

    timer_start = time.time()
    mapped_blocks = empyrion.map_to_empyrion_codes(smoothed_pts)
    new_bp = empyrion.build_new_bp(bp_body, mapped_blocks, bp_class)
    sys.stderr.write("Blueprint generation took %s seconds.\n" %
                     str(time.time() - timer_start))
    sys.stderr.write("Resulting blueprint size: %d bytes\n" % len(new_bp))
    sys.stderr.write("Voxelization operation took %s seconds.\n" %
                     str(time.time() - operation_start))

    return base64.b64encode(new_bp)


def blueprint_size(v):
    """
    Parse a string as a blueprint size:
    - Either an integer >= 1
    - An integer in (1,2,3), a comma, an integer >= 1
    """
    try:
        iv = int(v)
        if iv < 1:
            raise ValueError("Dimension size must be at least 1")
        return iv
    except ValueError:
        dimS, sizeS = v.split(',')
        dim = int(dimS)
        size = int(sizeS)
        if dim not in [1, 2, 3]:
            raise ValueError('Dimension for blueprint size must be 1, 2, or 3')
        if dim < 1:
            raise ValueError("Dimension size must be at least 1")
        return [dim, size]


def version_check():
    """
    Check GitHub for the latest version tag, and the versio tag of this commit
    """
    try:
        with open('git.json', 'r') as fp:
            git_md = json.loads(fp.read())
    except IOError:
        # In the event that there is no git metadata, just print null values
        # twice.
        print "null"
        print "null"

    if git_md['GitHub']:
        if git_md['GitHubUser'] is not None and git_md[
                'GitHubRepo'] is not None:
            latest_release = json.loads(
                urllib2.urlopen(
                    "https://api.github.com/repos/%s/%s/releases/latest" % (
                        git_md['GitHubUser'], git_md['GitHubRepo'])).read())
            latest_tag = latest_release['tag_name']

            # Go through all of the tags to see if this commit matches a tag.
            tags = json.loads(
                urllib2.urlopen(
                    "https://api.github.com/repos/%s/%s/git/refs/tags" % (
                        git_md['GitHubUser'], git_md['GitHubRepo'])).read())

            current_tag = "Unreleased"
            for tag in tags:
                if tag['object']['sha'] == git_md['GitSHA']:
                    current_tag = tag['ref'].split('/')[-1]

            print current_tag
            print latest_tag
        else:
            print "MissingGitHubDetails"
            print "MissingGitHubDetails"
    else:
        # In the event that there is a git file, but it doesn't indicate GitHub
        # then just print some stuff indicating that.
        print "NonGitHub"
        print "NonGitHub"


def __main():
    import json
    import argparse

    if not sys.stdin.isatty():
        input_data = sys.stdin.read()
    else:
        input_data = None

    try:
        pargs = None
        new_bp_64 = lambda_handler(json.loads(input_data), None)
    except Exception:
        parser = argparse.ArgumentParser(
            description="""Takes a text format STL file on stdin, and prints an
            Empytion blueprint file to stdout.""")
        parser.add_argument(
            "--stl-file",
            required=False,
            default=None,
            help="Filename of the input STL file.")
        parser.add_argument(
            "--blueprint-output-file",
            required=False,
            default=None,
            help="""Filename of the file to write the output blueprint to. All
            contents will be overwritten if the file already exists.""")
        parser.add_argument(
            "--blueprint-size",
            required=False,
            default=25,
            type=blueprint_size,
            help="""Number of blocks (on the longest dimension) to use in the
            resulting Blueprint resolution. If a value of the form '1,50' is
            given, then the model is chosen to have a size of 50 in the first
            dimension. Viable dimension indicators are 1, 2, or 3.""")
        parser.add_argument(
            "--dimension-remap",
            required=False,
            default="1,2,3",
            help="A permutation of 1,2,3 to remap the coordinates. Example: 1,3,2"
        )
        parser.add_argument(
            "--dimension-mirror",
            required=False,
            default="",
            help="""A list of 1, 2 and/or 3 that indicates which dimensions the
            model should be reflected in.""")
        parser.add_argument(
            "--blueprint-class",
            required=False,
            default=None,
            help="The class (CV, HV, SV, BA) of the blueprint.")
        parser.add_argument(
            "--morphological-factors",
            required=False,
            default=None,
            help="""A positive integer value indicating how much morphological smoothing/filling
            to do. If given as two positive integer values separated by a comma, the first value
            will be used for dilation, and the second value will be used for erosion."""
        )
        parser.add_argument(
            "--hollow-radius",
            required=False,
            default=None,
            type=int,
            help="""A positive integer value indicating how much hollowing to perform
            after the smoothing process. Best used in conjunction with morphological
            smoothing to hollow out filled interiors. Larger values result in thicker
            walls.""")
        parser.add_argument(
            "--disable-smoothing",
            required=False,
            default=False,
            action='store_true',
            help="""Disable the addition of slanted or other non-cube blocks to the
            resulting voxel model.""")
        parser.add_argument(
            "--corner-blocks",
            action='store_true',
            default=False,
            help="""Whether or not corner blocks should be added when the choice and
            placement are unambiguous.""")
        parser.add_argument(
            "--disable-multithreading",
            required=False,
            default=False,
            action='store_true',
            help="""Force the use fo single-threaded code and disabeles the use of
            multiprocessing modules even if they are available.""")
        parser.add_argument(
            "--version-check",
            required=False,
            default=False,
            action='store_true',
            help="""When specified, overrides all other behaviours and simply checks
            with GitHub to determine if this is the latest version or not. Always
            prints the current version on the first line, and the newest version
            on the second line.""")
        pargs = parser.parse_args()

        if pargs.version_check:
            version_check()
            return

        if pargs.stl_file is not None:
            with open(pargs.stl_file, 'rb') as fp:
                input_data = fp.read()

        if input_data is None:
            sys.stderr.write("")
            return

        if pargs.morphological_factors is not None:
            m_factors = [
                int(f) for f in pargs.morphological_factors.strip().split(",")
            ]
            if len(m_factors) == 1:
                m_factors = m_factors * 2
        else:
            m_factors = None

        lambda_body = {
            'STLBody':
            base64.b64encode(input_data),
            'DisableSmoothing':
            pargs.disable_smoothing,
            'CornerBlocks':
            pargs.corner_blocks,
            'DimensionRemap':
            [int(d) for d in pargs.dimension_remap.split(",")],
            'DimensionMirror':
            [int(p) for p in pargs.dimension_mirror.split(',') if p != ""],
            'BlueprintSize':
            pargs.blueprint_size,
            'BlueprintClass':
            pargs.blueprint_class
            if pargs.blueprint_class in ['HV', 'SV', 'CV', 'BA'] else 'SV',
            'MorphologicalFactors':
            m_factors,
            'HollowRadius':
            pargs.hollow_radius,
            'NoMultithreading':
            pargs.disable_multithreading
        }

        flusher = StderrFlusher()
        flusher.start()

        new_bp_64 = lambda_handler(lambda_body, None)

        flusher.running = False
        flusher.join()

    if pargs is not None and pargs.blueprint_output_file is not None:
        with open(pargs.blueprint_output_file, 'wb') as fp:
            fp.write(base64.b64decode(new_bp_64))
    else:
        sys.stdout.write(base64.b64decode(new_bp_64))


if __name__ == "__main__":
    __main()
