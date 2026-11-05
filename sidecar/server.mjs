// Independently implemented transport. Provider code and native binaries are external.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import os from 'node:os';
import {pathToFileURL} from 'node:url';
import {allKnown,validCleanClose,closeKnownOwner} from './ledger-lifecycle.mjs';
const MAX_IN=256*1024, MAX_OUT=2*1024*1024;
const methods=new Set(['hello','capabilities','ax_observe','ax_query','ax_action','window_keyboard','cancel','status','shutdown']);
const writes=new Set(['ax_action','window_keyboard']);
const dir=process.env.GCODE_CU_STATE_DIR;
const providerPath=process.env.GCODE_CU_PROVIDER;
if(!dir || !path.isAbsolute(dir) || !providerPath || !path.isAbsolute(providerPath)) throw Error('Explicit absolute GCODE_CU_STATE_DIR and GCODE_CU_PROVIDER required');
fs.mkdirSync(dir,{recursive:true,mode:0o700});
const machineDir=process.env.GCODE_CU_MACHINE_DIR ?? path.join(os.homedir(),'.local','state','gcode','desktop-cu');
if(!path.isAbsolute(machineDir))throw Error('GCODE_CU_MACHINE_DIR must be absolute');
fs.mkdirSync(machineDir,{recursive:true,mode:0o700});
const stat=fs.statSync(machineDir);if(process.getuid && stat.uid!==process.getuid())throw Error('Machine state directory must be owned by current user');
// Exclusive lifetime lock: never steal an uncertain stale lock automatically.
const lock=path.join(machineDir,'writer.lock');
try { fs.mkdirSync(lock,{mode:0o700}); } catch { throw Error('CU_STATE_LOCKED: resolve existing lock after verifying previous process has exited'); }
fs.writeFileSync(path.join(lock,'owner.json'),JSON.stringify({pid:process.pid,started_at:new Date().toISOString(),nonce:crypto.randomUUID()}),{mode:0o600});
let clean=false;
function unlock(){if(!clean){clean=true;try{fs.unlinkSync(path.join(lock,'owner.json'));fs.rmdirSync(lock)}catch{}}}
process.on('exit',unlock);
const ledgerPath=path.join(machineDir,'ledger.json');
let ledger={version:1, actions:{}, stopped:false};
const existingLedger=fs.existsSync(ledgerPath);
if(existingLedger) { ledger=JSON.parse(fs.readFileSync(ledgerPath,'utf8')); if(ledger.version!==1 || !ledger.actions || typeof ledger.stopped!=='boolean') throw Error('Invalid ledger'); }
// Provider-local scope and text-dedup state cannot safely be reconstructed after restart.
if(existingLedger && Object.keys(ledger.actions).length){const entries=Object.entries(ledger.actions);const rec=ledger.reconciliation;const onlyProvenLaunch=entries.length===1 && ledger.owner===entries[0][1].owner && !(ledger.closed_owners??[]).includes(ledger.owner) && rec?.kind==='proven_nonpayload_launch' && rec.action_id===entries[0][0] && rec.fingerprint===entries[0][1].fingerprint && entries[0][1].state==='preparation_reconciled' && entries[0][1].response?.delivery_state==='delivery_unknown' && rec.original_response_sha256===crypto.createHash('sha256').update(JSON.stringify(entries[0][1].response)).digest('hex');if(!onlyProvenLaunch && !validCleanClose(ledger)) ledger.stopped=true;}
// Any accepted action lacking a terminal receipt is uncertain after restart.
for(const a of Object.values(ledger.actions)) if(a.state==='dispatching'){a.state='delivery_unknown';ledger.stopped=true;}
function persist(){const tmp=path.join(machineDir,`ledger.${process.pid}.tmp`);fs.writeFileSync(tmp,JSON.stringify(ledger),{mode:0o600});const fd=fs.openSync(tmp,'r');fs.fsyncSync(fd);fs.closeSync(fd);fs.renameSync(tmp,ledgerPath);const d=fs.openSync(machineDir,'r');try{fs.fsyncSync(d)}finally{fs.closeSync(d)}}
persist();
const mod=await import(pathToFileURL(providerPath).href);
if(typeof mod.createBridge!=='function') throw Error('Provider must export createBridge');
const identity={protocol:1,platform:process.platform, process_id:process.pid, process_started_at:new Date().toISOString(), process_nonce:crypto.randomUUID(), provider_sha256:crypto.createHash('sha256').update(fs.readFileSync(providerPath)).digest('hex'), ...await (mod.identity?.() ?? {})};
const bridges=new Map();let active=false; let owner=ledger.owner??null;const freshOwners=new Set();const needFreshBinding=validCleanClose(ledger);
function reply(id, payload, onFlushed){let result={v:1,id,runtime_identity:identity,...payload};let line=JSON.stringify(result);if(Buffer.byteLength(line)>MAX_OUT){const hash=crypto.createHash('sha256').update(line).digest('hex');const ad=path.join(dir,'artifacts');fs.mkdirSync(ad,{recursive:true,mode:0o700});const filename=path.join(ad,hash+'.json');if(!fs.existsSync(filename))fs.writeFileSync(filename,line,{mode:0o600,flag:'wx'});result={v:1,id,runtime_identity:identity,ok:payload.ok,delivery_state:payload.delivery_state,verification_state:'unknown',artifact_reference:{sha256:hash,path:filename},error:{code:'OUTPUT_STORED',message:'Full response stored locally'}};line=JSON.stringify(result)} process.stdout.write(line+'\n',onFlushed)}
function err(id,code,message,delivery_state='not_dispatched'){reply(id,{ok:false,delivery_state,verification_state:'unknown',error:{code,message}})}
async function handle(r){
 if(!r || typeof r!=='object' || Array.isArray(r) || r.v!==1 || typeof r.id!=='string' || !r.id || typeof r.run_id!=='string' || !r.run_id || typeof r.session_id!=='string' || !r.session_id || !methods.has(r.method) || !Number.isInteger(r.timeout_ms) || r.timeout_ms<1 || r.timeout_ms>120000 || (r.scope_epoch!==undefined && (!Number.isSafeInteger(r.scope_epoch)||r.scope_epoch<0)) || (r.action_id!==undefined && (typeof r.action_id!=='string'||!r.action_id)) || !r.params || typeof r.params!=='object' || Array.isArray(r.params) || Object.keys(r).some(k=>!['v','id','run_id','session_id','method','timeout_ms','params','scope_epoch','action_id'].includes(k))) return err(r?.id??null,'INVALID_REQUEST','Invalid request envelope');
 if(r.method==='hello'||r.method==='capabilities') { if(active)return err(r.id,'BUSY','Another call is active'); active=true; try { const key=JSON.stringify([r.run_id,r.session_id]); let b=bridges.get(key); if(!b){b=await mod.createBridge({run_id:r.run_id,session_id:r.session_id});bridges.set(key,b)} const schemas=b.schemas??[]; const schema_sha256=crypto.createHash('sha256').update(JSON.stringify(schemas)).digest('hex'); return reply(r.id,{ok:true,capabilities:schemas,schema_sha256,delivery_state:'not_dispatched',verification_state:'unknown'}); } catch(e){return err(r.id,'PROVIDER_ERROR',String(e))} finally {active=false} }
 if(r.method==='status') return reply(r.id,{ok:true,details:{stopped:ledger.stopped,clean_closed:validCleanClose(ledger),scope_closed:(ledger.closed_owners??[]).includes(JSON.stringify([r.run_id,r.session_id])),lease_owned:owner===JSON.stringify([r.run_id,r.session_id]),actions:Object.fromEntries(Object.entries(ledger.actions).filter(([,a])=>a.owner===JSON.stringify([r.run_id,r.session_id])))},delivery_state:'not_dispatched',verification_state:'unknown'});
 if(r.method==='cancel') return err(r.id,'CANCEL_UNCONFIRMED','No active action can be declared safely cancelled');
 if(r.method==='shutdown'){
  const requested=JSON.stringify([r.run_id,r.session_id]);
  if(active)return err(r.id,'SHUTDOWN_IN_FLIGHT','An active call is not confirmed finished');
  if(owner!==null && requested!==owner)return err(r.id,'LEASE_OWNER_MISMATCH','Only the current owner may close the lease');
  let cleanClose=false;
  if(owner!==null && !ledger.stopped && allKnown(ledger)){closeKnownOwner(ledger,owner,{source:'explicit_shutdown'});owner=null;persist();cleanClose=true}
  reply(r.id,{ok:true,details:{clean_close:cleanClose,stopped:ledger.stopped},delivery_state:'not_dispatched',verification_state:'unknown'},()=>process.exit(0));
  process.stdin.pause();return
 }
 if(active) return err(r.id,'BUSY','Another call is active');
 const key=JSON.stringify([r.run_id,r.session_id]);
 if(writes.has(r.method)){
  if(typeof r.action_id!=='string'||!r.action_id) return err(r.id,'ACTION_ID_REQUIRED','An action ID is required');
  const fingerprint=crypto.createHash('sha256').update(JSON.stringify([r.method,r.params,r.scope_epoch??null])).digest('hex'); const old=ledger.actions[r.action_id];if(old){if(old.owner!==key) return err(r.id,'ACTION_OWNER_MISMATCH','Action belongs to another run/session');if(old.fingerprint!==fingerprint) return err(r.id,'ACTION_ID_CONFLICT','Action ID is already associated with different parameters');return reply(r.id,old.response??{ok:false,delivery_state:'delivery_unknown',verification_state:'unknown',error:{code:'DELIVERY_UNKNOWN',message:'Prior action may have been dispatched'}})}
  if(ledger.stopped)return err(r.id,'WRITES_STOPPED','Prior delivery is unknown');
  if((ledger.closed_owners??[]).includes(key))return err(r.id,'OWNER_CLOSED','This run/session scope is closed');
  if(owner===null && needFreshBinding && !freshOwners.has(key))return err(r.id,'FRESH_BINDING_REQUIRED','Obtain a complete current task-window observation for the new owner');
  if(owner!==null&&owner!==key)return err(r.id,'LEASE_HELD','Desktop write lease belongs to another run/session');
  owner=key; ledger.owner=key; ledger.clean_shutdown=null; ledger.actions[r.action_id]={owner:key,fingerprint,state:'dispatching'};persist();
 }
 active=true;let retainActive=false;
 try{
  let bridge=bridges.get(key); if(!bridge){bridge=await mod.createBridge({run_id:r.run_id,session_id:r.session_id});bridges.set(key,bridge)}
  if(typeof bridge.call!=='function') throw Error('Invalid provider bridge');
  let timer; const timeout=new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('TIMEOUT')),r.timeout_ms)});
  let value;try{value=await Promise.race([bridge.call(r.method,r.params,{id:r.id,scope_epoch:r.scope_epoch,timeout_ms:r.timeout_ms}),timeout])}finally{clearTimeout(timer)}
  if(!value || typeof value!=='object' || Array.isArray(value) || (value.content!==undefined && !Array.isArray(value.content)) || (value.details!==undefined && (!value.details || typeof value.details!=='object' || Array.isArray(value.details)))) throw Error('Provider returned invalid response');
  if(r.method==='ax_observe' && value?.isError!==true){const obs=value?.details?.axObservation,n=obs?.native,scope=value?.details?.scope;if(obs?.target==='task' && n?.ok===true && n.command==='snapshot' && n.data?.complete===true && n.data?.window?.id && n.data.window.id===scope?.windowId && n.data.app===scope?.appName && ['window','dialog','alertdialog','sheet','popover'].includes(n.data?.tree?.role))freshOwners.add(key)}
  const stopped=value?.details?.nativeWritesStopped===true || value?.details?.windowKeyboardStopped===true;
  const delivery=(writes.has(r.method)&&['not_dispatched','not_delivered','delivered_unverified','delivery_unknown'].includes(value?.delivery_state))?value.delivery_state:(writes.has(r.method)?'delivery_unknown':'not_dispatched');
  const response={ok:!value?.isError,content:value?.content??[],details:value?.details??{},receipt:value?.receipt??null,delivery_state:delivery,verification_state:value?.verification_state??'unknown'};
  if(writes.has(r.method)){if(stopped||response.delivery_state==='delivery_unknown'){ledger.stopped=true;response.delivery_state='delivery_unknown'}ledger.actions[r.action_id]={owner:key,fingerprint:ledger.actions[r.action_id].fingerprint,state:response.delivery_state,response};persist()}
  reply(r.id,response);
 }catch(e){if(e?.message==='TIMEOUT')retainActive=true;if(writes.has(r.method)){ledger.stopped=true;ledger.actions[r.action_id]={owner:key,fingerprint:ledger.actions[r.action_id].fingerprint,state:'delivery_unknown'};persist();err(r.id,'DELIVERY_UNKNOWN',String(e),'delivery_unknown')}else err(r.id,'PROVIDER_ERROR',String(e));}
 finally{if(!retainActive)active=false}
}
let buffer=Buffer.alloc(0),discard=false;
process.stdin.on('data',chunk=>{for(const byte of chunk){if(discard){if(byte===10){discard=false;err(null,'FRAME_TOO_LARGE','Input exceeds 256 KiB')}continue}if(byte===10){const line=buffer;buffer=Buffer.alloc(0);try{const decoder=new TextDecoder('utf-8',{fatal:true});const obj=JSON.parse(decoder.decode(line));void handle(obj)}catch(e){err(null,'INVALID_JSON',String(e))}}else{buffer=Buffer.concat([buffer,Buffer.from([byte])]);if(buffer.length>MAX_IN){buffer=Buffer.alloc(0);discard=true}}}});
process.stdin.on('end',()=>{if(active){ledger.stopped=true;for(const a of Object.values(ledger.actions))if(a.state==='dispatching')a.state='delivery_unknown';persist()}process.exit(0)});
