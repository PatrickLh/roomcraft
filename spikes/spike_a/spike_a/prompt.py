"""Spike A 提示词（版本化，评审后迭代必须升版本并复测全部样本）。"""

from __future__ import annotations

PROMPT_VERSION = "v3.1"

SYSTEM = "你是严谨的户型图结构化解析器。你只输出一个 JSON 对象，不输出任何解释、Markdown 代码块或多余文本。"

USER_TEMPLATE = """请把这张户型图解析为结构化 JSON。输出必须是下面两种之一：

【输出一：失败】若图片不是户型图、无法辨认、或图上没有任何尺寸标注：
{"failure": {"category": "<not_floor_plan|unreadable|no_scale_annotation>", "reason": "<一句话中文原因>"}}

【输出二：成功】符合下方 JSON Schema 的对象。

字段结构示例（字段名与层级必须与此完全一致，禁止发明字段如 x2/y2，禁止尾随逗号）：
{"schemaVersion":"0.1","meta":{"name":"示例","sourceType":"electronic","floorHeight":2.8},
 "walls":[
   {"id":"w1","p1":{"x":0,"y":0},"p2":{"x":4.2,"y":0},"thickness":0.24,
    "openings":[{"id":"o1","type":"window","t":1.0,"width":1.5,"height":1.5,"sill":0.9},
                {"id":"o2","type":"door","t":3.0,"width":0.9,"height":2.05,"sill":0}]},
   {"id":"w2","p1":{"x":0,"y":0},"p2":{"x":0,"y":3.6},"thickness":0.24,"openings":[]}],
 "rooms":[{"id":"r1","name":"客厅","polygon":[{"x":0,"y":0},{"x":4.2,"y":0},{"x":4.2,"y":3.6},{"x":0,"y":3.6}],"labelPosition":{"x":2.1,"y":1.8}}],
 "scale":{"references":[{"id":"s1","valueM":4.2,"p1":{"x":0,"y":0},"p2":{"x":4.2,"y":0},"source":"annotation"}]}}

工作方法（先读这里）：
0. 禁止做像素级测量与单位换算推演——那会消耗大量推理预算且不可靠。正确顺序：
   ① 从尺寸标注读出外廓与关键尺寸（各段标注之和 = 总长）；
   ② 按图中比例目测各内墙位置，构造一套自洽的米制坐标；
   ③ 输出前自检：每条 scale.references 的 valueM 与其 p1/p2 两点距离之差 ≤ 0.15 米。
1. 坐标系：单位米；原点为户型图左上角，x 向右增大，y 向下增大。所有坐标（墙、房间、标定）使用同一坐标系。
2. 尺寸标注的范围看「尺寸界线/箭头的起止」，不要只看文字所在位置——一条标注通常从一条墙延伸到另一条墙，文字只是居中放置。
3. 只识别四类元素：墙体、门、窗、房间名标签。降级规则：飘窗→按墙+窗处理并在 meta.unsupportedFeatures 加 "bay_window"；柱子→忽略并加 "column"；复式/跃层/楼梯→只解析可确认的底层结构并加 "duplex" 或 "stairs"。不要虚构不存在的结构。
4. 墙体：p1/p2 是墙中心线端点（Point2 对象，含 x 与 y 两个键）；thickness 外墙通常 0.24、内墙 0.12；门洞 height 约 2.05、sill 必须为 0；窗按图估 sill（常见 0.9）与 height（常见 1.2~1.5）。同一墙上的开口按 t（距 p1 距离）从小到大给出，不得重叠、不得超出墙长。
4b. 严格字段纪律：只使用 Schema 中定义的字段，禁止添加任何额外字段（如 door、swing、area、style、notes 等描述性键）——多余字段会导致整个 JSON 被拒绝。门的全部信息就是 openings 里 {"type":"door", ...} 这一项，不存在的键一律不要写。
5. 比例标定：从标注文本（如 "3600"、"4200"，单位毫米）读取真实长度，换算为米写入 scale.references：valueM 为真实长度，p1/p2 为该标注对应线段的两端点。必须至少 1 条，多条更好。若图上没有任何可靠尺寸标注：禁止估算比例，输出失败 JSON（category="no_scale_annotation"）。
6. meta.sourceType：图面规整的电子图填 "electronic"，翻拍/截图填 "photo"。
7. 房间：name 用图上原名（客厅/主卧/阳台…）；polygon 尽量给出；labelPosition 取名称文本位置。
8. 你不需要展示推理过程，直接给出最终 JSON。

JSON Schema（$defs 展开见属性定义）：
{schema}
"""


def build_user_prompt(schema_text: str) -> str:
    # 模板内含 JSON 花括号示例，不能用 str.format
    return USER_TEMPLATE.replace("{schema}", schema_text)
