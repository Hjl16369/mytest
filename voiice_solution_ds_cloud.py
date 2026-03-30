"""
正掌讯 · AI 销售质检系统 v2.0 - Streamlit 云端版
支持文件上传、文本粘贴，自动分析并生成报告，支持历史记录和团队看板。

运行方式：
    streamlit run app_streamlit.py
"""

import re
import json
import sqlite3
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
import requests
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ══════════════════════════════════════════════════════
# 配置区
# ══════════════════════════════════════════════════════
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "sk-c4bbfc49d1a84880ae3241dff77a9e8f")
DB_PATH           = "sales_ai.db"
OUTPUT_DIR        = Path("reports")          # HTML 报告输出目录
MODEL             = "qwen-plus"


# ══════════════════════════════════════════════════════
# Step 1  文本预处理（增强版：支持标签+多行正文格式）
# ══════════════════════════════════════════════════════

def split_sentences(text: str) -> list:
    """
    增强版分句：正确处理“标签行 + 多行正文”的格式，确保每条句子都带有说话者前缀。
    支持纯标签行（如“销售：”）后跟多行正文，直到遇到下一个标签或文件结束。
    """
    lines = text.strip().split("\n")
    out = []
    current_speaker = None   # 当前说话者前缀，例如“销售：”
    buffer = []               # 缓存当前说话者的多行正文

    # 正则匹配纯标签行（可能包含前后空白，但标签单独成行）
    tag_pattern = re.compile(r'^\s*(客户|顾客|买方|销售|业务|销售员|代表|客|销)[：:]\s*$')

    for line in lines:
        line = line.rstrip('\n')
        if not line.strip():
            # 空行：可视为段落分隔，但不丢失当前说话者（根据需求可清空buffer，这里保留）
            # 为了保持连贯性，暂时跳过空行，不清buffer，让正文连续
            continue

        tag_match = tag_pattern.match(line)
        if tag_match:
            # 遇到新的标签行：先处理之前的缓存内容
            if buffer and current_speaker:
                full_body = ' '.join(buffer).strip()
                if full_body:
                    # 按标点切分正文为句子
                    parts = re.split(r'(?<=[。！？…])', full_body)
                    for p in parts:
                        p = p.strip()
                        if p:
                            out.append(current_speaker + p)
                buffer = []
            # 更新当前说话者
            current_speaker = tag_match.group(1) + '：'  # 统一使用中文冒号
        else:
            # 正文行：如果有当前说话者，则加入buffer；否则按原逻辑处理（无前缀）
            if current_speaker:
                # 去除行首可能的说话者前缀残留（如“客户：”被误判为正文）
                cleaned = re.sub(r'^(客户|顾客|买方|销售|业务|销售员|代表|客|销)[：:]', '', line).strip()
                buffer.append(cleaned)
            else:
                # 没有说话者信息，使用原逻辑（按行匹配前缀并切分）
                m = re.match(r'^((?:客户|顾客|买方|销售|业务|销售员|代表|客|销)[：:])\s*', line)
                prefix = m.group(0) if m else ""
                body = line[len(prefix):] if prefix else line
                parts = re.split(r'(?<=[。！？…])', body)
                for p in parts:
                    p = p.strip()
                    if p:
                        out.append(prefix + p)

    # 处理最后一段缓存
    if buffer and current_speaker:
        full_body = ' '.join(buffer).strip()
        if full_body:
            parts = re.split(r'(?<=[。！？…])', full_body)
            for p in parts:
                p = p.strip()
                if p:
                    out.append(current_speaker + p)

    return out


def identify_speaker(sentence: str) -> str:
    """
    识别说话者：优先通过句子开头的前缀判断，若无则回退到关键词匹配。
    """
    s = sentence.strip()
    # 先检查前缀
    if re.match(r'^(客户|顾客|买方|客)[：:]', s):
        return "customer"
    if re.match(r'^(销售|业务|销售员|代表|销)[：:]', s):
        return "sales"

    # 回退：关键词匹配
    sales_kw    = ["我们公司","我们产品","我来介绍","我们可以","这款产品","推荐您","我们这边","给您","合作","方案"]
    customer_kw = ["你们价格","太贵了","考虑一下","别家","你们的","有没有优惠","我需要","我再想想"]
    sc = sum(1 for k in sales_kw    if k in s)
    cc = sum(1 for k in customer_kw if k in s)
    if sc > cc: return "sales"
    if cc > sc: return "customer"
    return "unknown"


def clean_prefix(s: str) -> str:
    """去除句子开头的说话者前缀（如“销售：”）"""
    return re.sub(r'^(客户|顾客|买方|销售|业务|销售员|代表|客|销)[：:]\s*', '', s).strip()


def build_dialogue(sentences: list) -> list:
    """
    根据带前缀的句子构建对话列表，每条包含 speaker 和 text（已去前缀）。
    """
    out = []
    for s in sentences:
        speaker = identify_speaker(s)
        text = clean_prefix(s)
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


@st.cache_data(ttl=3600)
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
# Step 5  HTML 报告生成器（保持不变）
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
# Streamlit 应用主体
# ══════════════════════════════════════════════════════

