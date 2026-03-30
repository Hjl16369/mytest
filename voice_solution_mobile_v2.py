"""
正掌讯 · AI 销售质检系统 v2.0
新增：内置 Web 上传界面，支持用户上传文本文件后自动分析并生成报告

运行方式：
    python voice_solution_mobile_v2.py              # 启动 Web 上传界面（推荐）
    python voice_solution_mobile_v2.py --text 文字稿.txt --rep 张三 --id R002   # CLI 方式
    python voice_solution_mobile_v2.py --demo       # 使用内置演示文字稿

Web 界面默认地址：http://localhost:8765
"""

import re
import json
import sqlite3
import os
import sys
import argparse
import webbrowser
import threading
import urllib.parse
import io
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from pathlib import Path
import requests


# ══════════════════════════════════════════════════════
# 纯标准库 multipart/form-data 解析器（兼容 Python 3.13+）
# 替代已移除的 cgi 模块
# ══════════════════════════════════════════════════════

def parse_multipart(body: bytes, content_type: str) -> dict:
    """
    解析 multipart/form-data，返回 {field_name: bytes} 字典。
    文件字段和普通字段均以 bytes 存储。
    """
    # 从 Content-Type 中提取 boundary
    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part[len("boundary="):].strip().strip('"')
            break
    if not boundary:
        raise ValueError("multipart/form-data 缺少 boundary 参数")

    sep      = ("--" + boundary).encode()
    end_sep  = ("--" + boundary + "--").encode()
    fields   = {}

    # 按分隔符切割
    for chunk in body.split(sep):
        chunk = chunk.strip(b"\r\n")
        if not chunk or chunk == b"--" or chunk.startswith(b"--"):
            continue

        # 分离头部和正文（以第一个 \r\n\r\n 为界）
        if b"\r\n\r\n" in chunk:
            raw_headers, value = chunk.split(b"\r\n\r\n", 1)
        elif b"\n\n" in chunk:
            raw_headers, value = chunk.split(b"\n\n", 1)
        else:
            continue

        # 去掉末尾的 \r\n
        value = value.rstrip(b"\r\n")

        # 解析 Content-Disposition
        name = None
        for line in raw_headers.decode("utf-8", errors="replace").splitlines():
            if line.lower().startswith("content-disposition:"):
                for seg in line.split(";"):
                    seg = seg.strip()
                    if seg.startswith('name='):
                        name = seg[5:].strip().strip('"')
        if name:
            fields[name] = value

    return fields

# ══════════════════════════════════════════════════════
# 配置区
# ══════════════════════════════════════════════════════
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "sk-c4bbfc49d1a84880ae3241dff77a9e8f")
DB_PATH           = "sales_ai.db"
OUTPUT_DIR        = Path("reports")          # HTML 报告输出目录
MODEL             = "qwen-plus"
WEB_PORT          = 8765                     # Web 上传界面端口


# ══════════════════════════════════════════════════════
# Step 1  文本预处理
# ══════════════════════════════════════════════════════

def split_sentences(text: str) -> list:
    lines = text.strip().split("\n")
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^((?:客户|顾客|买方|销售|业务|销售员|代表|客|销)[：:])\s*', line)
        prefix = m.group(0) if m else ""
        body   = line[len(prefix):] if prefix else line
        parts = re.split(r'(?<=[。！？…])', body)
        for p in parts:
            p = p.strip()
            if p:
                out.append(prefix + p)
    return out


def identify_speaker(sentence: str) -> str:
    s = sentence.strip()
    if re.match(r'^(客户|顾客|买方|客)[：:]', s):
        return "customer"
    if re.match(r'^(销售|业务|销售员|代表|销)[：:]', s):
        return "sales"
    sales_kw    = ["我们公司","我们产品","我来介绍","我们可以","这款产品","推荐您","我们这边","给您","合作","方案"]
    customer_kw = ["你们价格","太贵了","考虑一下","别家","你们的","有没有优惠","我需要","我再想想"]
    sc = sum(1 for k in sales_kw    if k in s)
    cc = sum(1 for k in customer_kw if k in s)
    if sc > cc: return "sales"
    if cc > sc: return "customer"
    return "unknown"


def clean_prefix(s: str) -> str:
    return re.sub(r'^(客户|顾客|买方|销售|业务|销售员|代表|客|销)[：:]\s*', '', s).strip()


def build_dialogue(sentences: list) -> list:
    out = []
    for s in sentences:
        speaker = identify_speaker(s)
        text    = clean_prefix(s)
        if text:
            out.append({"speaker": speaker, "text": text})
    return out


# ══════════════════════════════════════════════════════
# LLM 调用
# ══════════════════════════════════════════════════════

