import crypto from 'node:crypto';
export const shaJson=value=>crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex');
export function isKnown(ledger,id,entry){
 if(!entry || typeof entry.owner!=='string' || typeof entry.fingerprint!=='string' || !entry.response)return false;
 if(['not_dispatched','not_delivered','delivered_unverified'].includes(entry.state))return entry.response.delivery_state===entry.state;
 const rec=ledger.reconciliation;
 return entry.state==='preparation_reconciled' && rec?.kind==='proven_nonpayload_launch' && rec.action_id===id && rec.fingerprint===entry.fingerprint && entry.response.delivery_state==='delivery_unknown' && rec.original_response_sha256===shaJson(entry.response);
}
export function allKnown(ledger){return Object.entries(ledger.actions??{}).every(([id,e])=>isKnown(ledger,id,e));}
export function validCleanClose(ledger){
 const c=ledger.clean_shutdown,closed=ledger.closed_owners;
 return ledger.stopped===false && ledger.owner===null && Array.isArray(closed) && closed.length>0 && new Set(closed).size===closed.length && c?.version===1 && closed.includes(c.closed_owner) && c.action_count===Object.keys(ledger.actions??{}).length && c.actions_sha256===shaJson(ledger.actions) && allKnown(ledger) && Object.values(ledger.actions).every(e=>closed.includes(e.owner));
}
export function closeKnownOwner(ledger,owner,metadata={}){
 if(ledger.stopped!==false || ledger.owner!==owner || !allKnown(ledger))throw Error('Scope cannot be closed with an unknown, active, stopped or mismatched action');
 const closed=ledger.closed_owners??[];
 if(!Array.isArray(closed) || closed.includes(owner))throw Error('Owner already closed or ledger invalid');
 // Never close if another owner's work has not previously been closed.
 if(Object.values(ledger.actions).some(e=>e.owner!==owner && !closed.includes(e.owner)))throw Error('Another owner is not closed');
 ledger.closed_owners=[...closed,owner];ledger.owner=null;
 ledger.clean_shutdown={version:1,closed_owner:owner,at:new Date().toISOString(),action_count:Object.keys(ledger.actions).length,actions_sha256:shaJson(ledger.actions),...metadata};
 return ledger.clean_shutdown;
}
