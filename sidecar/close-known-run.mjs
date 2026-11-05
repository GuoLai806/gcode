// Explicit operator-only closure for a previous-version sidecar which exited cleanly.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {allKnown,closeKnownOwner} from './ledger-lifecycle.mjs';
const args=process.argv.slice(2),opts={};
if(args.length%2)throw Error('Arguments must be --name value pairs');
for(let i=0;i<args.length;i+=2){if(!args[i].startsWith('--')||opts[args[i]])throw Error('Invalid arguments');opts[args[i]]=args[i+1]}
const keys=['--machine-dir','--owner-json','--final-evidence','--final-sha256','--exit-evidence','--exit-sha256'];
if(keys.some(k=>!opts[k])||Object.keys(opts).some(k=>!keys.includes(k)))throw Error('Required: --machine-dir --owner-json --final-evidence --final-sha256 --exit-evidence --exit-sha256');
for(const key of ['--machine-dir','--final-evidence','--exit-evidence'])if(!path.isAbsolute(opts[key]))throw Error('Paths must be absolute');
const dir=opts['--machine-dir'],st=fs.statSync(dir);if(process.getuid && st.uid!==process.getuid())throw Error('Machine directory owner mismatch');
const ownerArray=JSON.parse(opts['--owner-json']);if(!Array.isArray(ownerArray)||ownerArray.length!==2||ownerArray.some(v=>typeof v!=='string'||!v))throw Error('Owner must be [run_id, session_id]');
const owner=JSON.stringify(ownerArray),lock=path.join(dir,'writer.lock');
try{fs.mkdirSync(lock,{mode:0o700})}catch{throw Error('CU_STATE_LOCKED: verify prior process exited before closure')}
fs.writeFileSync(path.join(lock,'owner.json'),JSON.stringify({pid:process.pid,started_at:new Date().toISOString(),purpose:'close-known-run'}),{mode:0o600});
try{
 const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
 const read=(file,expected)=>{const b=fs.readFileSync(file);if(!/^[a-f0-9]{64}$/.test(expected)||sha(b)!==expected)throw Error('Evidence hash mismatch');return JSON.parse(b)};
 const final=read(opts['--final-evidence'],opts['--final-sha256']),exit=read(opts['--exit-evidence'],opts['--exit-sha256']);
 const response=final?.response?.details,identity=response?.runtime_identity,obs=response?.details?.axObservation,native=obs?.native,scope=response?.details?.scope;
 if(final?.request?.method!=='ax_observe'||final?.response?.is_error!==false||response?.ok!==true||obs?.target!=='task'||native?.ok!==true||native.command!=='snapshot'||native.data?.complete!==true||!native.data?.window?.id||native.data.window.id!==scope?.windowId||native.data.app!==scope?.appName||!['window','dialog','alertdialog','sheet','popover'].includes(native.data?.tree?.role))throw Error('Final complete task-window evidence required');
 if(response.details?.nativeWritesStopped!==false || response.details?.windowKeyboardStopped===true)throw Error('Original bridge was stopped');
 if(!Number.isSafeInteger(identity?.process_id)||identity.process_id<=0||typeof identity.process_nonce!=='string'||!identity.process_nonce||identity.manifest_verified!==true)throw Error('Final runtime identity missing');
 if(exit?.version!==1||JSON.stringify(exit.owner)!==owner||exit.pid!==identity.process_id||exit.process_nonce!==identity.process_nonce||exit.exit_code!==0||exit.termination!=='clean_shutdown'||exit.final_evidence_sha256!==opts['--final-sha256'])throw Error('Explicit clean process-exit evidence mismatch');
 try{process.kill(identity.process_id,0);throw Error('Prior process still exists')}catch(e){if(e.code!=='ESRCH')throw e}
 const ledgerPath=path.join(dir,'ledger.json'),ledger=JSON.parse(fs.readFileSync(ledgerPath,'utf8'));
 if(ledger.version!==1||ledger.stopped!==false||ledger.owner!==owner||ledger.clean_shutdown||!allKnown(ledger)||!Object.values(ledger.actions??{}).some(e=>e.owner===owner))throw Error('Ledger is not an open known-action scope');
 const audit=closeKnownOwner(ledger,owner,{source:'offline_operator',final_evidence_sha256:opts['--final-sha256'],exit_evidence_sha256:opts['--exit-sha256'],prior_process_id:identity.process_id,prior_process_nonce:identity.process_nonce});
 const tmp=path.join(dir,`close.${process.pid}.tmp`);fs.writeFileSync(tmp,JSON.stringify(ledger),{mode:0o600,flag:'wx'});const fd=fs.openSync(tmp,'r');fs.fsyncSync(fd);fs.closeSync(fd);fs.renameSync(tmp,ledgerPath);const d=fs.openSync(dir,'r');try{fs.fsyncSync(d)}finally{fs.closeSync(d)}
 process.stdout.write(JSON.stringify({ok:true,closed:true,verification_state:'unknown',audit})+'\n');
}finally{fs.unlinkSync(path.join(lock,'owner.json'));fs.rmdirSync(lock)}
