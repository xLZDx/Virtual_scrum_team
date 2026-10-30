"""Single-use Windows launcher and one-process S2-4.12c WSL protocol."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"D:\Repo\Virtual_scrum_team\docs\sdlc\evidence")
PREFIX = "s2-runtime-qual-3a3a0e67-s2-runtime-20261030-2b5e04a3"
WSL = r"C:\Windows\System32\wsl.exe"
WSL_SOURCE = r'''import base64,datetime,hashlib,json,os,pathlib,stat,subprocess,sys,time,struct,socket,sqlite3,urllib.parse,grp
class StopChain(Exception): pass
P={'request_id':'3a3a0e67-5577-4383-8e1b-5bf803727558','head':'7d1d16f6348e6c00a5a568b5cfbc8caf309194b9','run_id':'s2-runtime-20261030-2b5e04a37cbc430f0adb239658a29910','bootstrap_request_id':'e520e04f58ad5e6a431a3a20b0efb87c','nonce':'0aac24fec9a2a5c53c5e9da21cbb4a42','runtime_selector':'/opt/vst-runtime-80c2b81deac364ed6466600fd46af47aafe805e2','attempt_path':'docs/sdlc/evidence/s2-runtime-qual-7f3f3b3c-s2-runtime-20261030-2b5e04a3.attempt.json'}
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def cmd(argv,cwd=None,timeout=30):
 t=utc()
 try: p=subprocess.run(argv,cwd=cwd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,timeout=timeout)
 except Exception as e: return {'argv':argv,'started_utc':t,'finished_utc':utc(),'exit_code':None,'error':type(e).__name__+': '+str(e),'stdout_b64':'','stderr_b64':''}
 return {'argv':argv,'started_utc':t,'finished_utc':utc(),'exit_code':p.returncode,'stdout_b64':base64.b64encode(p.stdout).decode(),'stderr_b64':base64.b64encode(p.stderr).decode(),'stdout_bytes':len(p.stdout),'stderr_bytes':len(p.stderr),'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()}
def out(x): return base64.b64decode(x.get('stdout_b64',''))
def txt(x): return out(x).decode('utf8','replace')
R={'schema':'S2_RUNTIME_QUALIFICATION_ONE_SHOT_ATTEMPT_V1','request_id':P['request_id'],'authorization':'GPT-PM single-use S2-4.12c; retry_cap=0','head':P['head'],'tuple':{k:P[k] for k in ('run_id','bootstrap_request_id','nonce','runtime_selector')},'started_utc':utc(),'checks':[],'stages':{},'artifacts':{},'terminal':None}
mounted=False
def stop(reason): R.update(terminal='HOLD',reason=reason); raise StopChain()
def check(name,ok,**more): R['checks'].append({'id':name,'pass':bool(ok),**more})
try:
 mp='/mnt/d'; os.makedirs(mp,exist_ok=True)
 m0=cmd(['/usr/bin/findmnt','-n','-o','SOURCE,FSTYPE,OPTIONS','--mountpoint',mp]); parts=txt(m0).strip().split()
 if m0.get('exit_code')==0:
  if len(parts)<3 or parts[0]!='D:' or parts[1]!='9p' or 'ro' not in parts[2].split(',') or 'rw' in parts[2].split(','):
   R['mount']={'before':m0}; stop('Existing /mnt/d is not verified D: 9p read-only; no remount or alternate mount attempted.')
  R['mount']={'before':m0,'source':parts[0],'fstype':parts[1],'options':parts[2],'mount_added_by_attempt':False}
 else:
  mx=cmd(['/usr/bin/mount','-t','drvfs','D:',mp,'-o','ro']); R['mount']={'before':m0,'mount_command':mx,'mount_added_by_attempt':mx.get('exit_code')==0}; mounted=mx.get('exit_code')==0
  if not mounted: stop('The single permitted temporary D: read-only mount failed; no retry.')
  mv=cmd(['/usr/bin/findmnt','-n','-o','SOURCE,FSTYPE,OPTIONS','--mountpoint',mp]); parts=txt(mv).strip().split(); R['mount']['verified']=mv
  if mv.get('exit_code')!=0 or len(parts)<3 or parts[0]!='D:' or parts[1]!='9p' or 'ro' not in parts[2].split(',') or 'rw' in parts[2].split(','): stop('The one mount did not verify as D:, 9p, ro; no retry.')
  R['mount'].update(source=parts[0],fstype=parts[1],options=parts[2])
 repo=pathlib.Path('/mnt/d/Repo/Virtual_scrum_team')
 if not repo.is_dir() or str(repo.resolve())!='/mnt/d/Repo/Virtual_scrum_team': stop('Intended repository does not resolve under verified D: mount.')
 a=json.loads((repo/P['attempt_path']).read_text()); tuple_ok=a.get('head')==P['head'] and a.get('run_id')==P['run_id'] and a.get('bootstrap_request_id')==P['bootstrap_request_id'] and a.get('nonce')==P['nonce'] and a.get('runtime_selector')==P['runtime_selector']
 check('immutable_tuple_matches_pinned_attempt',tuple_ok,attempt_path=P['attempt_path'],attempt_request_id=a.get('request_id'))
 pins=a.get('execution',{}).get('source_hashes',{})
 if len(pins)!=6: stop('Pinned attempt did not contain exactly six source pins.')
 h=cmd(['/usr/bin/git','rev-parse','HEAD'],str(repo)); head=txt(h).strip(); R['head_check']=h; check('exact_HEAD',h.get('exit_code')==0 and head==P['head'],observed=head,expected=P['head'])
 if h.get('exit_code')!=0 or head!=P['head'] or not tuple_ok: stop('HEAD or immutable tuple mismatch; no runtime operation.')
 for rel,expected_sha in pins.items():
  f=repo/rel; local=hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else None; blob=cmd(['/usr/bin/git','show','HEAD:'+rel],str(repo)); clean=cmd(['/usr/bin/git','diff','--quiet','HEAD','--',rel],str(repo))
  check('source_pin:'+rel,blob.get('exit_code')==0 and blob.get('stdout_sha256')==expected_sha and local==expected_sha and clean.get('exit_code')==0,expected=expected_sha,working_sha256=local,blob_sha256=blob.get('stdout_sha256'),clean_exit=clean.get('exit_code'))
 if not all(x['pass'] for x in R['checks']): stop('An exact source pin failed; no runtime operation.')
 repo_import_root=str(repo.resolve())
 if repo_import_root!='/mnt/d/Repo/Virtual_scrum_team': stop('Verified repository import root differs from the authorized path.')
 if repo_import_root in sys.path: sys.path.remove(repo_import_root)
 sys.path.insert(0,repo_import_root)
 if str(pathlib.Path(sys.path[0]).resolve())!=repo_import_root: stop('Pinned repository import path could not be established.')
 # Fresh read-only post-apply status; do not rerun collector or validator.
 status_start=utc(); bundle=json.loads((repo/'docs/sdlc/runtime-config/bundle-manifest.json').read_text()); layout=json.loads((repo/'docs/sdlc/runtime-config/installation-layout.json').read_text()); applied_doc=json.loads((repo/'docs/sdlc/evidence/s2-runtime-qual-7f3f3b3c-s2-runtime-20261030-2b5e04a3-apply.stdout.bin').read_bytes()); bfiles={x['path']:x for x in bundle['files']}; expected={}
 for x in layout['configuration_files']+layout['unit_overrides']:
  q=bfiles.get(x['source'])
  if q is None: stop('Pinned bundle source missing: '+x['source'])
  expected[x['destination']]={'uid':x['uid'],'gid':x['gid'],'mode':x['mode'],'size':q['size'],'sha256':q['sha256']}
 for x in bundle['units']:
  if x.get('publication')=='new absent-only configuration unit; no enable/start during installation':
   q=bfiles.get(x['source'])
   if q is None: stop('Pinned unit source missing: '+x['source'])
   expected[x['destination']]={'uid':x['uid'],'gid':x['gid'],'mode':x['mode'],'size':q['size'],'sha256':q['sha256']}
 applied={x['path']:x for x in applied_doc['files']}; observed={}; errors=[]
 if len(expected)!=26 or set(expected)!=set(applied): errors.append({'expected_count':len(expected),'apply_count':len(applied),'path_sets_equal':set(expected)==set(applied)})
 for path,w in expected.items():
  try:
   st=os.lstat(path); item={'state':'PRESENT','kind':'regular' if stat.S_ISREG(st.st_mode) else 'other','uid':st.st_uid,'gid':st.st_gid,'mode':format(stat.S_IMODE(st.st_mode),'04o'),'size':st.st_size,'sha256':hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()}
  except Exception as e: item={'state':'ERROR','error':type(e).__name__+': '+str(e)}
  observed[path]=item
  if item.get('state')!='PRESENT' or item.get('kind')!='regular' or any(item.get(k)!=v for k,v in w.items()) or applied.get(path,{}).get('sha256')!=item.get('sha256'): errors.append({'path':path,'expected':w,'applied_sha256':applied.get(path,{}).get('sha256'),'observed':item})
 check('all_26_post_apply_paths_type_uid_gid_mode_size_sha256_exact',not errors,count=len(observed),errors=errors)
 paths={'supervisor':'/etc/vst-runner/supervisor-service.json','bootstrap':'/etc/vst-runner/bootstrap-request.json','probe':'/etc/vst-runner/probe-request.json','profile':'/etc/vst-runner/network-profile.json'}; cfg={k:json.loads(pathlib.Path(v).read_text()) for k,v in paths.items()}
 boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(); selector=os.path.realpath('/opt/vst-runtime')
 check('runtime_selector',pathlib.Path('/opt/vst-runtime').is_symlink() and selector==P['runtime_selector'],observed=selector,expected=P['runtime_selector'])
 check('boot_identity_unchanged',boot==applied_doc.get('boot_id'),observed=boot,expected=applied_doc.get('boot_id'))
 tuple_target=cfg['supervisor'].get('run_id')==P['run_id'] and cfg['supervisor'].get('probe_nonce')==P['nonce'] and cfg['bootstrap'].get('request_id')==P['bootstrap_request_id'] and cfg['bootstrap'].get('run_id')==P['run_id'] and cfg['probe']=={'run_id':P['run_id'],'nonce':P['nonce']} and cfg['profile'].get('environment_id')=='Ubuntu-24.04:S2:'+P['run_id'] and cfg['profile'].get('external_allowlist')==[]
 check('immutable_run_request_nonce_selector_tuple',tuple_target,supervisor_run_id=cfg['supervisor'].get('run_id'),bootstrap_request_id=cfg['bootstrap'].get('request_id'),bootstrap_run_id=cfg['bootstrap'].get('run_id'))
 selector_test='tests/vst/test_s2_assignment_basis.py::test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment'; manifest=cfg['bootstrap'].get('task_manifest',{})
 from tools.vst.contracts import manifest_sha256
 task_ok=manifest.get('retry_cap')==0 and manifest.get('required_tests')==[{'acceptance':['REQ-003'],'slot':'runtime-tests','test_id':selector_test}] and manifest_sha256(manifest)==bundle.get('task_manifest_sha256')
 check('single_exact_test_manifest_retry_cap_zero',task_ok,selector=selector_test,retry_cap=manifest.get('retry_cap'),required_tests=manifest.get('required_tests'))
 units=['vst-assignment-bootstrap.service','vst-dispatch-issuer.service','vst-dispatch-owner.service','vst-dispatch-owner.socket','vst-dispatcher.service','vst-runner.service','vst-sandbox-probe.service','vst-signer.service','vst-supervisor.service']; unit_records={}
 for u in units:
  q=cmd(['/usr/bin/systemctl','show',u,'--property=LoadState','--property=ActiveState','--property=SubState','--property=MainPID','--property=Job']); raw=txt(q).splitlines(); props={}
  for line in raw:
   if '=' in line:
    key,value=line.split('=',1); props[key]=value
  unit_records[u]={'exit_code':q.get('exit_code'),'properties':props,'raw_lines':raw,'stdout_b64':q.get('stdout_b64'),'stdout_sha256':q.get('stdout_sha256')}
 def unit_safe(u,item):
  props=item.get('properties',{}); pid=props.get('MainPID')
  pid_ok=(pid=='0') if u.endswith('.service') else (pid in (None,'0'))
  return item.get('exit_code')==0 and props.get('LoadState')=='loaded' and props.get('ActiveState')=='inactive' and props.get('SubState')=='dead' and props.get('Job')=='' and pid_ok
 unit_verdicts={u:unit_safe(u,item) for u,item in unit_records.items()}; unit_ok=len(unit_records)==9 and all(unit_verdicts.values()); R['post_apply_unit_status']=unit_records; check('all_9_units_loaded_inactive_dead_no_pid',unit_ok,unit_verdicts=unit_verdicts)
 jobs=cmd(['/usr/bin/systemctl','list-jobs','--no-legend','--no-pager']); R['post_apply_systemd_jobs']=jobs; check('no_systemd_jobs',jobs.get('exit_code')==0 and not txt(jobs).strip())
 system=cmd(['/usr/bin/systemctl','is-system-running']); R['post_apply_systemd_state']=system; check('systemd_running',system.get('exit_code')==0 and txt(system).strip()=='running')
 presence={p:os.path.lexists(p) for p in [cfg['supervisor'].get('store_path'),cfg['supervisor'].get('preflight_record_path'),'/run/vst-preflight/network-policy-attestation.json','/run/vst-supervisor/supervisor.sock','/run/vst-supervisor/dispatch-owner.sock','/run/vst-runner/runner.sock']}; R['post_apply_status']={'captured_utc':status_start,'finished_utc':utc(),'boot_id':boot,'runtime_selector':selector,'configuration_files':observed,'path_presence':presence}; check('no_existing_store_preflight_attestation_or_runtime_sockets',all(v is False for v in presence.values()),observed=presence)
 if not all(x['pass'] for x in R['checks']): stop('Fresh post-apply status or pin predicate failed; root preflight and later stages NOT_RUN.')
 # Stage A: exactly one authorized root-captured preflight.
 args=['/usr/bin/python3','tools/vst/preflight_host_capture.py','--run-id',P['run_id'],'--nonce',P['nonce'],'--expected-head',P['head'],'--expected-sha256',pins['tools/vst/preflight_host_capture.py'],'--request-id',P['bootstrap_request_id'],'--expected-supervisor-sha256',expected['/etc/vst-runner/supervisor-service.json']['sha256'],'--expected-profile-sha256',expected['/etc/vst-runner/network-profile.json']['sha256'],'--expected-bootstrap-sha256',expected['/etc/vst-runner/bootstrap-request.json']['sha256'],'--expected-manifest-sha256',bundle['task_manifest_sha256']]
 pf=cmd(args,str(repo),timeout=130); R['stages']['root_preflight']=pf
 if pf.get('exit_code')!=0: stop('Single root preflight failed; claim/probe and TestRun NOT_RUN.')
 def artifact(path):
  st=os.stat(path); data=pathlib.Path(path).read_bytes(); return {'path':path,'uid':st.st_uid,'gid':st.st_gid,'mode':format(stat.S_IMODE(st.st_mode),'04o'),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'content_b64':base64.b64encode(data).decode()}
 preflight=artifact(cfg['supervisor']['preflight_record_path']); att=artifact('/run/vst-preflight/network-policy-attestation.json'); R['artifacts']['root_preflight']=preflight; R['artifacts']['network_attestation']=att
 if preflight['uid']!=0 or preflight['mode']!='0600' or att['uid']!=0 or att['mode']!='0600': stop('Root preflight artifacts failed ownership/mode checks; claim/probe and TestRun NOT_RUN.')
 R['stages']['root_preflight_verdict']='PASS'
 # Stage B: start only the temporary test stack and submit one identity-bound assignment.
 starts=[]
 for u in ['vst-supervisor.service','vst-signer.service','vst-runner.service','vst-dispatcher.service','vst-dispatch-owner.socket']:
  q=cmd(['/usr/bin/systemctl','start',u],timeout=45); starts.append({'unit':u,**q})
  if q.get('exit_code')!=0: R['stages']['service_start']=starts; stop('Runtime service start failed; no retries or assignment submission.')
 R['stages']['service_start']=starts
 since='@'+str(time.time()-2); bootcmd=cmd(['/usr/bin/systemctl','start','vst-assignment-bootstrap.service'],timeout=40); R['stages']['bootstrap_service']=bootcmd
 if bootcmd.get('exit_code')!=0: stop('Single bootstrap service invocation failed; no retry/issuer/claim/TestRun.')
 bj=cmd(['/usr/bin/journalctl','-u','vst-assignment-bootstrap.service','--no-pager','-o','cat','--since',since]); R['stages']['bootstrap_journal']=bj; handoffs=[]
 for line in txt(bj).splitlines():
  try:
   obj=json.loads(line); br=obj.get('bootstrap_request',{})
   if br.get('request_id')==P['bootstrap_request_id'] and obj.get('run_id')==P['run_id']: handoffs.append(obj)
  except Exception: pass
 if len(handoffs)!=1: stop('Bootstrap handoff absent or ambiguous; no replacement/issuer/claim/TestRun.')
 handoff=handoffs[0]; opid=handoff.get('assignment_operation_id')
 if not isinstance(opid,str) or len(opid)!=64 or handoff.get('task_id')!='S2-4-runtime-owner-runner-qualification' or handoff.get('story_id')!='S2-4' or handoff.get('slot')!='runtime-tests' or handoff.get('attempt')!=1 or handoff.get('run_id')!=P['run_id'] or handoff.get('bootstrap_request',{}).get('request_id')!=P['bootstrap_request_id'] or handoff.get('bootstrap_request',{}).get('task_manifest',{}).get('required_tests')!=manifest.get('required_tests'): R['bootstrap_handoff']=handoff; stop('Bootstrap handoff differs from authorized identity; no retry.')
 R['bootstrap_handoff']=handoff
 ipath='/etc/vst-runner/issuance-request.json'
 if os.path.lexists(ipath): stop('Derived issuer request path already exists; no overwrite.')
 gid=grp.getgrnam('vst-supervisor-client').gr_gid; layout_entry=next((x for x in layout.get('runtime_derived_files',[]) if x.get('path')==ipath),None)
 if not layout_entry or (layout_entry.get('uid'),layout_entry.get('gid'),layout_entry.get('mode'))!=(0,gid,'0640'): stop('Derived issuance request ownership contract missing or ambiguous.')
 ibody=json.dumps({'assignment_operation_id':opid},sort_keys=True,separators=(',',':')).encode(); fd=os.open(ipath,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); os.write(fd,ibody); os.fchown(fd,0,gid); os.fchmod(fd,0o640); os.close(fd)
 ist=os.stat(ipath); R['stages']['issuer_request']={'path':ipath,'uid':ist.st_uid,'gid':ist.st_gid,'mode':format(stat.S_IMODE(ist.st_mode),'04o'),'bytes':len(ibody),'sha256':hashlib.sha256(ibody).hexdigest()}
 since='@'+str(time.time()-2); issuer=cmd(['/usr/bin/systemctl','start','vst-dispatch-issuer.service'],timeout=40); R['stages']['issuer_service']=issuer
 if issuer.get('exit_code')!=0: stop('Single issuer service invocation failed; no retry/Owner submission/TestRun.')
 ij=cmd(['/usr/bin/journalctl','-u','vst-dispatch-issuer.service','--no-pager','-o','cat','--since',since]); R['stages']['issuer_journal']=ij; instructions=[]
 for line in txt(ij).splitlines():
  try:
   obj=json.loads(line)
   if obj.get('task_id')==handoff['task_id'] and obj.get('run_id')==P['run_id'] and obj.get('slot')=='runtime-tests' and obj.get('attempt')==1: instructions.append(obj)
  except Exception: pass
 if len(instructions)!=1: stop('Signed instruction absent or ambiguous; no Owner submission/TestRun.')
 instruction=instructions[0]
 from tools.vst.assignment_basis import validate_policy
 from tools.vst.dispatch_issuance import issuance_identity
 policy_obj=json.loads(pathlib.Path('/etc/vst-runner/assignment-delegation-policy.json').read_text()); policy,policy_sha=validate_policy(policy_obj); ident=issuance_identity(handoff,policy={'policy':policy,'policy_sha256':policy_sha},now=datetime.datetime.now(datetime.timezone.utc))
 from tools.vst.dispatch_instruction import validate_dispatch_instruction
 instruction=validate_dispatch_instruction(instruction)
 if instruction.get('request_id')!=ident['request_id'] or instruction.get('epoch')!=handoff['epoch'] or not instruction.get('signature'): stop('Signed instruction does not bind exact handoff; no retry.')
 R['dispatch_instruction']=instruction
 from tools.vst.contracts import canonical_bytes
 payload=canonical_bytes({'instruction':instruction}); s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.settimeout(40); s.connect('/run/vst-supervisor/dispatch-owner.sock'); s.sendall(struct.pack('!I',len(payload))+payload); s.shutdown(socket.SHUT_WR)
 headbuf=b''
 while len(headbuf)<4:
  z=s.recv(4-len(headbuf))
  if not z: raise RuntimeError('owner response header truncated')
  headbuf+=z
 n=struct.unpack('!I',headbuf)[0]; response=b''
 while len(response)<n:
  z=s.recv(n-len(response))
  if not z: raise RuntimeError('owner response truncated')
  response+=z
 s.close(); owner=json.loads(response); R['stages']['owner_submission']={'request_bytes':len(payload),'request_sha256':hashlib.sha256(payload).hexdigest(),'response_bytes':len(response),'response_sha256':hashlib.sha256(response).hexdigest(),'response':owner}
 if not owner.get('ok') or owner.get('result',{}).get('instruction')!=instruction: stop('Owner did not durably accept the exact instruction; no retry or claim reuse.')
 R['stages']['owner_submission_verdict']='ACCEPTED'
 # Stage B durable Runner claim, then Stage C one manifest-bound report receipt.
 uri='file:'+urllib.parse.quote(cfg['supervisor']['store_path'],safe='/')+'?mode=ro'; deadline=time.monotonic()+float(bundle.get('timeout_sec',120))+45; claim=None; events=[]; receipts=[]; snapshots=[]
 while time.monotonic()<deadline:
  db=sqlite3.connect(uri,uri=True,timeout=1); db.row_factory=sqlite3.Row
  claims=[dict(x) for x in db.execute('SELECT grant_id,invocation_id,request_id,task_id,slot,runner_id,attempt,epoch,run_id,service_generation,manifest_sha256,payload_sha256,grant_body,claimed_at FROM runner_execution_claims WHERE task_id=?',(handoff['task_id'],))]
  if claims:
   events=[dict(x) for x in db.execute('SELECT grant_id,state,payload,created_at FROM runner_execution_events WHERE grant_id IN (SELECT grant_id FROM runner_execution_claims WHERE task_id=?) ORDER BY seq',(handoff['task_id'],))]
   receipts=[dict(x) for x in db.execute('SELECT slot,attempt,epoch,receipt_sha256,prev_receipt_sha256,body FROM receipts WHERE task_id=? ORDER BY seq',(handoff['task_id'],))]
  db.close(); snapshots.append({'utc':utc(),'claims':len(claims),'event_states':[x['state'] for x in events],'receipts':len(receipts)})
  if len(claims)>1 or len(receipts)>1: stop('Multiple durable claim/receipt rows; no retry/reuse.')
  if claims:
   claim=claims[0]
   # Contract basis: tools/vst/store.py:231-254 (append-only claim/event schema),
   # :5290-5317 (canonical grant digest and PENDING event), and :5510-5522
   # (reservation is accepted only from one exact PENDING claim); the bounded
   # status/generation API is tools/vst/supervisor_service.py:510-560.
   try:
    from tools.vst.contracts import canonical_bytes
    from tools.vst.execution_grant import validate_execution_grant
    grant=json.loads(claim['grant_body']); grant=validate_execution_grant(grant); grant_bytes=canonical_bytes(grant); grant_digest=hashlib.sha256(grant_bytes).hexdigest()
    event_payloads=[json.loads(x['payload']) for x in events]
   except Exception as e: R['stages']['durable_runner_claim_error']=type(e).__name__+': '+str(e); stop('Durable claim/grant/event is malformed; no retry/reuse/TestRun.')
   fields=('grant_id','invocation_id','request_id','task_id','slot','runner_id','attempt','epoch','run_id','service_generation','manifest_sha256')
   column_binding=all(claim.get(k)==grant.get(k) for k in fields)
   tuple_binding=(grant.get('request_id')==instruction.get('request_id') and grant.get('task_id')==handoff['task_id'] and grant.get('slot')=='runtime-tests' and grant.get('runner_id')==handoff['runner_id'] and grant.get('attempt')==1 and grant.get('epoch')==handoff['epoch'] and grant.get('run_id')==P['run_id'] and grant.get('manifest_sha256')==bundle['task_manifest_sha256'] and grant.get('service_generation')==claim.get('service_generation') and claim.get('payload_sha256')==grant_digest and claim.get('claimed_at') is not None)
   states=[x['state'] for x in events]
   pending={'event':'RUNNER_EXECUTION_PENDING','state':'PENDING','grant_id':grant.get('grant_id'),'invocation_id':grant.get('invocation_id'),'request_id':grant.get('request_id'),'task_id':grant.get('task_id'),'slot':grant.get('slot'),'runner_id':grant.get('runner_id'),'attempt':grant.get('attempt'),'epoch':grant.get('epoch'),'service_generation':grant.get('service_generation'),'run_id':grant.get('run_id'),'payload_sha256':grant_digest}
   reserved={'event':'RUNNER_EXECUTION_RESERVED','state':'EXECUTION_RESERVED','grant_id':grant.get('grant_id'),'payload_sha256':grant_digest,'invocation_id':grant.get('invocation_id'),'request_id':grant.get('request_id'),'service_generation':grant.get('service_generation')}
   event_binding=(states in (['PENDING'],['PENDING','EXECUTION_RESERVED']) and event_payloads[0]==pending and (len(event_payloads)==1 or event_payloads[1]==reserved))
   from tools.vst.supervisor_service import SupervisorClient
   supervisor_client=SupervisorClient(cfg['supervisor'].get('socket_path','/run/vst-supervisor/supervisor.sock'))
   live_generation=supervisor_client.generation(); claim_status=supervisor_client.claim_status(grant)
   status_binding=(live_generation==grant.get('service_generation') and claim_status.get('service_generation')==grant.get('service_generation') and claim_status.get('state') in ('PENDING','EXECUTION_RESERVED'))
   R['stages']['durable_runner_claim']={'claim':claim,'grant':grant,'event_states':states,'event_payloads':event_payloads,'live_generation':live_generation,'claim_status':claim_status,'column_binding':column_binding,'tuple_binding':tuple_binding,'event_binding':event_binding,'status_binding':status_binding}
   if not all((column_binding,tuple_binding,event_binding,status_binding)): stop('Durable Runner claim does not exactly bind the authorized request/epoch/generation/tuple and PENDING or EXECUTION_RESERVED status; no retry/reuse/TestRun.')
   R['stages']['durable_runner_claim']['verdict']='PASS'; break
  time.sleep(0.2)
 else: R['stages']['claim_observations']=snapshots[-12:]; stop('No durable Runner claim within bounded wait; no retry/TestRun.')
 R['stages']['test_run_verdict']='IN_PROGRESS'
 while time.monotonic()<deadline:
  db=sqlite3.connect(uri,uri=True,timeout=1); db.row_factory=sqlite3.Row; receipts=[dict(x) for x in db.execute('SELECT slot,attempt,epoch,receipt_sha256,prev_receipt_sha256,body FROM receipts WHERE task_id=? ORDER BY seq',(handoff['task_id'],))]; events=[dict(x) for x in db.execute('SELECT grant_id,state,created_at FROM runner_execution_events WHERE grant_id=? ORDER BY created_at',(claim['grant_id'],))]; db.close()
  if len(receipts)>1: stop('Multiple TestRun receipts; no retry.')
  if len(receipts)==1: break
  ru=cmd(['/usr/bin/systemctl','show','vst-runner.service','--property=ActiveState','--property=SubState','--property=MainPID','--value'])
  if ru.get('exit_code')!=0 or not txt(ru).splitlines() or txt(ru).splitlines()[0]!='active': R['stages']['runner_status']=ru; stop('Runner not active before terminal receipt; no retry.')
  time.sleep(0.2)
 else: stop('One report-bound TestRun did not finish by bounded deadline; no retry.')
 from tools.vst.contracts import receipt_sha256
 receipt=json.loads(receipts[0]['body']); digest=receipt_sha256(receipt); selector_test='tests/vst/test_s2_assignment_basis.py::test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment'
 accepted=(digest==receipts[0]['receipt_sha256'] and receipt.get('receipt_type')=='TestRun' and receipt.get('result')=='PASS' and receipt.get('task_id')==handoff['task_id'] and receipt.get('slot')=='runtime-tests' and receipt.get('attempt')==1 and receipt.get('run_id')==P['run_id'] and receipt.get('manifest_sha256')==bundle['task_manifest_sha256'] and receipt.get('expected_test_ids')==[selector_test] and receipt.get('executed_test_ids')==[selector_test] and receipt.get('skipped_test_ids')==[] and receipt.get('xfail_test_ids')==[])
 R['stages']['test_run']={'verdict':'PASS' if accepted else 'FAIL','receipt':receipt,'stored_receipt_sha256':receipts[0]['receipt_sha256'],'computed_receipt_sha256':digest,'runner_event_states':[x['state'] for x in events],'selector':selector_test}; check('single_exact_report_bound_TestRun',accepted,selector=selector_test,result=receipt.get('result'),receipt_sha256=digest)
 if not accepted: stop('Single TestRun ended without exact PASS; no retry.')
 R.update(terminal='COMPLETE',reason='Exact one-shot root preflight, Owner-to-Runner claim, and report-bound TestRun passed.')
except StopChain: pass
except BaseException as e: R.update(terminal='HOLD',reason='one-shot wrapper failure: '+type(e).__name__+': '+str(e))
finally:
 R['finished_utc']=utc()
 if mounted:
  R['temporary_unmount']=cmd(['/usr/bin/umount','/mnt/d'])
  if R['temporary_unmount'].get('exit_code')!=0: R['unmount_warning']='temporary D: mount could not be removed'
 if R.get('terminal') is None: R.update(terminal='HOLD',reason='terminal status missing')
 R['zero_retry_confirmed']=True; R['top_level_wsl_processes']=1
print(json.dumps(R,separators=(',',':')),flush=True)
'''

def main() -> int:
    script = WSL_SOURCE.encode("utf-8")
    child = [WSL, "--distribution", "Ubuntu-24.04", "--user", "root", "--exec",
             "/usr/bin/python3.12", "-I", "-B", "-S", "-"]
    record = {
        "schema": "S2_RUNTIME_QUALIFICATION_ONE_SHOT_ATTEMPT_V1",
        "request_id": "3a3a0e67-5577-4383-8e1b-5bf803727558",
        "authorization": "GPT-PM single-use S2-4.12c; retry_cap=0",
        "head": "7d1d16f6348e6c00a5a568b5cfbc8caf309194b9",
        "tuple": {"run_id": "s2-runtime-20261030-2b5e04a37cbc430f0adb239658a29910",
                  "bootstrap_request_id": "e520e04f58ad5e6a431a3a20b0efb87c",
                  "nonce": "0aac24fec9a2a5c53c5e9da21cbb4a42",
                  "runtime_selector": "/opt/vst-runtime-80c2b81deac364ed6466600fd46af47aafe805e2"},
        "launcher": "C:\\Python314\\python.exe -I -B -S",
        "child_command": child,
        "script_transport": "stdin",
        "script_bytes": len(script),
        "script_sha256": hashlib.sha256(script).hexdigest(),
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "wsl_spawned": False,
    }
    try:
        result = subprocess.run(child, input=script, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False)
        record["wsl_spawned"] = True
        record["wsl_exit_code"] = result.returncode
        stdout, stderr = result.stdout, result.stderr
    except Exception as exc:
        record["wsl_spawn_error"] = type(exc).__name__ + ": " + str(exc)
        stdout, stderr = b"", (type(exc).__name__ + ": " + str(exc)).encode("utf-8")
    for suffix, data in (("-wsl.stdout.bin", stdout), ("-wsl.stderr.bin", stderr)):
        path = ROOT / (PREFIX + suffix)
        path.write_bytes(data)
        record[suffix[1:-4]] = {"path": "docs/sdlc/evidence/" + path.name,
                                "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    record["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    if stdout:
        try:
            record["protocol"] = json.loads(stdout.decode("utf-8").splitlines()[-1])
        except Exception:
            record["protocol_parse_error"] = "WSL stdout did not end with one JSON protocol record"
    attempt = ROOT / (PREFIX + ".attempt.json")
    attempt.write_text(json.dumps(record, sort_keys=True, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in record.items() if k != "protocol"}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
