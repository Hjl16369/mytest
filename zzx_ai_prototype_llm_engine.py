"""
AI 需求分析 & 原型生成引擎
=========================================
依赖：pip install requests
运行：python ai_demand_to_prototype_engine_python.py
      → 自动打开浏览器 http://localhost:18888
"""

import json, re, os, sys, threading, webbrowser, time, uuid, html as _html
import requests
from datetime import datetime
from typing import Dict, Any, List
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# ══════════════════════════════════════════════════════
# 配置
# ══════════════════════════════════════════════════════
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "sk-c4bbfc49d1a84880ae3241dff77a9e8f")
DASHSCOPE_URL     = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL             = "qwen-plus"
PORT              = 18888

# 全局任务状态存储  {task_id: {status, log, result, raw_input}}
_tasks: Dict[str, Dict] = {}
_tasks_lock = threading.Lock()

# ══════════════════════════════════════════════════════
# LLM 调用
# ══════════════════════════════════════════════════════

def call_llm(prompt: str, system: str = "", max_tokens: int = 2000) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        r = requests.post(
            DASHSCOPE_URL,
            headers={"Authorization": f"Bearer {DASHSCOPE_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": MODEL, "messages": messages,
                  "max_tokens": max_tokens, "temperature": 0.3},
            timeout=90
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {e}"


def call_llm_json(prompt: str, system: str = "") -> Any:
    sys_full = (system or "") + "\n\n【重要】只输出合法 JSON，不加任何说明，不使用 Markdown 代码块。"
    raw = call_llm(prompt, sys_full.strip())
    clean = re.sub(r'^```(?:json)?\s*', '', raw.strip())
    clean = re.sub(r'\s*```$', '', clean.strip())
    try:
        return json.loads(clean)
    except Exception:
        m = re.search(r'(\{.*\}|\[.*\])', clean, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return {"error": "JSON解析失败", "raw": raw[:400]}

# ══════════════════════════════════════════════════════
# Prompt 模板
# ══════════════════════════════════════════════════════

def prompt_semantic_clean(raw_text: str) -> str:
    return f"""你是一名资深企业软件产品经理，请对以下客户沟通内容进行语义增强整理。

输入:
{raw_text}

输出JSON数组，每项包含：角色(role)、内容(content)、标签(tags，字符串数组)。"""


def prompt_structured_extraction(cleaned_json: str) -> str:
    return f"""请提取系统需求，输出JSON对象。

输入:
{cleaned_json}

必须包含以下字段（值可为字符串或数组）：
业务目标、用户角色、核心场景、功能模块、业务流程、数据对象、权限角色、关键指标、约束条件、优先级判断"""


def prompt_prototype(structured_json: str) -> str:
    return f"""请生成系统原型JSON。

输入:
{structured_json}

输出JSON对象，包含：
- pages: 数组，每项含 name(字符串) 和 components(字符串数组)
- flows: 字符串数组，描述主业务流程步骤"""


def prompt_questions(structured_json: str) -> str:
    return f"""请针对以下需求提出10个关键澄清问题。

输入:
{structured_json}

输出JSON数组，每项包含 id(数字) 和 question(字符串) 字段。"""

# ══════════════════════════════════════════════════════
# 引擎核心
# ══════════════════════════════════════════════════════

class AIPrototypeEngine:

    def run_pipeline(self, raw_text: str, task_id: str = None) -> Dict:

        def log(msg):
            if task_id:
                with _tasks_lock:
                    _tasks[task_id]["log"].append(msg)
            print(msg)

        log("⏳ [1/4] 语义整理中，请稍候...")
        cleaned = call_llm_json(prompt_semantic_clean(raw_text))
        log("✅ [1/4] 语义整理完成")

        log("⏳ [2/4] 提取结构化需求中...")
        requirements = call_llm_json(prompt_structured_extraction(
            json.dumps(cleaned, ensure_ascii=False)))
        log("✅ [2/4] 结构化需求提取完成")

        log("⏳ [3/4] 生成系统原型中...")
        prototype = call_llm_json(prompt_prototype(
            json.dumps(requirements, ensure_ascii=False)))
        log("✅ [3/4] 系统原型生成完成")

        log("⏳ [4/4] 生成澄清问题中...")
        questions = call_llm_json(prompt_questions(
            json.dumps(requirements, ensure_ascii=False)))
        log("✅ [4/4] 澄清问题生成完成")
        log("🎉 分析完成！正在生成报告...")

        return {
            "cleaned":      cleaned,
            "requirements": requirements,
            "prototype":    prototype,
            "questions":    questions
        }

# ══════════════════════════════════════════════════════
# HTML 报告渲染
# ══════════════════════════════════════════════════════

def _e(text: str) -> str:
    """HTML 转义"""
    return _html.escape(str(text))


def _render_value(val: Any) -> str:
    if isinstance(val, dict):
        rows = "".join(
            f'<tr><td class="key-cell">{_e(k)}</td>'
            f'<td>{_render_value(v)}</td></tr>'
            for k, v in val.items()
        )
        return f'<table class="inner-table">{rows}</table>'
    elif isinstance(val, list):
        if not val:
            return '<span class="empty">（空）</span>'
        items = "".join(f'<li>{_render_value(i)}</li>' for i in val)
        return f'<ul class="inner-list">{items}</ul>'
    return f'<span class="value-text">{_e(str(val))}</span>'


def generate_html_report(result: Dict, raw_input: str = "") -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── 语义整理 ──
    cleaned = result.get("cleaned", [])
    if isinstance(cleaned, list) and cleaned:
        cleaned_html = ""
        role_colors = {
            "产品经理":"accent","PM":"accent","pm":"accent",
            "客户":"accent2","顾客":"accent2","用户":"accent2",
            "销售":"accent3","业务":"accent3",
        }
        for item in cleaned:
            if not isinstance(item, dict):
                continue
            role    = _e(item.get("role", "—"))
            content = _e(item.get("content", ""))
            tags    = item.get("tags", [])
            color   = role_colors.get(item.get("role",""), "accent4")
            tag_html = "".join(f'<span class="tag">{_e(t)}</span>'
                               for t in (tags if isinstance(tags, list) else [str(tags)]))
            cleaned_html += f"""<div class="dialogue-item clr-{color}">
  <div class="role-badge">{role}</div>
  <div class="dialogue-body">
    <p class="dialogue-content">{content}</p>
    <div class="tag-row">{tag_html}</div>
  </div>
</div>"""
    else:
        cleaned_html = f'<pre class="raw-pre">{_e(json.dumps(cleaned, ensure_ascii=False, indent=2))}</pre>'

    # ── 结构化需求 ──
    requirements = result.get("requirements", {})
    ICONS = {"业务目标":"🎯","用户角色":"👥","核心场景":"🎬","功能模块":"🧩",
             "业务流程":"🔄","数据对象":"🗄️","权限角色":"🔐","关键指标":"📊",
             "约束条件":"⚠️","优先级判断":"📌"}
    req_html = ""
    if isinstance(requirements, dict):
        for key, val in requirements.items():
            icon = ICONS.get(key, "▪️")
            req_html += f"""<div class="req-card">
  <div class="req-title"><span>{icon}</span>{_e(key)}</div>
  <div class="req-body">{_render_value(val)}</div>
</div>"""
    else:
        req_html = f'<pre class="raw-pre">{_e(json.dumps(requirements, ensure_ascii=False, indent=2))}</pre>'

    # ── 原型 ──
    prototype = result.get("prototype", {})
    pages = prototype.get("pages", []) if isinstance(prototype, dict) else []
    flows = prototype.get("flows", []) if isinstance(prototype, dict) else []

    pages_html = ""
    for pg in (pages if isinstance(pages, list) else []):
        name  = _e(pg.get("name","页面") if isinstance(pg,dict) else str(pg))
        comps = pg.get("components",[]) if isinstance(pg,dict) else []
        chips = "".join(f'<span class="comp-chip">{_e(c if isinstance(c,str) else json.dumps(c,ensure_ascii=False))}</span>'
                        for c in (comps if isinstance(comps,list) else [comps]))
        pages_html += f"""<div class="page-card">
  <div class="page-name">📄 {name}</div>
  <div class="comp-row">{chips or '<span class="empty">无组件</span>'}</div>
</div>"""

    flows_html = ""
    for idx, step in enumerate(flows if isinstance(flows,list) else [], 1):
        label = _e(step if isinstance(step,str) else json.dumps(step,ensure_ascii=False))
        flows_html += f'<div class="flow-step"><span class="step-num">{idx}</span><span class="step-label">{label}</span></div>'

    # ── 澄清问题 ──
    q_list = result.get("questions", [])
    if not isinstance(q_list, list):
        q_list = []
    q_html = ""
    for item in q_list:
        qid  = _e(str(item.get("id","?")))  if isinstance(item,dict) else "?"
        qtxt = _e(item.get("question",str(item))) if isinstance(item,dict) else _e(str(item))
        q_html += f"""<div class="q-item">
  <span class="q-num">Q{qid}</span>
  <span class="q-text">{qtxt}</span>
</div>"""

    raw_json = json.dumps(result, ensure_ascii=False, indent=2)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 需求分析报告</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{{
  --bg:#0d1117;--surf:#161b22;--surf2:#1c2230;--bdr:#30363d;
  --accent:#58a6ff;--accent2:#3fb950;--accent3:#d2a8ff;--accent4:#ffa657;
  --tx:#e6edf3;--txm:#8b949e;--r:12px;
  --font:'Noto Sans SC',sans-serif;--mono:'JetBrains Mono',monospace;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font-family:var(--font);font-size:14px;line-height:1.7;min-height:100vh}}

/* header */
.hdr{{background:linear-gradient(135deg,#0d1117,#161b22,#1a2332);border-bottom:1px solid var(--bdr);padding:36px 48px 28px;position:relative;overflow:hidden}}
.hdr::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 60% 80% at 80% 50%,rgba(88,166,255,.08),transparent 70%);pointer-events:none}}
.hdr-row{{display:flex;align-items:center;gap:14px;margin-bottom:6px}}
.logo{{width:42px;height:42px;background:linear-gradient(135deg,var(--accent),var(--accent3));border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0}}
.hdr h1{{font-size:24px;font-weight:700;background:linear-gradient(90deg,var(--accent),var(--accent3));-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.badge{{background:rgba(88,166,255,.15);border:1px solid rgba(88,166,255,.3);color:var(--accent);border-radius:20px;padding:2px 12px;font-size:11px;font-family:var(--mono)}}
.hdr-meta{{color:var(--txm);font-size:12px;margin-top:4px}}
.dl-btn{{margin-left:auto;background:rgba(63,185,80,.15);border:1px solid rgba(63,185,80,.4);color:var(--accent2);border-radius:8px;padding:8px 20px;font-family:var(--font);font-size:13px;font-weight:500;cursor:pointer;text-decoration:none;display:flex;align-items:center;gap:6px;transition:background .2s}}
.dl-btn:hover{{background:rgba(63,185,80,.25)}}

/* nav */
.nav{{display:flex;gap:2px;padding:0 48px;background:var(--surf);border-bottom:1px solid var(--bdr);position:sticky;top:0;z-index:100;overflow-x:auto}}
.nav-btn{{padding:13px 20px;background:none;border:none;color:var(--txm);font-family:var(--font);font-size:13px;font-weight:500;cursor:pointer;border-bottom:2px solid transparent;transition:all .2s;white-space:nowrap}}
.nav-btn:hover{{color:var(--tx)}}
.nav-btn.active{{color:var(--accent);border-bottom-color:var(--accent)}}

/* sections */
.main{{padding:32px 48px;max-width:1200px;margin:0 auto}}
.sec{{display:none;animation:fi .3s ease}}
.sec.active{{display:block}}
@keyframes fi{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
.sec-title{{font-size:17px;font-weight:700;margin-bottom:22px;padding-bottom:11px;border-bottom:1px solid var(--bdr);display:flex;align-items:center;gap:10px}}
.dot{{width:8px;height:8px;border-radius:50%;background:var(--accent);box-shadow:0 0 8px var(--accent)}}

/* dialogue */
.dialogue-item{{display:flex;gap:12px;padding:13px 16px;background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);margin-bottom:9px;transition:border-color .2s}}
.dialogue-item:hover{{border-color:rgba(88,166,255,.35)}}
.clr-accent  .role-badge{{background:rgba(88,166,255,.15);border:1px solid rgba(88,166,255,.3);color:var(--accent)}}
.clr-accent2 .role-badge{{background:rgba(63,185,80,.15);border:1px solid rgba(63,185,80,.3);color:var(--accent2)}}
.clr-accent3 .role-badge{{background:rgba(210,168,255,.15);border:1px solid rgba(210,168,255,.3);color:var(--accent3)}}
.clr-accent4 .role-badge{{background:rgba(255,166,87,.15);border:1px solid rgba(255,166,87,.3);color:var(--accent4)}}
.role-badge{{flex-shrink:0;padding:3px 11px;border-radius:20px;font-size:11px;font-weight:600;height:fit-content;margin-top:3px;background:rgba(255,166,87,.15);border:1px solid rgba(255,166,87,.3);color:var(--accent4)}}
.dialogue-content{{color:var(--tx);margin-bottom:5px}}
.tag-row{{display:flex;flex-wrap:wrap;gap:5px}}
.tag{{background:rgba(88,166,255,.1);border:1px solid rgba(88,166,255,.2);color:var(--accent);border-radius:4px;padding:1px 7px;font-size:11px;font-family:var(--mono)}}

/* req grid */
.req-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}}
.req-card{{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);padding:16px 18px;transition:border-color .2s,transform .2s}}
.req-card:hover{{border-color:rgba(88,166,255,.4);transform:translateY(-2px)}}
.req-title{{font-weight:600;font-size:13px;margin-bottom:10px;display:flex;align-items:center;gap:7px}}
.req-body{{color:var(--txm);font-size:13px}}
.inner-table{{width:100%;border-collapse:collapse}}
.inner-table tr:not(:last-child) td{{border-bottom:1px solid var(--bdr)}}
.inner-table td{{padding:4px 0;vertical-align:top}}
.key-cell{{color:var(--txm);width:100px;font-size:12px;padding-right:8px}}
.inner-list{{padding-left:15px}}
.inner-list li{{margin-bottom:2px}}
.value-text{{color:var(--tx)}}
.empty{{color:var(--txm);font-style:italic}}

/* prototype */
.proto-sec{{margin-bottom:32px}}
.proto-sub{{font-size:15px;font-weight:600;margin-bottom:14px;color:var(--accent3)}}
.pages-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}}
.page-card{{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);padding:14px 16px;transition:border-color .2s}}
.page-card:hover{{border-color:rgba(210,168,255,.45)}}
.page-name{{font-weight:600;margin-bottom:9px;color:var(--accent3);font-size:13px}}
.comp-row{{display:flex;flex-wrap:wrap;gap:5px}}
.comp-chip{{background:var(--surf2);border:1px solid var(--bdr);border-radius:5px;padding:2px 9px;font-size:12px;color:var(--txm)}}
.flow-track{{display:flex;flex-wrap:wrap;align-items:center}}
.flow-step{{display:flex;align-items:center;gap:8px;background:var(--surf);border:1px solid var(--bdr);border-radius:8px;padding:9px 14px;margin:5px 0;transition:border-color .2s}}
.flow-step:hover{{border-color:rgba(63,185,80,.45)}}
.flow-step:not(:last-child)::after{{content:'→';color:var(--txm);margin:0 6px;font-size:15px}}
.step-num{{width:22px;height:22px;background:linear-gradient(135deg,var(--accent2),#2ea043);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#fff;flex-shrink:0}}
.step-label{{font-size:13px}}

/* questions */
.q-item{{display:flex;align-items:flex-start;gap:12px;padding:13px 16px;background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);margin-bottom:9px;transition:border-color .2s}}
.q-item:hover{{border-color:rgba(255,166,87,.4)}}
.q-num{{flex-shrink:0;background:rgba(255,166,87,.15);border:1px solid rgba(255,166,87,.3);color:var(--accent4);border-radius:5px;padding:2px 9px;font-size:12px;font-family:var(--mono);font-weight:600}}

/* raw json */
.raw-box{{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);overflow:hidden}}
.raw-toolbar{{display:flex;align-items:center;justify-content:space-between;padding:9px 16px;background:var(--surf2);border-bottom:1px solid var(--bdr)}}
.raw-label{{font-family:var(--mono);font-size:11px;color:var(--txm)}}
.copy-btn{{background:rgba(88,166,255,.1);border:1px solid rgba(88,166,255,.3);color:var(--accent);border-radius:5px;padding:3px 12px;font-size:12px;cursor:pointer;transition:background .2s}}
.copy-btn:hover{{background:rgba(88,166,255,.2)}}
.raw-pre{{padding:18px;font-family:var(--mono);font-size:12px;line-height:1.6;color:var(--txm);overflow-x:auto;white-space:pre-wrap;word-break:break-all;max-height:600px;overflow-y:auto}}

/* input box */
.input-box{{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);padding:18px 22px;white-space:pre-wrap;font-size:14px;line-height:1.8}}

