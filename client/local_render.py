import os
import shutil
import subprocess
import sys
import time

BLENDER_PATH = "/Applications/Blender.app/Contents/MacOS/Blender"


def main(blender_file, start, end):
    filename = blender_file[:-6]
    directory = blender_file[:-6] + '/'
    output_path = directory + filename
    os.mkdir(directory)
    log = 'timestamp,status\n'

    # Render the file into PNG frames
    for i in range(int(start), int(end)+1, 3):
        command = [BLENDER_PATH, '-b', blender_file, '-E', 'CYCLES', '-o', output_path, '-s', str(i), '-e', str(min(i+2, int(end))), '-a']
        subprocess.run(command, check=True)
        log += str(time.time()) + f",Rendered animation {blender_file} frames {start} to {end}\n"

    # Sequence the frames into an MP4 video
    framerate = '24'
    resolution = '1920x1080'
    file_template = output_path + '%04d.png'
    output_file = filename + '.mp4'
    command = ['ffmpeg',
               '-r', framerate,
               '-s', resolution,
               '-i', file_template,
               output_file]
    subprocess.run(command, check=True)
    log += str(time.time()) + f",Sequenced {blender_file}\n"

    # Cleanup the PNG files directory
    shutil.rmtree(filename + '/')

    with open('local.csv', 'w') as f:
        f.write(log)


if __name__ == '__main__':
    file_arg = sys.argv[1]
    start_arg = sys.argv[2]
    end_arg = sys.argv[3]
    main(file_arg, start_arg, end_arg)
