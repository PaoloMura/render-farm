import subprocess
import time


def main():
    f = open('hpa_logs.txt', 'w')
    f.close()
    while True:
        command = ['kubectl', 'get', 'hpa']
        result = subprocess.run(command, check=False, capture_output=True)
        if result.returncode != 0:
            with open('hpa_logs.txt', 'a') as f:
                f.write(result.stderr.decode('utf-8'))
            raise Exception('Failed')
        with open('hpa_logs.txt', 'a') as f:
            f.write(result.stdout.decode('utf-8'))
        time.sleep(30)


if __name__ == '__main__':
    main()
