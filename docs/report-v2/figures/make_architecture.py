"""Paper-style architecture figure for CredProof (English and Chinese) from one layout.

    python docs/report-v2/figures/make_architecture.py   # writes arch-en.svg / arch-zh.svg

Render to PNG/PDF with Chromium (see README) so fonts match the report.
"""
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
W, H = 1900, 1110
INK, SUB, NAVY = "#1d2733", "#5a6675", "#24406b"
RED, GREEN, AMBER, VIOLET, BROWN = "#b3261e", "#2e7d32", "#9a6200", "#5e48a8", "#8a5a12"
MATH = "'Latin Modern Math', 'Latin Modern Roman', serif"
MATH_CHARS = set("ΦφΔ𝒫∃∀∈⊤⊥∥⊕⟨⟩≻")

L = {
    "en": {
        "font": "Inter, 'Noto Sans CJK SC', sans-serif",
        "zoneA": "Patch Sources", "zoneA_s": "untrusted",
        "llm": "LLM Patch Generator", "llm_l": ["local open-weight model", "isolated process, loopback only", "no repository, no real secrets"],
        "dev": "Developer Revision", "dev_l": ["new version; AI output kept", "same gate, no bypass"],
        "gate": "CredProof Trusted Gate",
        "policy": "Policy 𝒫", "policy_s": "credproof.toml — declared by humans, immutable to the model",
        "policy_l": "entry · mutable scope M · allowed / forbidden dirs · allowed service · credential env · required tests T · scenarios S",
        "iso": "Isolation Boundary", "iso_s": "bubblewrap · read-only rootfs · private network · empty env · rlimits",
        "iso_items": [("Disposable copy", "tool ⊕ Δ, required tests T"),
                      ("Canary credential c", "fresh random secret per run"),
                      ("Access component", "policy-bound read / GET, no redirect"),
                      ("Mock services", "allow (/redirect → deny) · deny")],
        "obs": "Observation Layer", "obs_s": "installed before project code is imported",
        "obs_items": [("O_file", "audit(open) → canonical path → allow / forbid"),
                      ("O_net", "connections + service receipts (path, auth)"),
                      ("O_leak", "c in return · stdout · stderr · log · exception"),
                      ("O_test", "per-case pytest: collected · run · passed · skipped")],
        "ver": "Verdict Engine", "ver_s": "fixed program · 14 predicates over evidence E",
        "phi": [("Φ_safe", "no leak · no forbidden read · no forbidden service"),
                ("Φ_obl", "reads allowed file · authenticates to service"),
                ("Φ_biz", "required tests pass · scenarios as declared")],
        "rules": [("UNKNOWN", "E incomplete: blocked · skipped · not reached", AMBER),
                  ("FAIL", "∃φ ∈ Φ : φ(E) = ⊥", RED),
                  ("PASS", "∀φ ∈ Φ : φ(E) = ⊤", GREEN)],
        "order": "precedence  UNKNOWN ≻ FAIL ≻ PASS",
        "bind": "Evidence Binding", "bind_s": "verdicts and decisions tied to exact bytes",
        "bind_l": ["h = H(tree ∥ 𝒫 ∥ T ∥ component)", "report r applies  iff  r.h = h", "versions  v₀ (AI) → v₁ (developer) → …", "guarded op  ⟨v, h, H(r), |D|⟩ must match"],
        "zoneC": "Human Authority & Delivery",
        "human": "Human Approval", "human_l": ["approve only a current PASS", "cannot override FAIL / UNKNOWN", "append-only decisions"],
        "bundle": "Evidence Bundle", "bundle_l": ["Δ, 𝒫, tests, component, report"],
        "recheck": "Independent Recheck", "recheck_l": ["fresh environment, full re-run", "never trusts a stored verdict"],
        "ci": "Regression Test → CI", "ci_l": ["re-verifies every commit"],
        "pass_only": "PASS only",
        "steps": ["propose Δ", "execute T, S in isolation", "collect evidence E", "verdict V bound to h", "human approval",
                  "export bundle", "independent re-execution", "counterexample feedback"],
        "leg": [("solid", "data flow"), ("feedback", "feedback"), ("iso", "isolation boundary"), ("untrusted", "untrusted")],
    },
    "zh": {
        "font": "'Noto Sans CJK SC', Inter, sans-serif",
        "zoneA": "补丁来源", "zoneA_s": "不可信",
        "llm": "大模型补丁生成", "llm_l": ["本地开源模型", "独立进程，仅本地回环网络", "看不到仓库与真实凭据"],
        "dev": "开发者修订", "dev_l": ["保存为新版本，AI原件保留", "同一闸门，不能绕过"],
        "gate": "CredProof 可信验收闸门",
        "policy": "验收策略 𝒫", "policy_s": "credproof.toml — 由人工声明，模型不可修改",
        "policy_l": "入口 · 可修改范围 M · 允许 / 禁止目录 · 允许服务 · 凭据变量 · 必要测试 T · 场景 S",
        "iso": "隔离边界", "iso_s": "bubblewrap · 只读根文件系统 · 独立网络 · 空环境变量 · 资源上限",
        "iso_items": [("一次性副本", "工具 ⊕ Δ，必要测试 T"),
                      ("诱饵凭据 c", "每次运行随机生成"),
                      ("受控访问组件", "按策略读文件 / GET，不跟随跳转"),
                      ("模拟服务", "允许服务（/redirect → 禁止）· 禁止服务")],
        "obs": "观测层", "obs_s": "在加载项目代码之前安装",
        "obs_items": [("O_file", "审计 open → 解析真实路径 → 允许 / 禁止"),
                      ("O_net", "连接记录 + 服务回执（路径、认证）"),
                      ("O_leak", "c 出现在返回值 · 输出 · 日志 · 异常"),
                      ("O_test", "逐用例 pytest：收集 · 执行 · 通过 · 跳过")],
        "ver": "判定引擎", "ver_s": "固定程序 · 基于证据 E 的 14 项谓词",
        "phi": [("Φ_safe", "不泄密 · 不越界读取 · 不访问禁止服务"),
                ("Φ_obl", "必须读取允许文件 · 必须完成服务认证"),
                ("Φ_biz", "必要测试通过 · 场景符合声明")],
        "rules": [("证据不足", "E 不完整：隔离阻断 · 测试跳过 · 场景未触达", AMBER),
                  ("不通过", "∃φ ∈ Φ : φ(E) = ⊥", RED),
                  ("通过", "∀φ ∈ Φ : φ(E) = ⊤", GREEN)],
        "order": "判定优先级  证据不足 ≻ 不通过 ≻ 通过",
        "bind": "证据绑定", "bind_s": "结论与决定对应确切字节",
        "bind_l": ["h = H(tree ∥ 𝒫 ∥ T ∥ component)", "报告 r 适用  当且仅当  r.h = h", "版本链  v₀（AI）→ v₁（开发者）→ …", "受保护操作  ⟨v, h, H(r), |D|⟩ 必须一致"],
        "zoneC": "人工权限与交付",
        "human": "人工采纳", "human_l": ["只能采纳当前“通过”的版本", "不能推翻“不通过 / 证据不足”", "决定只追加，不覆盖"],
        "bundle": "证据包", "bundle_l": ["Δ、𝒫、测试、组件、报告"],
        "recheck": "独立复检", "recheck_l": ["新环境完整重新执行", "从不读取保存的结论"],
        "ci": "回归测试 → CI", "ci_l": ["每次提交自动重新验收"],
        "pass_only": "仅“通过”",
        "steps": ["提出补丁 Δ", "隔离执行 T、S", "采集证据 E", "结论 V 绑定 h", "人工采纳",
                  "导出证据包", "新环境重新执行", "反例反馈"],
        "leg": [("solid", "数据流"), ("feedback", "反馈"), ("iso", "隔离边界"), ("untrusted", "不可信")],
    },
}


