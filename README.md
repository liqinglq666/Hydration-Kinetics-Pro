<p align="center">
  <h1 align="center">🌌 Hydration Kinetics Pro (HK-Pro)</h1>
  <p align="center">
    <strong>A Physics-Informed Computational Framework for Complex Cementitious Hydration Kinetics</strong>
    <br><em>Empowering your hydration data to meet the rigorous standards of CCR & CCC.</em>
    <br />
    <br />
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.9+-blue.svg?logo=python&logoColor=white" alt="Python"></a>
    <a href="https://scipy.org/"><img src="https://img.shields.io/badge/Math-SciPy%201.10+-lightgrey.svg?logo=scipy&logoColor=white" alt="SciPy"></a>
    <a href="https://pandas.pydata.org/"><img src="https://img.shields.io/badge/Data-Pandas%202.0+-150458.svg?logo=pandas&logoColor=white" alt="Pandas"></a>
    <a href="https://www.originlab.com/"><img src="https://img.shields.io/badge/Render-OriginLab%20Ready-ff6600.svg" alt="OriginLab"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License"></a>
  </p>
</p>

---

## 📑 Abstract

**Hydration Kinetics Pro (HK-Pro)** 是一款专为复杂多相胶凝体系（如掺入海工大掺量粉煤灰、矿渣及多源固废的复合体系）打造的工业级水化动力学解析求解器。

本计算框架基于 **Krstulovic-Dabic (K-D)** 物理动力学模型，彻底摒弃了传统软件中极易发散的微分域非线性逼近算法。HK-Pro 开创性地采用 **带物理约束的积分域对数映射 (Physics-Constrained Integral-Domain Mapping)** 与 **引入跨度惩罚的滑动寻优引擎 (Span-Penalized Sliding Optimization)**。

**🎯 核心愿景：** 本引擎不仅能完美剥离高度重叠的水化机制，实现极高置信度（$R^2 > 0.99$）的动力学常数解耦，其输出的动力学方程与特征参数矩阵更是**像素级对齐了 *Cement and Concrete Research* (CCR) 等顶刊的经典制表范式**。结合内置的端到端 “OriginLab 零摩擦出版管线”，HK-Pro 致力于打通从原始热量数据量测到 SCI 高保真图谱渲染的最后一公里。

---

## 🚀 Algorithmic Breakthroughs

### 1. 刚性物理量纲约束 (Rigid Physical Dimension Constraint)
针对传统拟合算法在处理界面反应 (I) 与扩散控制 (D) 阶段时容易产生的“动力学斜率畸变”与“机制重叠坍塌”问题，HK-Pro 在底层寻优域中强制锁死了收缩核模型与 Jander 模型的几何边界条件（严格物理斜率 $1.0$）。这从根本上杜绝了伪相关性，确保反推所得的动力学速率常数 ($K'_2, K'_3$) 具有绝对严谨的宏观热力学量纲 ($time^{-1}$)，**完美迎合严苛审稿人的理论审查**。

### 2. 抗过拟合跨度奖励机制 (Anti-Overfitting Span Reward Engine)
为了克服微积分极限下短区间拟合导致的“$R^2=1.0$ 贪心陷阱”，HK-Pro 引入了独创的 **Penalized Metric** 评价体系。通过动态滑动窗口配合 IQR 离群点清洗（Robust Outlier Filtering），并在损失函数中注入物理覆盖率（Coverage Span）惩罚权重。迫使求解器在“局部极端线性度”与“宏观物理跨度代表性”之间达成纳什均衡，为你产出经得起推敲的 $0.99+$ 真实拟合度。

### 3. 拓扑零交叉机制边界检测 (Topological Zero-Crossing Boundary Detection)
抛弃缺乏统计学支撑的经验切线法（肉眼识图），HK-Pro 内置高频微积分扫描器。在 $\alpha \in [0.005, 0.995]$ 连续域内执行 $2000$ 级高保真切片。依据机制短板理论（$F_{total} = \min(F_{NG}, F_I, F_D)$），利用高维一阶差分与符号跃变（Sign-Flip）算法，精准且鲁棒地捕获机制转换的绝对数学临界点 $\alpha_1$ 与 $\alpha_2$。

---

## 🧮 Physics-Informed Core Equations

底层计算管线严格遵循 K-D 动力学框架，驱动以下三大微观控制机制的串联演化：