@media(max-width:768px){{
  .hdr,.main{{padding-left:16px;padding-right:16px}}
  .nav{{padding:0 8px}}
  .req-grid,.pages-grid{{grid-template-columns:1fr}}
  .dl-btn span{{display:none}}
}}
</style>
</head>
<body>
<div class="hdr">
  <div class="hdr-row">
    <div class="logo">🤖</div>
    <h1>AI 需求分析报告</h1>
    <span class="badge">{MODEL}</span>
    <a class="dl-btn" id="dl-btn" href="#" onclick="downloadReport()">⬇ <span>下载报告</span></a>
  </div>
  <div class="hdr-meta">生成时间：{now}</div>
</div>
<nav class="nav">
  <button class="nav-btn active" onclick="sw('cleaned',this)">💬 语义整理</button>
  <button class="nav-btn" onclick="sw('requirements',this)">📋 结构化需求</button>
  <button class="nav-btn" onclick="sw('prototype',this)">🖥️ 系统原型</button>
  <button class="nav-btn" onclick="sw('questions',this)">❓ 澄清问题</button>
  <button class="nav-btn" onclick="sw('raw',this)">📦 原始 JSON</button>
  <button class="nav-btn" onclick="sw('input',this)">📝 输入原文</button>
</nav>
<main class="main">
  <div id="tab-cleaned" class="sec active">
    <div class="sec-title"><span class="dot"></span>语义增强整理</div>
    {cleaned_html or '<p class="empty">无数据</p>'}
  </div>
  <div id="tab-requirements" class="sec">
    <div class="sec-title"><span class="dot" style="background:var(--accent2);box-shadow:0 0 8px var(--accent2)"></span>结构化需求</div>
    <div class="req-grid">{req_html or '<p class="empty">无数据</p>'}</div>
  </div>
  <div id="tab-prototype" class="sec">
    <div class="sec-title"><span class="dot" style="background:var(--accent3);box-shadow:0 0 8px var(--accent3)"></span>系统原型</div>
    <div class="proto-sec"><h3 class="proto-sub">🖥️ 页面列表</h3>
      <div class="pages-grid">{pages_html or '<p class="empty">暂无</p>'}</div></div>
    <div class="proto-sec"><h3 class="proto-sub">➡️ 业务流程</h3>
      <div class="flow-track">{flows_html or '<p class="empty">暂无</p>'}</div></div>
  </div>
  <div id="tab-questions" class="sec">
    <div class="sec-title"><span class="dot" style="background:var(--accent4);box-shadow:0 0 8px var(--accent4)"></span>关键澄清问题（{len(q_list)} 条）</div>
    {q_html or '<p class="empty">无数据</p>'}
  </div>
  <div id="tab-raw" class="sec">
    <div class="sec-title"><span class="dot" style="background:#6e7681"></span>完整 JSON 输出</div>
    <div class="raw-box">
      <div class="raw-toolbar"><span class="raw-label">result.json</span>
        <button class="copy-btn" id="cpbtn" onclick="cpJson()">复制</button></div>
      <pre class="raw-pre" id="raw-content">{_e(raw_json)}</pre>
    </div>
  </div>
  <div id="tab-input" class="sec">
    <div class="sec-title"><span class="dot" style="background:#6e7681"></span>输入原文</div>
    <div class="input-box">{_e(raw_input) or '（未提供）'}</div>
  </div>
