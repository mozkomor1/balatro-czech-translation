import os
import shutil

os.system("pip install -r requirements.txt --break")
os.system("pyinstaller --onefile --noconsole patch.py")

# ...existing build code...

# Clean up build folder and .spec file
if os.path.exists('build'):
    shutil.rmtree('build')
if os.path.exists('patch.spec'):
    os.remove('patch.spec')
shutil.move("dist/patch.exe", "patch.exe")
shutil.rmtree("dist")