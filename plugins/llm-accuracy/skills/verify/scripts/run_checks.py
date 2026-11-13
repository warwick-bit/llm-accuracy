"""Execute bounded literal equations or read actual UTF-8 deliverables.

Source truth, unit semantics, claim coverage and factual prose remain unverified.
"""
import argparse
import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path
from saved_output_formulas import expression, check as labelled_formulas

LIMIT = 'Only submitted equations or observed file bytes are checked. Sources, units, completeness and prose require source review.'

def parse_places(value):
    if value == 'shown':
        return value
    try:
        places = int(value)
        if 0 <= places <= 12:
            return places
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("must be 'shown' or an integer from 0 to 12")


def shown_places(value):
    if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)', value):
        return None
    places = len(value.partition('.')[2])
    return places if places <= 12 else None


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
            stated = rhs[:-1].strip() if percent else rhs
            decimal_places = shown_places(stated) if places == 'shown' else places
            observed_display = Fraction(stated)
            computed = expression(lhs)
            displayed = computed*100 if percent else computed
            rounded = round(displayed,decimal_places) if decimal_places is not None else displayed
            if places == 'shown' and decimal_places is not None and rounded != observed_display:
                scale = 10 ** decimal_places
                scaled = displayed * scale
                # A reduced rational has denominator 2 exactly at a rounding tie.
                if scaled.denominator == 2:
                    half_up = Fraction((abs(scaled.numerator) // 2 + 1) * (1 if scaled > 0 else -1), scale)
                    if observed_display == half_up:
                        rounded = half_up
                        row['tie_pass'] = 'half_up'
            row.update(status='pass' if rounded==observed_display else 'fail',computed_exact=str(computed),
                       computed_display_exact=str(rounded),reported_display_exact=str(observed_display),
                       percent=percent,decimal_places=decimal_places)
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
    calc = commands.add_parser('calculate',help='Check submitted literal equalities; %% on the right means a fractional rate')
    calc.add_argument('--check',action='append',required=True)
    calc.add_argument('--places',type=parse_places,metavar='0..12|shown',help='Round computed values to 0..12 decimal places, or use each stated value\'s precision with shown (in percent units when RHS uses %%); shown accepts half-even or half-up at exact ties')
    inspect = commands.add_parser('inspect',help='Return actual saved bytes as UTF-8 text plus hashes; never an accuracy certificate')
    inspect.add_argument('files',nargs='+')
    args = parser.parse_args()
    result = calculate(args.check,args.places) if args.operation=='calculate' else inspect_files(args.files)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status'] in ['pass','inspected'] else 1 if result['status']=='fail' else 2

if __name__=='__main__':
    raise SystemExit(main())
