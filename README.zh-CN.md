# 研究驱动的鞋垫分区与晶格工作流

本项目用于基于左右脚鞋垫 `STL`，生成适合切片器控制的分区 `3MF`、带局部参数的拓竹工程 `3MF`，以及可直接打印的 TPMS/gyroid 晶格鞋垫 `STL`。

默认分区采用研究驱动的解剖区域模型：

- `innerHeel`
- `outerHeel`
- `innerArch`
- `outerArch`
- `innerForefoot`
- `centralForefoot`
- `outerForefoot`
- `toe`
- `edgeFrame`

这套分区的目标是把常见的足底高压区域、足弓支撑区和外轮廓稳固区拆开处理。当前仓库默认模板面向 `健康成年亚洲男性` 的 `日常步行 + 轻运动` 混合场景，同时保留 profile 切换能力以适配不同用户需求。

## 项目目标

- 从现有鞋垫 `STL` 自动生成分区结果，不依赖交互式建模软件
- 在切片器中用 modifier 控制不同区域的填充方式和密度
- 保留一条可直接导出真实晶格 `STL` 的打印路径
- 让参数、分区和导出流程都可脚本化复现

## 设计依据

本项目的默认分区和参数不是医学处方，而是基于公开文献中的通用设计规律提炼出的工程默认值。当前默认模板主要参考：

- 健康无症状男性使用不同鞋垫后的足底压力重分布
- 正常青年华人在静态和步行状态下的足底压力基线
- 足弓支撑、总接触和多孔结构对压力再分配的通用规律
- 外轮廓稳固区对切片稳定性和打印耐久性的工程需求

简短参考来源见 `REFERENCES.zh-CN.md`。

## 数据来源切换

本项目支持两种输入数据来源，每个输入可独立选择模式，也可混合使用。

### 数据来源一：现有封闭鞋垫 STL（`insole_solid`）

适用场景：你已有完整的鞋垫 3D 模型（水密封闭体），例如 CAD 软件设计导出的 STL。

```json
{
  "name": "left",
  "path": "input/left_insole.stl",
  "mode": "insole_solid",
  "side": "left"
}
```

- 此模式下 `prepare_inputs.py` 会跳过预处理，直接复用原始 STL
- 无需配置 `scan_preprocess` 相关参数

### 数据来源二：脚底直扫开放曲面 STL（`plantar_scan_surface`）

适用场景：你用 3D 扫描 App（如 Polycam、Scaniverse 等）扫描了脚底表面，得到的是**开放曲面**而非封闭体。

```json
{
  "name": "left",
  "path": "input/left_plantar_scan.stl",
  "mode": "plantar_scan_surface",
  "side": "left"
}
```

- 此模式下 `prepare_inputs.py` 会将开放曲面封闭为可打印的鞋垫坯体
- 轮廓按 `outline_margin_mm` 等距外扩；底面为平底，顶面跟随扫描
- `scan_preprocess.max_relief_mm` 默认 `8.0`，限制相对最低点的拱起；准备报告里有厚度范围
- **必须配置** `scan_preprocess` 坐标轴参数，确保与 App 导出坐标系一致
- 推荐坐标约定：脚宽为 X、脚长为 Y、足底高度/鞋垫厚度为 Z

### 混合使用示例

左右脚可以使用不同数据来源：

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

### 切换步骤总结

1. 将 STL 文件放到 `input/` 目录（或任意可解析路径）
2. 编辑 `config/zone_params.json` 的 `inputs` 部分
3. 如果是直扫数据，确认 `scan_preprocess.*` 坐标参数匹配
4. 运行 `python scripts/prepare_inputs.py` 验证预处理结果

## 目录结构

- `config/zone_params.json`：主配置文件
- `scripts/prepare_inputs.py`：把直扫脚底表面预处理为封闭鞋垫坯体
- `scripts/inspect_mesh.py`：检查 STL 尺寸、包围盒、水密性并导出预览
- `scripts/build_zones.py`：生成研究驱动的解剖分区和分区预览
- `scripts/generate_tpms.py`：按分区阈值生成 gyroid 体素场
- `scripts/clip_lattice.py`：把体素晶格裁剪进鞋垫外形并导出最终 STL
- `scripts/export_result.py`：验证导出的最终 STL
- `scripts/export_zoned_3mf.py`：导出基础鞋垫 + modifier 分区几何的普通 `3MF`
- `scripts/export_bambu_project_3mf.py`：基于模板导出带局部切片参数的拓竹工程 `3MF`
- `scripts/run_pipeline.py`：按顺序运行整条流程
- `tests/`：核心逻辑回归测试
- `bootstrap_uv.ps1`：使用 `uv` 初始化本地虚拟环境

