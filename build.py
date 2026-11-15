"""Build the standalone x64 Windows executable with a Python/Tk runtime directory."""

import os
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT = Path(__file__).resolve().parent
STAGING = PROJECT / '.build'
RELEASE = PROJECT / 'release'


def copy_dir(source, destination):
    shutil.copytree(source, destination, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))


def build(source, runtime):
    RELEASE.mkdir(exist_ok=True)
    for path in source.iterdir():
        if path.is_file() and path.suffix.lower() in {'.exe', '.dll', '.txt'}:
            shutil.copy2(path, runtime)
    for name in ('DLLs', 'tcl'):
        copy_dir(source / name, runtime / name)
    source_lib = source / 'Lib'
    target_lib = runtime / 'Lib'
    target_lib.mkdir(exist_ok=True)
    excluded = {'site-packages', 'test', '__pycache__', 'ensurepip', 'idlelib', 'venv', 'turtledemo'}
    for path in source_lib.iterdir():
        if path.name in excluded:
            continue
        if path.is_dir():
            copy_dir(path, target_lib / path.name)
        elif path.suffix == '.py':
            shutil.copy2(path, target_lib)
    site = source_lib / 'site-packages'
    pillow = [site / 'PIL', *site.glob('pillow*.dist-info'), *site.glob('pillow*.libs')]
    for package in pillow:
        copy_dir(package, target_lib / 'site-packages' / package.name)

    for script in ('train_local.py', 'analysis.py', 'quality.py', 'dialogue.py'):
        subprocess.run([sys.executable, '-B', script], cwd=PROJECT, check=True)

    payload = STAGING / 'aboard-payload.zip'
    modules = ('desktop.py', 'mission.py', 'medical_followup.py', 'demo_journal.py', 'nasa_reference.py', 'polish.py', 'anatomy-atlas.png', 'credentials.py', 'aboard.py', 'motion.py', 'analysis.py', 'local_model.json', 'assistants.py', 'quality.py',
               'demo_scan.png', 'crew.py', 'avatar3d.py', 'dialogue.py', 'voice.py', 'cloud_agent.py', 'cloud_capture.py', 'storage.py',
               'wellbeing_ui.py', 'equipment-atlas.png', 'baseline.py', 'ai_label.py')
    with ZipFile(payload, 'w', ZIP_DEFLATED) as archive:
        for name in ('measurement_gallery.py', 'measurement-frames.png', 'activity_gallery.py', 'activity-frames.png', 'activity-man.png',
                     'activity-woman-extra.png', 'activity-man-extra.png'):
            archive.write(PROJECT / name, name)
        for name in modules:
            archive.write(PROJECT / name, name)
        for path in sorted(runtime.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                archive.write(path, Path('runtime') / path.relative_to(runtime))

    compiler = Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
    exe = RELEASE / os.environ.get('ABOARD_EXE_NAME', 'Aboard.exe')
    subprocess.run(
        [str(compiler), '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
         f'/out:{exe}', f'/resource:{payload},Aboard.Payload',
         '/r:System.IO.Compression.dll', '/r:System.IO.Compression.FileSystem.dll',
         '/r:System.Windows.Forms.dll', str(PROJECT / 'Launcher.cs')],
        check=True,
    )
    print(f'{exe} ({exe.stat().st_size / 1048576:.1f} MB)')


if __name__ == '__main__':
    source = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(sys.executable).resolve().parent
    STAGING.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='runtime-', dir=STAGING) as staging_runtime:
        build(source, Path(staging_runtime))
