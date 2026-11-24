# 示例输入

本目录用于放置本地鞋垫输入文件，仓库不提交原始 STL 或扫描件。

## 两种数据来源

本项目支持两种输入模式，在 `config/zone_params.json` 的 `inputs` 中通过 `mode` 字段切换：

### 模式一：`insole_solid`（现有封闭鞋垫 STL）

如果你已经有完整的鞋垫 3D 模型（水密封闭体）：

```json
{
  "name": "left",
  "path": "input/left_insole.stl",
  "mode": "insole_solid",
  "side": "left"
}
```

- 来源：CAD 建模软件导出、已有鞋垫 STL 文件
- 预处理：此模式跳过预处理，直接复用原始 STL

### 模式二：`plantar_scan_surface`（脚底直扫开放曲面 STL）

如果你用 iPhone/FaceID 类 App 扫描了脚底表面：

```json
{
  "name": "left",
  "path": "input/left_plantar_scan.stl",
  "mode": "plantar_scan_surface",
  "side": "left"
}
```

- 来源：3D 扫描 App（如 Polycam、Scaniverse 等）导出的脚底曲面
- 预处理：`prepare_inputs.py` 会将开放曲面封闭为可打印的鞋垫坯体。轮廓按 `outline_margin_mm` 等距外扩，底面为平底，顶面跟随扫描，相对最低点的拱起默认不超过 `scan_preprocess.max_relief_mm`（`8.0`）
- 注意：需要确认 `scan_preprocess.*` 坐标轴参数与 App 输出一致

## 本地文件

建议将你自己的输入文件放在这里，或者在 `config/zone_params.json` 里填写任意可解析路径。

- `left_insole.stl`：左脚封闭鞋垫输入示例名
- `right_insole.stl`：右脚封闭鞋垫输入示例名
- `left_plantar_scan.stl`：左脚脚底扫描输入示例名
- `right_plantar_scan.stl`：右脚脚底扫描输入示例名

这些文件名仅用于说明配置约定，不随仓库提交。

## 快速切换示例

完整配置示例（左脚用封闭 STL、右脚用直扫）：

```json
"inputs": [
  {
    "name": "left",
    "path": "input/left_insole.stl",
    "mode": "insole_solid",
    "side": "left"
  },
  {
    "name": "right",
    "path": "input/right_plantar_scan.stl",
    "mode": "plantar_scan_surface",
    "side": "right"
  }
]
```

每个输入的模式独立，可混合使用。
