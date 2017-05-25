# EmpyrionGSTools

This is a set of scripts and tools for working with Empyrion blueprints, and converting STL meshes into Empyrion blurprint files.

If you need help or have questions, you can find help on the [Steam Community thread](https://steamcommunity.com/app/383120/discussions/8/343786195673053843/).

## Getting Started

Download the latest GitHub release for this project, which contains the Python scripts as well as the bundled Python and GUI binaries for Windows. Release can be found [here](https://github.com/Riebart/EmpyrionGSTools/releases).

For Linux and Mac users, the CLI is probably your best bet, but you can run the GUI application under Mono as it is written in C# and uses .NET.

For Windows users that want to use the CLI, I recommend using the Windows Subsystem for Linux, and then installing PyPy. This will offer the best performance.

### Using your own blueprint prototype

Starting with Alpha5, Empyrion embeds the Steam account information into the Blueprint file, and this tool does not make any attempts to repair that. In order to use this tool, you will need to replace the `BlueprintBase/BlueprintBase.epb` file with a prototype blueprint created with your Steam account.

To create this blueprint file, spawn a new ship of any type using the Starter Kit, and delete all blocks except for one steel hull block, then save this single-block 'ship' as a blueprint and leave the game. Copy this .epb file you just created (located in `steamapps/common/Empyrion - Galactic Survival/Saves/Blueprints/<SteamId>/<BlueprintName>/<BlueprintName>.epb`) and overwrite `BlueprintBase/BlueprintBase.epb` with it.

Once you have done this you should be read to use either the Python script or the GUI/.exe file.

## Converting your first model

I am going to assume you are using the GUI for this example:

- Go to your favourite website, Thingverse is great as most models are available in STL format (which is the only format this supports), and download a model. Make sure you save or extract the .STL file.
- Follow the steps in the above section on creating your own prototype Blueprint base file.
- Open up the EGS-GUI.exe application, and it should present you with a collection of options.
- In the first box at the top, double-click and select the input STL file.
- In the second box, double-click and choose where to save the blueprint that it produces. You'll probably want to save it into your Empyrion saves folder, over an existing blueprint that you created just for this (since it will completely overwrite the target file, *do not choose a blueprint file you care about as the destination*)
- Select any and all options you want.
- Run!
- Once it's done, you'll need to re-load a saved game for the new blueprint to be spawnable in game.

Some common issues that arise:

- A common issue is that the blueprints come out oriented incorrectly. I recommend using a small blueprint size (15 or so is usually good), and try different values for the dimension remapping parameter (`1,3,2` is one that is frequently useful). After each conversion, you need to reload a saved game, then spawn the BP into the game to see the changes. Do this until you find the right value to get the right orientation.
- If you find that the blueprint is pointing the wrong way, but otherwise oriented correctly, use the dimension-mirror option. Again, try different values until you find the right one.
- By default, this tool uses the SV/HV steel hull block for everything, which causes issues when generating CV blueprints. To address this, you can use the builtin `replaceblocks` command at the Empyrion in-game terminal:
```
replaceblocks <entity id> HullFull HullFullLarge
```
  - For combat steel, since this tool produces exactly the exterior shell, use `HullCombatFullLarge`
  - You can get the entity ID by using the `di` command at the terminal, and then looking at your newly imported ship.

## Parameter help

```
  --stl-file STL_FILE   Filename of the input STL file.
  --blueprint-output-file BLUEPRINT_OUTPUT_FILE
                        Filename of the file to write the output blueprint to.
                        All contents will be overwritten if the file already
                        exists.
  --blueprint-size BLUEPRINT_SIZE
                        Number of blocks (on the longest dimension) to use in
                        the resulting Blueprint resolution. If a value of the
                        form '1,50' is given, then the model is chosen to have
                        a size of 50 in the first dimension. Viable dimension
                        indicators are 1, 2, or 3.
  --dimension-remap DIMENSION_REMAP
                        A permutation of 1,2,3 to remap the coordinates.
                        Example: 1,3,2
  --dimension-mirror DIMENSION_MIRROR
                        A list of 1, 2 and/or 3 that indicates which
                        dimensions the model should be reflected in.
  --blueprint-class BLUEPRINT_CLASS
                        The class (CV, HV, SV, BA) of the blueprint.
  --morphological-factors MORPHOLOGICAL_FACTORS
                        A positive integer value indicating how much
                        morphological smoothing/filling to do. If given as two
                        positive integer values separated by a comma, the
                        first value will be used for dilation, and the second
                        value will be used for erosion.
  --hollow-radius HOLLOW_RADIUS
                        A positive integer value indicating how much hollowing
                        to perform after the smoothing process. Best used in
                        conjunction with morphological smoothing to hollow out
                        filled interiors. Larger values result in thicker
                        walls.
  --disable-smoothing   Disable the addition of slanted or other non-cube
                        blocks to the resulting voxel model.
  --corner-blocks       Whether or not corner blocks should be added when the
                        choice and placement are unambiguous.
  --disable-multithreading
                        Force the use fo single-threaded code and disabeles
                        the use of multiprocessing modules even if they are
                        available.
  --version-check       When specified, overrides all other behaviours and
                        simply checks with GitHub to determine if this is the
                        latest version or not. Always prints the current
                        version on the first line, and the newest version on
                        the second line.
  --reflect REFLECT     When specified, the voxel cloud is sliced along the
                        given dimension, and the cloud is reflected to produce
                        a perfectly symmetric cloud. Smoothing is performed
                        after this.
```

## Converting .MSH to .STL with `msh_to_stl.py`

This script only has CLI support, so you need to run it from the command line on a Unix-like system.

Example usage: `cat mesh.msh | python msh_to_stl.py > mesh.stl`

## Model Sources

- Megathron: http://www.thingiverse.com/thing:89260
  - Recommended finest resolution: 1
  - Recommended dimension remap: 1,3,2
- ThunderForge: http://francophone.dansteph.com/?page=addon&id=15
  - Recommended finest resolution: 1
  - Recommended dimension remap: 1,2,3
- Andromeda Ascendant: https://www.cgtrader.com/free-3d-models/vehicle/sci-fi/the-andromeda-ascendant
  - NOTE: This is provided in binary STL format, which is not supported by the scripts.
  - Recommended finest resolution: 10
  - Recommended dimension remap: 1,3,2
- Nostromo: http://www.thingiverse.com/thing:418367
  - Recommended finest resolution: 150
  - Recommended dimension remap: 1,3,2
- Bentusi Harbour Ship: https://www.tinkercad.com/things/bqqIfyfBCOj-homeworld-the-great-harbor-ship-bentus
  - Recommended dimension remap: 1,3,2
- GTG Zephyrus: https://p3d.in/mFZFz
  - Recommended dimentino mirror: 3
- FS2 models: http://sectorgame.com/fsfiles/?dir=uploads/Models/

## Conversion resources

Because models come in a variety of sources, and this tool only imports STL models,
a site like http://www.ofoct.com/3d-model-file-for-3d-printer-converter/3d-model-file-converter.html 
or http://www.meshconvert.com/ can be useful for converting from one format to STL.

## References

- `.msh` file format reference: http://3dcenter.ru/forum/index.php?act=attach&type=post&id=171261

## Deploying to AWS

This function is suitable for deployment to AWS Lambda using the following script as a scaffold:

```
chmod 755 *py BlueprintBase BlueprintBase/*
rm deploy.zip && zip deploy.zip lambda_index.py empyrion.py BlueprintBase/*
aws lambda update-function-code --function-name EmpyrionBlueprintConverter --zip-file fileb://deploy.zip
time wget -O- --header "Content-Type: application/json" \
--post-data "{\"STLBody\": \"`cat Models/Machriel.stl | base64 -w0`\",\"BlueprintSize\":25}" \
https://z6q4xdau9i.execute-api.us-east-1.amazonaws.com/Production/BlueprintFromMesh | \
tr -d '"' | base64 -d - > \
/cygdrive/c/Program\ Files\ \(x86\)/Steam/steamapps/common/Empyrion\ -\ Galactic\ Survival/Saves/Blueprints/76561197978304234/SingleBlock_0/SingleBlock_0.epb
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