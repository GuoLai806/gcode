// User-local integration adapter: loads an explicitly configured installed bridge.
// No Pi/native implementation or binaries are included or redistributed here.
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';
import {verifyLaunchReceipt} from './launch-proof.mjs';
function required(name){const p=process.env[name];if(!p || !path.isAbsolute(p))throw Error(`${name} must be an explicit absolute path`);return p}
function hash(p){return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')}
export async function identity(){
 const extension=required('GCODE_PI_EXTENSION'),binary=required('PI_AGENT_DESKTOP_BINARY'),sdk=required('GCODE_PI_SDK_PACKAGE');
 const keyboard=process.env.PI_CU_WINDOW_KEYBOARD,manifest=process.env.GCODE_PI_MANIFEST;
 const result={bridge_sha256:hash(extension),native_sha256:hash(binary),keyboard_sha256:keyboard?hash(keyboard):null,sdk_package_sha256:hash(sdk),manifest_verified:false};
 if(manifest){
  if(!path.isAbsolute(manifest))throw Error('GCODE_PI_MANIFEST must be absolute');
  const data=JSON.parse(fs.readFileSync(manifest,'utf8')),base=path.resolve(path.dirname(manifest),'..');
  const entries=[...(data.files??[]).map(x=>({file:path.resolve(base,x.path),expected:x.sha256})),...(data.dependencies??[]).map(x=>({file:x.file,expected:x.sha256}))];
  if(!entries.length)throw Error('Empty bridge manifest');
  const hashes=[];for(const e of entries){if(!e.file || !path.isAbsolute(e.file) || !/^[a-f0-9]{64}$/.test(e.expected??''))throw Error('Invalid manifest entry');const actual=hash(e.file);if(actual!==e.expected)throw Error('Manifest dependency hash mismatch');hashes.push(actual)}
  result.manifest_sha256=hash(manifest);result.manifest_entry_count=hashes.length;result.manifest_entries_sha256=crypto.createHash('sha256').update(JSON.stringify(hashes)).digest('hex');result.manifest_verified=true;
 }
 return result;
}
// Only classify explicit, internally consistent native disposition; never infer task completion.
export function classifyReceipt(result, executions, params){
 const details=result?.details??{};
 if(details.nativeWritesStopped===true || details.windowKeyboardStopped===true) return {delivery_state:'delivery_unknown'};
 const keyboard=details.windowKeyboardReceipt;
 if(keyboard && typeof keyboard==='object') {
  const requested=(params.action??params).type?.replace(/^window-/, '');
  if(result?.isError!==true && keyboard.command==='action' && keyboard.type===requested && keyboard.ok===true && keyboard.exitCode===0 && keyboard.delivery==='delivered_unverified' && keyboard.possibleDelivered===true && Number.isSafeInteger(keyboard.events_posted) && (requested==='focus'?keyboard.events_posted===0 && keyboard.focus_confirmed===true:keyboard.events_posted>=2))
   return {delivery_state:'delivered_unverified', receipt:keyboard};
  if(keyboard.command==='action' && keyboard.type===requested && keyboard.ok===false && keyboard.exitCode===1 && keyboard.possibleDelivered===false)
   return {delivery_state:'not_delivered', receipt:keyboard};
  return {delivery_state:'delivery_unknown', receipt:keyboard};
 }
 const action=params.action??params;
 if(action.type==='launch' && typeof action.app==='string' && action.activate===false) {
  const launches=executions.filter(e=>e.command==='launch');
  const otherWrites=executions.filter(e=>e.mutating && e.command!=='launch');
  const inventories=executions.filter(e=>e.command==='list-windows' && e.result.code===0 && e.result.killed===false);
  if(launches.length===1 && otherWrites.length===0){
   const e=launches[0];let native;try{native=JSON.parse(e.result.stdout)}catch{}
   for(const i of inventories){let inventory;try{inventory=JSON.parse(i.result.stdout)}catch{}
    if(verifyLaunchReceipt(native,e.result.code,e.result.killed,details.axObservation,inventory,action.app))
     return {delivery_state:'delivered_unverified',receipt:{command:'launch',exit_code:e.result.code,killed:e.result.killed,native},verification_state:'unknown'};
   }
  }
 }
 const entries=executions.filter(e=>e.mutating);
 if(entries.length!==1)return {delivery_state:'delivery_unknown'};
 const e=entries[0];let native;try{native=JSON.parse(e.result.stdout)}catch{return {delivery_state:'delivery_unknown'}}
 const receipt={command:e.command, exit_code:e.result.code, killed:e.result.killed, native};
 if(e.result.killed!==false || !Number.isInteger(e.result.code) || e.result.code<0 || native?.command!==e.command) return {delivery_state:'delivery_unknown',receipt};
 const disposition=native?.data?.disposition;
 if(native?.data?.action===e.command && disposition?.delivery==='delivered_unverified' && disposition.retry==='unsafe') return {delivery_state:'delivered_unverified',receipt};
 const error=native?.error?.disposition;
 if(native?.ok===false && error?.delivery==='not_delivered' && error.retry==='safe')return {delivery_state:'not_delivered',receipt};
 return {delivery_state:'delivery_unknown',receipt};
}
// An omitted isError is not evidence of a successful native read.
export function classifyRead(result, executions){
 const receipts=executions.map(e=>{let native=null;try{native=JSON.parse(e.result.stdout)}catch{}return {command:e.command,exit_code:e.result.code,killed:e.result.killed,native}});
 if(result?.isError===true)return {isError:true,receipt:receipts,read_outcome:'native_error'};
 if(!receipts.length){const d=result?.details;const cached=d?.nativeDecisionSurfaceCurrent===true && d?.originalCli===false && d?.decisionSurface && typeof d.decisionSurface==='object';return {isError:!cached,receipt:[],read_outcome:cached?'current_surface_reused':'unconfirmed'};}
 const successful=receipts.every(r=>r.killed===false && r.exit_code===0 && r.native?.ok===true && r.native.command===r.command);
 return {isError:!successful,receipt:receipts,read_outcome:successful?'native_read_succeeded':'native_error_or_unconfirmed'};
}
export async function createBridge(){
 const extension=required('GCODE_PI_EXTENSION'), sdk=required('GCODE_PI_SDK_PACKAGE');
 const require=createRequire(sdk);const {createJiti}=require('jiti');const value=require('typebox/value');
 const entry=(name)=>{const pkg=(name==='@earendil-works/pi-coding-agent'?sdk:require.resolve.paths(name).map(base=>path.join(base,name,'package.json')).find(fs.existsSync));if(!pkg)throw Error('Installed SDK package not found: '+name);const meta=JSON.parse(fs.readFileSync(pkg,'utf8'));return path.resolve(path.dirname(pkg),meta.exports?.['.']?.import??meta.main)};
 const alias={'@earendil-works/pi-ai':entry('@earendil-works/pi-ai'),'@earendil-works/pi-coding-agent':entry('@earendil-works/pi-coding-agent')};
 const module=await createJiti(import.meta.url,{moduleCache:true,alias}).import(extension);
 const tools=new Map();const binary=required('PI_AGENT_DESKTOP_BINARY');
 let executions=[];
 const pi={registerTool(t){if(['ax_observe','ax_query','ax_action'].includes(t.name))tools.set(t.name,t)},on(){},registerToolRenderer(){},getActiveTools(){return [...tools.keys()]},
  exec(command,args,options={}){if(command!==binary)throw Error('Provider exec denied');return new Promise((resolve,reject)=>{const child=spawn(command,args,{stdio:['ignore','pipe','pipe'],signal:options.signal});let stdout='',stderr='';child.stdout.on('data',b=>stdout+=b);child.stderr.on('data',b=>stderr+=b);const timer=setTimeout(()=>child.kill(),options.timeout??30000);child.on('error',reject);child.on('close',(code,signal)=>{clearTimeout(timer);const result={stdout,stderr,code:code??-1,killed:signal!==null};const command=args[0]==='--session'?args[2]:args[0];executions.push({command,mutating:!['snapshot','get','query','list-windows'].includes(command),result});resolve(result)})})}};
 (module.default??module)(pi);
 if(!['ax_observe','ax_query','ax_action'].every(k=>tools.has(k)))throw Error('Required Pi desktop tools missing');
 const schemas=[...tools.values()].map(t=>({name:t.name,description:t.description,input_schema:t.parameters}));
 return {schemas,async call(method,params,{id}){const t=tools.get(method);if(!t)throw Error('Unsupported provider method');if(!value.Check(t.parameters,params))throw Error('Parameter schema mismatch; no dispatch');executions=[];const result=await t.execute(id,params,undefined);if(method!=='ax_action')return {...result,...classifyRead(result,executions)};const classified=classifyReceipt(result,executions,params);return {...result,...classified,isError:result?.isError===true || classified.receipt?.native?.ok===false,verification_state:'unknown'}}};
}
