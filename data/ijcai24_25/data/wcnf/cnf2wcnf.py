#  KBDiag
#
#  Copyright (c) –2026
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

from pysat.formula import CNF

KBs = ['DELL', 'ubuntu', 'windows8']

for KB in KBs:
    fn = '%s.dimacs' % KB
    print(f'Converting {fn} to wcnf')

    formula = CNF(from_file=fn)

    print(f'\t#variables: {formula.nv}')
    print(f'\t#clauses: {len(formula.clauses)}')

    wcnf = formula.weighted()

    print('\tAfter weighted')
    print(f'\t\tHard clauses: {wcnf.hard}')
    print(f'\t\t#Hard clauses: {len(wcnf.hard)}')
    print(f'\t\t#Soft clauses: {len(wcnf.soft)}')
    print(f'\t\t#Weights: {len(wcnf.wght)}')

    # remove the first element from the soft clauses
    # add the first element to the hard clauses
    wcnf.hard.append(wcnf.soft.pop(0))
    wcnf.wght.pop(0)

    print('\tAfter modification')
    print(f'\t\tHard clauses: {wcnf.hard}')
    print(f'\t\t#Hard clauses: {len(wcnf.hard)}')
    print(f'\t\t#Soft clauses: {len(wcnf.soft)}')
    print(f'\t\t#Weights: {len(wcnf.wght)}')

    wcnf.to_file('%s.wcnf' % KB)

print('Done')