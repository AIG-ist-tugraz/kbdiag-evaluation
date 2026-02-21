#  KBDiag
#
#  Copyright (c) 2025
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)
from pysat.formula import WCNF

KBs = ['DELL', 'ubuntu', 'windows8']
testcases_files = {
    'DELL': ["DELL_c5_0.testcases", "DELL_c10_0.testcases", "DELL_c25_0.testcases", "DELL_c50_0.testcases",
             "DELL_c100_0.testcases", "DELL_c250_0.testcases", "DELL_c500_0.testcases"],
    'ubuntu': ["ubuntu_c5_0.testcases", "ubuntu_c10_0.testcases", "ubuntu_c25_0.testcases", "ubuntu_c50_0.testcases",
               "ubuntu_c100_0.testcases", "ubuntu_c250_0.testcases", "ubuntu_c500_0.testcases"],
    'windows8': ["windows8_c5_0.testcases", "windows8_c10_0.testcases", "windows8_c25_0.testcases", "windows8_c50_0.testcases",
                 "windows8_c100_0.testcases", "windows8_c250_0.testcases", "windows8_c500_0.testcases"]
}


def get_index(from_file: str) -> dict:
    wcnf = WCNF(from_file=from_file)

    variables = {}
    for comment in wcnf.comments:
        parts = comment.split()
        key = parts[2]
        value = parts[1]
        variables[key] = value
    print(f'\tVariables: {variables}')
    return variables


for KB in KBs:
    fn = '%s.wcnf' % KB
    print(f'Converting testcases of {KB} to wcnf')

    variables = get_index(fn)

    tc_files = testcases_files[KB]
    for testcases_file in tc_files:
        print(f'\tTestcases file: {testcases_file}')
        with open(f'scenarios/{testcases_file}', 'r') as f:
            testcases = f.readlines()[1:] # skip the first line

            wcnf = WCNF(from_file=fn)
            counter = 0
            for testcase in testcases:
                # print(f'\t\tTestcase: {testcase.strip()}')
                # convert to cnf
                parts = testcase.split('&')
                clause = []
                for part in parts:
                    part = part.strip()
                    if part.startswith('~'):
                        clause.append(-int(variables[part[1:]]))
                    else:
                        clause.append(int(variables[part]))

                counter += 1
                # print(f'\t\tClause: {clause}')
                wcnf.comments.append('o {} 0'.format(' '.join(map(str, clause))))

            print(f'\t\t#test cases: {counter}')
            # get file name without extension
            out_file = testcases_file.split('.')[0]
            wcnf.to_file(f'scenarios_wcnf/{out_file}.wcnf')