"""Spike A 提示词（版本化，评审后迭代必须升版本并复测全部样本）。"""

from __future__ import annotations

PROMPT_VERSION = "v1"

SYSTEM = "你是严谨的户型图结构化解析器。你只输出一个 JSON 对象，不输出任何解释、Markdown 代码块或多余文本。"

USER_TEMPLATE = """请把这张户型图解析为结构化 JSON。输出必须是下面两种之一：

【输出一：失败】若图片不是户型图、无法辨认、或（见规则 4）无法标定比例：
{"failure": {"category": "<not_floor_plan|unreadable|no_scale_annotation>", "reason": "<一句话中文原因>"}}

【输出二：成功】符合下方 JSON Schema 的对象。

规则：
1. 坐标系：单位米；原点为户型图左上角，x 向右增大，y 向下增大。所有坐标（墙、房间、标定）使用同一坐标系。
2. 只识别四类元素：墙体、门、窗、房间名标签。降级规则：飘窗→按墙+窗处理并在 meta.unsupportedFeatures 加 "bay_window"；柱子→忽略并加 "column"；复式/跃层/楼梯→只解析可确认的底层结构并加 "duplex" 或 "stairs"。不要虚构不存在的结构。
3. 墙体：p1/p2 是墙中心线端点；thickness 外墙通常 0.24、内墙 0.12，按图判断；门洞 height 约 2.05、sill 必须为 0；窗按图估 sill（常见 0.9）与 height（常见 1.2~1.5）。同一墙上的开口按 t（距 p1 距离）从小到大给出，不得重叠、不得超出墙长。
4. 比例标定（最重要）：从图上的尺寸标注文本（如 "3600"、"4200"）读取真实长度，换算为米写入 scale.references：valueM 为真实长度，p1/p2 为该标注对应线段在坐标系中的两端点。必须给出至少 1 条；多条更好。若图上没有任何可靠尺寸标注：禁止估算比例，直接输出失败 JSON（category="no_scale_annotation"）。标注值必须与你给出的几何线段长度一致（偏差不超过 0.15 米），否则视为解析错误。
5. meta.sourceType：图面规整的电子图填 "electronic"，翻拍/截图填 "photo"。
6. 房间：name 用图上原名（客厅/主卧/阳台…）；polygon 尽量给出；labelPosition 取名称文本位置。

JSON Schema（$defs 展开见属性定义）：
{schema}
"""

def build_user_prompt(schema_text: str) -> str:
    # 模板内含 JSON 花括号示例，不能用 str.format
    return USER_TEMPLATE.replace("{schema}", schema_text)
