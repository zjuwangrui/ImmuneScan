"""
Report writer: generates a rich markdown report from agent results,
calling the LLM once more to add plain-language explanations.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from openai import OpenAI


# ─────────────────────────────────────────────
#  Markdown table builders
# ─────────────────────────────────────────────

def _config_table(config: dict) -> str:
    rows = [
        ("LLM 模型",          config.get("llm_model", "N/A")),
        ("LLM 接口地址",      config.get("llm_base_url", "N/A")),
        ("候选肽段长度",      config.get("peptide_length", "N/A")),
        ("MCMC 步数",         config.get("mcmc_steps", "N/A")),
        ("MCMC 突变率",       config.get("mcmc_mutation_rate", "N/A")),
        ("MCMC 温度",         config.get("mcmc_temperature", "N/A")),
        ("MCMC 半衰期",       config.get("mcmc_half_life", "N/A")),
        ("MCMC 优化 Top-N",   config.get("top_n_for_mcmc", "N/A")),
        ("最终输出 Top-N",    config.get("top_n_output", "N/A")),
        ("输入文件",          config.get("input_file", "N/A")),
        ("输出目录",          config.get("output_dir", "N/A")),
    ]
    lines = ["| 参数 | 值 |", "|------|-----|"]
    for label, val in rows:
        lines.append(f"| {label} | `{val}` |")
    return "\n".join(lines)


def _mutations_table(mutations: List[Dict]) -> str:
    lines = [
        "| 基因 | 突变位置 | 野生型氨基酸 | 突变型氨基酸 | 上下文序列 |",
        "|------|----------|------------|------------|----------|",
    ]
    for m in mutations:
        lines.append(
            f"| {m.get('gene','?')} | {m.get('pos','?')} | "
            f"{m.get('wt','?')} | {m.get('mut','?')} | `{m.get('context','?')}` |"
        )
    return "\n".join(lines)


def _results_table(top10: List[Dict]) -> str:
    lines = [
        "| 排名 | 肽段序列 | 基因/突变 | ddG | MCMC Loss | IC50 (nM) | %Rank | 综合评分 |",
        "|------|---------|----------|-----|-----------|-----------|-------|---------|",
    ]
    for i, c in enumerate(top10, 1):
        peptide  = c.get("optimized_peptide", c.get("peptide", "?"))
        gene     = c.get("gene", "?")
        mutation = c.get("mutation", "?")
        ddg      = f"{c['ddG']:.3f}"             if c.get("ddG")             is not None else "N/A"
        mcmc     = f"{c['mcmc_loss']:.3f}"        if c.get("mcmc_loss")       is not None else "N/A"
        ic50     = f"{c['ic50']:.1f}"             if c.get("ic50")            is not None else "N/A"
        rank     = f"{c['percentile_rank']:.2f}"  if c.get("percentile_rank") is not None else "N/A"
        score    = f"{c.get('composite_score', 0):.4f}"
        lines.append(
            f"| {i} | `{peptide}` | {gene}/{mutation} | {ddg} | {mcmc} | {ic50} | {rank} | {score} |"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────
#  LLM narrative generation
# ─────────────────────────────────────────────

_NARRATIVE_PROMPT = """\
你是一位擅长将复杂生物医学研究转化为通俗报告的科学作家。
请为以下个性化肿瘤新抗原疫苗筛选结果撰写报告内容，面向患者家属或非专业读者，语言务必通俗。

【患者信息】
HLA 分型：{hla}
肿瘤突变：{mutations_json}

【筛选结果（Top 候选肽段）】
{candidates_json}

请返回一个 JSON 对象，包含以下字段（均为字符串）：
- background        : 200字以内，通俗介绍"个性化肿瘤新抗原疫苗"是什么、为什么重要
- agent_value       : 60字以内，说明用 AI Agent 自动完成此流程相比人工的优势
- pipeline_steps    : 对 4 步流水线的通俗说明（生成候选→深度学习打分→MCMC优化→HLA结合验证），每步 1-2 句话，用换行分隔
- results_interpretation : 对 Top 候选的通俗解读，重点解释 IC50、%Rank 的含义和为什么数值越低越好
- clinical_significance  : 100字以内，说明本报告对患者个性化治疗的潜在价值
- lead_candidate_highlight : 对排名第一的候选肽段做一句话亮点总结

