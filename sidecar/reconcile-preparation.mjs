// Offline, explicit operator reconciliation for one proven non-payload launch.
// Run only while no sidecar is active; never delete or rewrite away evidence.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {verifyLaunchReceipt} from './launch-proof.mjs';
const args=process.argv.slice(2), options={};
if(args.length%2)throw Error('Arguments must be --name value pairs');
for(let i=0;i<args.length;i+=2){if(!args[i].startsWith('--')||options[args[i]])throw Error('Invalid or duplicate argument');options[args[i]]=args[i+1]}
const keys=['--machine-dir','--action-id','--params-json','--original-evidence','--original-sha256','--receipt-sha256','--fresh-evidence','--fresh-sha256'];
if(keys.some(k=>!options[k])||Object.keys(options).some(k=>!keys.includes(k)))throw Error('Required: --machine-dir --action-id --params-json --original-evidence --original-sha256 --receipt-sha256 --fresh-evidence --fresh-sha256');
for(const k of ['--machine-dir','--original-evidence','--fresh-evidence'])if(!path.isAbsolute(options[k]))throw Error('All filesystem paths must be absolute');
const dir=options['--machine-dir'],lock=path.join(dir,'writer.lock');
const stat=fs.statSync(dir);if(process.getuid && stat.uid!==process.getuid())throw Error('Machine state owner mismatch');
try{fs.mkdirSync(lock,{mode:0o700})}catch{throw Error('CU_STATE_LOCKED: stop sidecar and verify no process still owns the desktop before reconciliation')}
fs.writeFileSync(path.join(lock,'owner.json'),JSON.stringify({pid:process.pid,started_at:new Date().toISOString(),purpose:'launch-reconciliation'}),{mode:0o600});
try{
 const sha=v=>crypto.createHash('sha256').update(v).digest('hex');
 const readEvidence=(file,hash)=>{const bytes=fs.readFileSync(file);if(!/^[0-9a-f]{64}$/.test(hash)||sha(bytes)!==hash)throw Error('Evidence hash mismatch');return JSON.parse(bytes)};
 const originalMtime=fs.statSync(options['--original-evidence']).mtimeMs, freshMtime=fs.statSync(options['--fresh-evidence']).mtimeMs;
 if(freshMtime<originalMtime || Date.now()-freshMtime>300000 || freshMtime>Date.now()+10000)throw Error('Fresh evidence is stale or predates original');
 const original=readEvidence(options['--original-evidence'],options['--original-sha256']);
 const fresh=readEvidence(options['--fresh-evidence'],options['--fresh-sha256']);
 const ledgerPath=path.join(dir,'ledger.json'),ledger=JSON.parse(fs.readFileSync(ledgerPath,'utf8'));
 const entries=Object.entries(ledger.actions??{}),id=options['--action-id'],entry=ledger.actions?.[id];
 if(ledger.version!==1||ledger.stopped!==true||entries.length!==1||!entry||entry.state!=='delivery_unknown'||entry.owner!==ledger.owner||!entry.response)throw Error('Ledger is not a single unknown launch');
 const params=JSON.parse(options['--params-json']);
 if(!params || Array.isArray(params) || typeof params!=='object' || Object.keys(params).sort().join(',')!=='activate,app,type' || params.type!=='launch' || params.activate!==false || typeof params.app!=='string' || !params.app)throw Error('Only explicit background launch parameters are eligible');
 const fingerprint=sha(JSON.stringify(['ax_action',params,null]));
 if(entry.fingerprint!==fingerprint)throw Error('Action fingerprint mismatch');
 const originalResponse=original?.result?.details;
 const exact={};for(const k of ['ok','content','details','receipt','delivery_state','verification_state'])exact[k]=originalResponse?.[k];
 if(JSON.stringify(exact)!==JSON.stringify(entry.response) || exact.ok!==true || exact.delivery_state!=='delivery_unknown')throw Error('Original receipt differs from ledger');
 const identity=originalResponse?.runtime_identity,observed=fresh?.result?.details;
 const freshIdentity=observed?.runtime_identity;
 for(const k of ['native_sha256','bridge_sha256','manifest_sha256'])if(!identity?.[k]||identity[k]!==freshIdentity?.[k])throw Error('Runtime identity mismatch');
 if(!identity.process_nonce || !freshIdentity.process_nonce || identity.process_nonce===freshIdentity.process_nonce || !identity.process_started_at || !freshIdentity.process_started_at || Date.parse(freshIdentity.process_started_at)<Date.parse(identity.process_started_at) || !Number.isFinite(Date.parse(freshIdentity.process_started_at)))throw Error('Independent post-launch sidecar identity required');
 if(identity.manifest_verified!==true || freshIdentity.manifest_verified!==true)throw Error('Verified frozen manifest required');
 if(observed?.ok!==true || fresh?.result?.is_error!==false || !Array.isArray(observed.receipt) || observed.details?.nativeWritesStopped!==false || observed.details?.windowKeyboardStopped===true)throw Error('Fresh independent read unavailable or bridge stopped');
 if(exact.details?.nativeWritesStopped!==false || exact.details?.windowKeyboardStopped===true)throw Error('Original bridge stopped');
 const block=exact.content?.find(c=>c.type==='text' && /^ORIGINAL NATIVE ACTION RECEIPT/.test(c.text??''));
 const match=block?.text?.match(/^ORIGINAL NATIVE ACTION RECEIPT[^\n]*\n([^\n]+)\n\s*CLI exit=(\d+), killed=(true|false)(?:\n|$)/);
 if(!match)throw Error('Original native receipt is missing or malformed');
 if(!/^[0-9a-f]{64}$/.test(options['--receipt-sha256']) || sha(block.text)!==options['--receipt-sha256'])throw Error('Original native receipt hash mismatch');
 const native=JSON.parse(match[1]);
 const inventories=observed.receipt.filter(r=>r.command==='list-windows'&&r.exit_code===0&&r.killed===false).map(r=>r.native);
 const observation=exact.details.axObservation;
 if(!inventories.some(inv=>verifyLaunchReceipt(native,Number(match[2]),match[3]==='true',observation,inv,params.app)))throw Error('Fresh PID, process identity, app, window or complete observation mismatch');
 const audit={kind:'proven_nonpayload_launch',at:new Date().toISOString(),action_id:id,fingerprint,old_state:'delivery_unknown',new_state:'preparation_reconciled',original_evidence_sha256:options['--original-sha256'],native_receipt_sha256:options['--receipt-sha256'],fresh_evidence_sha256:options['--fresh-sha256'],original_response_sha256:sha(JSON.stringify(entry.response)),native_sha256:identity.native_sha256,bridge_sha256:identity.bridge_sha256,pid:native.data.pid,process_instance:native.data.process_instance,window_id:native.data.window.id};
 entry.state='preparation_reconciled';ledger.stopped=false;ledger.reconciliation=audit;
 const tmp=path.join(dir,`reconcile.${process.pid}.tmp`);fs.writeFileSync(tmp,JSON.stringify(ledger),{mode:0o600,flag:'wx'});const fd=fs.openSync(tmp,'r');fs.fsyncSync(fd);fs.closeSync(fd);fs.renameSync(tmp,ledgerPath);const df=fs.openSync(dir,'r');try{fs.fsyncSync(df)}finally{fs.closeSync(df)}
 process.stdout.write(JSON.stringify({ok:true,classification:'delivered_unverified',verification_state:'unknown',audit})+'\n');
} finally {fs.unlinkSync(path.join(lock,'owner.json'));fs.rmdirSync(lock)}
