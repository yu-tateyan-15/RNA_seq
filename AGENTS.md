# AGENTS.md

このファイルは、このRNA-seq projectでAI agentや自動化ツールが作業するときのリポジトリ運用ルールである。対象範囲はリポジトリ全体。ワークフローの理解を助けるとともに、結果を可視化し、知識を抽出することが主要な目的である。

## 最も避けるべきは、科学的曖昧さであり、誤りである。

- 安直なエラー回避、エラーハンドリングは、科学的不明瞭さを海だし、時には科学的ない誤りを生み出す可能性がある。そのため、必要以上の虚飾は不要であり、避けるべきである。

## Project Overview

このprojectは、初心者向けのRNA-seq解析ノートブックworkflowである。基本の実行順は次の通り。

1. `notebooks/00a_project_setup_metadata.ipynb`
2. `notebooks/00b_reference_setup_gencode_grch38.ipynb`
3. `notebooks/01_raw_read_qc.ipynb`
4. 解析ルートを1つ選ぶ:
   - `notebooks/transcript_mapping/`
   - `notebooks/gene_mapping/`
   - `notebooks/ref_free_mapping/`

主な共有設定は `config/analysis_config.json` にある。ノートブック間で使うサンプル表、contrast表、参照ファイル、DESeq2設定、enrichment設定はここから読む。

## Environment

作業環境はconda environment `rna-seq` を前提にする。

```bash
source scripts/activate_rna_seq.sh
```

重要なCLI/R/Python依存関係:

- Python 3.12, JupyterLab, pandas, numpy, matplotlib, seaborn, scikit-learn
- FastQC, MultiQC, Salmon, STAR, samtools, featureCounts
- R, DESeq2, clusterProfiler, org.Hs.eg.db, org.Mm.eg.db

素のshellでは `Rscript` やpandasが見えない場合があるため、検証時はconda環境内の実行ファイルを使う。

## Scientific Invariants

以下は明示的な依頼がない限り変更しない。

- sample inclusion、sample ID、condition、replicate、FASTQ対応
- contrastのtest/reference方向
- GENCODE release、reference FASTA/GTF、tx2geneの意味
- count matrixの行/列の定義
- DESeq2のdesign formula、filtering閾値、alpha、log2 fold-change閾値
- Salmon/STAR/featureCounts/Trinityの解析パラメータ
- 正規化、VST、PCA、correlation、enrichmentの解釈

科学的な意味が変わる修正をする場合は、前後の挙動、影響する出力、再実行が必要なノートブックを明記する。

## Gene ID Handling

このworkflowのDESeq2結果では、`gene_id` にGENCODE由来のEnsembl gene IDを使う。例: `ENSG00000000419.15`。

- `config/analysis_config.json` の `gene_id_type` は `ENSEMBL` を前提にする。
- clusterProfilerへ渡す前に、Ensembl version suffix（例: `.15`）を外して照合する。
- `SYMBOL` に戻す場合は、count matrix作成、DESeq2結果、clusterProfiler入力のIDがすべてgene symbolで揃うことを確認する。

## Notebook Editing Rules

ノートブックは「薄い実行・説明レイヤー」として保つ。

- reusableまたは複雑な処理は `scripts/` に置く。
- ノートブック内に大きなhelper関数や重複ロジックを増やさない。
- Markdownは日本語で、初心者が上から読める説明にする。
- 冒頭は「このノートブックの役割」「入力」「出力」「次に進む条件」を保つ。
- コマンドライン実行セルを追加・変更する場合は、近くのMarkdownに引数説明表を追加する。
- `.ipynb` のJSONを編集したら、必ずJSONとして読み込めることを確認する。
- 既存の出力やexecution countを不用意に消さない。出力を消す必要がある場合は理由を説明する。

## Heavy Commands

外部ツールや重い処理は、明示フラグ（True/False）で制御されている。

代表例:

- `RUN_DOWNLOAD`
- `RUN_BUILD_SALMON_INDEX`
- `RUN_BUILD_STAR_INDEX`
- `RUN_FASTQC`
- `RUN_MULTIQC`
- `RUN_SALMON`
- `RUN_STAR_ALIGN`
- `RUN_FEATURECOUNTS`
- `RUN_TRINITY`
- `RUN_DESEQ2`
- `RUN_CLUSTERPROFILER`

これらを `True` にする変更は、実行時間、必要メモリ、上書きされる出力を確認してから行う。ユーザーが求めていない場合、raw data、reference、resultsを再生成しない。

## Generated and Large Files

以下は解析データまたは生成物として扱う。

- `raw_data/`
- `reference/`
- `results/`
- `report/`
- `*.pptx`
- `*_STARtmp/`

削除、移動、再生成、上書きをする前に、目的と影響を明確にする。不要に見えるファイルでも、ユーザーの解析途中の成果物である可能性がある。

## Script and Template Consistency

`scripts/rebuild_rnaseq_notebooks.py` はノートブック再生成用のテンプレートを含む。ノートブックの恒久的な構造、説明文、共通セル、設定値を直す場合は、必要に応じてこのスクリプトも同じ方針に合わせる。

Rスクリプト:

- `scripts/deseq2_differential_expression.R`
- `scripts/clusterprofiler_enrichment.R`

これらを変更する場合は、該当ノートブックの引数説明と読み方も更新する。

## Validation

軽い検証:

```bash
python3 - <<'PY'
import json
from pathlib import Path
for path in Path("notebooks").rglob("*.ipynb"):
    json.loads(path.read_text(encoding="utf-8"))
print("all notebooks are valid JSON")
PY
```

Python script構文確認:

```bash
python3 -m py_compile scripts/rebuild_rnaseq_notebooks.py
```

R script構文確認:

```bash
/Users/yusuke_tateishi/miniconda3/envs/rna-seq/bin/Rscript -e 'parse("scripts/clusterprofiler_enrichment.R"); cat("R script parse OK\n")'
```

差分確認:

```bash
git diff --check
git status --short
```

重い解析セルや外部ツールの再実行は、必要なときだけ行う。
