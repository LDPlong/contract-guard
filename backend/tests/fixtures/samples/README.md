# 测试样本说明

本目录存放用于验证解析与切分的公开合同文本。**均为政府公开发布的示范文本，不含任何个人信息。**

| 文件 | 来源 | 获取日期 | 说明 |
|---|---|---|---|
| `lease_gd.pdf` | 广东省住房和城乡建设厅《广东省住房租赁合同示范文本》（经湛江市坡头区住建局公开渠道下载） | 2026-11-10 | 真实 PDF 排版，15 页，第一条~第十五条 |
| `training_samr.pdf` | 国家市场监督管理总局合同示范文本库《中小学生校外培训服务合同（示范文本）》（GF—2021—2604，教育部、市场监管总局制定） | 2026-11-10 | 由官方 HTML 文本转制为 PDF（见下），10 条 |
| `labor_jx.docx` / `labor_jx.pdf` | 江西省人力资源和社会保障厅《2024 年劳动合同示范文本》 | 2026-11-10 | docx 转制为 PDF；**原文含两份合同**（前 25 条 + 后 30 条，合计 55 条） |

## 关于"转制"

`training_samr.pdf` 与 `labor_jx.pdf` 由 `scripts/html_contract_to_pdf.py` 从官方 HTML / docx 文本生成：
版式简化为一栏正文，**条文结构与文字内容与官方原文一致**，但不保留原件的表格、勾选框位置。
它们用于验证切分与类型识别；**bbox 的真实版式验证只以 `lease_gd.pdf` 为准**。

转换命令：

```bash
python -m scripts.html_contract_to_pdf tests/fixtures/samples/training.html tests/fixtures/samples/training_samr.pdf
python -m scripts.html_contract_to_pdf tests/fixtures/samples/labor_jx.docx tests/fixtures/samples/labor_jx.pdf
```

## 已知局限

1. 三份都是**示范文本**（条款公平），且是**未填写**的空白模板，因此在本系统中承担的是
   "对照组"角色——实测任何 high 结论都是误报，中风险结论由空白模板识别降级。
   带问题的样本在 `eval/` 目录，见该目录的 README。
2. `labor_jx` 原文是两份合同拼在一起，条款编号从"第一条"重新开始，切分结果会出现两段编号。
   这是文档本身的特点，不是切分错误。
3. 样本量 9 份（3 组 × 3 类），达到文档 17.2 要求的"每类 3 份"下限，
   但问题样本全部为汇编而非真实签署原件，见 `eval/README.md` 的说明。

