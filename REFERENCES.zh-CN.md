# 研究参考来源

本项目的默认分区和参数来自公开文献中的通用工程规律提炼，不等同于临床处方。当前默认模板优先参考健康成人、尤其是健康亚洲青年男性的压力分布数据，再结合鞋垫结构设计研究。

## 1. 健康无症状男性的鞋垫压力重分布

- [Pressure Properties of Three Different Types of Prefabricated Insoles Related to Plantar Pressure in Asymptomatic Men](https://pmc.ncbi.nlm.nih.gov/articles/PMC9715923/)

简短说明：

- 该研究基于健康无症状男性，比较了足弓支撑、跖骨垫和外侧后跟楔形鞋垫对不同分区压力的影响。
- 这支持了本项目保留 `innerHeel / outerHeel`、`innerArch / outerArch` 和三分前掌结构，并将默认模板调成中性支撑而不是病理减压导向。

## 2. 正常青年华人的足底压力基线

- [正常青年人之足底壓力分析 / Foot Pressure Analysis in Normal Young Chinese Adults](https://www.airitilibrary.com/Article/Detail/10137688-199704-22-2-81-90-a)

简短说明：

- 该研究给出了正常青年华人在站立与步行状态下的足底压力基线。
- 摘要指出步行时峰值压力集中在第2跖骨头附近，步态线从外侧后跟开始并走向前掌中央区域。
- 这支持了本项目把 `centralForefoot` 提升为默认重点承力区，并保留 `outerHeel` 的正常落地缓冲属性。

## 3. 总接触与足弓支撑

- [Advancements in diabetic foot insoles: a comprehensive review of design, manufacturing, and performance evaluation](https://www.frontiersin.org/journals/bioengineering-and-biotechnology/articles/10.3389/fbioe.2024.1394758/full)

简短说明：

- 综述指出总接触定制、软硬结合材料和多孔结构对压力再分配很重要。
- 这支持了本项目把 `innerArch` 作为主要支撑区，同时保留顶面接触层和内部多孔晶格。

## 4. 使用方式建议

- 这些来源更适合用来决定默认分区和默认调参方向，而不是直接替代个体化足底压力数据。
- 如果后续有压力图、步态数据或试穿反馈，优先用个体数据覆盖默认参数。
