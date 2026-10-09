# Spike 样本库

Spike A 用的真实户型图样本放本目录。**M0-01 要求至少 10 张获授权的真实户型图**，
来源可以是：自家/亲友购房资料、经同意的中介宣传图、公开楼盘资料（记录出处）。

## 文件命名

```
NNN_<electronic|photo>_<简短描述>.<jpg|png|webp>
NNN_<electronic|photo>_<简短描述>.yaml   ← 每张图一个同名 sidecar 元数据
```

- `NNN`：三位序号（001、002…）
- `electronic`：电子户型图（开发商宣传图、中介电子图，图面横平竖直）
- `photo`：手机翻拍纸图或截图（可能有透视/光照问题）

示例：`001_electronic_xx小区两房.jpg`

## Sidecar 字段

```yaml
source: "xx小区购房资料（已获业主同意）"   # 授权来源，必填
has_annotation: true        # 图上是否有尺寸标注
expected_rooms: 3           # 人工数出的房间数（评审基准）
notes: "北向客厅，标准两房"  # 备注
```

## 注意

- `000_synth_smoke_electronic.png` 是**合成冒烟样本**（由 `make_synthetic.py` 生成），
  只用于验证管线能跑通，**不计入 10 张真实样本、不参与可用率统计**。
- 不要提交含个人信息的购房合同页；只提交户型图本身。
- 真实样本到位前，`pnpm spike:smoke`（mock provider）可用于验证脚本链路。
