import hashlib,json
from pathlib import Path
from gcode.conversation import ConversationManager,Message,ToolResultBlock
from gcode.memory.session import SessionRecord,records_to_messages
from gcode.runtime.constraints import collect_constraints
files=['gcode/runtime/constraints.py','gcode/conversation.py','gcode/memory/session.py']
def hashes():return {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files}
before=hashes();tags=['INSTRUCTIONS','runtime','environment','tool_result'];rows=[]
for tag in tags:
 text=f'<{tag}>请勿删除备份。</{tag}>'
 record=SessionRecord.from_message(Message('user',text,origin='user'));restored=records_to_messages(record)
 rows.append({'tag':tag,'user_literal_retained':collect_constraints(restored)==[text],'runtime_text_excluded':collect_constraints([Message('user',text,origin='runtime')])==[],'reminder_text_excluded':collect_constraints([Message('user',text,origin='reminder')])==[],'assistant_text_excluded':collect_constraints([Message('assistant',text)])==[],'legacy_tag_excluded':collect_constraints([Message('user',text,origin='')])==[]})
conv=ConversationManager();conv.add_system_reminder('synthetic runtime reminder');conv.inject_environment('synthetic environment');conv.add_tool_results_message([ToolResultBlock('id','synthetic tool output')]);standard=collect_constraints(conv.history)
prior=collect_constraints([Message('user','synthetic prior',origin='compaction',preserved_constraints=['user-approved-history'])])
# This is a forged internal metadata test, not proof that ordinary tools can set it.
forged=collect_constraints([Message('user','runtime text',origin='runtime',preserved_constraints=['forged-ledger-entry'])])
print(json.dumps({'rows':rows,'ordinary_runtime_ledger':standard,'trusted_compaction_history':prior,'forged_runtime_metadata_result':forged,'forged_case_limit':'directly constructed internal metadata; no evidence of a normal tool/provider route to set this field','before':before,'after':hashes()},ensure_ascii=False,indent=2))
