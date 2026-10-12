"""Regenerate the comparison figure section of figures.html from ai-patch-dataset.json."""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
data = json.loads((HERE.parent / "data/ai-patch-dataset.json").read_text(encoding="utf-8"))
rows = data["patches"]

leak = [r for r in rows if r["final"]["credential_leak"]]
green = [r for r in rows if r["at_time"]["business_tests_all_passed"]]
cred_rule = lambda r: any("credential" in x or "secret" in x for x in r["static"]["semgrep"])
bandit_cred = lambda r: any(x not in ("B310", "B108", "PARSE_ERROR") for x in r["static"]["bandit"])
semgrep_false = sum(cred_rule(r) and not r["final"]["credential_leak"] for r in rows)
known_good = 5  # reference fix, unrelated change, dotenv fixed, dotenv unrelated change, developer revision (all recorded PASS)


def panel(title, sub, group, items):
    n = len(group)
    out = [f'<p class="chart-title">{title}</p><p class="chart-sub">{sub}</p><div class="bars">']
    for label, small, hits, hl, extra in items:
        pct = 100 * hits / n
        bar = f'<div class="fill{" hl" if hl else ""}" style="width:{pct:.1f}%"></div>' if hits else '<span class="zero">一份也没发现</span>'
        name = f"<b>{label}</b>" if hl else label
        out.append(f'<div class="bar-label">{name}<small>{small}</small></div><div class="track">{bar}</div>'
                   f'<div class="val">{hits} / {n}{extra}</div>')
    out.append("</div>")
    return "".join(out)


a = panel(f"A　{len(leak)}份实际泄露凭据的AI补丁：各方法发现了几份",
          "凭据泄露由CredProof在运行中实际观测到（返回值、输出、日志或异常中出现本次随机凭据）",
          leak, [
              ("Gitleaks 密钥扫描", "默认规则", sum(bool(r["static"]["gitleaks"]) for r in leak), False, ""),
              ("Bandit 静态分析", "凭据相关规则", sum(bandit_cred(r) for r in leak), False, ""),
              ("Semgrep 静态分析", "凭据写入日志规则", sum(cred_rule(r) for r in leak), False, f'<small class="valnote">另误报{semgrep_false}份</small>'),
              ("业务测试（CI）", "因功能失败而附带拦下", sum(not r["at_time"]["business_tests_all_passed"] for r in leak), False, ""),
              ("CredProof 运行时验收", "14项必要条件", sum(r["final"]["verdict"] != "PASS" for r in leak), True, ""),
          ])
b = panel(f"B　{len(green)}份业务测试全部通过、但实际不合格的AI补丁",
          "这些补丁在常规CI中显示为绿色；不合格原因包括凭据泄露、越界访问、一刀切拒绝和入口崩溃",
          green, [
              ("业务测试（CI）", "pytest全部通过", 0, False, ""),
              ("Gitleaks 密钥扫描", "默认规则", sum(bool(r["static"]["gitleaks"]) for r in green), False, ""),
              ("Semgrep 静态分析", "凭据写入日志规则", sum(cred_rule(r) for r in green), False, ""),
              ("CredProof 运行时验收", "14项必要条件", sum(r["final"]["verdict"] != "PASS" for r in green), True, ""),
          ])
note = (f'<p class="note">已知正确的{known_good}个版本（参考修复、无关修改、python-dotenv修复版及其无关修改、开发者修订版）CredProof全部判定通过，没有误报。'
        f'Bandit的“URL打开”通用提示同样出现在原始漏洞代码上，且补丁改用其他库后即消失，不能说明补丁是否修好，因此不计为凭据相关发现。'
        f'数据：{data["summary"]["ai_patches"]}份唯一AI补丁，静态工具只读源码不运行。</p>')
section = f'<section class="fig" id="comparison">\n{a}<div style="height:34px"></div>{b}\n{note}\n</section>'
html = (HERE / "figures.html").read_text(encoding="utf-8")
html = re.sub(r'<section class="fig" id="comparison">.*?</section>', section, html, flags=re.S)
if ".valnote" not in html:
    html = html.replace("</style>", "  .valnote { display:block; font-size:18px; font-weight:400; color:var(--red); }\n</style>")
(HERE / "figures.html").write_text(html, encoding="utf-8")
print({"leak": len(leak), "green": len(green), "semgrep_false": semgrep_false})
