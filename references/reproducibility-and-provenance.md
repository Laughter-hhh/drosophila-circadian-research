# 可复现性与数据溯源

## 最小项目结构

```text
project/
  research-state.md
  task.json
  data/
    raw_manifest.csv
  metadata/
    data-dictionary.csv
  analysis/
    config.yaml
    scripts/
    notebooks/
  results/
    qc/
    tables/
    figures/
  logs/
  environment/
```

## 每次运行保存

- 输入文件路径、大小、哈希或版本；
- task contract 和 analysis config；
- 代码 commit 或文件版本；
- Python、Fiji、MATLAB、R、Java 及关键包版本；
- 完整命令、运行时间和随机种子；
- QC、排除列表、中间表和最终图表；
- 手动修改和任何无法自动复现的步骤。

## 重跑标准

分析脚本应能在干净环境中运行，测试数据至少包含一个已知阳性和一个阴性/空白对照。对浮点结果预先定义合理容差；对排序、标签和文件结构使用精确检查。不要用截图或手工复制数字作为唯一结果来源。

## 论文级产物

每个 Figure 应能回溯到一个或多个中间表；每个表应能回溯到原始输入和配置；每个主要结论应能回溯到图、统计模型和证据来源。无法追溯的结果只能作为探索性观察。