def call_llm(prompt: str, system: str = "", max_tokens: int = 2000) -> str:
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {DASHSCOPE_API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": 0.3},
            timeout=90
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {e}"


def call_llm_json(prompt: str, system: str = "") -> dict:
    sys_full = (system or "") + "\n\n【重要】只输出合法 JSON，不加说明文字，不使用 Markdown 代码块。"
    raw = call_llm(prompt, sys_full.strip())
    clean = re.sub(r'^```(?:json)?\s*', '', raw.strip())
    clean = re.sub(r'\s*```$', '', clean.strip())
    try:
        return json.loads(clean)
    except Exception:
        m = re.search(r'\{.*\}', clean, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        return {"error": "JSON解析失败", "raw": raw[:300]}


# ══════════════════════════════════════════════════════
# Step 2  阶段切分 + 标签
# ══════════════════════════════════════════════════════

SYS_STAGE = "你是专业销售培训顾问，擅长销售对话分析。请严格按要求输出 JSON。"
SYS_EVAL  = "你是资深销售培训专家，10年以上B2B/B2C销售培训经验，评估客观专业。请严格按要求输出 JSON。"


def stage_segmentation(dialogue: list) -> dict:
    prompt = f"""
请将以下销售对话每句话标注所属销售阶段。

阶段定义：
1.开场建立信任  2.需求探询  3.产品价值呈现  4.异议处理  5.成交推进  6.收场跟进

对话：
{json.dumps(dialogue, ensure_ascii=False, indent=2)}

输出 JSON：
{{
  "stage_analysis": [{{"index":0,"speaker":"sales","text":"...","stage":1,"stage_name":"开场建立信任","reason":"..."}},...],
  "stage_distribution": {{"1":2,"2":3,"3":1,"4":1,"5":0,"6":0}},
  "missing_stages": [5,6],
  "stage_summary": "描述"
}}"""
    return call_llm_json(prompt, SYS_STAGE)


def extract_tags(dialogue: list) -> dict:
    prompt = f"""
分析以下销售对话，提取关键行为标签。

对话：
{json.dumps(dialogue, ensure_ascii=False, indent=2)}

输出 JSON：
{{
  "questioning": {{"total_questions":3,"open_questions":["..."],"closed_questions":["..."],"question_quality":"高/中/低","question_quality_reason":"..."}},
  "price_sensitivity": {{"mentioned":true,"customer_reaction":"正面/负面/中性","objection_detail":"..."}},
  "objections": [{{"type":"价格异议","content":"...","handled":true,"handling_quality":"好/中/差"}}],
  "customer_emotion": {{"overall":"正面/负面/中性","trend":"好转/恶化/平稳","key_moments":["..."]}},
  "sales_behavior": {{"active_listening_signals":2,"product_mentions":3,"closing_attempts":1}}
}}"""
    return call_llm_json(prompt, SYS_STAGE)


# ══════════════════════════════════════════════════════
# Step 3  LLM 评估
# ══════════════════════════════════════════════════════

def extract_facts(dialogue: list) -> dict:
    prompt = f"""
从以下销售对话中提取可量化的销售行为事实（只做客观描述）。

对话：
{json.dumps(dialogue, ensure_ascii=False, indent=2)}

输出 JSON：
{{
  "basic_stats": {{"total_turns":10,"sales_turns":6,"customer_turns":4}},
  "questioning_facts": {{"total_questions_asked":2,"open_questions_count":1,"question_examples":["..."]}},
  "needs_discovery": {{"customer_needs_identified":["..."],"customer_pain_points":["..."],"needs_confirmed":false}},
  "product_presentation": {{"features_mentioned":["..."],"benefits_mentioned":["..."],"cases_mentioned":false}},
  "objection_handling": {{"objections_raised":["..."],"objections_addressed":["..."],"unhandled_objections":["..."]}},
  "closing": {{"closing_attempt_made":false,"next_step_defined":false,"commitment_obtained":false}},
  "rapport_building": {{"greeting_quality":"有/无","common_ground_found":false}}
}}"""
    return call_llm_json(prompt, SYS_EVAL)


def score_visit(facts: dict, tags: dict, stages: dict) -> dict:
    prompt = f"""
基于以下销售拜访事实、标签和阶段分析进行专业评分。

事实：{json.dumps(facts, ensure_ascii=False)}
标签：{json.dumps(tags,  ensure_ascii=False)}
阶段：{json.dumps(stages,ensure_ascii=False)}

评分维度（各0-10分）：
- opening(权重15%)：开场是否自然、是否建立信任
- needs(权重25%)：提问质量、需求挖掘深度
- presentation(权重20%)：产品优势表达、与需求匹配度
- objection(权重20%)：识别并有效处理客户异议
- closing(权重15%)：有效推进成交、明确下一步
- communication(权重5%)：语言表达、节奏控制

输出 JSON：
{{
  "scores": {{
    "opening":      {{"score":7,"weight":0.15,"weighted":1.05,"comment":"评分理由"}},
    "needs":        {{"score":5,"weight":0.25,"weighted":1.25,"comment":"评分理由"}},
    "presentation": {{"score":6,"weight":0.20,"weighted":1.20,"comment":"评分理由"}},
    "objection":    {{"score":4,"weight":0.20,"weighted":0.80,"comment":"评分理由"}},
    "closing":      {{"score":3,"weight":0.15,"weighted":0.45,"comment":"评分理由"}},
    "communication":{{"score":7,"weight":0.05,"weighted":0.35,"comment":"评分理由"}}
  }},
  "total_score":51,
  "grade":"C",
  "grade_description":"需要改进",
  "strengths":["优点1","优点2"],
  "weaknesses":["不足1","不足2"],
  "critical_issue":"最关键问题"
}}
评级：A(85-100优秀) B(70-84良好) C(55-69需改进) D(40-54较差) E(0-39很差)"""
    return call_llm_json(prompt, SYS_EVAL)


def generate_suggestions(dialogue: list, score: dict, facts: dict) -> dict:
    prompt = f"""
你是顶级销售教练，请基于以下分析提供专业辅导方案。

对话：{json.dumps(dialogue, ensure_ascii=False)}
评分：{json.dumps(score,    ensure_ascii=False)}
事实：{json.dumps(facts,    ensure_ascii=False)}

输出 JSON：
{{
  "improvement_plan": {{
    "priority_1": {{"dimension":"维度","current_issue":"问题","target_behavior":"期望","practice_exercise":"练习"}},
    "priority_2": {{"dimension":"维度","current_issue":"问题","target_behavior":"期望","practice_exercise":"练习"}}
  }},
  "script_improvement": [
    {{"original":"原话术","issue":"问题","improved":"改进话术","principle":"改进原则"}}
  ],
  "next_visit_script": {{
    "opening":"开场话术",
    "needs_questions":["提问1","提问2","提问3"],
    "objection_responses": {{"price_objection":"价格异议应对","competitor_objection":"竞品比较应对"}},
    "closing_statement":"成交推进话术"
  }},
  "30day_action_plan": [
    {{"week":1,"focus":"聚焦点","action":"具体行动","metric":"衡量指标"}},
    {{"week":2,"focus":"聚焦点","action":"具体行动","metric":"衡量指标"}},
    {{"week":3,"focus":"聚焦点","action":"具体行动","metric":"衡量指标"}},
    {{"week":4,"focus":"聚焦点","action":"具体行动","metric":"衡量指标"}}
  ],
  "coaching_summary":"200字以内整体辅导总结"
}}"""
    return call_llm_json(prompt, SYS_EVAL)


# ══════════════════════════════════════════════════════
# Step 4  数据存储
# ══════════════════════════════════════════════════════

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS visit_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visit_id TEXT, rep_id TEXT, rep_name TEXT,
        customer_id TEXT, visit_date TEXT,
        total_score REAL, grade TEXT,
        dialogue_json TEXT, stages_json TEXT, tags_json TEXT,
        facts_json TEXT, score_json TEXT, suggestions_json TEXT,
        html_path TEXT, created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS score_trend (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visit_id TEXT, rep_id TEXT,
        score_opening REAL, score_needs REAL, score_presentation REAL,
        score_objection REAL, score_closing REAL, score_communication REAL,
        total_score REAL, grade TEXT, visit_date TEXT, created_at TEXT
    )""")
    existing = {row[1] for row in c.execute("PRAGMA table_info(visit_analysis)").fetchall()}
    migrations = {
        "html_path":        "ALTER TABLE visit_analysis ADD COLUMN html_path TEXT DEFAULT ''",
        "customer_id":      "ALTER TABLE visit_analysis ADD COLUMN customer_id TEXT DEFAULT ''",
        "suggestions_json": "ALTER TABLE visit_analysis ADD COLUMN suggestions_json TEXT DEFAULT '{}'",
    }
    for col, sql in migrations.items():
        if col not in existing:
            c.execute(sql)
    conn.commit()
    conn.close()


def save_result(visit_id, rep_id, rep_name, customer_id, visit_date,
                dialogue, stages, tags, facts, score, suggestions,
                html_path="") -> int:
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    now  = datetime.now().isoformat()
    total_score = score.get("total_score", 0)
    grade       = score.get("grade", "N/A")
    if not visit_date:
        visit_date = datetime.now().strftime("%Y-%m-%d")
    c.execute("""INSERT INTO visit_analysis
        (visit_id,rep_id,rep_name,customer_id,visit_date,total_score,grade,
         dialogue_json,stages_json,tags_json,facts_json,score_json,suggestions_json,html_path,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (visit_id, rep_id, rep_name, customer_id, visit_date, total_score, grade,
         json.dumps(dialogue,    ensure_ascii=False),
         json.dumps(stages,      ensure_ascii=False),
         json.dumps(tags,        ensure_ascii=False),
         json.dumps(facts,       ensure_ascii=False),
         json.dumps(score,       ensure_ascii=False),
         json.dumps(suggestions, ensure_ascii=False),
         html_path, now))
    sc = score.get("scores", {})
    c.execute("""INSERT INTO score_trend
        (visit_id,rep_id,score_opening,score_needs,score_presentation,
         score_objection,score_closing,score_communication,total_score,grade,visit_date,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (visit_id, rep_id,
         sc.get("opening",       {}).get("score", 0),
         sc.get("needs",         {}).get("score", 0),
         sc.get("presentation",  {}).get("score", 0),
         sc.get("objection",     {}).get("score", 0),
         sc.get("closing",       {}).get("score", 0),
         sc.get("communication", {}).get("score", 0),
         total_score, grade, visit_date, now))
    conn.commit()
    row_id = c.lastrowid
    conn.close()
    return row_id


def load_history(limit=20) -> list:
    if not Path(DB_PATH).exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    existing = {row[1] for row in c.execute("PRAGMA table_info(visit_analysis)").fetchall()}
    html_col = ", html_path" if "html_path" in existing else ", '' as html_path"
    tags_col = ", tags_json"  if "tags_json"  in existing else ", '{}' as tags_json"
    try:
        rows = c.execute(f"""
            SELECT visit_id, rep_id, rep_name, visit_date, total_score, grade,
                   score_json {tags_col} {html_col}
            FROM visit_analysis ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    conn.close()
    out = []
    for row in rows:
        vid, rid, rname, vdate, tscore, grade, score_j, tags_j, hpath = row
        try:
            scores = json.loads(score_j or "{}").get("scores", {})
        except Exception:
            scores = {}
        try:
            tags = json.loads(tags_j or "{}")
        except Exception:
            tags = {}
        out.append({
            "visit_id":    vid,
            "rep_id":      rid,
            "rep_name":    rname or rid,
            "visit_date":  vdate or "",
            "total_score": tscore or 0,
            "grade":       grade or "-",
            "scores":      scores,
            "tags":        tags,
            "html_path":   hpath or "",
        })
    return out


# ══════════════════════════════════════════════════════
# Step 5  HTML 报告生成器
# ══════════════════════════════════════════════════════

def _esc(s: str) -> str:
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def _score_color(v) -> str:
    v = float(v or 0)
    if v >= 8:  return "#00A878"
    if v >= 6:  return "#0055D4"
    if v >= 4:  return "#F59E0B"
    return "#E5483A"

def _grade_color(g: str) -> str:
    return {"A":"#00A878","B":"#0055D4","C":"#F59E0B","D":"#E5483A","E":"#B91C1C"}.get(g, "#888")


def generate_html_report(result: dict, history: list) -> str:
    r    = result
    sc   = r["score"]
    scs  = sc.get("scores", {})
    tags = r.get("tags", {})
    sugg = r.get("suggestions", {})
    stg  = r.get("stages", {})

    total   = sc.get("total_score", 0)
    grade   = sc.get("grade", "-")
    g_color = _grade_color(grade)

    dim_keys   = ["opening","needs","presentation","objection","closing","communication"]
    dim_labels = ["开场信任","需求探询","产品呈现","异议处理","成交推进","沟通专业"]

    def dim_bars_html():
        rows = []
        for k, lbl in zip(dim_keys, dim_labels):
            v   = scs.get(k, {}).get("score", 0)
            cmt = _esc(scs.get(k, {}).get("comment", ""))
            col = _score_color(v)
            rows.append(f"""<div class="dim-row">
  <div class="dim-head"><span class="dim-label">{lbl}</span><span class="dim-score" style="color:{col}">{v}<span style="font-size:11px;font-weight:400">/10</span></span></div>
  <div class="dim-track"><div class="dim-fill" style="width:{v*10}%;background:{col}"></div></div>
  <div class="dim-cmt">{cmt}</div>
</div>""")
        return "\n".join(rows)

    def dialogue_html():
        stage_list = stg.get("stage_analysis", r.get("dialogue", []))
        rows = []
        for i, d in enumerate(stage_list):
            sp    = d.get("speaker", "unknown")
            text  = _esc(d.get("text", ""))
            sname = _esc(d.get("stage_name", ""))
            cls   = "turn-sales" if sp == "sales" else "turn-customer" if sp == "customer" else "turn-unknown"
            av    = "销" if sp == "sales" else "客" if sp == "customer" else "?"
            badge = f'<span class="stage-badge">{sname}</span>' if sname else ""
            label = "销售" if sp == "sales" else "客户" if sp == "customer" else "未知"
            rows.append(f"""<div class="turn {cls}">
  <div class="av">{av}</div>
  <div class="bwrap"><div class="bubble">{text}{badge}</div>
  <div class="turn-meta">{label} · #{i+1}</div></div>
</div>""")
        return "\n".join(rows)

    def sw_html():
        rows = []
        for s in sc.get("strengths", []):
            rows.append(f'<div class="sw-item sw-good"><span class="sw-icon">+</span><span>{_esc(s)}</span></div>')
        for w in sc.get("weaknesses", []):
            rows.append(f'<div class="sw-item sw-bad"><span class="sw-icon">−</span><span>{_esc(w)}</span></div>')
        return "\n".join(rows)

    def script_improve_html():
        rows = []
        for s in sugg.get("script_improvement", []):
            rows.append(f"""<div class="improve-card">
  <div class="improve-orig">原：{_esc(s.get('original',''))}</div>
  <div class="improve-issue">问题：{_esc(s.get('issue',''))}</div>
  <div class="improve-new">改进：{_esc(s.get('improved',''))}</div>
  <div class="improve-principle">{_esc(s.get('principle',''))}</div>
</div>""")
        return "\n".join(rows) or "<p class='muted'>暂无改进示例</p>"

    def next_script_html():
        nv  = sugg.get("next_visit_script", {})
        qs  = "".join(f'<div class="script-q">· {_esc(q)}</div>' for q in nv.get("needs_questions", []))
        obj = nv.get("objection_responses", {})
        return f"""<div class="script-block">
  <div class="script-lbl">开场</div>
  <div class="script-text">{_esc(nv.get('opening',''))}</div>
</div>
<div class="script-block">
  <div class="script-lbl">需求探询提问</div>
  {qs}
</div>
<div class="script-block">
  <div class="script-lbl">价格异议应对</div>
  <div class="script-text">{_esc(obj.get('price_objection',''))}</div>
</div>
<div class="script-block">
  <div class="script-lbl">成交推进话术</div>
  <div class="script-text highlight">{_esc(nv.get('closing_statement',''))}</div>
</div>"""

    def plan_html():
        rows = []
        for i, w in enumerate(sugg.get("30day_action_plan", [])):
            cls = "done" if i < 1 else "active" if i == 1 else ""
            rows.append(f"""<div class="tl-item {cls}">
  <div class="tl-dot"></div>
  <div class="tl-body">
    <div class="tl-week">第 {w.get('week', i+1)} 周 · {_esc(w.get('focus',''))}</div>
    <div class="tl-action">{_esc(w.get('action',''))}</div>
    <div class="tl-metric">目标：{_esc(w.get('metric',''))}</div>
  </div>
</div>""")
        return "\n".join(rows)

    def team_dim_bars_html():
        if not history:
            return ""
        dim_avgs = {}
        for k in dim_keys:
            vals = [h["scores"].get(k, {}).get("score", 0) for h in history if h.get("scores")]
            dim_avgs[k] = sum(vals) / len(vals) if vals else 0
        rows = []
        for k, lbl in zip(dim_keys, dim_labels):
            v   = dim_avgs[k]
            col = _score_color(v)
            rows.append(f"""<div class="dim-row">
  <div class="dim-head"><span class="dim-label">{lbl}</span><span class="dim-score" style="color:{col}">{v:.1f}</span></div>
  <div class="dim-track"><div class="dim-fill" style="width:{v*10}%;background:{col}"></div></div>
</div>""")
        return "\n".join(rows)

    def team_cards_html():
        if not history:
            return '<div class="empty-state">暂无历史记录，完成首次分析后将在此显示</div>'
        cards = []
        for h in history[:10]:
            gc    = _grade_color(h["grade"])
            tscore = h.get("total_score", 0)
            hp    = h.get("html_path", "")
            link  = f'href="{hp}"' if hp and Path(hp).exists() else 'href="#" onclick="return false"'
            cards.append(f"""<a class="hist-card" {link}>
  <div class="hist-score" style="background:{gc}18;color:{gc}">
    <div class="hs-num">{tscore}</div>
    <div class="hs-grade">{h['grade']}</div>
  </div>
  <div class="hist-info">
    <div class="hist-name">{_esc(h.get('rep_name',''))}</div>
    <div class="hist-meta">{_esc(h.get('visit_date',''))} · {_esc(h.get('visit_id',''))}</div>
  </div>
  <div class="hist-arrow">›</div>
</a>""")
        return "\n".join(cards)

    stage_dist    = stg.get("stage_distribution", {})
    stage_data    = [int(stage_dist.get(str(i), 0)) for i in range(1, 7)]
    radar_data    = [scs.get(k, {}).get("score", 0) for k in dim_keys]
    team_total    = len(history)
    team_avg      = round(sum(h["total_score"] for h in history) / team_total, 1) if history else 0
    team_best     = max((h["total_score"] for h in history), default=0)
    team_radar    = ([round(sum(h["scores"].get(k,{}).get("score",0) for h in history)/len(history),1) for k in dim_keys]
                     if history else [0]*6)
    trend_labels  = json.dumps([h["visit_date"] for h in reversed(history[:8])])
    trend_data_js = json.dumps([h["total_score"] for h in reversed(history[:8])])
    radar_js      = json.dumps(radar_data)
    stage_js      = json.dumps(stage_data)
    dim_lbl_js    = json.dumps(dim_labels)
    team_radar_js = json.dumps(team_radar)

    missing_banner = ""
    if stg.get("missing_stages"):
        stage_map = {1:"开场",2:"需求探询",3:"产品呈现",4:"异议处理",5:"成交推进",6:"收场跟进"}
        tags_str  = "".join(
            f'<span class="miss-tag">{stage_map.get(int(s) if str(s).isdigit() else s, str(s))}</span>'
            for s in stg["missing_stages"]
        )
        missing_banner = f'<div class="notice notice-amber">⚠ 缺失阶段：{tags_str}</div>'

    critical_banner = (f'<div class="notice notice-red">核心问题：{_esc(sc.get("critical_issue",""))}</div>'
                       if sc.get("critical_issue") else "")

    s_cnt = sum(1 for d in r.get("dialogue", []) if d["speaker"] == "sales")
    c_cnt = sum(1 for d in r.get("dialogue", []) if d["speaker"] == "customer")
    q_cnt = tags.get("questioning", {}).get("total_questions", 0)
    obj_cnt = len(tags.get("objections", []))

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<title>正掌讯 · {_esc(r.get('rep_name',''))} 拜访报告</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}}
html{{font-size:15px}}
body{{font-family:"PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif;
      background:#F0F3F9;color:#1A2035;line-height:1.65;
      padding-bottom:calc(64px + env(safe-area-inset-bottom))}}
a{{text-decoration:none;color:inherit}}
.topbar{{background:#0055D4;color:#fff;height:54px;
         display:flex;align-items:center;padding:0 16px;gap:10px;
         position:sticky;top:0;z-index:200}}
.topbar-logo{{width:32px;height:32px;background:rgba(255,255,255,.18);
              border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.topbar-logo svg{{width:20px;height:20px}}
.topbar-name{{font-size:16px;font-weight:700;letter-spacing:.03em}}
.topbar-sub{{font-size:10px;opacity:.7;margin-top:1px}}
.topbar-right{{margin-left:auto;text-align:right;font-size:10px;opacity:.75;line-height:1.5}}
.bottom-nav{{position:fixed;bottom:0;left:0;right:0;
             background:#fff;border-top:1px solid #E4E8F0;
             display:flex;z-index:200;
             padding-bottom:env(safe-area-inset-bottom)}}
.nav-tab{{flex:1;display:flex;flex-direction:column;align-items:center;
          justify-content:center;gap:3px;padding:10px 0;
          font-size:11px;color:#9BA3B8;cursor:pointer;
          border:none;background:none;font-family:inherit;transition:color .15s}}
.nav-tab.active{{color:#0055D4}}
.nav-tab svg{{width:22px;height:22px}}
.page{{display:none;padding:14px 14px 20px}}
.page.active{{display:block}}
.hero{{background:#0055D4;border-radius:20px;padding:20px;margin-bottom:14px;color:#fff}}
.hero-top{{display:flex;align-items:flex-start;gap:16px;margin-bottom:16px}}
.hero-score-circle{{flex-shrink:0;text-align:center}}
.hero-score-circle .num{{font-size:56px;font-weight:700;line-height:1;font-variant-numeric:tabular-nums}}
.hero-score-circle .num-lbl{{font-size:11px;opacity:.7;margin-top:2px}}
.hero-grade-badge{{display:inline-block;background:rgba(255,255,255,.2);
                   border-radius:8px;padding:3px 14px;font-size:24px;font-weight:700;margin-top:6px}}
.hero-right{{flex:1;min-width:0}}
.hero-visit{{font-size:11px;opacity:.7;margin-bottom:3px}}
.hero-rep{{font-size:18px;font-weight:700;margin-bottom:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hero-stats{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
.hero-stat{{background:rgba(255,255,255,.12);border-radius:10px;padding:8px 10px;text-align:center}}
.hero-stat .sv{{font-size:18px;font-weight:700}}
.hero-stat .sl{{font-size:10px;opacity:.75;margin-top:2px}}
.hero-grade-desc{{background:rgba(255,255,255,.1);border-radius:10px;padding:8px 12px;font-size:13px;opacity:.9;text-align:center}}
.card{{background:#fff;border-radius:16px;border:1px solid #E8ECF4;padding:16px;margin-bottom:12px}}
.card-title{{font-size:11px;font-weight:600;color:#9BA3B8;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px}}
.metric-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px}}
.metric-cell{{background:#fff;border-radius:14px;border:1px solid #E8ECF4;padding:14px 12px}}
.metric-cell .mlbl{{font-size:11px;color:#9BA3B8;margin-bottom:5px}}
.metric-cell .mval{{font-size:26px;font-weight:700;font-variant-numeric:tabular-nums;line-height:1}}
.metric-cell .msub{{font-size:11px;color:#9BA3B8;margin-top:3px}}
.dim-row{{padding:10px 0;border-bottom:1px solid #F2F4F8}}
.dim-row:last-child{{border:none}}
.dim-head{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px}}
.dim-label{{font-size:13px;color:#3A4258}}
.dim-score{{font-size:16px;font-weight:700}}
.dim-track{{height:6px;background:#EEF1F7;border-radius:3px;overflow:hidden}}
.dim-fill{{height:100%;border-radius:3px;transition:width 1s cubic-bezier(.22,1,.36,1)}}
.dim-cmt{{font-size:11px;color:#9BA3B8;margin-top:4px;line-height:1.5}}
.chart-wrap{{position:relative;width:100%}}
.turn{{display:flex;gap:9px;margin-bottom:12px}}
.turn-customer{{flex-direction:row-reverse}}
.av{{width:30px;height:30px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700}}
.turn-sales    .av{{background:#E8F0FF;color:#0055D4}}
.turn-customer .av{{background:#E3F7F0;color:#00A878}}
.turn-unknown  .av{{background:#EEF1F7;color:#9BA3B8}}
.bwrap{{max-width:78%}}
.bubble{{padding:9px 12px;font-size:13px;line-height:1.65;border-radius:4px 14px 14px 14px}}
.turn-sales    .bubble{{background:#F0F4FF;color:#1A2035}}
.turn-customer .bubble{{background:#0055D4;color:#fff;border-radius:14px 4px 14px 14px}}
.stage-badge{{display:inline-block;background:rgba(0,85,212,.1);color:#0055D4;font-size:10px;padding:1px 6px;border-radius:4px;margin-left:5px;vertical-align:middle}}
.turn-customer .stage-badge{{background:rgba(255,255,255,.25);color:#fff}}
.turn-meta{{font-size:10px;color:#BCC2D0;margin-top:3px;padding:0 2px}}
.sw-item{{display:flex;gap:10px;padding:9px 0;border-bottom:1px solid #F2F4F8;align-items:flex-start;font-size:13px}}
.sw-item:last-child{{border:none}}
.sw-icon{{width:20px;height:20px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;margin-top:1px}}
.sw-good .sw-icon{{background:#E3F7F0;color:#00A878}}
.sw-bad  .sw-icon{{background:#FEECEB;color:#E5483A}}
.improve-card{{background:#F8FAFF;border-radius:12px;padding:14px;margin-bottom:10px;border-left:3px solid #0055D4}}
.improve-orig{{font-size:12px;color:#9BA3B8;text-decoration:line-through;margin-bottom:5px}}
.improve-issue{{font-size:12px;color:#E5483A;margin-bottom:7px}}
.improve-new{{font-size:13px;color:#007A58;line-height:1.7;margin-bottom:5px}}
.improve-principle{{font-size:11px;color:#9BA3B8;font-style:italic}}
.script-block{{background:#F8FAFF;border-radius:12px;padding:12px 14px;margin-bottom:10px}}
.script-lbl{{font-size:10px;color:#9BA3B8;text-transform:uppercase;letter-spacing:.07em;margin-bottom:5px}}
.script-text{{font-size:13px;color:#1A2035;line-height:1.7}}
.script-text.highlight{{color:#0055D4;font-weight:500}}
.script-q{{font-size:13px;color:#1A2035;padding:3px 0;line-height:1.6}}
.timeline{{padding-left:18px;position:relative}}
.timeline::before{{content:'';position:absolute;left:6px;top:5px;bottom:5px;width:1.5px;background:#E4E8F0}}
.tl-item{{position:relative;padding:0 0 16px 16px}}
.tl-dot{{position:absolute;left:-13px;top:4px;width:9px;height:9px;border-radius:50%;background:#EEF1F7;border:2px solid #D0D6E4}}
.tl-item.done   .tl-dot{{background:#00A878;border-color:#00A878}}
.tl-item.active .tl-dot{{background:#0055D4;border-color:#0055D4}}
.tl-week{{font-size:12px;font-weight:600;color:#0055D4;margin-bottom:3px}}
.tl-action{{font-size:13px;color:#1A2035;line-height:1.6}}
.tl-metric{{font-size:11px;color:#9BA3B8;margin-top:3px}}
.notice{{border-radius:12px;padding:11px 14px;font-size:13px;margin-bottom:12px;display:flex;gap:8px;align-items:flex-start;line-height:1.6}}
.notice-amber{{background:#FEF3C7;color:#92580A}}
.notice-red{{background:#FEECEB;color:#B91C1C}}
.miss-tag{{display:inline-block;background:rgba(245,158,11,.2);color:#92580A;padding:1px 8px;border-radius:5px;font-size:12px;margin:0 2px}}
.summary-text{{font-size:13px;color:#3A4258;line-height:1.9;background:#F8FAFF;border-radius:12px;padding:14px;border-left:3px solid #0055D4}}
.hist-card{{display:flex;align-items:center;gap:12px;background:#fff;border-radius:14px;border:1px solid #E8ECF4;padding:12px 14px;margin-bottom:9px;cursor:pointer;transition:border-color .15s;-webkit-tap-highlight-color:transparent}}
.hist-card:active{{background:#F8FAFF;border-color:#0055D4}}
.hist-score{{width:52px;height:52px;border-radius:12px;flex-shrink:0;display:flex;flex-direction:column;align-items:center;justify-content:center}}
.hs-num{{font-size:20px;font-weight:700;line-height:1;font-variant-numeric:tabular-nums}}
.hs-grade{{font-size:11px;font-weight:600;margin-top:2px}}
.hist-info{{flex:1;min-width:0}}
.hist-name{{font-size:14px;font-weight:500;margin-bottom:2px}}
.hist-meta{{font-size:11px;color:#9BA3B8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-arrow{{font-size:20px;color:#C8CDD8;flex-shrink:0}}
.empty-state{{text-align:center;padding:40px 16px;color:#9BA3B8;font-size:14px}}
.muted{{color:#9BA3B8;font-size:12px}}
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-logo">
    <svg viewBox="0 0 20 20" fill="none">
      <rect x="2" y="5" width="16" height="11" rx="2" stroke="white" stroke-width="1.6"/>
      <path d="M5 9h10M5 12.5h6" stroke="white" stroke-width="1.6" stroke-linecap="round"/>
      <circle cx="15.5" cy="5.5" r="3" fill="#7FB3FF"/>
    </svg>
  </div>
  <div>
    <div class="topbar-name">正掌讯 AI 销售教练</div>
    <div class="topbar-sub">Sales Intelligence</div>
  </div>
  <div class="topbar-right">
    {_esc(r.get('rep_name',''))}<br>{_esc(r.get('visit_date',''))}
  </div>
</div>

<!-- 本次报告页 -->
<div class="page active" id="page-report">

  <!-- Hero 卡 -->
  <div class="hero">
    <div class="hero-top">
      <div class="hero-score-circle">
        <div class="num">{total}</div>
        <div class="num-lbl">综合评分</div>
        <div class="hero-grade-badge" style="color:{g_color}">{grade}</div>
      </div>
      <div class="hero-right">
        <div class="hero-visit">{_esc(r.get('visit_id',''))} · {_esc(r.get('customer_id',''))}</div>
        <div class="hero-rep">{_esc(r.get('rep_name',''))}</div>
        <div class="hero-stats">
          <div class="hero-stat"><div class="sv">{s_cnt}</div><div class="sl">销售话轮</div></div>
          <div class="hero-stat"><div class="sv">{c_cnt}</div><div class="sl">客户话轮</div></div>
          <div class="hero-stat"><div class="sv">{q_cnt}</div><div class="sl">提问次数</div></div>
          <div class="hero-stat"><div class="sv">{obj_cnt}</div><div class="sl">处理异议</div></div>
        </div>
      </div>
    </div>
    <div class="hero-grade-desc">{_esc(sc.get('grade_description',''))}</div>
  </div>

  {missing_banner}
  {critical_banner}

  <!-- 六维评分 -->
  <div class="card">
    <div class="card-title">六维评分</div>
    {dim_bars_html()}
  </div>

  <!-- 雷达图 -->
  <div class="card">
    <div class="card-title">能力雷达</div>
    <div class="chart-wrap" style="height:220px">
      <canvas id="teamRadarChart"></canvas>
    </div>
  </div>

  <!-- 优势 / 不足 -->
  <div class="card">
    <div class="card-title">优势 & 不足</div>
    {sw_html()}
  </div>

  <!-- 阶段分布 -->
  <div class="card">
    <div class="card-title">销售阶段分布</div>
    <div class="chart-wrap" style="height:180px">
      <canvas id="stageChart"></canvas>
    </div>
    <div style="font-size:12px;color:#9BA3B8;margin-top:8px">{_esc(stg.get('stage_summary',''))}</div>
  </div>

  <!-- 对话回放 -->
  <div class="card">
    <div class="card-title">对话回放</div>
    {dialogue_html()}
  </div>

  <!-- 话术改进 -->
  <div class="card">
    <div class="card-title">话术改进示例</div>
    {script_improve_html()}
  </div>

  <!-- 下次话术 -->
  <div class="card">
    <div class="card-title">下次拜访话术脚本</div>
    {next_script_html()}
  </div>

  <!-- 30天计划 -->
  <div class="card">
    <div class="card-title">30天提升计划</div>
    <div class="timeline">
      {plan_html()}
    </div>
  </div>

  <!-- 教练总结 -->
  <div class="card">
    <div class="card-title">教练辅导总结</div>
    <div class="summary-text">{_esc(sugg.get('coaching_summary',''))}</div>
  </div>

</div><!-- /page-report -->

<!-- 团队看板页 -->
<div class="page" id="page-team">
  <div class="metric-grid">
    <div class="metric-cell">
      <div class="mlbl">分析记录数</div>
      <div class="mval">{team_total}</div>
      <div class="msub">共计拜访</div>
    </div>
    <div class="metric-cell">
      <div class="mlbl">平均评分</div>
      <div class="mval">{team_avg}</div>
      <div class="msub">综合均值</div>
    </div>
    <div class="metric-cell">
      <div class="mlbl">最高评分</div>
      <div class="mval">{team_best}</div>
      <div class="msub">历史最优</div>
    </div>
    <div class="metric-cell">
      <div class="mlbl">本次评分</div>
      <div class="mval">{total}</div>
      <div class="msub">{grade} 级</div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">团队维度均值</div>
    {team_dim_bars_html()}
  </div>

  <div class="card">
    <div class="card-title">历史趋势</div>
    <div class="chart-wrap" style="height:180px">
      <canvas id="trendChart"></canvas>
    </div>
  </div>

  <div class="card">
    <div class="card-title">历史记录</div>
    {team_cards_html()}
  </div>
</div><!-- /page-team -->

<!-- 底部 Tab -->
<nav class="bottom-nav">
  <button class="nav-tab active" id="tab-report" onclick="switchTab('report')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
      <rect x="4" y="3" width="16" height="18" rx="2"/>
      <path d="M8 8h8M8 12h8M8 16h5" stroke-linecap="round"/>
    </svg>
    本次报告
  </button>
  <button class="nav-tab" id="tab-team" onclick="switchTab('team')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
      <circle cx="9" cy="7" r="3"/><circle cx="15" cy="7" r="3"/>
      <path d="M3 20c0-3.3 2.7-6 6-6h6c3.3 0 6 2.7 6 6" stroke-linecap="round"/>
    </svg>
    团队看板
  </button>
</nav>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
const BRAND="#0055D4",GREEN="#00A878";
const LABELS={dim_lbl_js};
const RADAR_D={radar_js};
const STAGE_D={stage_js};

function switchTab(t){{
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(b=>b.classList.remove('active'));
  document.getElementById('page-'+t).classList.add('active');
  document.getElementById('tab-'+t).classList.add('active');
}}

new Chart(document.getElementById('stageChart'),{{
  type:'bar',
  data:{{
    labels:['开场','需求探询','产品呈现','异议处理','成交推进','收场跟进'],
    datasets:[{{data:STAGE_D,backgroundColor:['#E8F0FF','#D1E4FF','#B5D4FF','#8FBBFF','#5C99FF',BRAND],borderRadius:5}}]
  }},
  options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}}}},
    scales:{{x:{{grid:{{display:false}},ticks:{{font:{{size:10}},maxRotation:30}}}},y:{{beginAtZero:true,ticks:{{stepSize:1,font:{{size:10}}}}}}}}
  }}
}});

new Chart(document.getElementById('teamRadarChart'),{{
  type:'radar',
  data:{{
    labels:LABELS,
    datasets:[
      {{label:'本次',data:RADAR_D,backgroundColor:'rgba(0,85,212,.08)',borderColor:BRAND,pointBackgroundColor:BRAND,pointRadius:3,borderWidth:2}},
      {{label:'团队均值',data:{team_radar_js},backgroundColor:'rgba(0,168,120,.08)',borderColor:GREEN,pointBackgroundColor:GREEN,pointRadius:3,borderWidth:2,borderDash:[4,3]}}
    ]
  }},
  options:{{responsive:true,maintainAspectRatio:false,
    scales:{{r:{{min:0,max:10,ticks:{{stepSize:2,font:{{size:10}},backdropColor:'transparent'}},pointLabels:{{font:{{size:11}}}}}}}},
    plugins:{{legend:{{display:true,position:'bottom',labels:{{font:{{size:11}},boxWidth:10,padding:12}}}}}}
  }}
}});

new Chart(document.getElementById('trendChart'),{{
  type:'line',
  data:{{
    labels:{trend_labels},
    datasets:[{{label:'综合评分',data:{trend_data_js},borderColor:BRAND,backgroundColor:'rgba(0,85,212,.08)',pointBackgroundColor:BRAND,pointRadius:4,fill:true,tension:0.35,borderWidth:2.5}}]
  }},
  options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}}}},
    scales:{{x:{{grid:{{display:false}},ticks:{{font:{{size:10}},maxRotation:40}}}},y:{{min:0,max:100,ticks:{{stepSize:20,font:{{size:10}}}}}}}}
  }}
}});
</script>
</body>
</html>"""
    return html


# ══════════════════════════════════════════════════════
# Web 上传界面 HTML
# ══════════════════════════════════════════════════════

def get_upload_page_html() -> str:
    """生成文件上传交互页面"""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>正掌讯 · AI 销售质检 - 文件上传</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif;
     background:#F0F3F9;color:#1A2035;min-height:100vh}

.topbar{background:#0055D4;color:#fff;height:54px;
        display:flex;align-items:center;padding:0 20px;gap:12px}
.topbar-logo{width:34px;height:34px;background:rgba(255,255,255,.18);
             border-radius:9px;display:flex;align-items:center;justify-content:center}
.topbar-logo svg{width:22px;height:22px}
.topbar-name{font-size:17px;font-weight:700}
.topbar-sub{font-size:11px;opacity:.7;margin-top:1px}

.container{max-width:560px;margin:0 auto;padding:24px 16px}

.welcome{background:#fff;border-radius:20px;border:1px solid #E8ECF4;
          padding:28px 24px;margin-bottom:20px;text-align:center}
.welcome-icon{width:64px;height:64px;background:linear-gradient(135deg,#0055D4,#3B82F6);
              border-radius:18px;display:flex;align-items:center;justify-content:center;
              margin:0 auto 16px}
.welcome-icon svg{width:36px;height:36px}
.welcome h1{font-size:22px;font-weight:700;margin-bottom:8px}
.welcome p{font-size:14px;color:#6B7280;line-height:1.7}

.upload-card{background:#fff;border-radius:20px;border:1px solid #E8ECF4;padding:24px;margin-bottom:16px}
.section-title{font-size:12px;font-weight:600;color:#9BA3B8;text-transform:uppercase;
               letter-spacing:.08em;margin-bottom:16px}

/* 文件拖拽区 */
.dropzone{border:2px dashed #CBD5E1;border-radius:14px;padding:32px 16px;
          text-align:center;cursor:pointer;transition:all .2s;position:relative;
          background:#F8FAFF}
.dropzone:hover,.dropzone.dragover{border-color:#0055D4;background:#EFF6FF}
.dropzone input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
.dz-icon{width:48px;height:48px;background:#E8F0FF;border-radius:12px;
          display:flex;align-items:center;justify-content:center;margin:0 auto 12px}
.dz-icon svg{width:26px;height:26px;color:#0055D4}
.dz-text{font-size:15px;font-weight:600;color:#3A4258;margin-bottom:6px}
.dz-hint{font-size:12px;color:#9BA3B8}

/* 文件预览 */
.file-preview{display:none;background:#F0F6FF;border-radius:12px;
               padding:14px 16px;margin-top:14px;align-items:center;gap:12px}
.file-preview.show{display:flex}
.fp-icon{width:40px;height:40px;background:#0055D4;border-radius:10px;flex-shrink:0;
          display:flex;align-items:center;justify-content:center}
.fp-icon svg{width:22px;height:22px;color:#fff}
.fp-info{flex:1;min-width:0}
.fp-name{font-size:14px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fp-size{font-size:12px;color:#6B7280;margin-top:2px}
.fp-del{width:28px;height:28px;border-radius:50%;background:#FEECEB;border:none;
         cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.fp-del svg{width:14px;height:14px;color:#E5483A}

/* 表单 */
.form-row{margin-bottom:14px}
.form-label{font-size:13px;font-weight:500;color:#3A4258;margin-bottom:6px;display:block}
.form-label span{color:#9BA3B8;font-weight:400}
.form-input{width:100%;padding:11px 14px;border:1.5px solid #E4E8F0;border-radius:10px;
            font-size:14px;font-family:inherit;color:#1A2035;background:#fff;
            transition:border-color .15s;outline:none}
.form-input:focus{border-color:#0055D4;box-shadow:0 0 0 3px rgba(0,85,212,.08)}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}

/* 文本粘贴区 */
.paste-divider{display:flex;align-items:center;gap:10px;margin:16px 0}
.pd-line{flex:1;height:1px;background:#E4E8F0}
.pd-text{font-size:12px;color:#9BA3B8;white-space:nowrap}
.paste-area{width:100%;padding:12px 14px;border:1.5px solid #E4E8F0;border-radius:10px;
            font-size:13px;font-family:inherit;color:#1A2035;background:#fff;resize:vertical;
            min-height:120px;transition:border-color .15s;outline:none;line-height:1.6}
.paste-area:focus{border-color:#0055D4;box-shadow:0 0 0 3px rgba(0,85,212,.08)}
.paste-area::placeholder{color:#BCC2D0}

/* 提交按钮 */
.btn-submit{width:100%;padding:15px;background:#0055D4;color:#fff;border:none;
             border-radius:12px;font-size:16px;font-weight:600;cursor:pointer;
             font-family:inherit;transition:background .15s;margin-top:4px}
.btn-submit:hover{background:#0047B3}
.btn-submit:disabled{background:#9BA3B8;cursor:not-allowed}

/* 进度状态 */
.progress-card{display:none;background:#fff;border-radius:20px;border:1px solid #E8ECF4;
               padding:28px 24px;margin-bottom:16px;text-align:center}
.progress-card.show{display:block}
.prog-icon{width:56px;height:56px;background:linear-gradient(135deg,#0055D4,#3B82F6);
            border-radius:16px;display:flex;align-items:center;justify-content:center;
            margin:0 auto 16px;animation:pulse 1.5s ease-in-out infinite}
@keyframes pulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.08);opacity:.85}}
.prog-title{font-size:17px;font-weight:700;margin-bottom:6px}
.prog-sub{font-size:13px;color:#6B7280;margin-bottom:20px}
.prog-steps{text-align:left}
.prog-step{display:flex;align-items:center;gap:10px;padding:8px 0;
            border-bottom:1px solid #F2F4F8;font-size:13px}
.prog-step:last-child{border:none}
.step-dot{width:20px;height:20px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:11px}
.step-pending{background:#EEF1F7;color:#9BA3B8}
.step-active{background:#0055D4;color:#fff;animation:pulse 1.2s infinite}
.step-done{background:#00A878;color:#fff}
.step-txt{flex:1;color:#3A4258}
.step-txt.done{color:#9BA3B8}

/* 错误提示 */
.error-banner{display:none;background:#FEECEB;border-radius:12px;padding:14px 16px;
              margin-bottom:16px;color:#B91C1C;font-size:13px;line-height:1.6}
.error-banner.show{display:block}

/* 成功跳转 */
.success-card{display:none;background:#fff;border-radius:20px;border:1px solid #E8ECF4;
              padding:28px 24px;margin-bottom:16px;text-align:center}
.success-card.show{display:block}
.suc-icon{width:64px;height:64px;background:#E3F7F0;border-radius:20px;
           display:flex;align-items:center;justify-content:center;margin:0 auto 16px}
.suc-icon svg{width:36px;height:36px;color:#00A878}
.suc-title{font-size:20px;font-weight:700;margin-bottom:8px}
.suc-sub{font-size:13px;color:#6B7280;margin-bottom:20px}
.btn-view{display:inline-block;padding:13px 32px;background:#0055D4;color:#fff;
           border-radius:12px;font-size:15px;font-weight:600;text-decoration:none}
.btn-again{display:inline-block;margin-left:10px;padding:13px 20px;background:#F0F3F9;
            color:#3A4258;border-radius:12px;font-size:15px;font-weight:600;cursor:pointer;border:none;font-family:inherit}
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-logo">
    <svg viewBox="0 0 20 20" fill="none">
      <rect x="2" y="5" width="16" height="11" rx="2" stroke="white" stroke-width="1.6"/>
      <path d="M5 9h10M5 12.5h6" stroke="white" stroke-width="1.6" stroke-linecap="round"/>
      <circle cx="15.5" cy="5.5" r="3" fill="#7FB3FF"/>
    </svg>
  </div>
  <div>
    <div class="topbar-name">正掌讯 AI 销售教练</div>
    <div class="topbar-sub">Sales Intelligence</div>
  </div>
</div>

<div class="container">

  <!-- 欢迎卡 -->
  <div class="welcome" id="welcome-block">
    <div class="welcome-icon">
      <svg viewBox="0 0 36 36" fill="none">
        <path d="M8 10h20M8 16h14M8 22h10" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
        <circle cx="28" cy="24" r="6" fill="#7FB3FF"/>
        <path d="M25.5 24l1.5 2 3-3" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <h1>销售拜访智能分析</h1>
    <p>上传销售对话文本文件（.txt），AI 将自动分析对话质量、识别销售阶段、评估销售技巧，并生成专业报告和改进建议。</p>
  </div>

  <!-- 错误提示 -->
  <div class="error-banner" id="error-banner"></div>

  <!-- 上传表单 -->
  <div class="upload-card" id="upload-form">
    <div class="section-title">上传对话文本</div>

    <!-- 拖拽上传 -->
    <div class="dropzone" id="dropzone">
      <input type="file" id="file-input" accept=".txt,.text" onchange="handleFileSelect(this)">
      <div class="dz-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
          <polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/>
          <polyline points="9 15 12 12 15 15"/>
        </svg>
      </div>
      <div class="dz-text">点击选择 或 拖拽文件至此</div>
      <div class="dz-hint">支持 .txt 文本文件 · 对话格式：销售：...  客户：...</div>
    </div>

    <!-- 文件预览 -->
    <div class="file-preview" id="file-preview">
      <div class="fp-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
      </div>
      <div class="fp-info">
        <div class="fp-name" id="fp-name">—</div>
        <div class="fp-size" id="fp-size">—</div>
      </div>
      <button class="fp-del" onclick="clearFile()" title="移除文件">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>

    <!-- 或直接粘贴 -->
    <div class="paste-divider">
      <div class="pd-line"></div>
      <div class="pd-text">或直接粘贴对话内容</div>
      <div class="pd-line"></div>
    </div>
    <textarea class="paste-area" id="paste-text"
      placeholder="销售：王老板您好，我是...&#10;客户：哦，小张啊...&#10;销售：明白，我先了解一下..."></textarea>

    <!-- 拜访信息 -->
    <div style="margin-top:20px">
      <div class="section-title">拜访信息 <span style="font-size:11px;text-transform:none;letter-spacing:0">（可选）</span></div>
      <div class="form-grid">
        <div class="form-row">
          <label class="form-label">销售姓名</label>
          <input class="form-input" id="rep-name" placeholder="如：张明" value="">
        </div>
        <div class="form-row">
          <label class="form-label">销售编号</label>
          <input class="form-input" id="rep-id" placeholder="如：R001" value="R001">
        </div>
        <div class="form-row">
          <label class="form-label">拜访编号</label>
          <input class="form-input" id="visit-id" placeholder="如：V001" value="">
        </div>
        <div class="form-row">
          <label class="form-label">客户编号</label>
          <input class="form-input" id="customer-id" placeholder="如：C001" value="C001">
        </div>
      </div>
      <div class="form-row">
        <label class="form-label">拜访日期 <span>（留空取今天）</span></label>
        <input class="form-input" id="visit-date" type="date" value="">
      </div>
    </div>

    <button class="btn-submit" id="btn-submit" onclick="submitAnalysis()">
      🚀 开始 AI 分析
    </button>
  </div>

  <!-- 进度卡 -->
  <div class="progress-card" id="progress-card">
    <div class="prog-icon">
      <svg viewBox="0 0 36 36" fill="none">
        <circle cx="18" cy="18" r="14" stroke="rgba(255,255,255,.3)" stroke-width="2"/>
        <path d="M10 18l5 5 11-11" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <div class="prog-title">AI 正在分析中…</div>
    <div class="prog-sub">请稍候，分析通常需要 30-60 秒</div>
    <div class="prog-steps">
      <div class="prog-step" id="step-1">
        <div class="step-dot step-pending" id="dot-1">1</div>
        <div class="step-txt" id="txt-1">文本预处理 · 分句 & 角色识别</div>
      </div>
      <div class="prog-step" id="step-2">
        <div class="step-dot step-pending" id="dot-2">2</div>
        <div class="step-txt" id="txt-2">销售阶段切分</div>
      </div>
      <div class="prog-step" id="step-3">
        <div class="step-dot step-pending" id="dot-3">3</div>
        <div class="step-txt" id="txt-3">关键行为标签提取</div>
      </div>
      <div class="prog-step" id="step-4">
        <div class="step-dot step-pending" id="dot-4">4</div>
        <div class="step-txt" id="txt-4">销售行为事实抽取</div>
      </div>
      <div class="prog-step" id="step-5">
        <div class="step-dot step-pending" id="dot-5">5</div>
        <div class="step-txt" id="txt-5">多维度 AI 评分</div>
      </div>
      <div class="prog-step" id="step-6">
        <div class="step-dot step-pending" id="dot-6">6</div>
        <div class="step-txt" id="txt-6">生成改进建议 & 话术脚本</div>
      </div>
    </div>
  </div>

  <!-- 成功卡 -->
  <div class="success-card" id="success-card">
    <div class="suc-icon">
      <svg viewBox="0 0 36 36" fill="none">
        <circle cx="18" cy="18" r="14" fill="#00A878" fill-opacity=".15"/>
        <path d="M11 18l5 5 9-9" stroke="#00A878" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <div class="suc-title">分析完成！</div>
    <div class="suc-sub">AI 报告已生成，点击下方查看详细分析结果</div>
    <a href="#" id="view-report-btn" class="btn-view" target="_blank">查看报告 →</a>
    <button class="btn-again" onclick="resetForm()">再分析一份</button>
  </div>

</div>

<script>
let selectedFile = null;
let pollingTimer = null;
let currentStep = 0;

// 初始化日期
document.getElementById('visit-date').value = new Date().toISOString().slice(0,10);

// 拖拽支持
const dz = document.getElementById('dropzone');
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('dragover'); });
dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
dz.addEventListener('drop', e => {
  e.preventDefault(); dz.classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (f) applyFile(f);
});

function handleFileSelect(input) {
  if (input.files[0]) applyFile(input.files[0]);
}

function applyFile(f) {
  if (!f.name.match(/\\.(txt|text)$/i)) {
    showError('请选择 .txt 格式的文本文件'); return;
  }
  selectedFile = f;
  document.getElementById('fp-name').textContent = f.name;
  document.getElementById('fp-size').textContent = (f.size / 1024).toFixed(1) + ' KB';
  document.getElementById('file-preview').classList.add('show');
  document.getElementById('paste-text').value = '';
  hideError();
}

function clearFile() {
  selectedFile = null;
  document.getElementById('file-preview').classList.remove('show');
  document.getElementById('file-input').value = '';
}

function showError(msg) {
  const el = document.getElementById('error-banner');
  el.textContent = '⚠ ' + msg; el.classList.add('show');
}
function hideError() {
  document.getElementById('error-banner').classList.remove('show');
}

function setStep(n) {
  if (n > currentStep) {
    for (let i = currentStep; i < n - 1; i++) {
      document.getElementById('dot-'+(i+1)).className = 'step-dot step-done';
      document.getElementById('dot-'+(i+1)).textContent = '✓';
      document.getElementById('txt-'+(i+1)).className = 'step-txt done';
    }
    if (n <= 6) {
      document.getElementById('dot-'+n).className = 'step-dot step-active';
    }
    currentStep = n;
  }
}

function resetSteps() {
  currentStep = 0;
  for (let i = 1; i <= 6; i++) {
    document.getElementById('dot-'+i).className = 'step-dot step-pending';
    document.getElementById('dot-'+i).textContent = i;
    document.getElementById('txt-'+i).className = 'step-txt';
  }
}

async function submitAnalysis() {
  hideError();
  const pasteText = document.getElementById('paste-text').value.trim();
  if (!selectedFile && !pasteText) {
    showError('请上传文本文件或直接粘贴对话内容'); return;
  }

  const repName   = document.getElementById('rep-name').value.trim() || '销售员';
  const repId     = document.getElementById('rep-id').value.trim()   || 'R001';
  let   visitId   = document.getElementById('visit-id').value.trim();
  const custId    = document.getElementById('customer-id').value.trim() || 'C001';
  const visitDate = document.getElementById('visit-date').value || new Date().toISOString().slice(0,10);

  if (!visitId) {
    visitId = 'V' + new Date().toISOString().slice(0,10).replace(/-/g,'') + '-' + Math.floor(Math.random()*900+100);
  }

  // 切换到进度界面
  document.getElementById('upload-form').style.display = 'none';
  document.getElementById('welcome-block').style.display = 'none';
  document.getElementById('progress-card').classList.add('show');
  resetSteps(); setStep(1);

  const formData = new FormData();
  if (selectedFile) {
    formData.append('file', selectedFile);
  } else {
    const blob = new Blob([pasteText], {type:'text/plain'});
    formData.append('file', blob, 'pasted_text.txt');
  }
  formData.append('rep_name',    repName);
  formData.append('rep_id',      repId);
  formData.append('visit_id',    visitId);
  formData.append('customer_id', custId);
  formData.append('visit_date',  visitDate);

  // 模拟步骤进度
  const stepTimes = [2000, 5000, 8000, 12000, 18000];
  stepTimes.forEach((t, i) => setTimeout(() => setStep(i + 2), t));

  try {
    const resp = await fetch('/analyze', { method: 'POST', body: formData });
    const data = await resp.json();

    // 完成所有步骤
    for (let i = 1; i <= 6; i++) {
      document.getElementById('dot-'+i).className = 'step-dot step-done';
      document.getElementById('dot-'+i).textContent = '✓';
    }

    setTimeout(() => {
      document.getElementById('progress-card').classList.remove('show');
      if (data.success) {
        document.getElementById('view-report-btn').href = data.report_url;
        document.getElementById('success-card').classList.add('show');
      } else {
        showError(data.error || '分析失败，请重试');
        document.getElementById('upload-form').style.display = 'block';
        document.getElementById('welcome-block').style.display = 'block';
      }
    }, 800);

  } catch(e) {
    document.getElementById('progress-card').classList.remove('show');
    showError('网络错误：' + e.message);
    document.getElementById('upload-form').style.display = 'block';
    document.getElementById('welcome-block').style.display = 'block';
  }
}

function resetForm() {
  document.getElementById('success-card').classList.remove('show');
  document.getElementById('upload-form').style.display = 'block';
  document.getElementById('welcome-block').style.display = 'block';
  clearFile();
  document.getElementById('paste-text').value = '';
  resetSteps();
}
</script>
</body>
</html>"""


# ══════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════

def run_pipeline(
    text:        str,
    visit_id:    str = "V001",
    rep_id:      str = "R001",
    rep_name:    str = "销售员",
    customer_id: str = "C001",
    visit_date:  str = "",
    open_browser: bool = True
) -> dict:
    print(f"\n{'═'*54}")
    print(f"  正掌讯 · AI 销售教练")
    print(f"  拜访编号: {visit_id} | 销售: {rep_name}")
    print(f"{'═'*54}\n")

    if not visit_date:
        visit_date = datetime.now().strftime("%Y-%m-%d")

    print("[1/6] 文本预处理：分句 + 角色识别 ...")
    sentences = split_sentences(text)
    dialogue  = build_dialogue(sentences)
    s_cnt = sum(1 for d in dialogue if d["speaker"] == "sales")
    c_cnt = sum(1 for d in dialogue if d["speaker"] == "customer")
    print(f"      → {len(dialogue)} 句  (销售 {s_cnt} / 客户 {c_cnt})")

    print("[2/6] 阶段切分 ...")
    stages = stage_segmentation(dialogue)
    missing = stages.get("missing_stages", [])
    if missing:
        m = {1:"开场",2:"需求探询",3:"产品呈现",4:"异议处理",5:"成交推进",6:"收场跟进"}
        print(f"      → ⚠  缺失: {[m.get(int(s) if isinstance(s,str) and s.isdigit() else s, str(s)) for s in missing]}")

    print("[3/6] 关键标签提取 ...")
    tags = extract_tags(dialogue)

    print("[4/6] 销售行为事实抽取 ...")
    facts = extract_facts(dialogue)

    print("[5/6] 多维度 AI 评分 ...")
    score = score_visit(facts, tags, stages)
    print(f"      → 综合评分 {score.get('total_score',0)} 分 ({score.get('grade','N/A')} 级)")

    print("[6/6] 生成改进建议 + 话术脚本 ...")
    suggestions = generate_suggestions(dialogue, score, facts)

    result = {
        "visit_id":    visit_id,  "rep_id":      rep_id,
        "rep_name":    rep_name,  "customer_id": customer_id,
        "visit_date":  visit_date,"dialogue":    dialogue,
        "stages":      stages,    "tags":        tags,
        "facts":       facts,     "score":       score,
        "suggestions": suggestions
    }
    history = load_history()

    OUTPUT_DIR.mkdir(exist_ok=True)
    html_path = OUTPUT_DIR / f"report_{visit_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

    row_id = save_result(
        visit_id, rep_id, rep_name, customer_id, visit_date,
        dialogue, stages, tags, facts, score, suggestions,
        html_path=str(html_path)
    )
    print(f"\n[DB] 已保存 (记录 ID: {row_id})")

    print("[HTML] 生成报告 ...")
    history_fresh = load_history()
    html_content  = generate_html_report(result, history_fresh)

    html_path.write_text(html_content, encoding="utf-8")
    print(f"[HTML] 报告已写入: {html_path.resolve()}\n")

    json_path = OUTPUT_DIR / f"report_{visit_id}.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if open_browser:
        webbrowser.open(html_path.resolve().as_uri())

    return result, html_path


# ══════════════════════════════════════════════════════
# Web 服务器
# ══════════════════════════════════════════════════════

class UploadHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # 简化日志输出
        print(f"[Web] {self.address_string()} - {format % args}")

    def do_GET(self):
        if self.path == "/" or self.path == "/upload":
            html = get_upload_page_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        elif self.path.startswith("/reports/"):
            # 提供报告文件
            fname = self.path[1:]  # 去掉开头斜杠
            fpath = Path(fname)
            if fpath.exists() and fpath.suffix == ".html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(fpath.read_bytes())
            else:
                self.send_error(404, "报告文件不存在")
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/analyze":
            self.send_error(404)
            return

        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            # 解析 multipart/form-data（纯标准库，兼容 Python 3.13+）
            fields = parse_multipart(body, content_type)

            # 读取文件字段内容（bytes）
            raw_bytes = fields.get("file", b"")
            if not raw_bytes:
                raise ValueError("未收到文件内容，请重新上传")

            # 自动检测编码
            text = None
            for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312", "big5"):
                try:
                    text = raw_bytes.decode(enc)
                    break
                except Exception:
                    continue
            if text is None:
                text = raw_bytes.decode("utf-8", errors="replace")

            def get_field(name, default=""):
                val = fields.get(name, b"")
                s = val.decode("utf-8", errors="replace").strip() if isinstance(val, bytes) else str(val).strip()
                return s if s else default

            rep_name    = get_field("rep_name",    "销售员")
            rep_id      = get_field("rep_id",      "R001")
            visit_id    = get_field("visit_id",    f"V{datetime.now().strftime('%Y%m%d')}-001")
            customer_id = get_field("customer_id", "C001")
            visit_date  = get_field("visit_date",  datetime.now().strftime("%Y-%m-%d"))

            print(f"\n[Web] 收到分析请求 visit_id={visit_id} rep={rep_name} 文本长度={len(text)}")

            # 在当前线程执行分析（同步，前端等待）
            init_db()
            result, html_path = run_pipeline(
                text        = text,
                visit_id    = visit_id,
                rep_id      = rep_id,
                rep_name    = rep_name,
                customer_id = customer_id,
                visit_date  = visit_date,
                open_browser= False
            )

            report_url = f"/reports/{html_path.as_posix()}"
            resp = json.dumps({"success": True, "report_url": report_url}, ensure_ascii=False)

        except Exception as e:
            import traceback
            traceback.print_exc()
            resp = json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(resp.encode("utf-8"))


def start_web_server(port: int = WEB_PORT):
    """启动 Web 上传服务"""
    init_db()
    OUTPUT_DIR.mkdir(exist_ok=True)
    server = HTTPServer(("0.0.0.0", port), UploadHandler)
    url = f"http://localhost:{port}"
    print(f"\n{'═'*54}")
    print(f"  正掌讯 · AI 销售教练 v2.0 - Web 上传模式")
    print(f"{'═'*54}")
    print(f"\n  🌐 上传界面已启动：{url}")
    print(f"  📂 报告输出目录：{OUTPUT_DIR.resolve()}")
    print(f"  ⌨  按 Ctrl+C 停止服务\n")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n[Web] 服务已停止。")
        server.shutdown()


# ══════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════

DEMO_TEXT = """销售：王老板您好，我是正康医药的小张，上个月来过一次，当时您提到心脑血管产品动销一般，我今天过来主要想看看最近有没有变化，也一起帮您分析下提升的方法。
客户：哦，小张啊。最近还是那样，心血管类整体卖得都不太好。
销售：明白，我先简单了解一下，目前您店里心血管类主要在卖哪些产品？像降压、降脂、保健调理这几类大概占比怎么样？
客户：降压药走得还可以，像氨氯地平这些处方外流的还行。保健类的就一般了，你们那个护心康卖得不多。
销售：好的，那护心康这边我想具体了解一下：最近一个月大概动销多少盒？是有陈列但顾客不主动问，还是店员推荐不多？
客户：一个月大概也就卖个10来盒吧，主要是顾客问的少，店员也不太主动推。
销售：明白，这种情况比较典型，我再确认两个点：来您店里的中老年顾客比例大概多少？有没有做过慢病会员管理或者健康档案？
客户：中老年大概占40%左右吧，会员是有，但没怎么精细管理。
销售：那其实是有空间的。像护心康这种产品，核心不是"等顾客问"，而是"围绕慢病人群做主动推荐"。我这边看到几个问题点：产品没有进入店员"优先推荐清单"，没有绑定高血压/高血脂人群做关联销售，没有做复购提醒（这类产品是典型复购型）。
客户：嗯，说得有点道理，但现在店员也比较忙，不太愿意多推。
销售：这个我理解，所以我们通常不是单纯让店员"多说话"，而是帮您降低推荐难度。比如我们在其他门店做的方式是：做一个"心血管联合用药推荐卡"（放在柜台），把护心康绑定"降压药+调理"组合，给店员一个简单话术（比如"这个可以长期保护心脏，很多老顾客都在吃"）。上个月在一个类似规模的药店，护心康从月销8盒做到28盒。
客户：提升这么多？那是他们店位置好吧。
销售：位置有影响，但不是核心。那个店一开始情况和您很像，关键是做了两件事：店员激励（每盒提成+1元），做了老会员回访（电话+微信提醒复购）。
客户：那成本也增加了吧？
销售：是的，但算账是正向的。比如：每盒增加1元激励，但销量从10盒→25盒，您毛利增加远大于激励成本，而且这类产品一旦形成复购，后面是持续收益。
客户：听起来可以试试，但我这边不太会搞这些。
销售：没问题，我可以帮您一起落地：帮您做一版"心血管联合推荐卡"，给店员做一个10分钟培训，帮您筛一批老会员做一次简单回访话术，我们先试一周，如果销量没有明显变化，您也没有损失。
客户：那可以，你先帮我弄一版看看。
销售：好的，那我今天先记录一下您目前库存和陈列情况，明天把物料和方案发您，这周我再过来帮店员过一遍。"""


def main():
    parser = argparse.ArgumentParser(
        description="正掌讯 · AI 销售教练系统 v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python voice_solution_mobile_v2.py                        # 启动 Web 上传界面（推荐）
  python voice_solution_mobile_v2.py --demo                 # 使用内置演示文字稿
  python voice_solution_mobile_v2.py --text 对话.txt        # 直接分析指定文件
  python voice_solution_mobile_v2.py --port 9000            # 指定 Web 端口
        """
    )
    parser.add_argument("--text",     type=str,  help="文字稿文件路径（.txt）")
    parser.add_argument("--demo",     action="store_true", help="使用内置演示文字稿分析")
    parser.add_argument("--web",      action="store_true", default=True, help="启动 Web 上传界面（默认）")
    parser.add_argument("--port",     type=int,  default=WEB_PORT, help=f"Web 服务端口（默认 {WEB_PORT}）")
    parser.add_argument("--visit-id", type=str,  default="", help="拜访编号")
    parser.add_argument("--rep-id",   type=str,  default="R001", help="销售人员ID")
    parser.add_argument("--rep",      type=str,  default="张明",  help="销售人员姓名")
    parser.add_argument("--customer", type=str,  default="C-王老板药店", help="客户ID")
    parser.add_argument("--date",     type=str,  default="", help="拜访日期 YYYY-MM-DD")
    parser.add_argument("--no-open",  action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    if args.text or args.demo:
        # CLI 模式：直接分析文件或演示文字稿
        if args.text:
            p = Path(args.text)
            if not p.exists():
                print(f"错误：文件不存在 → {args.text}")
                sys.exit(1)
            text = p.read_text(encoding="utf-8")
            print(f"[CLI] 读取文件：{p.resolve()}  ({len(text)} 字符)")
        else:
            text = DEMO_TEXT
            print("[CLI] 使用内置演示文字稿")

        visit_id = args.visit_id or f"V{datetime.now().strftime('%Y%m%d')}-001"
        init_db()
        run_pipeline(
            text        = text,
            visit_id    = visit_id,
            rep_id      = args.rep_id,
            rep_name    = args.rep,
            customer_id = args.customer,
            visit_date  = args.date,
            open_browser= not args.no_open
        )
    else:
        # Web 模式（默认）
        start_web_server(port=args.port)


if __name__ == "__main__":
    main()