* **Nucleation and Crystal Growth (NG):**
  $$[-\ln(1-\alpha)]^{1/n} = K_1'(t-t_0) \quad \xrightarrow{\text{Diff.}} \quad F_{NG}(\alpha) = K_1 n (1-\alpha) [-\ln(1-\alpha)]^{\frac{n-1}{n}}$$

* **Phase Boundary Interaction (I):**
  $$1-(1-\alpha)^{1/3} = K_2'(t-t_0) \quad \xrightarrow{\text{Diff.}} \quad F_I(\alpha) = 3 K_2 (1-\alpha)^{2/3}$$

* **Diffusion Control (D):**
  $$[1-(1-\alpha)^{1/3}]^2 = K_3'(t-t_0) \quad \xrightarrow{\text{Diff.}} \quad F_D(\alpha) = \frac{3 K_3 (1-\alpha)^{2/3}}{2 [1 - (1-\alpha)^{1/3}]}$$

---

## 🧬 Zero-Friction Publication Pipeline (一键对齐顶刊与 Origin 出图)

科研的时间应该花在机理分析上，而不是手动对齐数组和敲击计算器。HK-Pro 在 UI 与 I/O 层为你提供了一套“摧枯拉朽”的出版流：

### 📊 顶刊制表极速复刻
UI 面板内置 **“TSV 剪贴板映射技术”**。只需点击 `📋 复制表格`，即可将底层计算的 $Q_{max}, t_{50}, K', \alpha, R^2$ 矩阵一键无损粘贴至 Excel 或 Word 中。输出的线代方程式（如 `ln[1-(1-α)^(1/3)] = ln(t-t0) - C`）在视觉上**完美屏蔽了复杂体系的干扰系数，绝对契合经典 K-D 理论的排版范式**，让你的 Table 数据看起来如同顶级实验室的产出一般专业。

### 📈 OriginLab 零代码制图源数据
HK-Pro 导出的 `_Origin_Plot_Data.xlsx` 包含三个独立物理域，为你彻底解决了不同阶段数组长度不一（Uneven arrays）的 `NaN` 报错问题：

| 出版图谱目标 | 映射工作表 (Sheet) | OriginLab 傻瓜式渲染逻辑 (Ctrl+C $\to$ Ctrl+V) |
| :--- | :--- | :--- |
| **Knudsen 外推图** | `1_Knudsen拟合` | 选中 $X, Y_{Fit}$ 列作 Scatter 散点图 $\rightarrow$ 直接 `Linear Fit`。系统已在底层为你规避了早期弯曲数据的干扰，保障 $Q_{max}$ 取值的物理合法性。 |
| **K-D 机制线性映射** | `2_KD分段散点拟合` | 分别选中分离重组后的 NG, I, D 核心散点列 $\rightarrow$ `Linear Fit`。直线将完美穿过深色散点区域，视觉呈现极高的置信度。 |
| **动力学速率复合包络线** | `3_理论速率包络线` | 以 $\alpha$ 为唯一横轴，实验率与理论率函数矩阵为纵轴 $\rightarrow$ 绘制多线段图 (Line)。完美复现 $F_{NG}, F_I, F_D$ 在 $\alpha_1, \alpha_2$ 处的极限接力点。 |

---

## 🛠️ Architecture & Tech Stack

本项目在软件工程实践上遵循严格的 MVC (Model-View-Controller) 标准与异步并发逻辑：
* **Data Models** (`dataclasses`): 强制内存结构排布，分离物理张量与时域特征，杜绝动态类型漂移。
* **Kinetics Solver** (`scipy.stats, numpy`): 核心引擎全面剥离 `for` 循环，采用底层 C-API 级别的 NumPy 矢量化（Vectorization）广播运算，确保高通量数据的毫秒级穿透。
* **Asynchronous GUI** (`PySide6`): QThread 后台事件循环与主线程渲染完全解耦，支持超大 CSV/Excel 载入时的零阻塞交互。

---

## 👨‍🔬 Citation & License

如果您在研究中应用了本框架以支撑水化动力学的数据解算与图谱生成，请在您的学术论文中引用本项目：

> Li, Q. (2026). *Hydration Kinetics Pro: A Physics-Informed Computational Framework for Complex Cementitious Hydration Kinetics*. Sun Yat-sen University. GitHub Repository. https://github.com/liqinglq666/Hydration-Kinetics-Pro

HK-Pro is proudly released under the [MIT License](LICENSE). 欢迎来自全球计算材料学领域的工程师提交 Pull Request，以共同推动非均相水化动力学求解器的边界。