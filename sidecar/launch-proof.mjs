// Strictly limited to launch preparation. Never classify payload/focus actions.
export function verifyLaunchReceipt(native, code, killed, observation, inventory, app) {
 if(killed!==false || code!==0 || native?.ok!==true || native.command!=='launch' || native.data?.app!==app) return false;
 const d=native.data,w=d.window;
 if(!Number.isSafeInteger(d.pid)||d.pid<=0 || typeof d.process_instance!=='string' || !/^macos-proc-v1:[0-9]+:[0-9]+$/.test(d.process_instance) || !w || w.pid!==d.pid || w.process_instance!==d.process_instance || typeof w.id!=='string' || !/^w-[0-9]+$/.test(w.id))return false;
 const snap=observation?.native;
 if(observation?.target!=='task' || snap?.ok!==true || snap.command!=='snapshot' || snap.data?.complete!==true || snap.data.app!==app || snap.data.window?.id!==w.id) return false;
 if(!inventory || inventory.ok!==true || inventory.command!=='list-windows' || !Array.isArray(inventory.data))return false;
 return inventory.data.some(item=>item.id===w.id && item.pid===d.pid && item.process_instance===d.process_instance && item.app_name===app);
}
