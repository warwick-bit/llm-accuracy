"""Bounded literal check for labelled SHA-256 citations in report prose.

Checks only recognized vN-labelled digests on lines explicitly naming SHA-256.
It does not establish that the actor ran a hash check or validate all prose.
"""
import re
PATTERN=re.compile(r'\b(?P<version>v[1-9]\d*)\s*:?\s*[`\"]?(?P<digest>[a-fA-F0-9]{8,64}(?:(?:…|\.{3})[a-fA-F0-9]{4,32})?)(?![a-fA-F0-9])')

def check(text,sources):
 rows=[];unscoped=[];narrative=[]
 for line_number,line in enumerate(text.splitlines(),1):
  if not re.search(r'\bsha[- ]?256\b',line,re.I):continue
  matches=list(PATTERN.finditer(line))
  if not matches:
   # Literal-looking but unrecognised claims remain unavailable. A generic
   # statement about hashing belongs to the separate narrative/process audit.
   literal_signal=re.search(r'\b[a-fA-F0-9]{8,}\b|\b(?:sha[- ]?256|v[1-9]\d*)\s*[:=]',line,re.I)
   (unscoped if literal_signal else narrative).append(line_number)
  for match in matches:
   version=match['version'];observed=match['digest'].lower();expected=sources.get(version)
   row=dict(line=line_number,version=version,observed=observed,expected=expected)
   if expected is None:row['status']='unavailable'
   elif '…' in observed or '...' in observed:
    prefix,suffix=re.split(r'…|\.{3}',observed)
    row['status']='pass' if expected.startswith(prefix) and expected.endswith(suffix) else 'fail'
   elif len(observed)==64:row['status']='pass' if observed==expected else 'fail'
   else:row['status']='unavailable'
   rows.append(row)
 return dict(status='fail' if any(r['status']=='fail' for r in rows) else 'unavailable' if unscoped or any(r['status']=='unavailable' for r in rows) else 'pass' if rows else 'not_applicable',
  checks=rows,unrecognized_sha256_lines=unscoped,nonnumeric_sha256_lines_for_narrative_review=narrative,
  limits=['Only recognized labelled SHA-256 literals; absence of a match does not establish complete citation coverage.',
          'Digest agreement does not establish actor execution, source truth or whole-report accuracy.',
          'Nonliteral hashing statements require separate narrative/process review; this literal checker does not certify them.'])
