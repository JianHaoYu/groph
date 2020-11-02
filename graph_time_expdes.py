# import fnmatch
import matplotlib
# Do not use any X11 backend
matplotlib.use('Agg')
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype'] = 42
import matplotlib.pyplot as plt
import numpy as np
import os


def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    return type('Enum', (), enums)


XPS = enum('NONE', 'TCP', 'QUIC')
buf_tcp = {}
blacklist_tcp = []
buf_quic = {}
blacklist_quic = []


def extract_https_results_from_file(filename_ext, run, topo, config, blacklist=False):
    res_file = open(filename_ext)
    lines = res_file.readlines()
    full_lines = "".join(lines)
    res_file.close()
    if blacklist:
        if (run, topo, config) in blacklist_tcp:
            return None
    else:
        if full_lines in buf_tcp:
            buf_tcp[full_lines].append((run, topo, config))
        else:
            buf_tcp[full_lines] = [(run, topo, config)]
    for line in lines:
        if line.startswith("real"):
            try:
                return float(line.split("m")[1].split("s")[0]) + 60.0 * float(line.split("m")[0].split()[1])
            except Exception:
                return None


def extract_quic_results_from_file(filename_ext, run, topo, config, blacklist=False):
    res_file = open(filename_ext)
    lines = res_file.readlines()
    full_lines = "".join(lines)
    res_file.close()
    if blacklist:
        if (run, topo, config) in blacklist_quic:
            return None
    else:
        if full_lines in buf_quic:
            buf_quic[full_lines].append((run, topo, config))
        else:
            buf_quic[full_lines] = [(run, topo, config)]
    try:
        time_raw = lines[-1].split()[-1]
        if "ms" in time_raw:
            return float(time_raw.split("ms")[0]) / 1000.0
        elif "m" in time_raw:
            splitted = time_raw.split("m")
            return float(splitted[0]) * 60.0 + float(splitted[1].split("s")[0])
        else:
            return float(time_raw.split("s")[0])
    except Exception:
        return None


def detect_xp(filename):
    if filename == "https_client.log":
        return XPS.TCP
    if filename == "quic_client.log":
        return XPS.QUIC

    return XPS.NONE


def get_results(results_dir_ext="results", blacklist=False):
    results = {}
    for directory in os.listdir(results_dir_ext):
        print(directory)
        # if fnmatch.fnmatch(directory, 'https_quic_*_mptcp'):
        directory_ext = os.path.join(results_dir_ext, directory)
        for dirpath, dirnames, filenames in os.walk(directory_ext):
            for filename in filenames:
                # Two cases: MPTCP or QUIC
                xp = detect_xp(filename)
                if xp == XPS.NONE:
                    continue

                topo = dirpath.split('/')[-3]
                if topo not in results:
                    results[topo] = {}

                protocol = dirpath.split('/')[-2]
                if protocol not in results[topo]:
                    results[topo][protocol] = {}

                multipath = dirpath.split('/')[-1]
                if multipath not in results[topo][protocol]:
                    results[topo][protocol][multipath] = []

                filename_ext = os.path.abspath(os.path.join(dirpath, filename))
                print(filename_ext)
                if xp == XPS.TCP:
                    to_append = extract_https_results_from_file(filename_ext, dirpath.split('/')[-4], topo, multipath, blacklist=blacklist)
                elif xp == XPS.QUIC:
                    to_append = extract_quic_results_from_file(filename_ext, dirpath.split('/')[-4], topo, multipath, blacklist=blacklist)

                if to_append:
                    results[topo][protocol][multipath].append(to_append)

    return results

all_results_blacklist = get_results(".")
cnt = 0
for lines in buf_quic.keys():
    if len(buf_quic[lines]) > 1:
        print(buf_quic[lines])
        blacklist_quic += buf_quic[lines]
        cnt += len(buf_quic[lines])
print(cnt)
cnt = 0
for lines in buf_tcp.keys():
    if len(buf_tcp[lines]) > 1:
        print(buf_tcp[lines])
        blacklist_tcp += buf_tcp[lines]
        cnt += len(buf_tcp[lines])
print(cnt)
all_results = get_results(".", blacklist=True)


configs = ["0", "1"]
config_label = {"0": "Time TCP / QUIC" , "1": "Time MPTCP / MPQUIC"}
ls = {"0": "-", "1": "--"}
matplotlib.rcParams.update({'font.size': 18})
plt.figure(figsize=(8, 6))
plt.clf()
for config in configs:
    cdf_line = []
    for topo in all_results.keys():
        tcp_res = all_results[topo].get("https", {}).get(config, [])
        quic_res = all_results[topo].get("quic", {}).get(config, [])
        if tcp_res and quic_res:
            ratio = np.median(tcp_res) / np.median(quic_res)
            cdf_line.append(ratio)
            if config == "1" and (ratio < 0.5 or ratio > 2):
                print(topo, ratio)

    sorted_array = np.array(sorted(cdf_line))
    above_1 = [x for x in sorted_array if x >= 1.01]
    print(config, len(above_1) * 100.0 / len(sorted_array))
    # yvals = np.arange(len(sorted_array)) / float(len(sorted_array))
    yvals = np.arange(1, len(sorted_array) + 1) / float(len(sorted_array))
    if len(sorted_array) > 0:
        yvals = np.insert(yvals, 0, 0)
        sorted_array = np.insert(sorted_array, 0, sorted_array[0])
        plt.plot(sorted_array, yvals, linewidth=4, label=config_label[config], ls=ls[config])

plt.xlabel("Time Ratio")
plt.xscale("log")
plt.xlim(xmin=0.1, xmax=10)
plt.ylim(ymin=0, ymax=1)
plt.ylabel("CDF")
plt.grid()
plt.legend(loc="upper left", fontsize=15)
# plt.title("GET 20 MB, 400 simulations low-BDP-no-loss")
plt.title("GET 20MB, 506 simulations, high-BDP-losses")
plt.tight_layout()
plt.savefig("time_expdes.png", transparent=True)
plt.savefig("time_expdes.pdf")
