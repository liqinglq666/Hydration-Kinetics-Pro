<p align="center">
  <h1 align="center">🌌 Hydration Kinetics Pro (HK-Pro)</h1>
  <p align="center">
    <strong>A Physics-Informed Computational Framework for Complex Cementitious Hydration Kinetics</strong>
    <br><em>(Or: How to stop worrying and learn to love Reviewer #2)</em>
    <br />
    <br />
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.9+-blue.svg?logo=python&logoColor=white" alt="Python"></a>
    <a href="https://scipy.org/"><img src="https://img.shields.io/badge/Math-SciPy%201.10+-lightgrey.svg?logo=scipy&logoColor=white" alt="SciPy"></a>
    <a href="https://pandas.pydata.org/"><img src="https://img.shields.io/badge/Data-Pandas%202.0+-150458.svg?logo=pandas&logoColor=white" alt="Pandas"></a>
    <a href="https://www.originlab.com/"><img src="https://img.shields.io/badge/Render-Reviewer%20Friendly-ff6600.svg" alt="OriginLab"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License"></a>
  </p>
</p>

---

## 📑 Abstract

**Hydration Kinetics Pro (HK-Pro)** 并不是一个单纯的数据处理脚本，它是针对复杂多相胶凝体系（如大掺量粉煤灰、矿渣、ECC 专用多源固废等）的专属热力学与动力学“物理外挂”。

本框架基于 **Krstulovic-Dabic (K-D)** 物理动力学模型，彻底埋葬了传统算法中极易发散的微分域非线性逼近漏洞。HK-Pro 开创性地采用 **受热力学边界约束的积分域对数拓扑映射 (Physics-Constrained Integral-Domain Topological Mapping)** 与 **拓扑感知正则化寻优引擎 (Topology-Aware Regularization via Penalized Metric)**。它不仅能从极其复杂的量热数据中完美剥离高度重叠的反应机制，实现极限置信度 ( $R^2 > 0.99$ ) 的机制解耦，更内置了端到端的 “OriginLab 零摩擦出版管线”，确保输出图谱与推导逻辑满足最严苛的同行评审标准。

---

## 🚀 Algorithmic Breakthroughs

### 1. 热力学边界条件强制执行 (Thermodynamic Boundary Condition Enforcement)
在传统逼近算法中，针对界面反应 (I) 与扩散控制 (D) 的求解往往会遭遇“表观斜率畸变 (Apparent Slope Distortion)”。HK-Pro 在底层寻优域中，**强制锁死了理想球体收缩核 (Shrinking-Core) 与 Jander 扩散模型的几何维度边界**。通过拒绝在对数积分域释放线性斜率，本框架从根本上杜绝了伪数学相关性，确保反推所得的动力学速率常数 ( $K'_2, K'_3$ ) 严格服从阿伦尼乌斯 (Arrhenius) 方程框架下的本征热力学量纲 ( $time^{-1}$ )，而非毫无意义的数学分形常数。

### 2. 拓扑感知正则化与跨度惩罚 (Topology-Aware Regularization via Penalized Metric)
微积分极限下局部的线性逼近往往会引发严重的过拟合（即局部 $R^2 \to 1.0$ 的贪心陷阱）。HK-Pro 创新性地在损失函数 (Loss Function) 中引入了基于时间拓扑跨度的正则化惩罚项 (Span Penalty)。通过构建结合四分位距 (IQR) 的鲁棒估计量，求解器被迫在“极端的局部线性度”与“宏观物理过程的特征覆盖率 (Coverage Span)”之间寻找纳什均衡。这保障了提取的动力学机制在全生命周期内具有真实的代表性。

### 3. 竞争动力学分叉点捕获 (Competitive Kinetic Bifurcation Detection)
摒弃缺乏统计学与数学支撑的经验切线法。HK-Pro 内置高频微积分扫描器，在 $\alpha \in [0.005, 0.995]$ 的非定态域内执行 2000 级连续高保真切片。基于反应机制的竞争短板原理 ( $F_{total} = \min(F_{NG}, F_I, F_D)$ )，利用多维一阶偏导与符号跃变检测（Sign-Flip Detection），精准、冷酷且鲁棒地定位机制控制权交接的绝对数学临界点 $\alpha_1$ 与 $\alpha_2$ 。

---

## 🧮 Physics-Informed Core Equations & Phenomenological Derivations

HK-Pro 的底层计算管线拒绝纯经验公式，其推导严格锚定于固体反应动力学的核心偏微分几何模型：

### Phase 1: Nucleation and Crystal Growth (NG Stage)
由 **Avrami-Erofeev 结晶动力学理论**主导。在水化极早期，溶出离子的非均相成核与晶体三维生长决定了放热行为。其积分形式与表观放热率函数为：

$$[-\ln(1-\alpha)]^{1/n} = K_1'(t-t_0) \quad \xrightarrow{\text{Diff.}} \quad F_{NG}(\alpha) = K_1 n (1-\alpha) [-\ln(1-\alpha)]^{\frac{n-1}{n}}$$

> **Physics Note:** 结晶生长指数 $n$ 反映了早期水化产物（如 C-S-H 凝胶或 AFt 晶体）的维度演化特征与成核速率的非稳态耦合。

### Phase 2: Phase Boundary Interaction (I Stage)
随着水化产物初步包裹未反应的胶凝颗粒，反应过渡至受表面几何收缩限制的**球体收缩核模型 (Contracting Sphere Model)**。积分常数 $1/3$ 严格源自球体表面积与体积比的几何演化：

$$1-(1-\alpha)^{1/3} = \frac{k_s}{r_0}(t-t_0) \equiv K_2'(t-t_0) \quad \xrightarrow{\text{Diff.}} \quad F_I(\alpha) = 3 K_2 (1-\alpha)^{2/3}$$

### Phase 3: Diffusion Control (D Stage)
进入水化中后期，致密的产物包覆层使得反应受限于离子浓度的拓扑梯度。基于**菲克第一定律 (Fick's First Law)** 推导的 3D **Jander 扩散方程**成为主导机制：

$$\left[1-(1-\alpha)^{1/3}\right]^2 = \frac{2 D_{eff}}{r_0^2}(t-t_0) \equiv K_3'(t-t_0) \quad \xrightarrow{\text{Diff.}} \quad F_D(\alpha) = \frac{3 K_3 (1-\alpha)^{2/3}}{2 [1 - (1-\alpha)^{1/3}]}$$

> **Physics Note:** 此时表观速率常数 $K_3'$ 与产物层的有效离子扩散系数 ( $D_{eff}$ ) 高度正相关。HK-Pro 在此处强制锁死积分域斜率为 1.0，从而守卫了提取出纯净扩散动力学特征的物理底线。

---

## 🧬 Reviewer-Friendly Publication Pipeline

HK-Pro 的 I/O 模块将极具挑战性的异构特征数组对齐工作封装为黑盒。一键导出的 `Origin_Plot_Data.xlsx` 包含三个独立物理域，为您铺平通往 Accept 的最后里程：

| 出版图谱目标 | 映射工作表 (Sheet) | OriginLab 渲染逻辑 (Ctrl+C $\to$ Ctrl+V) | 学术论证意义 (Why Reviewers Care) |
| :--- | :--- | :--- | :--- |
| **Knudsen 渐近外推** | `1_Knudsen拟合` | 选中 $X, Y_{Fit}$ 列作 Scatter 散点图 $\rightarrow$ `Linear Fit`。 | 截距倒数严格映射体系极限水化热潜力 $Q_{max}$，内置短龄期塌陷保护机制。 |
| **K-D 机制积分域验证** | `2_KD分段散点拟合` | 分别选中分离重组后的 NG, I, D 散点列 $\rightarrow$ `Linear Fit`。 | 视觉直观呈现极高的 Pearson 相关系数 $R^2$，证明物理机制解耦的正确性。 |
| **动力学率包络演化** | `3_理论速率包络线` | 以 $\alpha$ 为横轴，表观与理论率函数矩阵为纵轴 $\rightarrow$ 绘制多线段图 (Line)。 | 确证 $F_{NG}, F_I, F_D$ 在临界点 $\alpha_1, \alpha_2$ 处的极限接力，论证体系机制转换拓扑连续性。 |

---

## 🛠️ Architecture & Tech Stack

本项目在软件工程实践上遵循严格的 MVC (Model-View-Controller) 标准：
* **Data Models** (`dataclasses`): 强制内存拓扑排布，杜绝动态类型漂移。
* **Kinetics Solver** (`scipy.stats, numpy`): 核心引擎全面剥离低效循环，依托底层 C-API 级别的 NumPy 矢量化（Vectorization）广播算子，保障宏量数据集的毫秒级穿透。
* **Asynchronous GUI** (`PySide6`): QThread 后台事件队列与主线程渲染管线物理隔离，确保科研工具的极致丝滑与零阻塞体验。

---

## 👨‍🔬 Citation & License

如果 HK-Pro 协助您从纷繁复杂的量热数据中提取了精准的物理机制，并助力您的手稿登上了顶级计算或材料学期刊的版面，请在您的学术论文中引用本项目：

> Li, Q. (2026). *Hydration Kinetics Pro: A Physics-Informed Computational Framework for Complex Cementitious Hydration Kinetics*. Sun Yat-sen University. GitHub Repository. https://github.com/liqinglq666/Hydration-Kinetics-Pro

HK-Pro is proudly released under the [MIT License](LICENSE). 愿您的拟合总如直线般纯粹，审稿意见皆为 Minor Revision。