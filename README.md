# Using the tools

To use these scripts, you'll need a 3D, or other source of initial data. Once you have that, you'll want to use the `replace_bp.py` script to replace the blocks zip file portion of a blueprint. Included is a simple blueprint file that is a suitable surrogate for the new blocks.

- Generate a collection of points in 3D space with integer coordinates (see `Sphere.csv`)
  - This can be generated from a 3D model, or other source. The included Mathematica notebook generates them from any 3D model supported by Mathematical, and the `msh_to_stl.py` will convert a specific file format into an STL file.
  - The input coordinates should be integer (as they are cast to integers in the Python script), so make sure that the truncation is happening intelligently, before being fed into `replace_bp.py`.
  - The input coordinates can be at any scale, and positive or negative in any way (compared to STL vertices which must all lie in the non-negative octant).
  - The input coordinates are transformed so that the object lies close to the origin, and so that transformation doesn't need to happen before sending the vertices to the Python script.
  - Note that blocks, regardless of blueprint type (HC, SV, CV, BA) are unit cubes (1x1x1), so when constructing the coordinates for blocks, it is important to note that gaps larger than one unit in any dimension between locations will have no block present (there won't be any filling).
- Optional: Save the collection of points as a CSV
- Pass the collection of points to the stdin of the `replace_bp.py` Python script, giving the script a single argument that is the filename of the `.epb` file in the example BP folder.
  - It is recommended that a copy of the example BP folder be made before clobbering the contents, as good practice.
- Once the script completes, copy the folder containing the modified BP into the `Saves/Blueprints/<SteamID>` folder, and spawn it in game.
  - The game only loads the Blueprint collection when you join a game, so if you are currently in a game you will have to exit the game then rejoin/load a game.
  - When saving blueprints inside of a game, the changes are immediately reflected on disk, so no leave/load steps need to be performed for simply inspecting/copying the Blueprints created in-game.

## Environment
These scripts rely on some command line Linux knowledge and capability. They will run fine under the Windows X bash/Subsystem for Linux, and any Unix environment.

Example usage: `cat Sphere.csv | python replace_bp.py SingleBlock/SingleBlock.epb`

## `msh_to_stl.py`
Example usage: `cat mesh.msh | python msh_to_stl.py > mesh.stl`

# Model Sources
- Megathron: http://www.thingiverse.com/thing:89260
  - Recommended finest resolution: 1
  - Recommended dimension remap: 1,3,2
- ThunderForge: http://francophone.dansteph.com/?page=addon&id=15
  - Recommended finest resolution: 1
  - Recommended dimension remap: 1,2,3
- Andromeda Ascendant: https://www.cgtrader.com/free-3d-models/vehicle/sci-fi/the-andromeda-ascendant
  - NOTE: This is provided in binary STL format, which is not supported by the `stl_to_pts.py` script.
  - Recommended finest resolution: 10
  - Recommended dimension remap: 1,3,2
- Nostromo: http://www.thingiverse.com/thing:418367
  - Recommended finest resolution: 150
  - Recommended dimension remap: 1,3,2
- Bentusi Harbour Ship: https://www.tinkercad.com/things/bqqIfyfBCOj-homeworld-the-great-harbor-ship-bentus
  - Recommended dimension remap: 1,3,2

# References
- `.msh` file format reference: http://3dcenter.ru/forum/index.php?act=attach&type=post&id=171261
