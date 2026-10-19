"""快速截图奖励页游戏卡区域，判定「去玩游戏/立即领取/已领取」状态。"""
import io
import sys

sys.path.insert(0, r'G:\project_X')

from qqreader.device.adb import AdbClient  # noqa: E402
from qqreader.page.recognizer import PageRecognizer  # noqa: E402
from qqreader.page.profiles import DEFAULT_PROFILE  # noqa: E402

cfg_path = r'G:\project_X\configs\qqreader.local.json'
import json

with io.open(cfg_path, encoding='utf-8') as f:
    cfg = json.load(f)

m = cfg['machine']
adb = AdbClient(m['adb_path'], m['adb_address'])
png = adb.screenshot()
print('截图字节:', len(png))

from PIL import Image  # noqa: E402

img = Image.open(io.BytesIO(png))
out = r'G:\project_X\runtime\screenshots\manual_refresh_test.png'
img.save(out)
print('已保存:', out)

rec = PageRecognizer(DEFAULT_PROFILE)
obs = rec.recognize(img)
texts = getattr(obs, 'ocr_texts', None) or []
print('状态:', getattr(obs, 'state', '?'))
keys = ('去玩游戏', '立即领取', '已领取', '明日再来', '今日已获赠币', '回到顶部', '获奖记录', '在线玩')
hits = [t for t in texts if any(k in t for k in keys)]
print('关键命中:')
for h in hits:
    print(' -', h)
