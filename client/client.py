import requests
import sys


def validate_args(file, start, end):
    if len(file) < 7 or file[-6:] != '.blend':
        raise ValueError('File must be a Blender .blend file')
    elif not (start.isnumeric() and end.isnumeric()):
        raise ValueError('Start and end frames must be integers')
    elif int(start) > int(end):
        raise ValueError('Start frame must be less than end frame.')
    return


def submit_request(url, file, start, end):
    data = {'file': file, 'start': start, 'end': end}
    try:
        r = requests.post(url, json=data)
    except Exception as e:
        raise Exception(f'Request failed: {e}')
    return r.text


def main():
    if len(sys.argv) < 5:
        print('Require command line arguments:')
        print('\tserver_url')
        print('\tfilename')
        print('\tstart_frame')
        print('\tend_frame')
        exit(1)

    server_url = sys.argv[1]
    filename = sys.argv[2]
    start_frame = sys.argv[3]
    end_frame = sys.argv[4]

    validate_args(filename, start_frame, end_frame)
    result = submit_request(server_url, filename, start_frame, end_frame)
    print(result)


if __name__ == '__main__':
    main()
