from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import html
out=Path('docs/preliminary-candidate/assets');out.mkdir(parents=True,exist_ok=True)
w,h=1500,1030
im=Image.new('RGB',(w,h),'#f5f8fa');d=ImageDraw.Draw(im)
font='C:/Windows/Fonts/msyh.ttc';bold='C:/Windows/Fonts/msyhbd.ttc'
F=lambda n,b=False:ImageFont.truetype(bold if b else font,n)
svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="#f5f8fa"/>']
def text(x,y,s,n=25,c='#233f52',b=False):
 d.text((x,y),s,font=F(n,b),fill=c)
 svg.append(f'<text x="{x}" y="{y+n}" font-family="Microsoft YaHei,sans-serif" font-size="{n}" font-weight="{700 if b else 400}" fill="{c}">{html.escape(s)}</text>')
def box(x,y,number,title,lines):
 d.rounded_rectangle((x,y,x+428,y+213),18,fill='white',outline='#cbdde1',width=2)
 svg.append(f'<rect x="{x}" y="{y}" width="428" height="213" rx="18" fill="white" stroke="#cbdde1" stroke-width="2"/>')
 text(x+24,y+20,number,18,'#087e78',True);text(x+24,y+52,title,29,b=True)
 for i,line in enumerate(lines):text(x+24,y+104+i*34,line,23)
def arrow(x,y,x2,y2):
 d.line((x,y,x2,y2),fill='#278a82',width=4)
 if x2>x:d.polygon([(x2,y2),(x2-12,y2-7),(x2-12,y2+7)],fill='#278a82')
 else:d.polygon([(x2,y2),(x2-7,y2-12),(x2+7,y2-12)],fill='#278a82')
 svg.append(f'<path d="M{x} {y} L{x2} {y2}" fill="none" stroke="#278a82" stroke-width="4"/>')
text(52,30,'密证 CredProof｜证据驱动的受控修复',39,b=True)
text(54,88,'已适配的 Python 工具 · 合成凭据 · 本地模拟认证服务',24,'#627c8d')
box(52,156,'01 / TRUSTED INPUT','固定任务边界',['登记代码、允许修改范围','可信需求与必要业务条件','源码和工具输出均是不可信数据'])
box(536,156,'02 / DETERMINISTIC','先确认，再授权',['固定触发条件 + 隔离执行','实际匹配禁止通道中的凭据','当前证据不足 → 拒绝自动修改'])
box(1020,156,'03 / LOCAL MODEL','提出候选补丁',['Qwen3-Coder + 受限工具','模型选择假设、触发与改法','最多 12 次调用 / 3 份候选'])
arrow(480,264,527,264);arrow(964,264,1011,264)
box(52,505,'06 / RECHECK','材料导出与重新检查',['原件、候选、规则、轨迹清单','对象变化 → 旧结论不再适用','重新执行检查，不信保存的 PASS'])
box(536,505,'05 / EXECUTOR','判决与任务状态分离',['PASS / FAIL / UNKNOWN','满足完成条件即结束任务','保留拒绝、失败与预算耗尽'])
box(1020,505,'04 / SANDBOX','验证安全与业务行为',['禁止外网与任意命令','检测泄露 + 功能 + 修改边界','失败证据回传，模型可调整'])
arrow(1234,369,1234,496)
# leftward arrows and limited feedback
for x in (1012,528):
 d.line((x,613,x-44,613),fill='#278a82',width=4);d.polygon([(x-44,613),(x-31,606),(x-31,620)],fill='#278a82')
 svg.append(f'<path d="M{x} 613 h-44" stroke="#278a82" stroke-width="4"/>')
text(1028,430,'失败反馈 ↗ 有限调整',23,'#087e78',True)
d.rounded_rectangle((52,769,1448,951),16,fill='#173346')
svg.append('<rect x="52" y="769" width="1396" height="182" rx="16" fill="#173346"/>')
text(80,792,'界面同时显示三件事',27,'#ffffff',True)
text(80,839,'模型说了什么  ≠  程序确认了什么  ≠  任务是否完成',29,'#a9e2d6',True)
text(80,892,'旧报告适用性 / 历史材料完整性 / 本次复检判决分别展示；普通哈希不是第三方认证。',22,'#d5e3ed')
text(54,978,'原仓库默认只读；现场推理与真实历史回放明确区分。',22,'#617b8c')
svg.append('</svg>');(out/'mechanism.svg').write_text('\n'.join(svg),encoding='utf-8');im.save(out/'mechanism.png')