## 快速开始

### 1. 安装依赖

**推荐方式（跨平台）：使用 uv**

[uv](https://github.com/astral-sh/uv) 是一个快速的 Python 包管理器，支持 Windows / macOS / Linux。

安装 uv 后，在项目目录下运行：

```powershell
# Windows
.\bootstrap_uv.ps1
```

```bash
# macOS / Linux
uv venv --python 3.12 && uv pip install -r requirements.txt
```

**备选方式：直接用 pip**

如果你已经有可用的 Python，也可以直接：

```bash
python -m pip install -r requirements.txt
```

### 2. 运行整条流程

```bash
python scripts/run_pipeline.py
```

如果你想用自己的输入文件而不编辑配置文件：

```bash
# 替换左右脚输入路径
python scripts/run_pipeline.py \
  --input "left=input/my_left.stl,mode=insole_solid,side=left" \
  --input "right=input/my_right.stl,mode=insole_solid,side=right"

# 左脚用封闭 STL，右脚用直扫
python scripts/run_pipeline.py \
  --input "left=input/my_left.stl,mode=insole_solid,side=left" \
  --input "right=input/my_right_scan.stl,mode=plantar_scan_surface,side=right"
```

注意：`--input` 格式使用逗号分隔 key=value 对，避免 Windows 路径中 `C:\` 冒号的冲突。

### 3. 按步骤运行

如果你想在人工确认点逐步检查：

```bash
python scripts/prepare_inputs.py
python scripts/inspect_mesh.py
python scripts/build_zones.py
python scripts/generate_tpms.py
python scripts/clip_lattice.py
python scripts/export_result.py
python scripts/export_zoned_3mf.py
python scripts/export_bambu_project_3mf.py
```

## 输出文件

### 1. 预处理鞋垫坯体

在 `output/prepared/` 下：

- `left_prepared_insole.stl`
- `right_prepared_insole.stl`
- `left_prepare_report.json`
- `right_prepare_report.json`

当输入为 `plantar_scan_surface` 时，这一步会把开放脚底曲面生成可体素填充的封闭鞋垫坯体：轮廓按 `outline_margin_mm` 等距外扩，底面为平底，顶面跟随扫描，相对最低点的拱起受 `scan_preprocess.max_relief_mm`（默认 `8.0`）限制。准备报告里有厚度范围。当输入为旧的 `insole_solid` 时，会复用原始封闭 STL 并只输出准备报告。

### 2. 分区预览

在 `output/zones/` 下：

- `left_zones.json`
- `right_zones.json`
- `left_zones.png`
- `right_zones.png`

这里可以看到：

- 鞋垫长轴识别结果
- 宏观纵向分区边界：`heel / arch / forefoot / toe`
- 曲线分区参数
- 解剖分区预览

### 3. 可直接打印的晶格 STL

在 `output/final/` 下：

- `left_lattice_insole.stl`
- `right_lattice_insole.stl`

这些文件已经包含：

- 外轮廓边框
- 顶面接触层
- 底部承托层
- 内部分区 TPMS

### 4. 普通分区 3MF

在 `output/final/` 下：

- `left_zoned_modifiers.3mf`
- `right_zoned_modifiers.3mf`

每个 `3MF` 包含：

- `*_base`
- `*_innerHeel`
- `*_outerHeel`
- `*_innerArch`
- `*_outerArch`
- `*_innerForefoot`
- `*_centralForefoot`
- `*_outerForefoot`
- `*_toe`
- `*_edgeFrame`

配套建议文件：

- `left_zoned_modifiers_settings.json`
- `right_zoned_modifiers_settings.json`
- `left_zoned_modifiers_settings.md`
- `right_zoned_modifiers_settings.md`

在拓竹/Orca 中建议：

1. 保留 `*_base` 为普通模型
2. 将其余对象设为 `modifier`
3. 按建议参数覆盖各分区填充

### 5. 带局部参数的拓竹工程 3MF

在 `output/final/` 下：

- `left_engineering_modifiers.3mf`
- `right_engineering_modifiers.3mf`

这两个文件会自动写入各分区的局部填充建议，适合直接在 Bambu Studio 中继续观察和试切。

## 默认分区策略

### 宏观纵向分区

默认纵向比例：

- `heel`: `25%`
- `arch`: `25%`
- `forefoot`: `30%`
- `toe`: `20%`

### 解剖分区逻辑

当前版本将纵向分区进一步细化为：

- 后跟：`innerHeel` / `outerHeel`
- 中足：`innerArch` / `outerArch`
- 前掌：`innerForefoot` / `centralForefoot` / `outerForefoot`
- 脚趾：`toe`
- 外轮廓稳固区：`edgeFrame`

### 默认切片建议

当前默认建议为：

- `base`：`gyroid 20%`，`3` 墙
- `innerHeel`：`gyroid 24%`，`3` 墙
- `outerHeel`：`gyroid 20%`，`3` 墙
- `innerArch`：`gyroid 34%`，`4` 墙
- `outerArch`：`gyroid 26%`，`3` 墙
- `innerForefoot`：`gyroid 22%`，`3` 墙
- `centralForefoot`：`gyroid 22%`，`3` 墙
- `outerForefoot`：`gyroid 17%`，`2` 墙
- `toe`：`gyroid 13%`，`2` 墙
- `edgeFrame`：`grid 70%`，`4` 墙

### 可切换模板

通过 `config/zone_params.json` 中的 `default_profile` 可切换内置模板：

- `healthy_asian_male_mixed`：默认，适合日常步行和轻运动混合场景，`不使用局部墙覆盖`
- `healthy_asian_male_daily_soft`：更柔和的日常脚感，`不使用局部墙覆盖`
- `healthy_asian_male_sport_stable`：更稳的轻运动模板，`不使用局部墙覆盖`
- `supportive_generic`：较强支撑的通用模板，`保留局部墙覆盖`

默认设计选择“不在 modifier 中单独写局部墙数”，以减少分区边界两侧因额外周长产生的硬峰。边框强化默认主要依赖 `edgeFrame` 的高密度和边框宽度，而不是额外局部墙。

## 关键参数说明

主要调参入口都在 `config/zone_params.json`。

### 输入参数

- `inputs[].mode`：`insole_solid` 表示现有封闭鞋垫 STL，`plantar_scan_surface` 表示 iPhone/FaceID 类 App 输出的开放脚底扫描 STL
- `inputs[].side`：`left / right`，用于记录左右脚来源
- `inputs[].prepared_path`：可选；指定直扫输入预处理后的封闭坯体路径，默认写入 `output/prepared/<name>_prepared_insole.stl`
- `long_axis`：下游分区使用的长度方向；直扫数据如果坐标不稳定，建议显式设为 `x / y / z`

### 脚底直扫预处理参数

- `scan_preprocess.length_axis`：原始扫描中脚跟到脚趾方向
- `scan_preprocess.lateral_axis`：原始扫描中内外侧方向
- `scan_preprocess.surface_axis`：原始扫描中足底高度方向，预处理输出会统一为 Z 厚度方向
- `scan_preprocess.surface_direction`：足底表面高度沿该轴的正向或负向
- `scan_preprocess.target_thickness_mm`：生成鞋垫坯体的基础厚度
- `scan_preprocess.bottom_clearance_mm`：顶面足底曲面与底面之间额外留量
- `scan_preprocess.outline_margin_mm`：轮廓等距外扩的距离。直扫坯体底面为平底，顶面跟随扫描
- `scan_preprocess.max_relief_mm`：默认 `8.0`，限制顶面相对最低点的拱起。准备报告里有厚度范围
- `scan_preprocess.max_gap_mm`：用于过滤跨越扫描缺口的过大三角面
- `scan_preprocess.min_foot_length_mm` / `max_foot_length_mm`：单位或足长异常的质量检查阈值

### 分区参数

- `default_profile`：切换默认模板
- `zone_settings_overrides`：按分区覆盖当前模板中的切片建议，包括是否启用局部墙
- `zone_ratios`：控制 `heel / arch / forefoot / toe` 四段长度比例
- `zone_shape.heel_curve_mm`：后跟边界在中部向前延伸的幅度
- `zone_shape.arch_curve_mm`：足弓边界在中部向前延伸的幅度
- `zone_shape.toe_curve_mm`：前掌到脚趾边界在中部提前收束的幅度
- `zone_shape.inner_side`：`auto / min / max`，用于判定哪一侧更接近内侧
- `zone_shape.forefoot_center_width_ratio`：中央前掌占宽度比例

### 晶格参数

- `voxel_pitch_mm`：体素分辨率，当前默认 `1.0 mm`
- `tpms.wavelength_mm`：gyroid 波长
- `tpms.threshold_overrides`：对当前模板中的 TPMS 阈值做局部覆盖
- `edge_frame_margin_mm`：边框厚度

### 表皮与切片友好参数

- `surface.bottom_solid_layers`：底部连续承托层层数
- `surface.top_skin_layers`：顶面连续接触层层数
- `surface.top_dense_layers`：顶面加强层层数
- `surface.top_dense_threshold_boost`：顶面加强层额外阈值

## 建议工作流

### A. 模型尺寸与方向

先检查 `output/inspection/`，确认：

- 左右脚方向正确
- 长度、宽度、厚度符合预期
- 没有明显翻转或单位异常

直扫输入还应先检查 `output/prepared/*_prepare_report.json`，确认：

- `foot_length_mm` 和 `foot_width_mm` 与真人脚型一致
- `watertight` 和 `is_volume` 为 `true`
- 厚度范围符合预期：平底，顶面跟随扫描，相对最低点的拱起不超过 `scan_preprocess.max_relief_mm`（默认 `8.0`）
- `warnings` 中没有单位、长度或生成坯体异常

推荐直扫坐标约定是：脚宽为 X、脚长为 Y、足底高度/鞋垫厚度为 Z。若 App 输出坐标不同，优先通过 `scan_preprocess.*_axis` 和 `long_axis` 显式指定，不要依赖 `auto` 猜测。

### B. 解剖分区是否合理

检查 `output/zones/*.png`，重点观察：

- 足弓支撑区是否落在你希望被托起的位置
- 前掌三分区是否过宽或过窄
- 后跟内外侧分区是否太激进

### C. 切片可读性

检查：

- `output/final/*_zoned_modifiers.3mf`
- `output/final/*_engineering_modifiers.3mf`

重点确认：

- modifier 是否都被切片器识别
- 分区边界是否过于锯齿
- 参数是否在切片器中正确写入

### D. 实际打印与试穿

建议顺序：

1. 先试切片
2. 再打单脚或局部样件
3. 最后整垫试穿

如果脚感不合适，优先回调：

- 足弓过硬：降低 `innerArch` 阈值或密度
- 前掌发顶：降低 `innerForefoot` / `centralForefoot`
- 后跟太硬：先降 `innerHeel`，再降 `outerHeel`
- 外边易塌：提高 `edgeFrame` 密度或边框宽度

## 参数调优建议

- 想快速换一套整体风格：先切换 `default_profile`
- 想试“过渡区更少墙”的近似渐变：建议仅通过 `zone_settings_overrides` 对少数分区启用更低的局部墙数，而不要全局开启局部墙
- 想让边界更平滑：先降低 `voxel_pitch_mm`
- 想让足弓更有支撑：提高 `innerArch`
- 想让前掌更软：降低 `innerForefoot`、`centralForefoot`、`outerForefoot`
- 想让后跟更稳：提高 `innerHeel`
- 想减少切片错误：优先调整 `surface.bottom_solid_layers` 和 `surface.top_skin_layers`

## 测试

运行回归测试：

```powershell
python -m unittest discover -s tests
```

当前测试覆盖：

- 输入模式发现与直扫预处理
- 解剖分区命名与区域分配
- TPMS 阈值映射
- 工程 `3MF` 参数写入
- 顶底表皮策略

## 限制与说明

- 默认参数是工程起点，不应替代临床处方或个体化医疗建议
- 工程 `3MF` 目前面向 Bambu Studio 风格模板，其他切片器可能需要重新适配模板字段
- 默认阈值和密度更偏向日常支撑/缓冲场景，运动场景通常需要重新调参

## 后续改进方向

- 补充示例分区预览截图
- 模板 `3MF` 的来源和适配说明
- 一组默认打印材料和切片参数参考