只返回 JSON，不要任何额外内容。\
"""


def _llm_narrative(client: OpenAI, model: str,
                   hla: str, mutations: List[Dict], top10: List[Dict]) -> Dict[str, str]:
    prompt = _NARRATIVE_PROMPT.format(
        hla=hla,
        mutations_json=json.dumps(mutations, ensure_ascii=False, indent=2),
        candidates_json=json.dumps(top10, ensure_ascii=False, indent=2, default=str),
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as exc:
        print(f"  [report] LLM narrative failed: {exc}, using fallback text.")
        return {
            "background":              "个性化肿瘤新抗原疫苗基于患者肿瘤的特异性突变定制，有望实现精准免疫治疗。",
            "agent_value":             "AI Agent 全自动完成四步流水线，分钟级出结果，无需人工干预。",
            "pipeline_steps":          "1. 生成候选肽段\n2. 深度学习评分\n3. MCMC 优化\n4. HLA 结合验证",
            "results_interpretation":  "IC50 越低、%Rank 越小，代表肽段与 HLA 结合越紧密，更适合作为疫苗候选。",
            "clinical_significance":   "本报告可为临床个性化疫苗设计提供计算辅助决策参考。",
            "lead_candidate_highlight": "排名第一的候选肽段综合评分最高，建议优先考虑。",
        }


# ─────────────────────────────────────────────
#  Main entry
# ─────────────────────────────────────────────

def write_report(
    hla: str,
    mutations: List[Dict],
    top10: List[Dict],
    agent_report: str,
    config: dict,
) -> Path:
    """
    Assemble a rich markdown report and save to output_dir/reports/.
    Returns the path to the written file.
    """
    reports_dir = Path(config["output_dir"]) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    now       = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M")
    out_path  = reports_dir / f"{timestamp}_neoantigen_report.md"

    print("  [report] Calling LLM for narrative enrichment…")
    client    = OpenAI(api_key=config["llm_api_key"], base_url=config["llm_base_url"])
    narrative = _llm_narrative(client, config["llm_model"], hla, mutations, top10)

    sections = [
        f"# 个性化肿瘤新抗原疫苗候选筛选报告",
        f"",
        f"> **生成时间：** {now.strftime('%Y-%m-%d %H:%M')}",
        f"> **患者 HLA 分型：** `{hla}`",
        f"> **肿瘤突变数：** {len(mutations)} 个",
        f"> **最终候选数：** {len(top10)} 个",
        f"",
        f"---",
        f"",
        f"## 一、项目背景与意义",
        f"",
        narrative["background"],
        f"",
        f"**为什么用 AI Agent？** {narrative['agent_value']}",
        f"",
        f"---",
        f"",
        f"## 二、运行配置",
        f"",
        _config_table(config),
        f"",
        f"---",
        f"",
        f"## 三、输入数据",
        f"",
        f"**患者 HLA 分型：** `{hla}`",
        f"",
        f"### 肿瘤突变列表",
        f"",
        _mutations_table(mutations),
        f"",
        f"> 输入文件：`{config.get('input_file', 'N/A')}`",
        f"",
        f"---",
        f"",
        f"## 四、流水线执行过程",
        f"",
        narrative["pipeline_steps"],
        f"",
        f"---",
        f"",
        f"## 五、候选结果",
        f"",
        f"### Top 候选肽段排名",
        f"",
        _results_table(top10),
        f"",
        f"> **亮点：** {narrative['lead_candidate_highlight']}",
        f"",
        f"### 结果解读",
        f"",
        narrative["results_interpretation"],
        f"",
        f"---",
        f"",
        f"## 六、临床意义",
        f"",
        narrative["clinical_significance"],
        f"",
        f"---",
        f"",
        f"## 七、Agent 完整报告（原文）",
        f"",
        agent_report.strip(),
        f"",
        f"---",
        f"",
        f"## 八、原始候选数据",
        f"",
        f"```json",
        json.dumps(top10, indent=2, default=str, ensure_ascii=False),
        f"```",
        f"",
    ]

    out_path.write_text("\n".join(sections), encoding="utf-8")
    return out_path
