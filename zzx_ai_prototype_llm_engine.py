"""
AI 需求分析 & 原型生成引擎 —— Streamlit 版
=========================================
依赖：pip install streamlit requests
运行：streamlit run zzx_ai_prototype_llm_engine.py
"""

import json, re, os, html as _html
import requests
import streamlit as st
from datetime import datetime
from typing import Dict, Any

# ══════════════════════════════════════════════════════
# 配置
# ══════════════════════════════════════════════════════
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
DASHSCOPE_URL     = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL             = "qwen-plus"

# ══════════════════════════════════════════════════════
# LLM 调用
# ══════════════════════════════════════════════════════

def call_llm(prompt: str, system: str = "", max_tokens: int = 2000) -> str:
    api_key = st.session_state.get("api_key") or DASHSCOPE_API_KEY
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        r = requests.post(
            DASHSCOPE_URL,
            headers={"Authorization": f"Bearer {api_key}",
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

def run_pipeline(raw_text: str, progress_cb=None) -> Dict:
    def step(msg):
        if progress_cb:
            progress_cb(msg)

    step("⏳ [1/4] 语义整理中，请稍候...")
    cleaned = call_llm_json(prompt_semantic_clean(raw_text))
    step("✅ [1/4] 语义整理完成")

    step("⏳ [2/4] 提取结构化需求中...")
    requirements = call_llm_json(prompt_structured_extraction(
        json.dumps(cleaned, ensure_ascii=False)))
    step("✅ [2/4] 结构化需求提取完成")

    step("⏳ [3/4] 生成系统原型中...")
    prototype = call_llm_json(prompt_prototype(
        json.dumps(requirements, ensure_ascii=False)))
    step("✅ [3/4] 系统原型生成完成")

    step("⏳ [4/4] 生成澄清问题中...")
    questions = call_llm_json(prompt_questions(
        json.dumps(requirements, ensure_ascii=False)))
    step("✅ [4/4] 澄清问题生成完成")
    step("🎉 分析完成！")

    return {
        "cleaned":      cleaned,
        "requirements": requirements,
        "prototype":    prototype,
        "questions":    questions
    }

# ══════════════════════════════════════════════════════
# HTML 报告生成（供下载）
# ══════════════════════════════════════════════════════

def _e(text: str) -> str:
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
    input_html = _e(raw_input) if raw_input else "<em>（未记录）</em>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>AI 需求分析报告</title>
<style>
:root{{--bg:#0d1117;--surf:#161b22;--surf2:#1c2230;--bdr:#30363d;
  --accent:#58a6ff;--accent2:#3fb950;--accent3:#d2a8ff;--accent4:#ffa657;
  --tx:#e6edf3;--txm:#8b949e;--r:12px;
  --font:'Noto Sans SC',sans-serif;--mono:'JetBrains Mono',monospace;}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font-family:var(--font);font-size:14px;line-height:1.7}}
.hdr{{background:linear-gradient(135deg,#0d1117,#161b22);border-bottom:1px solid var(--bdr);padding:32px 48px}}
.hdr h1{{font-size:24px;font-weight:700;background:linear-gradient(90deg,var(--accent),var(--accent3));-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.hdr-meta{{color:var(--txm);font-size:12px;margin-top:6px}}
.nav{{display:flex;gap:2px;padding:0 48px;background:var(--surf);border-bottom:1px solid var(--bdr);position:sticky;top:0;z-index:100}}
.nav-btn{{padding:13px 20px;background:none;border:none;color:var(--txm);font-family:var(--font);font-size:13px;font-weight:500;cursor:pointer;border-bottom:2px solid transparent;transition:all .2s}}
.nav-btn.active{{color:var(--accent);border-bottom-color:var(--accent)}}
.main{{padding:32px 48px;max-width:1200px;margin:0 auto}}
.sec{{display:none}}.sec.active{{display:block}}
.sec-title{{font-size:17px;font-weight:700;margin-bottom:22px;padding-bottom:11px;border-bottom:1px solid var(--bdr)}}
.dialogue-item{{display:flex;gap:12px;padding:13px 16px;background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);margin-bottom:9px}}
.clr-accent .role-badge{{background:rgba(88,166,255,.15);border:1px solid rgba(88,166,255,.3);color:var(--accent)}}
.clr-accent2 .role-badge{{background:rgba(63,185,80,.15);border:1px solid rgba(63,185,80,.3);color:var(--accent2)}}
.clr-accent3 .role-badge{{background:rgba(210,168,255,.15);border:1px solid rgba(210,168,255,.3);color:var(--accent3)}}
.clr-accent4 .role-badge,.role-badge{{flex-shrink:0;padding:3px 11px;border-radius:20px;font-size:11px;font-weight:600;background:rgba(255,166,87,.15);border:1px solid rgba(255,166,87,.3);color:var(--accent4)}}
.tag-row{{display:flex;flex-wrap:wrap;gap:5px;margin-top:5px}}
.tag{{background:rgba(88,166,255,.1);border:1px solid rgba(88,166,255,.2);color:var(--accent);border-radius:4px;padding:1px 7px;font-size:11px}}
.req-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}}
.req-card{{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);padding:16px 18px}}
.req-title{{font-weight:600;font-size:13px;margin-bottom:10px;display:flex;align-items:center;gap:7px}}
.req-body{{color:var(--txm);font-size:13px}}
.inner-table{{width:100%;border-collapse:collapse}}
.inner-table td{{padding:4px 0;vertical-align:top}}
.key-cell{{color:var(--txm);width:100px;font-size:12px;padding-right:8px}}
.inner-list{{padding-left:15px}}
.value-text{{color:var(--tx)}}
.empty{{color:var(--txm);font-style:italic}}
.pages-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px;margin-bottom:28px}}
.page-card{{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);padding:14px 16px}}
.page-name{{font-weight:600;margin-bottom:9px;color:var(--accent3);font-size:13px}}
.comp-row{{display:flex;flex-wrap:wrap;gap:5px}}
.comp-chip{{background:var(--surf2);border:1px solid var(--bdr);border-radius:5px;padding:2px 9px;font-size:12px;color:var(--txm)}}
.flow-track{{display:flex;flex-wrap:wrap;align-items:center}}
.flow-step{{display:flex;align-items:center;gap:8px;background:var(--surf);border:1px solid var(--bdr);border-radius:8px;padding:9px 14px;margin:5px 0}}
.flow-step:not(:last-child)::after{{content:'→';color:var(--txm);margin:0 6px}}
.step-num{{width:22px;height:22px;background:linear-gradient(135deg,var(--accent2),#2ea043);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#fff;flex-shrink:0}}
.q-item{{display:flex;align-items:flex-start;gap:12px;padding:13px 16px;background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);margin-bottom:9px}}
.q-num{{flex-shrink:0;background:rgba(255,166,87,.15);border:1px solid rgba(255,166,87,.3);color:var(--accent4);border-radius:5px;padding:2px 9px;font-size:12px;font-weight:600}}
.raw-pre{{padding:18px;font-family:var(--mono);font-size:12px;line-height:1.6;color:var(--txm);overflow-x:auto;white-space:pre-wrap;word-break:break-all;max-height:600px;overflow-y:auto;background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r)}}
.proto-sub{{font-size:15px;font-weight:600;margin-bottom:14px;color:var(--accent3)}}
</style>
</head>
<body>
<div class="hdr">
  <h1>🤖 AI 需求分析报告</h1>
  <div class="hdr-meta">生成时间：{now} &nbsp;|&nbsp; 模型：{MODEL}</div>
</div>
<nav class="nav">
  <button class="nav-btn active" onclick="sw('cleaned',this)">💬 语义整理</button>
  <button class="nav-btn" onclick="sw('req',this)">📋 结构化需求</button>
  <button class="nav-btn" onclick="sw('proto',this)">🖥 系统原型</button>
  <button class="nav-btn" onclick="sw('q',this)">❓ 澄清问题</button>
  <button class="nav-btn" onclick="sw('raw',this)">📦 原始 JSON</button>
</nav>
<div class="main">
  <div id="sec-cleaned" class="sec active">
    <div class="sec-title">💬 语义整理结果</div>
    {cleaned_html}
  </div>
  <div id="sec-req" class="sec">
    <div class="sec-title">📋 结构化需求</div>
    <div class="req-grid">{req_html}</div>
  </div>
  <div id="sec-proto" class="sec">
    <div class="sec-title">🖥 系统原型</div>
    <div class="proto-sub">页面清单</div>
    <div class="pages-grid">{pages_html}</div>
    <div class="proto-sub">业务流程</div>
    <div class="flow-track">{flows_html}</div>
  </div>
  <div id="sec-q" class="sec">
    <div class="sec-title">❓ 澄清问题</div>
    {q_html}
  </div>
  <div id="sec-raw" class="sec">
    <div class="sec-title">📦 原始 JSON</div>
    <pre class="raw-pre">{_e(raw_json)}</pre>
  </div>
</div>
<script>
function sw(id, btn) {{
  document.querySelectorAll('.sec').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('sec-' + id).classList.add('active');
  btn.classList.add('active');
}}
</script>
</body></html>"""

# ══════════════════════════════════════════════════════
# Streamlit UI
# ══════════════════════════════════════════════════════

def render_results(result: Dict):
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["💬 语义整理", "📋 结构化需求", "🖥 系统原型", "❓ 澄清问题", "📦 原始 JSON"]
    )

    with tab1:
        cleaned = result.get("cleaned", [])
        role_colors = {
            "产品经理": "🔵", "PM": "🔵", "pm": "🔵",
            "客户": "🟢", "顾客": "🟢", "用户": "🟢",
            "销售": "🟣", "业务": "🟣",
        }
        if isinstance(cleaned, list):
            for item in cleaned:
                if not isinstance(item, dict):
                    continue
                role    = item.get("role", "—")
                content = item.get("content", "")
                tags    = item.get("tags", [])
                icon    = role_colors.get(role, "🟠")
                tag_str = "  ".join([f"`{t}`" for t in (tags if isinstance(tags, list) else [str(tags)])])
                with st.container(border=True):
                    st.markdown(f"**{icon} {role}**")
                    st.write(content)
                    if tag_str:
                        st.markdown(tag_str)
        else:
            st.json(cleaned)

    with tab2:
        requirements = result.get("requirements", {})
        ICONS = {"业务目标":"🎯","用户角色":"👥","核心场景":"🎬","功能模块":"🧩",
                 "业务流程":"🔄","数据对象":"🗄️","权限角色":"🔐","关键指标":"📊",
                 "约束条件":"⚠️","优先级判断":"📌"}
        if isinstance(requirements, dict):
            cols = st.columns(2)
            for i, (key, val) in enumerate(requirements.items()):
                icon = ICONS.get(key, "▪️")
                with cols[i % 2].container(border=True):
                    st.markdown(f"**{icon} {key}**")
                    if isinstance(val, list):
                        for v in val:
                            st.write(f"• {v}")
                    elif isinstance(val, dict):
                        for k2, v2 in val.items():
                            st.write(f"**{k2}：** {v2}")
                    else:
                        st.write(val)
        else:
            st.json(requirements)

    with tab3:
        prototype = result.get("prototype", {})
        pages = prototype.get("pages", []) if isinstance(prototype, dict) else []
        flows = prototype.get("flows", []) if isinstance(prototype, dict) else []

        st.markdown("#### 📄 页面清单")
        if pages:
            cols = st.columns(min(3, len(pages)))
            for i, pg in enumerate(pages if isinstance(pages, list) else []):
                name  = pg.get("name","页面") if isinstance(pg, dict) else str(pg)
                comps = pg.get("components",[]) if isinstance(pg, dict) else []
                with cols[i % 3].container(border=True):
                    st.markdown(f"**📄 {name}**")
                    for c in (comps if isinstance(comps, list) else [comps]):
                        st.write(f"• {c}")
        else:
            st.info("暂无页面数据")

        st.markdown("#### 🔄 业务流程")
        if flows:
            for idx, step in enumerate(flows if isinstance(flows, list) else [], 1):
                label = step if isinstance(step, str) else json.dumps(step, ensure_ascii=False)
                arrow = " → " if idx < len(flows) else ""
                st.markdown(f"`{idx}` {label}{arrow}")
        else:
            st.info("暂无流程数据")

    with tab4:
        q_list = result.get("questions", [])
        if not isinstance(q_list, list):
            q_list = []
        for item in q_list:
            qid  = str(item.get("id","?")) if isinstance(item, dict) else "?"
            qtxt = item.get("question", str(item)) if isinstance(item, dict) else str(item)
            with st.container(border=True):
                st.markdown(f"**Q{qid}** &nbsp; {qtxt}")

    with tab5:
        st.json(result)


def main():
    st.set_page_config(
        page_title="AI 需求原型引擎",
        page_icon="🤖",
        layout="wide"
    )

    st.title("🤖 AI 需求原型引擎")
    st.caption("输入客户沟通内容，AI 自动完成语义整理 → 需求提取 → 原型生成 → 澄清问题")

    # ── 侧边栏：API Key ──
    with st.sidebar:
        st.header("⚙️ 配置")
        api_key_input = st.text_input(
            "DashScope API Key",
            value=st.session_state.get("api_key", DASHSCOPE_API_KEY),
            type="password",
            help="也可通过环境变量 DASHSCOPE_API_KEY 设置"
        )
        st.session_state["api_key"] = api_key_input
        st.markdown("---")
        st.markdown("**使用提示**")
        st.markdown("""
- 输入越详细，结果越精准（建议 100 字以上）
- 可包含客户需求、痛点描述、业务场景等
- 分析约需 30～90 秒，请耐心等待
- 完成后可下载 HTML 报告
""")

    # ── 输入区 ──
    input_tab1, input_tab2 = st.tabs(["✏️ 粘贴文本", "📁 上传文件"])

    raw_text = ""
    with input_tab1:
        raw_text_paste = st.text_area(
            "请输入客户沟通内容 / 需求描述",
            height=220,
            placeholder="示例：\n客户说目前门店拜访无法管理，希望有系统记录销售行为，并统计动销情况。\n销售反馈需要能在手机端完成拜访打卡、拍照上传和填写拜访记录..."
        )
        if raw_text_paste:
            raw_text = raw_text_paste

    with input_tab2:
        uploaded = st.file_uploader("上传文本文件", type=["txt", "md"])
        if uploaded:
            raw_text = uploaded.read().decode("utf-8", errors="ignore")
            st.success(f"已加载文件：{uploaded.name}（{len(raw_text)} 字符）")
            with st.expander("文件预览"):
                st.text(raw_text[:500] + ("..." if len(raw_text) > 500 else ""))

    # ── 分析按钮 ──
    if st.button("🚀 开始 AI 分析", type="primary", disabled=not raw_text.strip()):
        if not st.session_state.get("api_key"):
            st.error("请先在侧边栏填写 DashScope API Key")
            st.stop()

        log_box     = st.empty()
        progress    = st.progress(0)
        log_msgs    = []
        prog_steps  = {"1/4": 25, "2/4": 50, "3/4": 75, "4/4": 95}

        def progress_cb(msg):
            log_msgs.append(msg)
            log_box.info("\n\n".join(log_msgs))
            for key, pct in prog_steps.items():
                if key in msg and msg.startswith("✅"):
                    progress.progress(pct)

        with st.spinner("AI 分析中..."):
            try:
                result = run_pipeline(raw_text.strip(), progress_cb=progress_cb)
                progress.progress(100)
                log_box.success("🎉 分析完成！")
                st.session_state["result"]    = result
                st.session_state["raw_input"] = raw_text
            except Exception as e:
                st.error(f"❌ 分析出错：{e}")
                st.stop()

    # ── 结果展示 ──
    if "result" in st.session_state:
        st.divider()
        st.subheader("📊 分析结果")

        # 下载按钮
        html_report = generate_html_report(
            st.session_state["result"],
            st.session_state.get("raw_input", "")
        )
        st.download_button(
            label="⬇️ 下载 HTML 报告",
            data=html_report.encode("utf-8"),
            file_name=f"ai_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            mime="text/html"
        )

        render_results(st.session_state["result"])


if __name__ == "__main__":
    main()
