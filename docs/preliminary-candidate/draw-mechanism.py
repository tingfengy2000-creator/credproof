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
text(52,30,'密证 CredProof——面向 AI 工具的凭据泄露验证与受控修复系统',39,b=True)
text(54,88,'本地模型生成候选 · 程序验收安全与业务 · 对应材料导出复检',24,'#627c8d')
box(52,156,'01 / TRUSTED INPUT','固定任务边界',['登记代码、允许修改范围','可信需求与必要业务条件','源码和工具输出均是不可信数据'])
box(536,156,'02 / DETERMINISTIC','先确认，再授权',['固定触发条件 + 隔离执行','实际匹配禁止通道中的凭据','当前证据不足 → 拒绝自动修改'])
box(1020,156,'03 / LOCAL MODEL','证据驱动候选生成',['读取代码与脱敏运行观察','提出假设、触发与候选补丁','最多 12 次调用 / 3 份候选'])
arrow(480,264,527,264);arrow(964,264,1011,264)
box(52,505,'06 / RECHECK','对应材料导出与复检',['原件、候选、规则、轨迹清单','对象变化 → 重新核对与检查','旧报告适用性 / 当前独立判决'])
box(536,505,'05 / EXECUTOR','判决与任务状态分离',['PASS / FAIL / UNKNOWN','满足完成条件即结束任务','保留拒绝、失败与预算耗尽'])
box(1020,505,'04 / SANDBOX','验收安全与业务行为',['隔离运行候选副本','检查泄露、业务与修改边界','失败证据回传，模型可调整'])
arrow(1234,369,1234,496)
# leftward arrows and limited feedback
for x in (1012,528):
 d.line((x,613,x-44,613),fill='#278a82',width=4);d.polygon([(x-44,613),(x-31,606),(x-31,620)],fill='#278a82')
 svg.append(f'<path d="M{x} 613 h-44" stroke="#278a82" stroke-width="4"/>')
# A separate return arrow makes the failure-feedback path explicit.
d.line([(1448,610),(1478,610),(1478,264),(1450,264)],fill='#278a82',width=3)
d.polygon([(1450,264),(1462,257),(1462,271)],fill='#278a82')
svg.append('<path d="M1448 610 H1478 V264 H1450" fill="none" stroke="#278a82" stroke-width="3"/>')
svg.append('<path d="M1450 264 l12 -7 v14 z" fill="#278a82"/>')
text(1040,430,'失败后调整',23,'#087e78',True)
d.rounded_rectangle((52,769,1448,951),16,fill='#173346')
svg.append('<rect x="52" y="769" width="1396" height="182" rx="16" fill="#173346"/>')
text(80,786,'三个作品特点',27,'#ffffff',True)
text(80,826,'证据驱动的候选生成与反馈调整',26,'#a9e2d6',True)
text(80,865,'程序控制的修改权限与安全/业务验收',26,'#a9e2d6',True)
text(80,904,'对应修复对象的材料导出与复检',26,'#a9e2d6',True)
text(54,978,'工作台分别展示模型判断、程序确认与任务状态，保留候选差异和验证回执。',22,'#617b8c')
svg.append('</svg>');(out/'mechanism.svg').write_text('\n'.join(svg),encoding='utf-8');im.save(out/'mechanism.png')
