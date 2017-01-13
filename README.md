# Example
 The simplest invocation uses default values.
 
 ```
 cat Machriel.stl | python lambda_index.py > blueprint.epb
 ```

 To see all invocation options, use `--help`:

 ```
$ python lambda_index.py --help
usage: lambda_index.py [-h] [--blueprint-size BLUEPRINT_SIZE]
                       [--dimension-remap DIMENSION_REMAP]
                       [--blueprint-class BLUEPRINT_CLASS]

Takes a text format STL file on stdin, and prints an Empytion blueprint file to stdout.

optional arguments:
  -h, --help            show this help message and exit
  --blueprint-size BLUEPRINT_SIZE
                        Number of blocks (on the longest dimension) to use in
                        the resulting Blueprint resolution.
  --dimension-remap DIMENSION_REMAP
                        A permutation of 1,2,3 to remap the coordinates.
                        Example: 1,3,2
  --blueprint-class BLUEPRINT_CLASS
                        The class (CV, HV, SV, BA) of the blueprint.
 ```

# Using the tools

To use these scripts, you'll need a 3D, or other source of initial data. Once you have that, you'll want to use the `replace_bp.py` script to replace the blocks zip file portion of a blueprint. Included is a simple blueprint file that is a suitable surrogate for the new blocks.

- Generate a collection of points in 3D space with integer coordinates (see `Sphere.csv`)
  - This can be generated from a 3D model, or other source. The included Mathematica notebook generates them from any 3D model supported by Mathematical, and the `msh_to_stl.py` will convert a specific file format into an STL file.
  - The input coordinates should be integer (as they are cast to integers in the Python script), so make sure that the truncation is happening intelligently, before being fed into `replace_bp.py`.
  - The input coordinates can be at any scale, and positive or negative in any way (compared to STL vertices which must all lie in the non-negative octant).
  - The input coordinates are transformed so that the object lies close to the origin, and so that transformation doesn't need to happen before sending the vertices to the Python script.
  - Note that blocks, regardless of blueprint type (HV, SV, CV, BA) are unit cubes (1x1x1), so when constructing the coordinates for blocks, it is important to note that gaps larger than one unit in any dimension between locations will have no block present (there won't be any filling).
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

# Deploying to AWS
This function is suitable for deployment to AWS Lambda using the following script as a scaffold:

```
chmod 755 *py BlueprintBase BlueprintBase/*
rm deploy.zip && zip deploy.zip lambda_index.py empyrion.py BlueprintBase/*
aws lambda update-function-code --function-name EmpyrionBlueprintConverter --zip-file fileb://deploy.zip
time wget --header "Content-Type: application/json" \
--post-data "{\"STLBody\": \"`cat Machriel.stl | base64 -w0`\",\"BlueprintSize\":100}" \
https://z6q4xdau9i.execute-api.us-east-1.amazonaws.com/Production/BlueprintFromMesh
```

### API Gateway API spec
The following is the API-Gateway extended Swagger definition of the API used to front this function.
```json
{
  "swagger": "2.0",
  "info": {
    "version": "2017-01-13T00:31:41Z",
    "title": "Empyrion"
  },
  "host": "z6q4xdau9i.execute-api.us-east-1.amazonaws.com",
  "basePath": "/Production",
  "schemes": [
    "https"
  ],
  "paths": {
    "/BlueprintFromMesh": {
      "post": {
        "produces": [
          "application/json"
        ],
        "responses": {
          "200": {
            "description": "200 response",
            "schema": {
              "$ref": "#/definitions/Empty"
            }
          }
        },
        "x-amazon-apigateway-integration": {
          "responses": {
            "default": {
              "statusCode": "200"
            }
          },
          "uri": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:0000000000:function:EmpyrionBlueprintConverter/invocations",
          "passthroughBehavior": "when_no_match",
          "httpMethod": "POST",
          "contentHandling": "CONVERT_TO_TEXT",
          "type": "aws"
        }
      },
      "options": {
        "consumes": [
          "application/json"
        ],
        "produces": [
          "application/json"
        ],
        "responses": {
          "200": {
            "description": "200 response",
            "schema": {
              "$ref": "#/definitions/Empty"
            },
            "headers": {
              "Access-Control-Allow-Origin": {
                "type": "string"
              },
              "Access-Control-Allow-Methods": {
                "type": "string"
              },
              "Access-Control-Allow-Headers": {
                "type": "string"
              }
            }
          }
        },
        "x-amazon-apigateway-integration": {
          "responses": {
            "default": {
              "statusCode": "200",
              "responseParameters": {
                "method.response.header.Access-Control-Allow-Methods": "'DELETE,GET,HEAD,OPTIONS,PATCH,POST,PUT'",
                "method.response.header.Access-Control-Allow-Headers": "'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token'",
                "method.response.header.Access-Control-Allow-Origin": "'*'"
              }
            }
          },
          "requestTemplates": {
            "application/json": "{\"statusCode\": 200}"
          },
          "passthroughBehavior": "when_no_match",
          "type": "mock"
        }
      }
    }
  },
  "definitions": {
    "Empty": {
      "type": "object",
      "title": "Empty Schema"
    }
  }
}
```