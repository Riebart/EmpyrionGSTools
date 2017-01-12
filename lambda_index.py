"""
Implements a generic function that ingests either a text STL file on stdin,
or a Lambda event body, and performs the necessary functions.
"""

import base64
import StringIO

import stl_to_pts
import replace_bp

def lambda_handler(Event, Context):
    """
    Given a Lambda event body, ready the STL file and generate a new blueprint
    based on the parameters.
    """
    stl_body = base64.b64decode(Event['STLBody'])
    voxel_dimension = int(Event['BlueprintSize']) if 'BlueprintSize' in Event else 100
    dim_remap = Event['DimensionRemap'] if 'DimensionRemap' in Event else [1, 2, 3]
    bp_class = Event['BlueprintClass'] if 'BlueprintClass' in Event else 'SV'

    with open('BlueprintBase/BlueprintBase.epb', 'r') as fp:
        bp_body = fp.read()

    ssi = StringIO.StringIO(stl_body)
    solids = stl_to_pts.STLFile.read_solids(ssi)
    triangles = [e for s in solids for e in s[1]]
    bounds = stl_to_pts.triangle_list_bounds(triangles)
    longest_dim = max([i[1]-i[0] for i in bounds])
    resolution = longest_dim / float(voxel_dimension)
    pts = stl_to_pts.parallel_split_tris(triangles, resolution)

    pts = [
        tuple([p[dim_remap[i]-1] for i in range(3)]) for p in pts
    ]

    smoothed_pts = stl_to_pts.smooth_pts(pts)
    mapped_blocks = stl_to_pts.map_to_empyrion_codes(smoothed_pts)

    new_bp = replace_bp.build_new_bp(bp_body, mapped_blocks, bp_class)

    return base64.b64encode(new_bp)

if __name__ == "__main__":
    import sys
    import json
    import argparse

    input_data = sys.stdin.read()
    try:
        new_bp_64 = lambda_handler(json.loads(input_data), None)
    except Exception:
        parser = argparse.ArgumentParser(
            description="Given an input CSV of coordinates, modify a Blueprint to match the blocks."
        )
        parser.add_argument(
            "--dimension-remap",
            required=False,
            default="1,2,3",
            help="A permutation of 1,2,3 to remap the coordinates. Example: 1,3,2")
        parser.add_argument(
            "--blueprint-class",
            required=False,
            default=None,
            help="The class (CV, HV, SV, BA) of the blueprint.")
        pargs = parser.parse_args()
        lambda_body = {
            'STLBody': base64.b64encode(input_data),
            'DimensionRemap': [int(d) for d in pargs.dimension_remap.split(",")],
            'BlueprintClass': pargs.blueprint_class if
                              pargs.blueprint_class in ['HV', 'SV', 'CV', 'BA'] else 'SV'
            }
        new_bp_64 = lambda_handler(lambda_body, None)

    print new_bp_64
