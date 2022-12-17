from pprint import pprint

import pandas as pd
import matplotlib.pyplot as plt
import sys


def plot_performance(farm_start, local_start, files):
    # Plot the render farm throughput
    timestamps = []
    for file in files:
        with open(file + '.csv', 'r') as f:
            f.readline()
            for line in f:
                timestamp, status = line.replace('\n', '').split(',')
                if 'Rendered' in status or 'Sequenced' in status:
                    time = float(timestamp) - float(farm_start)
                    quantised_time = time // 60
                    timestamps.append(quantised_time)
    time = sorted(list(set(timestamps)))
    throughput = [timestamps.count(t) for t in time]
    time.insert(0, 0)
    throughput.insert(0, 0)
    time.append(time[-1] + 1)
    throughput.append(0)
    plt.plot(time, throughput, marker='o', label='Render farm')

    # Plot the local renderer throughput
    timestamps = []
    with open('local.csv', 'r') as f:
        f.readline()
        for line in f:
            timestamp, status = line.replace('\n', '').split(',')
            if 'Rendered' in status or 'Sequenced' in status:
                time = float(timestamp) - float(local_start)
                quantised_time = time // 60
                timestamps.append(quantised_time)
    time = sorted(list(set(timestamps)))
    throughput = [timestamps.count(t) for t in time]
    time.insert(0, 0)
    throughput.insert(0, 0)
    time.append(time[-1] + 1)
    throughput.append(0)
    plt.plot(time, throughput, marker='o', label='Local renderer')

    # Display the graph
    plt.xlabel('Time (minutes)')
    plt.ylabel('Throughput (jobs processed/minute)')
    plt.title('Throughput for Cloud Render Farm')
    plt.legend()
    plt.show()


def plot_scaling():
    # Extract data from the HPA logs file
    targets = []
    replicas = []
    ages = []
    with open('hpa_logs.txt', 'r') as f:
        line = f.readline().replace('\n', '')
        items = line.split()
        targets_index = items.index('TARGETS')
        replicas_index = items.index('REPLICAS')
        age_index = items.index('AGE')
        for line in f:
            line = line.replace('\n', '')
            items = line.split()
            if items[0] == 'NAME':
                continue
            target = int(items[targets_index].split('%')[0])
            targets.append(target)
            replicas.append(int(items[replicas_index]))
            age = items[age_index]
            elapsed = .0
            if 'm' in age:
                m_i = age.index('m')
                elapsed += float(age[:m_i])
                secs = age[m_i+1:].replace('s', '')
                if secs:
                    elapsed += float(secs)/60
            elif 's' in age:
                elapsed += float(age[:-1])/60
            ages.append(elapsed)

    # Plot the lines
    fig, ax1 = plt.subplots()
    ax1.plot(ages, targets, label='CPU usage', color='red')
    ax2 = plt.twinx(ax1)
    ax2.step(ages, replicas, label='Pods', color='blue')
    ax1.axhline(y=50, color='g', linestyle='--')

    # Display the graph
    ax1.set_xlabel('Time (minutes)')
    ax1.set_ylabel('% CPU Usage')
    ax2.set_ylabel('Number of pods')
    ax2.set_ylim(0, 15)
    # ax1.yaxis.label.set_color(p1.get_color())
    # ax2.yaxis.label.set_color(p2.get_color())
    # ax1.legend(handles=[p1, p2])
    plt.show()


if __name__ == '__main__':
    if sys.argv[1] == 'throughput':
        farm_start_time = sys.argv[2]
        local_start_time = sys.argv[3]
        file_nums = sys.argv[4:]
        plot_performance(farm_start_time, local_start_time, file_nums)
    elif sys.argv[1] == 'scaling':
        plot_scaling()