</main>
<script>
function sw(name,btn){{
  document.querySelectorAll('.sec').forEach(s=>s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  btn.classList.add('active');
}}
function cpJson(){{
  navigator.clipboard.writeText(document.getElementById('raw-content').textContent)
    .then(()=>{{const b=document.getElementById('cpbtn');b.textContent='已复制 ✓';setTimeout(()=>b.textContent='复制',1500);}});
}}
function downloadReport(){{
  const blob=new Blob([document.documentElement.outerHTML],{{type:'text/html;charset=utf-8'}});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download='ai_prototype_report_{now.replace(" ","_").replace(":","").replace(":","")}.html';
  a.click();
  return false;
}}
</script>
</body></html>"""


# ══════════════════════════════════════════════════════
# 输入页 HTML
# ══════════════════════════════════════════════════════

INPUT_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 需求原型引擎</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0d1117;--surf:#161b22;--surf2:#1c2230;--bdr:#30363d;
  --accent:#58a6ff;--accent2:#3fb950;--accent3:#d2a8ff;--accent4:#ffa657;
  --tx:#e6edf3;--txm:#8b949e;--r:12px;
  --font:'Noto Sans SC',sans-serif;--mono:'JetBrains Mono',monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font-family:var(--font);min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;padding:40px 20px}

/* hero */
.hero{text-align:center;margin-bottom:44px}
.hero-icon{font-size:52px;margin-bottom:16px;filter:drop-shadow(0 0 20px rgba(88,166,255,.4))}
.hero h1{font-size:32px;font-weight:700;background:linear-gradient(90deg,var(--accent),var(--accent3));-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:10px}
.hero p{color:var(--txm);font-size:15px;line-height:1.6;max-width:500px;margin:0 auto}

/* card */
.card{width:100%;max-width:760px;background:var(--surf);border:1px solid var(--bdr);border-radius:16px;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,.4)}

/* card header */
.card-header{padding:22px 28px 0;border-bottom:1px solid var(--bdr);display:flex;gap:0}
.tab-link{padding:12px 20px;background:none;border:none;color:var(--txm);font-family:var(--font);font-size:13px;font-weight:500;cursor:pointer;border-bottom:2px solid transparent;transition:all .2s}
.tab-link.active{color:var(--accent);border-bottom-color:var(--accent)}

/* card body */
.card-body{padding:28px}
.tab-panel{display:none}
.tab-panel.active{display:block}

label.lbl{display:block;font-size:13px;font-weight:500;color:var(--txm);margin-bottom:8px;letter-spacing:.3px}
textarea{width:100%;height:200px;background:var(--surf2);border:1px solid var(--bdr);border-radius:var(--r);padding:14px 16px;color:var(--tx);font-family:var(--font);font-size:14px;line-height:1.7;resize:vertical;outline:none;transition:border-color .2s}
textarea:focus{border-color:var(--accent)}
textarea::placeholder{color:var(--txm)}

.file-zone{border:2px dashed var(--bdr);border-radius:var(--r);padding:32px;text-align:center;cursor:pointer;transition:border-color .2s,background .2s;position:relative}
.file-zone:hover,.file-zone.drag{border-color:var(--accent);background:rgba(88,166,255,.04)}
.file-zone input{position:absolute;inset:0;opacity:0;cursor:pointer}
.file-icon{font-size:32px;margin-bottom:10px}
.file-zone p{color:var(--txm);font-size:13px;line-height:1.6}
.file-name{color:var(--accent);font-weight:500;margin-top:8px;font-size:13px;min-height:20px}
.file-preview{margin-top:14px;background:var(--surf2);border:1px solid var(--bdr);border-radius:8px;padding:10px 14px;font-size:12px;color:var(--txm);max-height:120px;overflow-y:auto;white-space:pre-wrap;display:none}

/* submit */
.submit-btn{width:100%;margin-top:20px;padding:14px;background:linear-gradient(135deg,var(--accent),#3a7bd5);border:none;border-radius:var(--r);color:#fff;font-family:var(--font);font-size:15px;font-weight:600;cursor:pointer;transition:opacity .2s,transform .15s;letter-spacing:.4px}
.submit-btn:hover{opacity:.88;transform:translateY(-1px)}
.submit-btn:active{transform:translateY(0)}
.submit-btn:disabled{opacity:.45;cursor:not-allowed;transform:none}

/* progress */
.progress-wrap{display:none;margin-top:20px}
.prog-bar-bg{background:var(--surf2);border-radius:99px;height:6px;overflow:hidden;margin-bottom:14px}
.prog-bar{height:100%;width:0%;background:linear-gradient(90deg,var(--accent),var(--accent3));border-radius:99px;transition:width .5s ease}
.log-box{background:var(--surf2);border:1px solid var(--bdr);border-radius:var(--r);padding:14px 16px;max-height:180px;overflow-y:auto;font-family:var(--mono);font-size:12px;line-height:1.7}
.log-line{color:var(--txm);margin-bottom:2px}
.log-line.done{color:var(--accent2)}
.log-line.err{color:#f85149}
.log-line.info{color:var(--accent4)}

/* tips */
.tips{margin-top:24px;padding:14px 18px;background:rgba(88,166,255,.06);border:1px solid rgba(88,166,255,.15);border-radius:var(--r)}
.tips-title{font-size:12px;font-weight:600;color:var(--accent);margin-bottom:6px}
.tips ul{padding-left:16px}
.tips li{color:var(--txm);font-size:12px;line-height:1.7}

@media(max-width:600px){
  .hero h1{font-size:24px}
  .card-body{padding:18px}
}
</style>
</head>
<body>
<div class="hero">
  <div class="hero-icon">🤖</div>
  <h1>AI 需求原型引擎</h1>
  <p>输入客户沟通内容，AI 自动完成语义整理 → 需求提取 → 原型生成 → 澄清问题，一键生成专业报告</p>
</div>

<div class="card">
  <div class="card-header">
    <button class="tab-link active" onclick="switchInput('paste',this)">✏️ 粘贴文本</button>
    <button class="tab-link" onclick="switchInput('upload',this)">📁 上传文件</button>
  </div>
  <div class="card-body">

    <!-- 粘贴面板 -->
    <div id="panel-paste" class="tab-panel active">
      <label class="lbl">请输入客户沟通内容 / 需求描述</label>
      <textarea id="text-input" placeholder="示例：
客户说目前门店拜访无法管理，希望有系统记录销售行为，并统计动销情况。
销售反馈需要能在手机端完成拜访打卡、拍照上传和填写拜访记录..."></textarea>
    </div>

    <!-- 上传面板 -->
    <div id="panel-upload" class="tab-panel">
      <label class="lbl">上传文本文件（.txt / .md）</label>
      <div class="file-zone" id="drop-zone">
        <input type="file" id="file-input" accept=".txt,.md" onchange="handleFile(this)">
        <div class="file-icon">📂</div>
        <p>点击选择文件，或将文件拖拽至此处<br>支持 .txt / .md 格式</p>
        <div class="file-name" id="file-name"></div>
      </div>
      <div class="file-preview" id="file-preview"></div>
    </div>

    <button class="submit-btn" id="submit-btn" onclick="submitForm()">🚀 开始 AI 分析</button>

    <div class="progress-wrap" id="progress-wrap">
      <div class="prog-bar-bg"><div class="prog-bar" id="prog-bar"></div></div>
      <div class="log-box" id="log-box"></div>
    </div>

    <div class="tips">
      <div class="tips-title">💡 使用提示</div>
      <ul>
        <li>输入越详细，分析结果越精准，建议 100 字以上</li>
        <li>可包含客户需求、痛点描述、业务场景等信息</li>
        <li>分析过程约需 30～90 秒，请耐心等待</li>
        <li>生成报告后可在浏览器内直接下载 HTML 文件</li>
      </ul>
    </div>
  </div>
</div>

<script>
let fileContent = '';

function switchInput(name, btn) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-link').forEach(b => b.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  btn.classList.add('active');
}

function handleFile(input) {
  const file = input.files[0];
  if (!file) return;
  document.getElementById('file-name').textContent = '已选择：' + file.name;
  const reader = new FileReader();
  reader.onload = e => {
    fileContent = e.target.result;
    const prev = document.getElementById('file-preview');
    prev.style.display = 'block';
    prev.textContent = fileContent.slice(0, 400) + (fileContent.length > 400 ? '...' : '');
  };
  reader.readAsText(file, 'utf-8');
}

// drag & drop
const dz = document.getElementById('drop-zone');
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag'); });
dz.addEventListener('dragleave', () => dz.classList.remove('drag'));
dz.addEventListener('drop', e => {
  e.preventDefault(); dz.classList.remove('drag');
  const file = e.dataTransfer.files[0];
  if (file) { document.getElementById('file-input').files = e.dataTransfer.files; handleFile(document.getElementById('file-input')); }
});

function getInputText() {
  const active = document.querySelector('.tab-panel.active').id;
  if (active === 'panel-paste') return document.getElementById('text-input').value.trim();
  return fileContent.trim();
}

function addLog(msg, cls='') {
  const box = document.getElementById('log-box');
  const d = document.createElement('div');
  d.className = 'log-line ' + cls;
  d.textContent = msg;
  box.appendChild(d);
  box.scrollTop = box.scrollHeight;
}

function setProgress(pct) {
  document.getElementById('prog-bar').style.width = pct + '%';
}

async function submitForm() {
  const text = getInputText();
  if (!text) { alert('请输入或上传需求文本'); return; }

  const btn = document.getElementById('submit-btn');
  btn.disabled = true;
  btn.textContent = '⏳ 分析中，请稍候...';

  const pw = document.getElementById('progress-wrap');
  pw.style.display = 'block';
  document.getElementById('log-box').innerHTML = '';
  setProgress(5);
  addLog('📤 正在提交分析任务...', 'info');

  // 提交任务
  let taskId;
  try {
    const resp = await fetch('/api/submit', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text})
    });
    const data = await resp.json();
    taskId = data.task_id;
    addLog('✅ 任务已创建：' + taskId, 'done');
    setProgress(10);
  } catch(e) {
    addLog('❌ 提交失败：' + e, 'err');
    btn.disabled = false; btn.textContent = '🚀 开始 AI 分析';
    return;
  }

  // 轮询进度
  const steps = 4;
  let lastLog = 0;
  const progSteps = [25, 45, 65, 85, 95];

  const poll = setInterval(async () => {
    try {
      const resp = await fetch('/api/status?task_id=' + taskId);
      const data = await resp.json();

      // 新日志
      const logs = data.log || [];
      for (let i = lastLog; i < logs.length; i++) {
        const msg = logs[i];
        const cls = msg.startsWith('✅') ? 'done' : msg.startsWith('❌') ? 'err' : msg.startsWith('🎉') ? 'done' : '';
        addLog(msg, cls);
        const doneCount = logs.slice(0, i+1).filter(l => l.startsWith('✅')).length;
        setProgress(progSteps[Math.min(doneCount, progSteps.length-1)]);
      }
      lastLog = logs.length;

      if (data.status === 'done') {
        clearInterval(poll);
        setProgress(100);
        addLog('🎉 分析完成！正在跳转报告...', 'done');
        setTimeout(() => { window.location.href = '/report?task_id=' + taskId; }, 800);
      } else if (data.status === 'error') {
        clearInterval(poll);
        addLog('❌ 分析出错：' + (data.error || '未知错误'), 'err');
        btn.disabled = false; btn.textContent = '🚀 重新分析';
      }
    } catch(e) {
      // 网络抖动，继续轮询
    }
  }, 1500);
}
</script>
</body></html>"""

# ══════════════════════════════════════════════════════
# HTTP 请求处理
# ══════════════════════════════════════════════════════

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # 静默日志

    def _send(self, code: int, body: str | bytes, ctype: str = "text/html; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict):
        self._send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        qs     = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._send(200, INPUT_PAGE)

        elif path == "/api/status":
            task_id = qs.get("task_id", [""])[0]
            with _tasks_lock:
                task = _tasks.get(task_id)
            if not task:
                self._json(404, {"error": "task not found"})
            else:
                self._json(200, {
                    "status": task["status"],
                    "log":    task["log"],
                    "error":  task.get("error","")
                })

        elif path == "/report":
            task_id = qs.get("task_id", [""])[0]
            with _tasks_lock:
                task = _tasks.get(task_id)
            if not task or task["status"] != "done":
                self._send(404, "<h2>报告不存在或尚未完成</h2>")
            else:
                report_html = generate_html_report(task["result"], task.get("raw_input",""))
                self._send(200, report_html)

        else:
            self._send(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        if path == "/api/submit":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                payload = json.loads(body)
                text    = payload.get("text", "").strip()
            except Exception:
                self._json(400, {"error": "invalid json"})
                return

            if not text:
                self._json(400, {"error": "text is empty"})
                return

            task_id = str(uuid.uuid4())[:8]
            with _tasks_lock:
                _tasks[task_id] = {
                    "status":    "running",
                    "log":       [],
                    "result":    None,
                    "raw_input": text,
                    "error":     ""
                }

            # 后台线程执行分析
            def run(tid, raw):
                try:
                    engine = AIPrototypeEngine()
                    result = engine.run_pipeline(raw, task_id=tid)
                    with _tasks_lock:
                        _tasks[tid]["result"] = result
                        _tasks[tid]["status"] = "done"
                except Exception as e:
                    with _tasks_lock:
                        _tasks[tid]["status"] = "error"
                        _tasks[tid]["error"]  = str(e)
                        _tasks[tid]["log"].append(f"❌ 错误: {e}")

            t = threading.Thread(target=run, args=(task_id, text), daemon=True)
            t.start()

            self._json(200, {"task_id": task_id})

        else:
            self._send(404, "Not Found")


# ══════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════

def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    url    = f"http://localhost:{PORT}"
    print(f"""
╔══════════════════════════════════════════════════╗
║       AI 需求原型引擎  已启动                    ║
║  ➜  {url:<44}║
║  按 Ctrl+C 停止服务                              ║
╚══════════════════════════════════════════════════╝
""")
    # 延迟 0.8 秒再打开浏览器，等服务器就绪
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
