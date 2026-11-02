"""Execute bounded literal equations or read actual UTF-8 deliverables.

Source truth, unit semantics, claim coverage and factual prose remain unverified.
"""
import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from saved_output_formulas import expression, check as labelled_formulas

LIMIT = 'Only submitted equations or observed file bytes are checked. Sources, units, completeness and prose require source review.'

def calculate(equations, places=None):
    rows = []
    for equation in equations:
        row = {'equation':equation}
        try:
            if equation.count('=')!=1:
                raise ValueError('Supply one literal equality per check')
            lhs,rhs = equation.split('=')
            rhs = rhs.strip()
            percent = rhs.endswith('%')
            observed_display = Fraction(rhs[:-1].strip() if percent else rhs)
            computed = expression(lhs)
            displayed = computed*100 if percent else computed
            rounded = round(displayed,places) if places is not None else displayed
            row.update(status='pass' if rounded==observed_display else 'fail',computed_exact=str(computed),
                       computed_display_exact=str(rounded),reported_display_exact=str(observed_display),
                       percent=percent,decimal_places=places)
        except (ValueError,SyntaxError,ZeroDivisionError,OverflowError) as exc:
            row.update(status='unavailable',reason=str(exc))
        rows.append(row)
    status = 'fail' if any(r['status']=='fail' for r in rows) else 'unavailable' if not rows or any(r['status']=='unavailable' for r in rows) else 'pass'
    return {'operation':'calculate','status':status,'checks':rows,'limits':LIMIT}

def inspect_files(paths):
    rows = []
    for name in paths:
        row = {'path':str(Path(name).resolve())}
        try:
            with Path(name).open('rb') as handle:
                observed = handle.read(262145)
            if len(observed)>262144:
                raise ValueError('File exceeds262144-byte inspection bound; use an appropriate reader without claiming this check completed')
            text = observed.decode('utf-8-sig')
            row.update(status='inspected',sha256=hashlib.sha256(observed).hexdigest(),bytes=len(observed),
                       text=text,labelled_formula_check=labelled_formulas(text))
        except (OSError,UnicodeError,ValueError) as exc:
            row.update(status='unavailable',reason=str(exc))
        rows.append(row)
    return {'operation':'inspect','status':'inspected' if rows and all(r['status']=='inspected' for r in rows) else 'unavailable',
            'accuracy':'unverified','files':rows,'limits':LIMIT}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation',required=True)
    calc = commands.add_parser('calculate',help='Check submitted literal equalities; % on the right means a fractional rate')
    calc.add_argument('--check',action='append',required=True)
    calc.add_argument('--places',type=int,choices=range(13),help='Round computed values to this many displayed decimal places, in percent units when RHS uses %')
    inspect = commands.add_parser('inspect',help='Return actual saved bytes as UTF-8 text plus hashes; never an accuracy certificate')
    inspect.add_argument('files',nargs='+')
    args = parser.parse_args()
    result = calculate(args.check,args.places) if args.operation=='calculate' else inspect_files(args.files)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status'] in ['pass','inspected'] else 1 if result['status']=='fail' else 2

if __name__=='__main__':
    raise SystemExit(main())
