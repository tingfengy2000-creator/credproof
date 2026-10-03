"""Encode actual CUA browser frames; captions never replace screen content.

Dependencies: Pillow 11.3.0, imageio-ffmpeg 0.6.0 (a separate video-tools venv).
The frame folder is capture output, not synthetic screenshots. This script does
not operate the browser, run a model or manufacture an acceptance result.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

STEPS = [
 ('01-introduction',16,'凭据不写在代码里，也可能在运行时进入日志或异常输出。','本地模型提出候选，程序授权修改并检查安全与业务行为。'),
 ('02-three-stories',16,'三个精选历史案例：有限修复增量、真实反馈调整、正常保留。','它们来自同一历史批次；回放不代表本次新推理。'),
 ('03-h01-increment',24,'h01：凭据经函数参数进入日志；模型保留认证实参并改变日志值。','仅说明本例补足了项目固定启发式的盲点，不代表全面优于固定流程。'),
 ('04-h03-rejected',30,'h03 第一候选：只加 [REDACTED] 前缀，真实凭据值仍然存在。','程序给出两项日志泄露反例；模型说已经脱敏，不等于验收通过。'),
 ('05-h03-corrected',24,'h03 第二候选：改为固定安全摘要，安全与业务条件随后通过。','这是实际失败回执后的调整；同例固定流程也直接通过。'),
 ('06-h07-unchanged',18,'h07：合法认证和正确脱敏没有形成泄露依据，原代码保持不变。','程序确认、模型疑点、补丁验收和任务完成分别记录。'),
 ('07a-recheck-click',10,'现在点击重新验收：读取当前材料，在既有隔离环境执行检查。','这是新的固定程序执行，不调用大模型，也不复用旧 PASS 作判决。'),
 ('07b-recheck-result',32,'新复检返回 PASS：对象摘要、检查时间及历史材料完整性可以核对。','旧报告适用性、材料完整性与新验收结果分开；证据包可导出复检。'),
 ('08-close',10,'三种入口：查看作品、重新验收、现场修复。各自依赖清楚区分。','历史完整批次：C 合格修复 4/4、完整任务 6/8；外部 Twine 场景单列。'),
]
SHORT=[('01-introduction',0,6),('03-h01-increment',2,8),('04-h03-rejected',2,10),
       ('05-h03-corrected',2,8),('06-h07-unchanged',2,8),('07a-recheck-click',0,10),('07b-recheck-result',2,10)]


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('frames',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    rows=json.loads((a.frames/'capture.json').read_text('utf-8'));groups=defaultdict(list)
    for row in rows:
        file=a.frames/row['file']
        assert digest(file)==row['sha256'], 'Captured frame changed'
        groups[row['segment']].append(row)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',25)
    small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',21)
    prepared={}
    def frame(row,key):
        cache=(row['file'],key)
        if cache in prepared:return prepared[cache]
        title=next(s for s in STEPS if s[0]==key)
        canvas=Image.new('RGB',(1600,900),'#080f1d');d=ImageDraw.Draw(canvas)
        label='现场重新验收 · 无模型' if key.startswith('07') else '真实历史回放 REPLAY / 作品展示'
        d.text((28,12),'密证 CredProof',font=font,fill='#bdebe8')
        d.text((660,16),label+'  |  实录剪辑 · 字幕版',font=small,fill='#b9bfd5')
        src=Image.open(a.frames/row['file']).convert('RGB');src.thumbnail((1600,780),Image.Resampling.LANCZOS)
        canvas.paste(src,((1600-src.width)//2,52))
        d.text((28,836),title[2],font=font,fill='#e4edf9')
        d.text((28,869),title[3],font=small,fill='#aebbd0')
        b=canvas.tobytes();prepared[cache]=b
        # Keep memory bounded while encoding duplicate display frames.
        if len(prepared)>24:prepared.pop(next(iter(prepared)))
        return b
    receipts=[]
    for name,segments in [('credproof-demo-3min.mp4',[(s[0],0,s[1]) for s in STEPS]),('credproof-demo-1min.mp4',SHORT)]:
        target=a.output/name
        if target.exists():raise ValueError('Do not overwrite a recorded video')
        command=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','warning','-f','rawvideo','-pix_fmt','rgb24','-s','1600x900','-r','10','-i','-','-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(target)]
        proc=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        for key,offset,duration in segments:
            frames=groups[key]
            for n in range(duration*10):
                t=(offset+n/10)*1000
                selected=min(frames,key=lambda x:abs(x['relative_ms']-t))
                proc.stdin.write(frame(selected,key))
        proc.stdin.close();errors=proc.stderr.read().decode('utf-8','replace');rc=proc.wait()
        if rc:raise RuntimeError(errors)
        receipts.append({'file':name,'bytes':target.stat().st_size,'sha256':digest(target),'duration_s':sum(x[2] for x in segments),'fps':10,'resolution':[1600,900],'segments':segments,'command':command,'exit_code':rc,'stderr':errors})
    result={'capture_kind':'actual CUA browser PNG frame sequence around 2 fps, edited into captioned video; not continuous desktop/audio capture','source_commit':'1d697a16fcba2ad393e5755abec5a61c1724089c','same_source_for_both_edits':True,'source_frames':len(rows),'capture_manifest_sha256':digest(a.frames/'capture.json'),'source_frames_retained_locally':True,'audio':'none; subtitles only','time_policy':'inter-segment setup gaps omitted; inference is historical replay; the recheck click and response are new actual execution without acceleration','outputs':receipts}
    (a.output/'video-receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(receipts,ensure_ascii=False))


if __name__=='__main__':main()
