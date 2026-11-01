"""Explicit two-call numerical-implication audit using the existing Claude client.

No hooks, credentials, integrations or settings are installed or changed. Input
files are read-only. Successful arithmetic is not source or semantic approval.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

CORE=Path(__file__).resolve().parents[2]/'plugins/llm-accuracy/skills/verify/scripts'
sys.path.insert(0,str(CORE))
from run_checks import inspect_files
from evidence_handoff import EVIDENCE_SCHEMA, AUDIT_SCHEMA, EVIDENCE_PROMPT, AUDIT_PROMPT, compact_evidence, validate_audit


def digest(data):
    return hashlib.sha256(data).hexdigest()

def save(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode('utf8'))



def call_client(executable, model, effort, prompt, payload, schema, timeout, output):
    cmd=[executable,'--print','--model',model,'--effort',effort,'--output-format','json',
         '--json-schema',json.dumps(schema),'--tools','', '--strict-mcp-config',
         '--mcp-config','{"mcpServers":{}}','--setting-sources','',
         '--no-session-persistence','--no-chrome','--system-prompt',prompt]
    child_env=os.environ.copy()
    # Nested noninteractive client: retain selected auth/home and Windows discovery.
    for name in ('CLAUDECODE','CLAUDE_CODE_ENTRYPOINT'):
        child_env.pop(name,None)
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    result=subprocess.run(cmd,input=json.dumps(payload,ensure_ascii=False),text=True,
        capture_output=True,encoding='utf8',cwd=output,env=child_env,
        timeout=timeout,creationflags=flags)
    receipt={'exit':result.returncode,'native_hidden_child':os.name=='nt','model_requested':model,
             'stderr_tail':result.stderr[-600:]}
    try:
        envelope=json.loads(result.stdout)
        receipt.update(is_error=bool(envelope.get('is_error')),usage=envelope.get('usage'))
        if result.returncode or envelope.get('is_error'):
            raise ValueError('Client unavailable: '+str(envelope.get('result',''))[:600])
        value=envelope.get('structured_output')
        if value is None:
            value=json.loads(envelope['result'])
        return value,receipt
    except (ValueError,KeyError,TypeError) as exc:
        save(output/'client-unavailable.json',dict(receipt,reason=str(exc)))
        raise ValueError('Native client failed; no retry: '+str(exc)) from exc

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',action='append',required=True,type=Path)
    parser.add_argument('--candidate',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--claude',default='claude',help='Existing native client; authentication/profile is inherited')
    parser.add_argument('--model',default='sonnet')
    parser.add_argument('--effort',default='medium',choices=['low','medium','high'])
    parser.add_argument('--timeout',type=int,default=240)
    args=parser.parse_args(argv)
    args.output_dir.mkdir(exist_ok=False)
    output=args.output_dir.resolve()
    try:
        snapshots={p.resolve():p.read_bytes() for p in [*args.source,args.candidate]}
    except OSError as exc:
        save(output/'STOP.json',{'status':'unavailable','reason':str(exc),'retry':False})
        print(json.dumps({'status':'unavailable','reason':str(exc)}))
        return 2
    def preserved():
        if not all(p.read_bytes()==data for p,data in snapshots.items()):
            raise ValueError('Original input changed during audit')
    sources=[{'name':str(p.name),'text':snapshots[p.resolve()].decode('utf-8-sig')} for p in args.source]
    candidate=snapshots[args.candidate.resolve()].decode('utf-8-sig')
    payload={'sources':sources,'candidate':candidate,
             'conditional_cues':[candidate[m.start():m.start()+320] for m in re.finditer(r'\bif\b',candidate,re.I)]}
    save(output/'input-hashes.json',{str(p):digest(data) for p,data in snapshots.items()})
    try:
        executable=shutil.which(args.claude)
        if not executable:
            raise ValueError('Native Claude client unavailable')
        raw,first=call_client(executable,args.model,args.effort,EVIDENCE_PROMPT,payload,EVIDENCE_SCHEMA,args.timeout,output)
        save(output/'evidence-model.json',raw)
        save(output/'evidence-client.json',first)
        preserved()
        evidence=compact_evidence(raw,candidate)
        save(output/'claim-evidence.json',evidence)
        final,second=call_client(executable,args.model,args.effort,AUDIT_PROMPT,
            dict(payload,compact_evidence=evidence),AUDIT_SCHEMA,args.timeout,output)
        save(output/'audit-client.json',second)
        preserved()
        validate_audit(final,candidate)
        save(output/'audit.json',final)
        inspection=inspect_files([output/'audit.json'])
        save(output/'inspection.json',inspection)
        if inspection['status']!='inspected':
            raise ValueError('Final saved-byte inspection unavailable')
        save(output/'completion.json',{'status':'completed_unverified_semantics','model_calls':2,
            'source_inputs_unchanged':True,'saved_audit_sha256':inspection['files'][0]['sha256'],
            'limits':'Two model passes and literal arithmetic do not certify accuracy or complete source coverage.'})
        print(json.dumps({'status':'completed_unverified_semantics','audit':str(output/'audit.json'),
                          'sha256':inspection['files'][0]['sha256']}))
        return 0
    except (OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired) as exc:
        save(output/'STOP.json',{'status':'unavailable','reason':str(exc)[:4000],'retry':False})
        print(json.dumps({'status':'unavailable','reason':str(exc)[:1000]}))
        return 2

if __name__=='__main__':
    sys.exit(main())