def rich(s):
    """Escape text; set Greek/script/operators in the math font."""
    out, buf, cur = [], "", None
    for ch in s:
        kind = "m" if ch in MATH_CHARS else "t"
        if kind != cur and buf:
            out.append((cur, buf)); buf = ""
        cur, buf = kind, buf + ch
    if buf:
        out.append((cur, buf))
    return "".join(f'<tspan font-family="{MATH}" font-size="1.1em">{escape(b)}</tspan>' if k == "m" else escape(b)
                   for k, b in out)


def symbol(name):
    """O_file → O with subscript; Φ_safe → Φ with subscript, in math italic."""
    base, sub = name.split("_", 1)
    return (f'<tspan font-family="{MATH}" font-style="italic" font-size="1.18em">{escape(base)}</tspan>'
            f'<tspan font-family="{MATH}" font-style="italic" font-size="0.78em" dy="5">{escape(sub)}</tspan>')


def T(x, y, s, size=15, weight=400, fill=INK, anchor="start", italic=False, raw=None, rotate=None):
    extra = ' font-style="italic"' if italic else ""
    if rotate is not None:
        extra += f' transform="rotate({rotate} {x} {y})"'
    body = raw if raw is not None else rich(s)
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{extra}>{body}</text>'


def R(x, y, w, h, stroke=NAVY, fill="#ffffff", dash=None, sw=1.6, r=6):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>'


