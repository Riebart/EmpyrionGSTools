import re
import sys
import json
import zipfile
import StringIO
import subprocess


def git_md():
    """
    Subprocess out to git to get information about the repository including
    the current HEAD SHA and the origin GitHub user and repo names.
    """
    ret = dict()
    git_sha = subprocess.check_output(('git', 'rev-parse', 'HEAD'))
    ret['GitSHA'] = git_sha.strip()

    git_url = subprocess.check_output(
        ('git', 'remote', 'get-url', '--all', 'origin')).lower()
    # If the URL is GitHub, then parse out the
    if git_url.startswith('git@github.com'):
        ret['GitHub'] = True
        matches = re.match("^git@github.com:(.*)/(.*).git$", git_url)
        if matches is not None:
            ret['GitHubUser'] = matches.group(1)
            ret['GitHubRepo'] = matches.group(2)
        else:
            ret['GitHubUser'] = None
            ret['GitHubRepo'] = None
    else:
        ret['GitHub'] = False

    return json.dumps(ret)


def __main():
    # Run the pyinstaller process to rebuild the Python binary
    subprocess.check_call(
        ('pyinstaller', '--clean', '--onefile', 'lambda_index.py'))

    sso = StringIO.StringIO()
    zfile = zipfile.ZipFile(sso, 'w', zipfile.ZIP_DEFLATED)

    zfile.write("EGS-GUI/EGS-GUI/bin/Release/EGS-GUI.exe", "EGS-GUI.exe")
    zfile.write("dist/lambda_index.exe", "lambda_index.exe")
    zfile.write("lambda_index.py")
    zfile.write("empyrion.py")
    zfile.write("BlueprintBase/BlueprintBase.jpg")
    zfile.write("BlueprintBase/BlueprintBase.epb")
    zfile.writestr("git.json", git_md())
    zfile.close()
    sys.stdout.write(sso.getvalue())


if __name__ == "__main__":
    __main()
