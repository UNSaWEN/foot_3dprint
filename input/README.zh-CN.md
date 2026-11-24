# 输入模型说明

本目录预留给公开示例输入或你自己的鞋垫模型。

封闭鞋垫 STL 推荐做法：

- 将左脚鞋垫放为 `input/left_insole.stl`
- 将右脚鞋垫放为 `input/right_insole.stl`
- 然后在 `config/zone_params.json` 的 `inputs` 中同步更新路径

脚底直扫 STL 推荐做法：

- 将左脚扫描放为 `input/left_plantar_scan.stl`
- 将右脚扫描放为 `input/right_plantar_scan.stl`
- 在 `config/zone_params.json` 中将对应输入设为 `mode: "plantar_scan_surface"`
- 确认 `scan_preprocess.length_axis`、`lateral_axis`、`surface_axis` 和 `long_axis` 与 App 导出的坐标一致
- 轮廓会按 `outline_margin_mm` 等距外扩。底面为平底，顶面跟随扫描，相对最低点的拱起默认不超过 `scan_preprocess.max_relief_mm`（`8.0`）

示例：

```json
{
  "name": "left",
  "path": "input/left_plantar_scan.stl",
  "mode": "plantar_scan_surface",
  "side": "left"
}
```

项目本身不强制要求输入文件位于 `input/`，只要配置中的路径可解析即可。