def B(x, y, n, color=NAVY):
    return (f'<circle cx="{x}" cy="{y}" r="13" fill="{color}" stroke="#ffffff" stroke-width="2"/>'
            f'<text x="{x}" y="{y + 5}" font-size="14" font-weight="700" fill="#ffffff" text-anchor="middle" font-family="Inter, sans-serif">{n}</text>')


def A(points, color="#34495e", dash=None, sw=1.8, head="ah"):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    pts = " ".join(f"{x},{y}" for x, y in points)
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linejoin="round"{d} marker-end="url(#{head})"/>'


def figure(lang):
    t = L[lang]
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{t["font"]}">',
         '<defs>'
         '<marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#34495e"/></marker>'
         f'<marker id="ahr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{RED}"/></marker>'
         '<marker id="ahg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#7f8c99"/></marker>'
         '<pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" stroke="#eceef1" stroke-width="3"/></pattern>'
         '</defs>', f'<rect width="{W}" height="{H}" fill="#ffffff"/>']

    # Column A — untrusted patch sources
    s += [R(30, 190, 300, 580, stroke="#8d949c", fill="url(#hatch)", dash="7 5", sw=1.4, r=10),
          T(50, 224, t["zoneA"], 19, 700), T(50, 248, t["zoneA_s"], 14.5, 400, SUB, italic=(lang == "en")),
          R(50, 274, 260, 190, stroke=VIOLET, sw=1.8), T(68, 308, t["llm"], 17.5, 700)]
    s += [T(68, 342 + i * 30, "· " + x, 14.5, 400, SUB) for i, x in enumerate(t["llm_l"])]
    s += [R(50, 530, 260, 150, stroke=BROWN, sw=1.8), T(68, 564, t["dev"], 17.5, 700)]
    s += [T(68, 598 + i * 30, "· " + x, 14.5, 400, SUB) for i, x in enumerate(t["dev_l"])]

    # Column B — trusted gate
    gx, gw = 390, 1010
    lx, rx, cw = 414, 924, 452          # inner columns
    s += [R(gx, 30, gw, 950, stroke=NAVY, fill="#f3f6fa", sw=2.4, r=12), T(414, 70, t["gate"], 22, 700, NAVY),
          R(414, 90, 962, 104, stroke="#7f93ad"),
          T(434, 122, t["policy"], 18, 700), T(434, 150, t["policy_s"], 13.5, 400, SUB), T(434, 178, t["policy_l"], 14.5)]
    # isolation boundary
    s += [R(lx, 236, cw, 400, stroke=RED, dash="8 5", sw=1.9, r=8),
          T(lx + 20, 268, t["iso"], 18, 700, RED), T(lx + 20, 292, t["iso_s"], 12.5, 400, SUB)]
    for i, (h, b) in enumerate(t["iso_items"]):
        y = 312 + i * 78
        s += [R(lx + 20, y, cw - 40, 64, stroke="#cfd6df", fill="#fbfcfd", sw=1.2, r=5),
              T(lx + 36, y + 26, h, 15, 700), T(lx + 36, y + 50, b, 13.5, 400, SUB)]
    # observation
    s += [R(rx, 236, cw, 400, stroke="#4f739c", sw=1.7, r=8),
          T(rx + 20, 268, t["obs"], 18, 700), T(rx + 20, 292, t["obs_s"], 12.5, 400, SUB)]
    for i, (h, b) in enumerate(t["obs_items"]):
        y = 312 + i * 78
        s += [R(rx + 20, y, cw - 40, 64, stroke="#cfd6df", fill="#fbfcfd", sw=1.2, r=5),
              f'<text x="{rx + 36}" y="{y + 27}" font-size="17" fill="{INK}">{symbol(h)}</text>',
              T(rx + 36, y + 51, b, 13.5, 400, SUB)]
    # verdict engine
    vy = 676
    s += [R(lx, vy, cw, 284, stroke=NAVY, sw=1.9, r=8),
          T(lx + 20, vy + 32, t["ver"], 18, 700, NAVY), T(lx + 20, vy + 56, t["ver_s"], 12.5, 400, SUB)]
    for i, (h, b) in enumerate(t["phi"]):
        y = vy + 90 + i * 32
        s += [f'<text x="{lx + 22}" y="{y}" font-size="17" fill="{INK}">{symbol(h)}</text>', T(lx + 92, y, b, 13.5)]
    s.append(f'<line x1="{lx + 20}" y1="{vy + 176}" x2="{lx + cw - 20}" y2="{vy + 176}" stroke="#d5dbe3"/>')
    pill = 84 if lang == "en" else 74
    for i, (h, b, col) in enumerate(t["rules"]):
        y = vy + 206 + i * 30
        s += [f'<rect x="{lx + 20}" y="{y - 17}" width="{pill}" height="23" rx="11.5" fill="{col}"/>',
              T(lx + 20 + pill / 2, y, h, 12.5, 700, "#ffffff", anchor="middle"), T(lx + 30 + pill, y, b, 14)]
    # evidence binding
    s += [R(rx, vy, cw, 284, stroke="#4f739c", sw=1.7, r=8),
          T(rx + 20, vy + 32, t["bind"], 18, 700), T(rx + 20, vy + 56, t["bind_s"], 12.5, 400, SUB)]
    for i, line in enumerate(t["bind_l"]):
        y = vy + 76 + i * 50
        s += [R(rx + 20, y, cw - 40, 40, stroke="#e1e6ec", fill="#fbfcfd", sw=1, r=5), T(rx + 34, y + 26, line, 14.5)]

    # Column C — human authority and delivery
    cx, cw2 = 1470, 400
    s += [R(cx, 190, cw2, 790, stroke="#a8741a", fill="#fffaf2", sw=1.5, r=10), T(cx + 20, 224, t["zoneC"], 19, 700, "#7a5310")]
    boxes = {"human": (254, 150, "#a8741a"), "bundle": (468, 100, "#4f739c"),
             "recheck": (632, 124, "#4f739c"), "ci": (830, 96, "#4f739c")}
    for key, (y, h, col) in boxes.items():
        s += [R(cx + 20, y, cw2 - 40, h, stroke=col, sw=1.7), T(cx + 38, y + 32, t[key], 17.5, 700)]
        s += [T(cx + 38, y + 62 + i * 27, "· " + x, 14, 400, SUB) for i, x in enumerate(t[key + "_l"])]

    # ---- flows (badges carry step numbers; the key below explains them)
    s += [A([(310, 369), (352, 369), (352, 344), (lx + 20, 344)]), A([(310, 605), (352, 605), (352, 380)]),
          B(352, 470, "1")]
    s += [A([(lx + cw, 436), (rx, 436)]), B((lx + cw + rx) / 2, 436, "2")]
    s += [A([(rx + cw / 2, 636), (rx + cw / 2, 656), (lx + cw / 2, 656), (lx + cw / 2, vy)]), B((lx + rx + cw) / 2, 656, "3")]
    s += [A([(lx + cw, vy + 142), (rx, vy + 142)]), B((lx + cw + rx) / 2, vy + 142, "4")]
    s += [A([(rx + cw, vy + 100), (1428, vy + 100), (1428, 329), (cx + 20, 329)]), B(1428, 560, "5", GREEN),
          (T(1450, 480, t["pass_only"], 13, 700, GREEN, anchor="middle", rotate=-90) if lang == "en" else
           f'<text x="1452" y="440" font-size="14" font-weight="700" fill="{GREEN}" writing-mode="vertical-rl" letter-spacing="2">仅通过</text>')]
    s += [A([(cx + cw2 / 2, 404), (cx + cw2 / 2, 468)]), B(cx + cw2 / 2, 436, "6")]
    s += [A([(cx + cw2 / 2, 568), (cx + cw2 / 2, 632)]), B(cx + cw2 / 2, 600, "7")]
    s += [A([(cx + cw2 - 20, 518), (cx + cw2 - 6, 518), (cx + cw2 - 6, 878), (cx + cw2 - 20, 878)], color="#7f8c99", sw=1.4, head="ahg")]
    s += [A([(cx + 20, 694), (1452, 694), (1452, vy + 240), (rx + cw, vy + 240)], color="#7f8c99", dash="5 4", sw=1.4, head="ahg")]
    s += [A([(644, 194), (644, 236)], color="#7f93ad", sw=1.4, head="ahg"), A([(1150, 194), (1150, 236)], color="#7f93ad", sw=1.4, head="ahg")]
    # counterexample feedback into the untrusted zone
    s += [A([(lx, vy + 236), (180, vy + 236), (180, 770)], color=RED, dash="7 5", sw=1.9, head="ahr"), B(300, vy + 236, "8", RED)]

    # ---- bottom key: legend + numbered steps
    ky = 1012
    s.append(f'<line x1="30" y1="{ky - 18}" x2="{W - 30}" y2="{ky - 18}" stroke="#d5dbe3"/>')
    for i, (kind, label) in enumerate(t["leg"]):
        x = (40, 215, 390, 620)[i]
        if kind == "solid":
            s.append(A([(x, ky + 12), (x + 40, ky + 12)]))
        elif kind == "feedback":
            s.append(A([(x, ky + 12), (x + 40, ky + 12)], color=RED, dash="7 5", head="ahr"))
        elif kind == "iso":
            s.append(R(x, ky + 2, 40, 20, stroke=RED, dash="6 4", sw=1.6, r=3))
        else:
            s.append(R(x, ky + 2, 40, 20, stroke="#8d949c", fill="url(#hatch)", dash="6 4", sw=1.4, r=3))
        s.append(T(x + 50, ky + 17, label, 14))
    sx = 800
    per_row = 4
    colw = (W - 40 - sx) / per_row
    for i, label in enumerate(t["steps"]):
        x = sx + (i % per_row) * colw; y = ky + 12 + (i // per_row) * 40
        s += [B(x + 13, y, str(i + 1), RED if i == 7 else (GREEN if i == 4 else NAVY)), T(x + 34, y + 5, label, 14)]
    s.append("</svg>")
    return "\n".join(s)


if __name__ == "__main__":
    for lang in ("en", "zh"):
        (HERE / f"arch-{lang}.svg").write_text(figure(lang), encoding="utf-8")
    print("written arch-en.svg arch-zh.svg")
