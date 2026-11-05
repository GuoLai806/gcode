import hashlib,json
from pathlib import Path
from gcode.conversation import Message
from gcode.runtime.constraints import collect_constraints
path=Path('gcode/runtime/constraints.py');before=hashlib.sha256(path.read_bytes()).hexdigest()
prefixes=['本次会话延续自之前的对话，因上下文空间不足进行了压缩。以下是早期对话的摘要：','This session is being continued from a previous conversation that ran out of context.']
rows=[]
for prefix in prefixes:
 text=prefix+'\n请保留备份，不要删除。'
 rows.append({'language':'zh' if prefix.startswith('本次') else 'en','attributed_user_preserved':collect_constraints([Message('user',text,origin='user')])==[text],'legacy_origin_excluded':collect_constraints([Message('user',text,origin='')])==[],'runtime_origin_excluded':collect_constraints([Message('user',text,origin='runtime')])==[]})
print(json.dumps({'rows':rows,'before':before,'after':hashlib.sha256(path.read_bytes()).hexdigest(),'scope':'synthetic messages only; no cloud or GUI'},ensure_ascii=False,indent=2))
