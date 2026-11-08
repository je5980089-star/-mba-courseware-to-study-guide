# MBA Courseware → Study Guide Skill

把老师给的提纲型 PDF / PPT / Word / 课堂笔记变成**系统讲透的 MBA 课程知识手册**：适合复习、长期保存，也适合开卷考试时查找和引用。

> 核心解决的问题：一个知识点被写过，不等于一项管理方法已经讲完整。比如“岗位价值评价、薪酬调查、现状分析、薪酬战略、结构、构成”六个步骤分别讲过，还必须还原成可以执行的“薪酬体系设计”全过程。

## 适用范围

适用于人力资源管理、战略管理、市场营销、财务管理、运营管理、组织行为学等课程；不预设题目或考试重点。技能以老师上传的资料为事实起点，同时根据用户要求做明确标注的扩展解释，避免把外部知识冒充教师原话。

## 功能

1. 逐页检查多个文件，包括表格、图表和跨页步骤。
2. 提取显性知识、识别分散知识点之间的隐含管理任务。
3. 从定义、核心原理、运用、利弊、适用情境和案例解释知识。
4. 自动建立覆盖清单，并要求综合设计流程有独立完整章节。
5. 为用户制作可打印 Word；按要求控制页数、留白与可读性。
6. 提供可选的结构检查脚本，识别“有六个词、没有一套方法”等问题。

## 文件结构

```text
mba-courseware-to-study-guide/
├── SKILL.md                           # Skill主入口
├── README.md                          # 使用和发布说明
├── LICENSE
├── references/
│   ├── knowledge-model.md             # 跨页聚类、隐含管理任务还原
│   ├── writing-standard.md            # 完整段落与学术边界
│   └── print-layout.md                # A4打印与页数约束
├── examples/
│   └── coverage_manifest.sample.json  # 覆盖审查数据结构示例
├── scripts/
│   ├── scan_source_outline.py        # 独立的页/编号步骤扫描
│   └── audit_guide.py                 # 结构与打印页数审查
└── tests/
    └── test_audit_guide.py            # 漏“薪酬体系设计”的回归测试
```

## 如何使用

这是符合 `SKILL.md` 目录约定的**Agent Skill**，不是一个无需模型即可处理文件的独立程序。将整个技能目录导入支持 Agent Skills 的客户端或项目，在对话中上传课程讲义并提出需求即可。不同客户端的导入和安装方式不同；不要只把 `SKILL.md` 的内容复制到文档中当作普通讲义。

常用请求：

> 使用 mba-courseware-to-study-guide，把我上传的MBA讲义变成系统复习资料。请解释每个核心概念、还原跨页的管理流程，补上必要的管理实践、优缺点和例子。不预设考试题目。最终输出A4双面打印友好的Word，最多8页，保证字号可读并核验真实页数。不要在正文反复说“课件提到”。

如果只想忠实整理讲义，不希望补充其他教材内容，可以写：

> 只整理上传资料中有依据的内容，不做外部知识扩写；遇到老师没有展开的知识点明确标注，不要推断为老师原话。

如果希望深度MBA知识扩展，可以写：

> 允许补充标准管理学理论和可核验例子，但在来源说明里区分课堂资料与外部扩展。

## 运行质量检查

先扫描源文件，再由AI生成 `coverage_manifest.json`、`flow_decisions` 和学习资料 `.docx`。对扫描器识别的每组跨页步骤必须给出“应综合/不应综合”的判断，避免审核清单本身漏掉综合流程。

```bash
python scripts/scan_source_outline.py lecture1.pdf lecture2.pptx --out source_scan.json
```

然后运行：

```bash
python scripts/audit_guide.py \
  --manifest coverage_manifest.json \
  --document study-guide.docx \
  --source-scan source_scan.json \
  --pdf study-guide-print.pdf \
  --report audit.json
```

- 需检查 Word 文件时：`pip install python-docx`。扫描PPTX还需 `pip install python-pptx`。
- 需检查PDF排版与页数时：`pip install pymupdf`。
- PDF检查是可选输入，但**有页数硬限制时必须提供可验证的渲染结果才能声称“已核验页数”**。
- 脚本退出码：`0` 结构检查通过；`1` 仍需人工/打印复核；`2` 结构检查失败；`3` 文件或依赖错误。

运行回归测试：

```bash
python -m unittest discover -s tests -v
```

> 注意：本脚本只自动核对清单、章节、流程及页数线索，**无法凭关键词验证内容准确性**。仍需人工复核关键理论、公式和跨页推理。

## 放到 GitHub

1. 新建一个空仓库，例如 `mba-courseware-to-study-guide`。
2. 把本目录内的 `SKILL.md`、`references/`、`scripts/`、`examples/`、`tests/`、`README.md`、`LICENSE` 上传到仓库根目录。
3. 发布前运行单元测试，并用一份经授权的模拟讲义跑一遍生成流程。
4. 按你的客户端要求，通过 GitHub 仓库路径、Skill 安装命令或项目级技能目录安装。Codex 项目级技能也可以放进 `.agents/skills/mba-courseware-to-study-guide/`。

GitHub 仓库只放**通用技能规则和不含版权课件的测试样例**；不要未经许可上传同学、教师的讲义、未公开课堂材料或学生个人信息。

## 质量标准与边界

- 不承诺押中具体考试内容，也不保证覆盖老师没有提供的口头讲解。
- 知识覆盖不等于方法可用：必须检查完整综合流程。
- 不允许为了凑页数，把核心知识点静默删除或将字号压到不可读。
- 页数限制、指定格式、来源忠实性与用户隐私均为硬约束。
- 对扫描版PDF、复杂图、表格或版权敏感资料，需采用适当的视觉检查和来源管理。

## 背景：从一次真实遗漏中建立防回归机制

某版人力资源管理知识整理已经解释了“岗位评价、薪酬调查、薪酬战略”等概念，却缺少“薪酬体系设计”这一完整方法。本技能强制开展“跨页步骤识别→复合任务建模→逆向覆盖审查”，并用回归测试防止同类问题再次发生。

## 许可

MIT。技能规则可以开源；用户自己的课程资料与输出内容按各自权利和许可使用。
