#  KBDiag
#
#  Copyright (c) 2025
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

#  KBDiag
#
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)
import argparse
import os
import subprocess
import time

KBs = ['DELL', 'ubuntu', 'windows8']
testcases_files = {
    'DELL': ["DELL_c5_0.wcnf", "DELL_c10_0.wcnf", "DELL_c25_0.wcnf", "DELL_c50_0.wcnf",
             "DELL_c100_0.wcnf", "DELL_c250_0.wcnf", "DELL_c500_0.wcnf"],
    'ubuntu': ["ubuntu_c5_0.wcnf", "ubuntu_c10_0.wcnf", "ubuntu_c25_0.wcnf", "ubuntu_c50_0.wcnf",
               "ubuntu_c100_0.wcnf", "ubuntu_c250_0.wcnf", "ubuntu_c500_0.wcnf"],
    'windows8': ["windows8_c5_0.wcnf", "windows8_c10_0.wcnf", "windows8_c25_0.wcnf", "windows8_c50_0.wcnf",
                 "windows8_c100_0.wcnf", "windows8_c250_0.wcnf", "windows8_c500_0.wcnf"]
}
numIter = 3
result_path = './results'

parser = argparse.ArgumentParser()
parser.add_argument('-task', '--task', action='store', type=str, help='1 or all')
parser.add_argument('-size', '--size', action='store', type=str, help='all or 25')
args = parser.parse_args()

dresults = os.path.join(result_path, args.task)
print(dresults)

if not os.path.isdir(dresults):
    os.makedirs(dresults)

for KB in KBs:
    averages = {}

    out_file = f"results_hsd_{KB}_{args.task}.txt"
    lfname = os.path.join(dresults, out_file)

    with open(lfname, 'a') as f:
        if args.size == '25':
            testcases_files_kb = [testcases_files[KB][2]]
        else:
            testcases_files_kb = testcases_files[KB]

        # print(testcases_files_kb)

        for testcases_file in testcases_files_kb:
            print(f'Running {KB} {testcases_file}')

            # calculate the average time
            total_time = 0
            for i in range(numIter):
                command = ["hsd/hsd", "-e", args.task, "-c", "-v", f"scenarios_wcnf/{testcases_file}"]

                start = time.time()
                result = subprocess.run(command, capture_output=True, text=True)
                end = time.time()

                iteration_time = (end - start) * 1000
                total_time += iteration_time

                f.write(f"{KB} {testcases_file}\n")
                f.write(f"\tOutput: {result.stdout}\n")
                f.write(f"\tTime: {iteration_time} ms\n")

            average_time = total_time / numIter
            f.write(f"\tAverage Time: {average_time} ms\n")
            averages[testcases_file] = average_time

        # write the averages to a file
        f.write(f"\nAverages\n")
        for key, value in averages.items():
            f.write(f"\t{key}: {value} ms\n")