def run_pipeline(
    text:        str,
    visit_id:    str = "V001",
    rep_id:      str = "R001",
    rep_name:    str = "销售员",
    customer_id: str = "C001",
    visit_date:  str = "",
) -> tuple[dict, Path]:
    """执行完整分析流程，返回结果和 HTML 文件路径"""
    print(f"\n{'═'*54}")
    print(f"  正掌讯 · AI 销售教练")
    print(f"  拜访编号: {visit_id} | 销售: {rep_name}")
    print(f"{'═'*54}\n")

    if not visit_date:
        visit_date = datetime.now().strftime("%Y-%m-%d")

    st.write("**[1/6] 文本预处理：分句 + 角色识别 ...**")
    sentences = split_sentences(text)
    dialogue  = build_dialogue(sentences)
    s_cnt = sum(1 for d in dialogue if d["speaker"] == "sales")
    c_cnt = sum(1 for d in dialogue if d["speaker"] == "customer")
    st.write(f"      → {len(dialogue)} 句  (销售 {s_cnt} / 客户 {c_cnt})")

    st.write("**[2/6] 阶段切分 ...**")
    stages = stage_segmentation(dialogue)
    missing = stages.get("missing_stages", [])
    if missing:
        m = {1:"开场",2:"需求探询",3:"产品呈现",4:"异议处理",5:"成交推进",6:"收场跟进"}
        st.write(f"      → ⚠  缺失: {[m.get(int(s) if isinstance(s,str) and s.isdigit() else s, str(s)) for s in missing]}")

    st.write("**[3/6] 关键标签提取 ...**")
    tags = extract_tags(dialogue)

    st.write("**[4/6] 销售行为事实抽取 ...**")
    facts = extract_facts(dialogue)

    st.write("**[5/6] 多维度 AI 评分 ...**")
    score = score_visit(facts, tags, stages)
    st.write(f"      → 综合评分 {score.get('total_score',0)} 分 ({score.get('grade','N/A')} 级)")

    st.write("**[6/6] 生成改进建议 + 话术脚本 ...**")
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

    st.write("**[HTML] 生成报告 ...**")
    history_fresh = load_history()
    html_content  = generate_html_report(result, history_fresh)

    html_path.write_text(html_content, encoding="utf-8")
    st.write(f"[HTML] 报告已写入: {html_path.resolve()}")

    json_path = OUTPUT_DIR / f"report_{visit_id}.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result, html_path


def streamlit_app():
    st.set_page_config(page_title="正掌讯 AI 销售教练", layout="wide")
    st.title("正掌讯 AI 销售教练")
    st.markdown("上传销售对话文本文件或直接粘贴内容，AI 将自动分析并生成专业报告。")

    # 侧边栏配置
    with st.sidebar:
        st.header("配置")
        api_key = st.text_input("DASHSCOPE_API_KEY", value=DASHSCOPE_API_KEY, type="password")
        if api_key:
            os.environ["DASHSCOPE_API_KEY"] = api_key
        st.markdown("---")
        st.markdown("### 历史记录")
        history = load_history()
        if history:
            df = pd.DataFrame(history)
            st.dataframe(df[["visit_id", "rep_name", "visit_date", "total_score", "grade"]])
        else:
            st.info("暂无历史记录")

    # 主区域：文件上传和文本粘贴
    # 使用 st.session_state 存储对话内容，避免选项卡局部变量问题
    if "text_content" not in st.session_state:
        st.session_state.text_content = ""

    tab1, tab2 = st.tabs(["📁 上传文件", "✏️ 粘贴文本"])
    with tab1:
        uploaded_file = st.file_uploader("选择 .txt 文件", type=["txt"])
        if uploaded_file is not None:
            text = uploaded_file.read().decode("utf-8", errors="replace")
            st.session_state.text_content = text
            st.text_area("文件内容预览", text, height=200)
    with tab2:
        paste_text = st.text_area("直接粘贴对话内容", height=300, placeholder="销售：...\n客户：...")
        if paste_text:
            st.session_state.text_content = paste_text

    # 拜访信息表单
    col1, col2, col3 = st.columns(3)
    with col1:
        rep_name = st.text_input("销售姓名", value="销售员")
        rep_id = st.text_input("销售编号", value="R001")
    with col2:
        visit_id = st.text_input("拜访编号", value=f"V{datetime.now().strftime('%Y%m%d')}-001")
        customer_id = st.text_input("客户编号", value="C001")
    with col3:
        visit_date = st.date_input("拜访日期", value=datetime.now().date())
        visit_date_str = visit_date.strftime("%Y-%m-%d")

    if st.button("🚀 开始 AI 分析", type="primary"):
        text = st.session_state.text_content
        if not text:
            st.error("请先上传文件或粘贴对话内容")
        else:
            with st.spinner("AI 分析中，请稍候..."):
                try:
                    result, html_path = run_pipeline(
                        text=text,
                        visit_id=visit_id,
                        rep_id=rep_id,
                        rep_name=rep_name,
                        customer_id=customer_id,
                        visit_date=visit_date_str
                    )
                    st.success("分析完成！")
                    # 显示报告摘要
                    st.subheader("报告摘要")
                    score = result["score"]
                    st.metric("综合评分", f"{score.get('total_score',0)}", delta=None)
                    st.write(f"评级：{score.get('grade', '-')}")
                    st.write(f"优点：{', '.join(score.get('strengths', []))}")
                    st.write(f"不足：{', '.join(score.get('weaknesses', []))}")

                    # 提供下载链接
                    with open(html_path, "rb") as f:
                        st.download_button(
                            label="📥 下载完整报告 (HTML)",
                            data=f,
                            file_name=html_path.name,
                            mime="text/html"
                        )
                    # 嵌入报告
                    with st.expander("查看完整报告 (嵌入)", expanded=False):
                        st.components.v1.html(html_path.read_text(encoding="utf-8"), height=800, scrolling=True)
                except Exception as e:
                    st.error(f"分析失败：{str(e)}")
                    raise


if __name__ == "__main__":
    init_db()
    streamlit_app()