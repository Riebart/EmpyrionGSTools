import sys
import zipfile
import StringIO
import subprocess


def __main():
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
    zfile.close()
    sys.stdout.write(sso.getvalue())


if __name__ == "__main__":
    __main()