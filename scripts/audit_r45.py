"""审计 r45 records JSON：全阶段序列、recovery、截图清单。"""
from __future__ import annotations

import json
from pathlib import Path

p = Path(r'G:\project_X\runtime\records\DailyGameFlow_19700104_004229_203000.json')
rec = json.loads(p.read_text(encoding='utf-8'))

print('=== 顶层字段 ===')
for k in ('outcome', 'steps', 'final_state', 'duration_seconds'):
    print(f'{k}: {rec.get(k)}')

print('\n=== 证据截图 ===')
shots = rec.get('screenshots', [])
print(f'共 {len(shots)} 张:')
for s in shots:
    if isinstance(s, dict):
        print('  -', s.get('kind'), '|', (s.get('path') or '').split('\\')[-1])

print('\n=== 恢复历史 ===')
for r in rec.get('recovery_history', []):
    if isinstance(r, dict):
        print('  -', r.get('action'), '|', str(r.get('reason'))[:50])

print('\n=== 步骤中的关键节点 ===')
steps = rec.get('steps') or []
print(f'steps 字段类型: {type(steps).__name__}, 长度: {len(steps) if hasattr(steps, "__len__") else "?"}')
if isinstance(steps, list):
    for i, s in enumerate(steps):
        if isinstance(s, dict):
            desc = str(s.get('description') or s.get('note') or '')
            state = str(s.get('state') or '')
            if any(k in desc + state for k in ('GAME_', 'REWARD_', '确定', '勾选', '换卡', 'success', '进入', '退出')):
                print(f'  [{i}] state={state[:18]} desc={desc[:60]}')
        if i > 400:
            break
