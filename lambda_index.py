#!/usr/bin/env python

"""
Implements a generic function that ingests either a text STL file on stdin,
or a Lambda event body, and performs the necessary functions.
"""

import os
import sys
import base64
import StringIO

import empyrion


def lambda_handler(Event, Context):
    """
    Given a Lambda event body, ready the STL file and generate a new blueprint
    based on the parameters.
    """
    stl_body = base64.b64decode(Event['STLBody'])
    voxel_dimension = int(Event[
        'BlueprintSize']) if 'BlueprintSize' in Event else 25
    dim_remap = Event[
        'DimensionRemap'] if 'DimensionRemap' in Event else [1, 2, 3]
    dim_mirror = Event['DimensionMirror'] if 'DimensionMirror' in Event else []
    bp_class = Event['BlueprintClass'] if 'BlueprintClass' in Event else 'SV'

    with open('BlueprintBase/BlueprintBase.epb', 'r') as fp:
        bp_body = fp.read()

    ssi = StringIO.StringIO(stl_body)
    solids = empyrion.STLFile.read_solids(ssi)
    triangles = [e for s in solids for e in s[1]]
    sys.stderr.write("Model has %d triangles\n" % len(triangles))

    if len(triangles) == 0:
        return ""

    bounds = empyrion.triangle_list_bounds(triangles)
    sys.stderr.write("Model bounds: %s\n" % str(bounds))
    longest_dim = max([i[1] - i[0] for i in bounds])
    resolution = longest_dim / float(voxel_dimension)
    sys.stderr.write("Computed spatial resolution in model-space: %f\n" % resolution)

    shm_stat = None
    try:
        shm_stat = os.stat('/dev/shm')
    except OSError as e:
        if e.errno != 2:
            raise e

    if shm_stat is None:
        pts = empyrion.split_tris(triangles, resolution)
    else:
        pts = empyrion.parallel_split_tris(triangles, resolution)

    pts = [tuple([p[dim_remap[i] - 1] for i in range(3)]) for p in pts]
    sys.stderr.write("Split %d triangles into %d points.\n" % (len(triangles), len(pts)))

    # Mirror the dimensions listed
    for d in dim_mirror:
        pass

    smoothed_pts = empyrion.smooth_pts(pts)
    mapped_blocks = empyrion.map_to_empyrion_codes(smoothed_pts)
    sys.stderr.write("Smoothed %d voxels into %d blocks.\n" % (len(pts), len(mapped_blocks)))

    new_bp = empyrion.build_new_bp(bp_body, mapped_blocks, bp_class)
    sys.stderr.write("Resulting blueprint size: %d bytes\n" % len(new_bp))

    return base64.b64encode(new_bp)

if __name__ == "__main__":
    import json
    import argparse

    if not sys.stdin.isatty():
        input_data = sys.stdin.read()
    else:
        input_data = None

    try:
        new_bp_64 = lambda_handler(json.loads(input_data), None)
    except Exception:
        parser = argparse.ArgumentParser(
            description="Takes a text format STL file on stdin, and prints an Empytion blueprint file to stdout."
        )
        parser.add_argument(
            "--blueprint-size",
            required=False,
            default=25,
            type=int,
            help="Number of blocks (on the longest dimension) to use in the resulting Blueprint resolution."
        )
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
            help="A list of 1, 2 and/or 3 that indicates which dimensions should be mirror."
        )
        parser.add_argument(
            "--blueprint-class",
            required=False,
            default=None,
            help="The class (CV, HV, SV, BA) of the blueprint.")
        pargs = parser.parse_args()
        lambda_body = {
            'STLBody': base64.b64encode(input_data),
            'DimensionRemap':
            [int(d) for d in pargs.dimension_remap.split(",")],
            'DimensionMirror': [p for p in pargs.dimension_mirror.split(',') if p != ""],
            'BlueprintSize': pargs.blueprint_size
                             if pargs.blueprint_size > 0 else 25,
            'BlueprintClass': pargs.blueprint_class
                              if pargs.blueprint_class in ['HV', 'SV', 'CV', 'BA'] else 'SV'
        }
        new_bp_64 = lambda_handler(lambda_body, None)

    print base64.b64decode(new_bp_64)
