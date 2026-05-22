#!/usr/bin/env python3
"""Rebuild the beginner-oriented RNA-seq workflow notebooks."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent


PROJECT_DIR = Path("/Users/yusuke_tateishi/Documents/RNA_seq").resolve()
NOTEBOOK_DIR = PROJECT_DIR / "notebooks"


def _source(text: str) -> list[str]:
    text = dedent(text).strip("\n") + "\n"
    return text.splitlines(keepends=True)


def markdown(text: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": _source(text),
    }


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _source(text),
    }


def notebook(cells: list[dict]) -> dict:
    for index, cell in enumerate(cells, start=1):
        cell.setdefault("id", f"cell-{index:03d}")
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "RNA-seq workflow",
                "language": "python",
                "name": "rna-seq",
            },
            "language_info": {
                "name": "python",
                "version": "3.12",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write_notebook(filename: str, cells: list[dict]) -> None:
    NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)
    path = NOTEBOOK_DIR / filename
    path.write_text(json.dumps(notebook(cells), ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {path}")


def write_text(filename: str, text: str) -> None:
    path = PROJECT_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(text).strip("\n") + "\n")
    print(f"wrote {path}")


def nb_00_project_setup_metadata() -> list[dict]:
    return [
        markdown("""
            # 00a. Project setup and metadata

            このノートブックは、RNA-seq解析の「地図」を作る段階である。まだ統計解析はしない。

            **この段階が答える問い**

            - どのサンプルがあるか。
            - どの群を比較したいか。
            - 後続ノートブックがどの設定ファイルを見るか。

            **入力**

            - `raw_data/` のFASTQファイル: シーケンサーから出力された生の塩基配列データ（リード）。
            - この実験の設計メモ: サンプルの属性（細胞株、薬剤処理、時間、反復など）を記した実験設計のメタデータ。

            **出力**

            - `metadata/samples.tsv`: 各サンプル名、属する群、対応するFASTQファイルのパスをまとめたサンプルメタデータ表。
            - `metadata/contrasts.tsv`: 差分発現解析（DEG（Differentially Expressed Gene）解析）で比較する群の組み合わせ（例：`NAC_S2_2h` vs `Non`）を定義した比較表。
            - `config/analysis_config.json`: パス設定、使用ツール、並列スレッド数などの解析パラメータを保存したJSON設定ファイル。

            **次に進む条件**

            - サンプル名、群、replicate、FASTQパスが正しい。
            - `Non` を基準群にしてよい、という前提を一度確認した。
            """),
        markdown("""
            ## RNA-seq解析の全体像

            ```mermaid
            flowchart LR
              A["sample design"] --> B["FASTQ QC（Quality Control）"]
              B --> C["reference setup"]
              C --> D["Salmon quantification"]
              D --> E["gene count matrix"]
              E --> F["sample QC（Quality Control）"]
              F --> G["DESeq2"]
              G --> H["biological interpretation"]
            ```

            初心者が混乱しやすい点は、`FASTQ`、`参照ファイル`、`count matrix`、`DEGリスト` が別物だという点である。

            - FASTQ: シーケンサーから来たreadそのもの。
            - 参照ファイル: readを遺伝子・転写産物に対応づける辞書。
            - count matrix: サンプルごとに各遺伝子が何read相当読まれたかの表。
            - DEGリスト: 統計モデルで群間差を検定した結果。
            """),
        code(
            r'''
            from pathlib import Path
            import json
            import shutil
            import subprocess

            PROJECT_DIR = Path("/Users/yusuke_tateishi/Documents/RNA_seq").resolve()
            RAW_DATA_DIR = PROJECT_DIR / "raw_data"
            METADATA_DIR = PROJECT_DIR / "metadata"
            CONFIG_DIR = PROJECT_DIR / "config"
            RESULTS_DIR = PROJECT_DIR / "results"

            for path in [METADATA_DIR, CONFIG_DIR, RESULTS_DIR]:
                path.mkdir(parents=True, exist_ok=True)

            PROJECT_DIR
            '''
        ),
        markdown("""
            ## 解析に必要な環境（ライブラリ・ツール）の診断
            
            RNA-seq解析には、Pythonモジュール、統計解析用のRパッケージ、およびmappingやアセンブリを行う外部コマンドラインツール（CLIツール）が必要である。
            ここで主要なライブラリやツールが揃っているか確認する。
            """),
        code(
            r'''
            # Diagnostic check for required software, Python modules, and R libraries
            import shutil
            import subprocess
            import sys
            import pandas as pd

            diagnostic_results = []

            # 1. Check Python Libraries
            py_modules = {
                "pandas": "Data manipulation",
                "numpy": "Numerical computation",
                "matplotlib": "Plotting/visualization",
                "seaborn": "Statistical visualization",
                "sklearn": "Machine learning (scikit-learn)",
            }
            for mod, desc in py_modules.items():
                try:
                    m = __import__(mod)
                    ver = getattr(m, "__version__", "Available")
                    diagnostic_results.append({"Category": "Python", "Name": mod, "Available": True, "Details": f"version {ver} ({desc})"})
                except ImportError:
                    diagnostic_results.append({"Category": "Python", "Name": mod, "Available": False, "Details": f"Missing! ({desc})"})

            # 2. Check R Packages
            r_packages = {
                "DESeq2": "Differential expression analysis",
                "clusterProfiler": "Pathway enrichment analysis",
                "org.Hs.eg.db": "Human gene annotation database",
                "org.Mm.eg.db": "Mouse gene annotation database",
                "pheatmap": "Heatmap visualization",
                "ggplot2": "Advanced plotting",
            }
            rscript_path = shutil.which("Rscript")
            if rscript_path:
                for pkg, desc in r_packages.items():
                    res = subprocess.run([rscript_path, "-e", f"library({pkg})"], capture_output=True, text=True)
                    if res.returncode == 0:
                        diagnostic_results.append({"Category": "R Package", "Name": pkg, "Available": True, "Details": f"Available ({desc})"})
                    else:
                        diagnostic_results.append({"Category": "R Package", "Name": pkg, "Available": False, "Details": f"Failed to load! ({desc})"})
            else:
                for pkg, desc in r_packages.items():
                    diagnostic_results.append({"Category": "R Package", "Name": pkg, "Available": False, "Details": "Rscript command not found in PATH"})

            # 3. Check CLI Tools
            cli_tools = {
                "fastqc": "Quality control of raw reads",
                "multiqc": "Aggregate QC reports",
                "salmon": "Transcript abundance quantification",
                "STAR": "Genome mapping",
                "samtools": "BAM files processing",
                "featureCounts": "Summarize read counts over genomic features",
                "trinity": "De novo transcriptome assembly (optional)",
            }
            for tool, desc in cli_tools.items():
                path = shutil.which(tool)
                if path:
                    diagnostic_results.append({"Category": "CLI Tool", "Name": tool, "Available": True, "Details": f"{path} ({desc})"})
                else:
                    diagnostic_results.append({"Category": "CLI Tool", "Name": tool, "Available": False, "Details": f"Not found in PATH! ({desc})"})

            # Display as a formatted table
            df_diag = pd.DataFrame(diagnostic_results)
            display(df_diag)

            # Warning if anything critical is missing
            missing_critical = df_diag[~df_diag["Available"] & (df_diag["Name"] != "trinity")]
            if not missing_critical.empty:
                print("WARNING: Some critical components are missing from your environment!")
                print("Please make sure you have activated the correct Conda environment (e.g. 'rna-seq').")
            else:
                print("SUCCESS: All major environment components are verified and ready!")
            '''
        ),
        markdown("""
            ## まずFASTQファイルが見えるか確認する

            ここでは中身を解析せず、ファイルの場所だけ確認する。`*_1.fq.gz` と `*_2.fq.gz` がペアで並んでいることが大事である。
            """),
        code(
            r'''
            fastq_files = sorted(RAW_DATA_DIR.glob("*/*.fq.gz"))
            print(f"FASTQ files found: {len(fastq_files)}")
            for path in fastq_files[:20]:
                print(path.relative_to(PROJECT_DIR))
            '''
        ),
        markdown("""
            ## FASTQの中身を少し見る

            FASTQは巨大なテキストファイルなので、全部を開くのではなく、先頭の数readだけを見る。

            1 readは必ず4行である。

            $$
            1\\ \\mathrm{read} = \\mathrm{header} + \\mathrm{sequence} + \\mathrm{separator} + \\mathrm{quality}
            $$

            - 1行目: read名。`@` で始まる。
            - 2行目: 塩基配列。`A/T/G/C/N` が並ぶ。
            - 3行目: 区切り。通常は `+`。
            - 4行目: quality score。各塩基の信頼度を文字で表す。

            ここでは `NAC_S2_2h_1` のR1を例に、先頭3 readだけ表示する。
            """),
        code(
            r'''
            import gzip

            example_fastq = PROJECT_DIR / "raw_data/NAC_S2_2h_1/NAC_S2_2h_1_1.fq.gz"
            N_READS_TO_SHOW = 3

            with gzip.open(example_fastq, "rt") as handle:
                for read_index in range(1, N_READS_TO_SHOW + 1):
                    header = handle.readline().rstrip("\n")
                    sequence = handle.readline().rstrip("\n")
                    separator = handle.readline().rstrip("\n")
                    quality = handle.readline().rstrip("\n")

                    print(f"--- read {read_index} ---")
                    print("header   :", header)
                    print("sequence :", sequence[:80] + ("..." if len(sequence) > 80 else ""))
                    print("separator:", separator)
                    print("quality  :", quality[:80] + ("..." if len(quality) > 80 else ""))
                    print("length   :", len(sequence), "bases")
                    print()
            '''
        ),
        markdown("""
            ## sample table

            `samples.tsv` は「どのFASTQがどのサンプルか」を後続ノートブックへ伝える表である。

            `condition` はDESeq2で比較する群名である。ここでは現在の資料に合わせて `Non`、`Oxi_2h`、`NAC_S2_2h` を使う。
            """),
        code(
            r'''
            sample_rows = [
                {
                    "sample_id": "NAC_S2_2h_1",
                    "condition": "NAC_S2_2h",
                    "treatment": "NAC_S2",
                    "timepoint": "2h",
                    "replicate": 1,
                    "fastq_1": "raw_data/NAC_S2_2h_1/NAC_S2_2h_1_1.fq.gz",
                    "fastq_2": "raw_data/NAC_S2_2h_1/NAC_S2_2h_1_2.fq.gz",
                },
                {
                    "sample_id": "NAC_S2_2h_2",
                    "condition": "NAC_S2_2h",
                    "treatment": "NAC_S2",
                    "timepoint": "2h",
                    "replicate": 2,
                    "fastq_1": "raw_data/NAC_S2_2h_2/NAC_S2_2h_2_1.fq.gz",
                    "fastq_2": "raw_data/NAC_S2_2h_2/NAC_S2_2h_2_2.fq.gz",
                },
                {
                    "sample_id": "NAC_S2_2h_3",
                    "condition": "NAC_S2_2h",
                    "treatment": "NAC_S2",
                    "timepoint": "2h",
                    "replicate": 3,
                    "fastq_1": "raw_data/NAC_S2_2h_3/NAC_S2_2h_3_1.fq.gz",
                    "fastq_2": "raw_data/NAC_S2_2h_3/NAC_S2_2h_3_2.fq.gz",
                },
                {
                    "sample_id": "Non_1",
                    "condition": "Non",
                    "treatment": "Non",
                    "timepoint": "baseline",
                    "replicate": 1,
                    "fastq_1": "raw_data/Non_1/Non_1_1.fq.gz",
                    "fastq_2": "raw_data/Non_1/Non_1_2.fq.gz",
                },
                {
                    "sample_id": "Non_2",
                    "condition": "Non",
                    "treatment": "Non",
                    "timepoint": "baseline",
                    "replicate": 2,
                    "fastq_1": "raw_data/Non_2/Non_2_1.fq.gz",
                    "fastq_2": "raw_data/Non_2/Non_2_2.fq.gz",
                },
                {
                    "sample_id": "Non_3",
                    "condition": "Non",
                    "treatment": "Non",
                    "timepoint": "baseline",
                    "replicate": 3,
                    "fastq_1": "raw_data/Non_3/Non_3_1.fq.gz",
                    "fastq_2": "raw_data/Non_3/Non_3_2.fq.gz",
                },
                {
                    "sample_id": "Oxi_2h_1",
                    "condition": "Oxi_2h",
                    "treatment": "Oxi",
                    "timepoint": "2h",
                    "replicate": 1,
                    "fastq_1": "raw_data/Oxi_2h_1/Oxi_2h_1_1.fq.gz",
                    "fastq_2": "raw_data/Oxi_2h_1/Oxi_2h_1_2.fq.gz",
                },
                {
                    "sample_id": "Oxi_2h_2",
                    "condition": "Oxi_2h",
                    "treatment": "Oxi",
                    "timepoint": "2h",
                    "replicate": 2,
                    "fastq_1": "raw_data/Oxi_2h_2/Oxi_2h_2_1.fq.gz",
                    "fastq_2": "raw_data/Oxi_2h_2/Oxi_2h_2_2.fq.gz",
                },
                {
                    "sample_id": "Oxi_2h_3",
                    "condition": "Oxi_2h",
                    "treatment": "Oxi",
                    "timepoint": "2h",
                    "replicate": 3,
                    "fastq_1": "raw_data/Oxi_2h_3/Oxi_2h_3_1.fq.gz",
                    "fastq_2": "raw_data/Oxi_2h_3/Oxi_2h_3_2.fq.gz",
                },
            ]

            samples_path = METADATA_DIR / "samples.tsv"
            header = list(sample_rows[0])
            with samples_path.open("w", encoding="utf-8") as out:
                out.write("\t".join(header) + "\n")
                for row in sample_rows:
                    out.write("\t".join(str(row[column]) for column in header) + "\n")

            print(samples_path.relative_to(PROJECT_DIR))
            '''
        ),
        code(
            r'''
            import pandas as pd

            samples = pd.read_csv(METADATA_DIR / "samples.tsv", sep="\t")
            samples
            '''
        ),
        markdown("""
            ## FASTQパスの検査

            この検査は、表に書いたFASTQパスが実際に存在するかを見るだけである。ここで失敗する場合、後続のQCやSalmonは必ず失敗する。
            """),
        code(
            r'''
            missing = []
            for _, row in samples.iterrows():
                for column in ["fastq_1", "fastq_2"]:
                    path = PROJECT_DIR / row[column]
                    if not path.exists():
                        missing.append(str(path.relative_to(PROJECT_DIR)))

            if missing:
                print("Missing FASTQ paths:")
                for path in missing:
                    print(" -", path)
            else:
                print("All FASTQ paths in metadata exist.")
            '''
        ),
        markdown("""
            ## contrast table

            `contrasts.tsv` は「どの群とどの群を比べるか」を書く表である。

            `test_condition` が分子、`reference_condition` が基準である。たとえば `Oxi_2h_vs_Non` は、`Oxi_2h` が `Non` より上がるか下がるかを見る。
            """),
        code(
            r'''
            contrast_rows = [
                {
                    "contrast_id": "Oxi_2h_vs_Non",
                    "test_condition": "Oxi_2h",
                    "reference_condition": "Non",
                    "description": "Oxidative stress at 2h compared with untreated control",
                },
                {
                    "contrast_id": "NAC_S2_2h_vs_Non",
                    "test_condition": "NAC_S2_2h",
                    "reference_condition": "Non",
                    "description": "NAC_S2 at 2h compared with untreated control",
                },
                {
                    "contrast_id": "NAC_S2_2h_vs_Oxi_2h",
                    "test_condition": "NAC_S2_2h",
                    "reference_condition": "Oxi_2h",
                    "description": "NAC_S2 at 2h compared with oxidative stress at 2h",
                },
            ]

            contrasts_path = METADATA_DIR / "contrasts.tsv"
            header = list(contrast_rows[0])
            with contrasts_path.open("w", encoding="utf-8") as out:
                out.write("\t".join(header) + "\n")
                for row in contrast_rows:
                    out.write("\t".join(str(row[column]) for column in header) + "\n")

            contrasts = pd.read_csv(contrasts_path, sep="\t")
            contrasts
            '''
        ),
        markdown("""
            ## central config

            `analysis_config.json` は、ノートブック間で共有する設定メモである。

            重要なのは、参照ファイルの欄である。ここに書くパスは「これから作る予定の参照辞書」を指す。実ファイルは次の `00b_reference_setup_gencode_grch38.ipynb` で作る。
            """),
        code(
            r'''
            analysis_config = {
                "project_dir": str(PROJECT_DIR),  # Setting to the absolute project root used by every notebook.
                "raw_data_dir": "raw_data",  # Setting to the directory containing FASTQ sample folders.
                "samples_path": "metadata/samples.tsv",  # Setting to the sample metadata table.
                "contrasts_path": "metadata/contrasts.tsv",  # Setting to the DESeq2 group comparison table.
                "organism": "human",  # Setting to the organism assumption used for reference and enrichment.
                "gene_id_type": "ENSEMBL",  # Setting to the gene ID type used by clusterProfiler. GENCODE gene IDs include version suffixes, which the enrichment script strips before lookup.
                "reference": {
                    "gencode_release": "49",  # Setting to the GENCODE release used for all reference files.
                    "transcript_fasta": "reference/gencode_grch38/gencode.v49.transcripts.fa.gz",  # Setting to the transcript FASTA used to build the Salmon index.
                    "salmon_index": "reference/gencode_grch38/salmon_index",  # Setting to the Salmon transcriptome index directory.
                    "tx2gene_path": "reference/gencode_grch38/tx2gene.tsv",  # Setting to the transcript-to-gene mapping table.
                    "gtf_path": "reference/gencode_grch38/gencode.v49.annotation.gtf.gz",  # Setting to the annotation GTF matching the transcript FASTA.
                    "genome_fasta": "",  # Setting to the genome FASTA; not required for this Salmon-first workflow.
                },
                "quantification": {
                    "method": "salmon",  # Setting to the quantification backend used in notebook 02.
                    "threads": 8,  # Setting to the maximum CPU threads for external tools.
                    "salmon": {
                        "library_type": "A",  # Setting to Salmon automatic library type detection.
                        "validate_mappings": True,  # Setting to fail early if sample IDs and file paths do not match.
                    },
                    "star": {
                        "read_length": 150,  # Setting to the read length in base pairs.
                        "sjdb_overhang": 149,  # Setting to sjdbOverhang (read_length - 1).
                        "featurecounts_strandness": 0,  # Setting to featureCounts strand specificity (0: unstranded, 1: stranded, 2: reversely stranded).
                    },
                    "trinity": {
                        "max_memory": "10G",  # Setting to the maximum memory allocated for Trinity.
                        "seq_type": "fq",  # Setting to the sequence format (e.g. fq for fastq).
                        "ss_lib_type": "RF",  # Setting to the strand-specific library type (e.g. RF, FR, or empty).
                    },
                },
                "differential_expression": {
                    "count_matrix_path": "results/counts/gene_counts.tsv",  # Setting to the gene-level count matrix consumed by DESeq2.
                    "design_formula": "~ condition",  # Setting to the DESeq2 design formula.
                    "reference_condition": "Non",  # Setting to the baseline condition for factor releveling.
                    "min_count": 10,  # Setting to the minimum raw count used before DESeq2.
                    "min_samples": 2,  # Setting to the number of samples that must pass min_count.
                    "alpha": 0.05,  # Setting to the FDR threshold for significant genes.
                    "lfc_threshold": 1.0,  # Setting to the absolute log2 fold-change threshold used in plots/reports.
                },
            }

            config_path = CONFIG_DIR / "analysis_config.json"
            config_path.write_text(json.dumps(analysis_config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(config_path.relative_to(PROJECT_DIR))
            '''
        ),
        code(
            r'''
            config = json.loads((CONFIG_DIR / "analysis_config.json").read_text(encoding="utf-8"))
            config
            '''
        ),
        markdown("""
            ## この段階の確認

            ここまでで「解析対象のリスト」と「比較したい群」が決まりした。次は、FASTQ readを転写産物・遺伝子に対応づけるための参照辞書を作る。

            **よくある間違い**

            - `sample_id` とFASTQフォルダ名がずれている。
            - `condition` の表記揺れがある。例: `Oxi_2h` と `Oxi-2h`。
            - 基準群が意図と違う。ここでは `Non` を基準にしている。

            **小さい練習**

            `samples["condition"].value_counts()` を実行して、各群が3 replicateあることを確認しよう。
            """),
        code(
            r'''
            samples["condition"].value_counts()
            '''
        ),
    ]


def nb_00b_reference_setup() -> list[dict]:
    return [
        markdown("""
            # 00b. Reference setup: GENCODE GRCh38 and Salmon index

            このノートブックは、FASTQを遺伝子・転写産物に対応づけるための「参照辞書」を作る段階である。

            **この段階が答える問い**

            - RNA-seq readを何に照合するのか。
            - Salmonが使うindexはどこにあるのか。
            - transcript単位の結果をgene単位にまとめる対応表はどこにあるのか。

            **入力**

            - GENCODE human release 49 の transcript FASTA: GENCODEデータベースからダウンロードする、ヒト転写産物の基準塩基配列ファイル。
            - 同じreleaseの annotation GTF: 遺伝子構造（エクソンやイントロン、転写産物との対応など）が記載されたアノテーションファイル。

            **出力**

            - `reference/gencode_grch38/gencode.v49.transcripts.fa.gz`: ダウンロードした転写産物FASTAの圧縮ファイル。
            - `reference/gencode_grch38/gencode.v49.annotation.gtf.gz`: ダウンロードしたアノテーションGTFの圧縮ファイル。
            - `reference/gencode_grch38/salmon_index/`: Salmonがreadを高速にマッピングするために構築したインデックスフォルダ。
            - `reference/gencode_grch38/tx2gene.tsv`: 転写産物ID（transcript ID）と遺伝子ID（gene ID）の対応を示したテキスト表。

            **次に進む条件**

            - 上の4つの出力が存在する。
            - `config/analysis_config.json` の `reference` 欄がこの4つを指している。
            """),
        markdown("""
            ## 初心者向けの説明

            FASTQには短い配列readしか入っていない。readだけを見ても「どの遺伝子から来たreadか」は分からない。

            そこで、既知のヒト転写産物配列を集めたFASTAを使って、Salmon用のindexを作る。これは日本語の文章を辞書で引く準備に近い。

            GTFは、transcriptとgeneの対応表を作るために使う。Salmonの最初の結果はtranscript単位なので、DESeq2で扱いやすいgene単位へ集計するために `tx2gene.tsv` が必要である。
            """),
        code(
            r'''
            from pathlib import Path
            import gzip
            import json
            import re
            import shutil
            import subprocess

            PROJECT_DIR = Path("/Users/yusuke_tateishi/Documents/RNA_seq").resolve()
            CONFIG_PATH = PROJECT_DIR / "config" / "analysis_config.json"
            REFERENCE_DIR = PROJECT_DIR / "reference" / "gencode_grch38"
            REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

            GENCODE_RELEASE = "49"
            TRANSCRIPT_FASTA_NAME = f"gencode.v{GENCODE_RELEASE}.transcripts.fa.gz"
            GTF_NAME = f"gencode.v{GENCODE_RELEASE}.annotation.gtf.gz"
            GENOME_FASTA_NAME = "GRCh38.primary_assembly.genome.fa.gz"

            TRANSCRIPT_FASTA_PATH = REFERENCE_DIR / TRANSCRIPT_FASTA_NAME
            GTF_PATH = REFERENCE_DIR / GTF_NAME
            GENOME_FASTA_PATH = REFERENCE_DIR / GENOME_FASTA_NAME
            TX2GENE_PATH = REFERENCE_DIR / "tx2gene.tsv"
            SALMON_INDEX_DIR = REFERENCE_DIR / "salmon_index"
            STAR_INDEX_DIR = REFERENCE_DIR / "star_index"

            TRANSCRIPT_FASTA_URL = f"https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_{GENCODE_RELEASE}/{TRANSCRIPT_FASTA_NAME}"
            GTF_URL = f"https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_{GENCODE_RELEASE}/{GTF_NAME}"
            GENOME_FASTA_URL = f"https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_{GENCODE_RELEASE}/{GENOME_FASTA_NAME}"

            print("Reference directory:", REFERENCE_DIR)
            print("Transcript FASTA URL:", TRANSCRIPT_FASTA_URL)
            print("GTF URL:", GTF_URL)
            print("Genome FASTA URL:", GENOME_FASTA_URL)
            '''
        ),
        markdown("""
            ## Step 1: 参照ファイルをダウンロードする

            このセルはインターネットから大きめのファイルを取得する。初回だけ `RUN_DOWNLOAD = True` にしよう。

            途中で止まっても、`curl -C -` を使うので再開できる。
            """),
        code(
            r'''
            RUN_DOWNLOAD = False

            def download_with_curl(url: str, out_path: Path) -> None:
                curl = shutil.which("curl")
                if curl is None:
                    raise RuntimeError("curl was not found.")
                command = [curl, "-L", "--fail", "-C", "-", "-o", str(out_path), url]
                print("Running:", " ".join(command))
                subprocess.run(command, check=True)

            if RUN_DOWNLOAD:
                download_with_curl(TRANSCRIPT_FASTA_URL, TRANSCRIPT_FASTA_PATH)
                download_with_curl(GTF_URL, GTF_PATH)
                download_with_curl(GENOME_FASTA_URL, GENOME_FASTA_PATH)
            else:
                print("Set RUN_DOWNLOAD = True to download the GENCODE FASTA, GTF, and Genome FASTA files.")
            '''
        ),
        markdown("""
            ## Step 2: ダウンロードできたか確認する

            ここではファイルサイズとgzip形式を確認する。中身の生物学的評価ではなく、「壊れていないか」の最低限の確認である。
            """),
        code(
            r'''
            for path in [TRANSCRIPT_FASTA_PATH, GTF_PATH, GENOME_FASTA_PATH]:
                if path.exists():
                    print(path.relative_to(PROJECT_DIR), f"{path.stat().st_size / 1024 / 1024:.1f} MB")
                    with gzip.open(path, "rt") as handle:
                        first_line = handle.readline().strip()
                    print("  first line:", first_line[:120])
                else:
                    print("missing:", path.relative_to(PROJECT_DIR))
            '''
        ),
        markdown("""
            ## Step 3: Salmon indexを作る

            Salmon indexは、SalmonがFASTQ readを高速に照合するための専用データベースである。

            この処理は少し時間がかかる。初回だけ `RUN_BUILD_SALMON_INDEX = True` にしよう。
            """),
        code(
            r'''
            RUN_BUILD_SALMON_INDEX = False
            THREADS = 8

            if RUN_BUILD_SALMON_INDEX:
                salmon = shutil.which("salmon")
                if salmon is None:
                    raise RuntimeError("salmon was not found. Activate the rna-seq environment first.")
                if not TRANSCRIPT_FASTA_PATH.exists():
                    raise FileNotFoundError(TRANSCRIPT_FASTA_PATH)
                command = [
                    salmon,
                    "index",
                    "-t",
                    str(TRANSCRIPT_FASTA_PATH),
                    "-i",
                    str(SALMON_INDEX_DIR),
                    "--gencode",
                    "-p",
                    str(THREADS),
                ]
                print("Running:", " ".join(command))
                subprocess.run(command, check=True)
            else:
                print("Set RUN_BUILD_SALMON_INDEX = True after the transcript FASTA is downloaded.")
            '''
        ),
        markdown("""
            ## Step 3b: STAR indexを作る

            STAR indexは、STARがFASTQ readをGenome領域にmappingするためのGenomeインデックスデータベースである。

            > [!WARNING]
            > **メモリ消費量について**
            > ヒトGenome（GRCh38）に対するSTARのインデックス構築には、**通常30GB以上のRAM（メモリ）**が必要である。
            > もし個人のPCなどでメモリが足りない場合は、このステップをスキップし、十分なリソースがある共有サーバー等でインデックスを構築しよう。

            この処理には少し時間がかかる（約30分〜1時間）。初回だけ `RUN_BUILD_STAR_INDEX = True` にしよう。
            """),
        code(
            r'''
            RUN_BUILD_STAR_INDEX = False
            THREADS = 8
            SJDB_OVERHANG = 149

            if RUN_BUILD_STAR_INDEX:
                star = shutil.which("STAR")
                if star is None:
                    raise RuntimeError("STAR was not found. Activate the rna-seq environment first.")
                if not GENOME_FASTA_PATH.exists():
                    raise FileNotFoundError(GENOME_FASTA_PATH)
                if not GTF_PATH.exists():
                    raise FileNotFoundError(GTF_PATH)

                STAR_INDEX_DIR.mkdir(parents=True, exist_ok=True)

                # STAR genomeGenerate requires decompressed fasta and gtf
                decompressed_fasta = GENOME_FASTA_PATH.with_suffix("")
                decompressed_gtf = GTF_PATH.with_suffix("")

                print(f"Decompressing {GENOME_FASTA_PATH.name}...")
                with gzip.open(GENOME_FASTA_PATH, "rb") as f_in, decompressed_fasta.open("wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

                print(f"Decompressing {GTF_PATH.name}...")
                with gzip.open(GTF_PATH, "rb") as f_in, decompressed_gtf.open("wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

                try:
                    command = [
                        star,
                        "--runMode", "genomeGenerate",
                        "--genomeDir", str(STAR_INDEX_DIR),
                        "--genomeFastaFiles", str(decompressed_fasta),
                        "--sjdbGTFfile", str(decompressed_gtf),
                        "--sjdbOverhang", str(SJDB_OVERHANG),
                        "--runThreadN", str(THREADS),
                    ]
                    print("Running:", " ".join(command))
                    subprocess.run(command, check=True)
                finally:
                    # Clean up decompressed files to save disk space
                    if decompressed_fasta.exists():
                        print(f"Removing temporary decompressed FASTA: {decompressed_fasta}")
                        decompressed_fasta.unlink()
                    if decompressed_gtf.exists():
                        print(f"Removing temporary decompressed GTF: {decompressed_gtf}")
                        decompressed_gtf.unlink()
            else:
                print("Set RUN_BUILD_STAR_INDEX = True after the genome FASTA and GTF are downloaded.")
            '''
        ),
        markdown("""
            ## Step 4: `tx2gene.tsv`を作る

            `tx2gene.tsv` は2列以上の表である。

            - `Name`: Salmonの `quant.sf` に出るtranscript ID
            - `gene_id`: そのtranscriptをgene単位にまとめるためのID

            このworkflowでは、count matrixとDESeq2結果の `gene_id` にGENCODE由来のEnsembl gene ID（例: `ENSG000001234.5`）を使う。clusterProfilerへ渡すときは `gene_id_type = ENSEMBL` とし、Rスクリプト側で末尾のversion番号（`.5` など）を外して照合する。
            """),
        code(
            r'''
            RUN_BUILD_TX2GENE = False

            if RUN_BUILD_TX2GENE:
                if not GTF_PATH.exists():
                    raise FileNotFoundError(GTF_PATH)

                seen_transcripts = set()
                written = 0
                with gzip.open(GTF_PATH, "rt") as gtf, TX2GENE_PATH.open("w", encoding="utf-8") as out:
                    out.write("Name\tgene_id\tensembl_gene_id\n")
                    for line in gtf:
                        if line.startswith("#"):
                            continue
                        fields = line.rstrip("\n").split("\t")
                        if len(fields) != 9 or fields[2] != "transcript":
                            continue
                        attributes = fields[8]
                        attrs = dict(re.findall(r'(\S+) "([^"]+)"', attributes))
                        transcript_id = attrs.get("transcript_id")
                        ensembl_gene_id = attrs.get("gene_id")
                        gene_name = attrs.get("gene_name") or ensembl_gene_id
                        if not transcript_id or not gene_name:
                            continue
                        if transcript_id in seen_transcripts:
                            continue
                        seen_transcripts.add(transcript_id)
                        out.write(f"{transcript_id}\t{gene_name}\t{ensembl_gene_id}\n")
                        written += 1

                print("Wrote:", TX2GENE_PATH.relative_to(PROJECT_DIR))
                print("Transcript rows:", written)
            else:
                print("Set RUN_BUILD_TX2GENE = True after the GTF file is downloaded.")
            '''
        ),
        code(
            r'''
            if TX2GENE_PATH.exists():
                import pandas as pd

                tx2gene = pd.read_csv(TX2GENE_PATH, sep="\t")
                print(tx2gene.shape)
                display(tx2gene.head())
            else:
                print("tx2gene.tsv is not created yet.")
            '''
        ),
        markdown("""
            ## Step 5: configに参照パスを書き込む

            `analysis_config.json` の `reference` 欄に、今作った参照ファイルの場所を書きる。相対パスで書くので、別のノートブックからも同じように読める。
            """),
        code(
            r'''
            RUN_UPDATE_CONFIG = False

            if RUN_UPDATE_CONFIG:
                config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                config["organism"] = "human"
                config["gene_id_type"] = "ENSEMBL"
                config["reference"] = {
                    "gencode_release": GENCODE_RELEASE,
                    "transcript_fasta": str(TRANSCRIPT_FASTA_PATH.relative_to(PROJECT_DIR)),
                    "salmon_index": str(SALMON_INDEX_DIR.relative_to(PROJECT_DIR)),
                    "star_index": str(STAR_INDEX_DIR.relative_to(PROJECT_DIR)),
                    "tx2gene_path": str(TX2GENE_PATH.relative_to(PROJECT_DIR)),
                    "gtf_path": str(GTF_PATH.relative_to(PROJECT_DIR)),
                    "genome_fasta": str(GENOME_FASTA_PATH.relative_to(PROJECT_DIR)),
                }
                CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                print("Updated:", CONFIG_PATH.relative_to(PROJECT_DIR))
            else:
                print("Set RUN_UPDATE_CONFIG = True after the reference files and index are ready.")
            '''
        ),
        markdown("""
            ## 最終確認

            ここが全部 `True` になったら、各mappingルートに応じた定量処理へ進める。
            """),
        code(
            r'''
            readiness = {
                "transcript_fasta": TRANSCRIPT_FASTA_PATH.exists(),
                "genome_fasta": GENOME_FASTA_PATH.exists(),
                "gtf": GTF_PATH.exists(),
                "tx2gene": TX2GENE_PATH.exists(),
                "salmon_index_dir": SALMON_INDEX_DIR.exists(),
                "star_index_dir": STAR_INDEX_DIR.exists(),
                "config": CONFIG_PATH.exists(),
            }
            readiness
            '''
        ),
        markdown("""
            **よくある間違い**

            - FASTAとGTFのreleaseを混ぜる。例: FASTAはv49、GTFはv48。
            - Salmon indexやSTAR indexを作らずに発現定量へ進む。
            - `tx2gene.tsv` を作らずにgene count matrixを作ろうとする。

            **小さい練習**

            `readiness` のどれが `False` かを見て、次に実行すべき `RUN_*` フラグを1つだけ選ぼう。
            """),
    ]


def nb_01_raw_read_qc() -> list[dict]:
    return [
        markdown("""
            # 01. Raw read QC（Quality Control）

            このノートブックは、FASTQが解析に耐えられるかを見る段階である。

            **この段階が答える問い**

            - FASTQファイルが壊れていないか。
            - read数がサンプル間で極端に違わないか。
            - read quality、adapter contamination、GC biasに大きな問題がないか。

            **入力**

            - `metadata/samples.tsv`: 各サンプル名、属する群、対応するFASTQファイルのパスをまとめたサンプルメタデータ表。
            - `raw_data/` のFASTQファイル: シーケンサーから出力された生の塩基配列データ（リード）。

            **出力**

            - `results/qc/fastq_inventory.tsv`: FASTQファイルのチェック結果（サイズ、MD5値、総リード数など）を記録した一覧表。
            - `results/qc/fastqc/`: 各サンプルのFASTQの品質評価情報（リード長、GC含量、アダプター配列の混入など）をまとめたFastQC出力結果フォルダ。
            - `results/qc/multiqc_report.html`: 全サンプルのFastQC結果を1つに統合したHTMLレポートファイル。

            **次に進む条件**

            - ファイル破損がない。
            - FastQC/MultiQCで重大な問題がない、または問題を理解して次に進む判断ができる。
            """),
        code(
            r'''
            from pathlib import Path
            import gzip
            import hashlib
            import json
            import shutil
            import subprocess

            import pandas as pd

            PROJECT_DIR = Path("/Users/yusuke_tateishi/Documents/RNA_seq").resolve()
            CONFIG = json.loads((PROJECT_DIR / "config" / "analysis_config.json").read_text(encoding="utf-8"))
            SAMPLES = pd.read_csv(PROJECT_DIR / CONFIG["samples_path"], sep="\t")
            QC_DIR = PROJECT_DIR / "results" / "qc"
            FASTQC_DIR = QC_DIR / "fastqc"
            QC_DIR.mkdir(parents=True, exist_ok=True)
            FASTQC_DIR.mkdir(parents=True, exist_ok=True)

            SAMPLES
            '''
        ),
        markdown("""
            ## FASTQ inventory

            まず、ファイルサイズと存在確認をする。これは品質評価ではなく、解析対象のファイル一覧を固定する作業である。
            """),
        code(
            r'''
            rows = []
            for _, sample in SAMPLES.iterrows():
                for mate_column in ["fastq_1", "fastq_2"]:
                    path = PROJECT_DIR / sample[mate_column]
                    rows.append(
                        {
                            "sample_id": sample["sample_id"],
                            "mate": mate_column,
                            "path": str(path.relative_to(PROJECT_DIR)),
                            "exists": path.exists(),
                            "size_gb": path.stat().st_size / 1024**3 if path.exists() else None,
                        }
                    )

            inventory = pd.DataFrame(rows)
            inventory.to_csv(QC_DIR / "fastq_inventory.tsv", sep="\t", index=False)
            inventory
            '''
        ),
        markdown("""
            ## gzipとして読めるか確認する

            `.fq.gz` はgzip圧縮ファイルである。先頭1行だけ読んで、圧縮ファイルとして壊れていないかを軽く確認する。
            """),
        code(
            r'''
            RUN_GZIP_SMOKE_TEST = True

            if RUN_GZIP_SMOKE_TEST:
                gzip_rows = []
                for path_text in inventory["path"]:
                    path = PROJECT_DIR / path_text
                    try:
                        with gzip.open(path, "rt") as handle:
                            first_line = handle.readline().strip()
                        gzip_rows.append({"path": path_text, "gzip_readable": True, "first_line": first_line[:80]})
                    except Exception as exc:
                        gzip_rows.append({"path": path_text, "gzip_readable": False, "first_line": str(exc)})
                gzip_check = pd.DataFrame(gzip_rows)
                gzip_check.to_csv(QC_DIR / "gzip_smoke_test.tsv", sep="\t", index=False)
                display(gzip_check)
            '''
        ),
        markdown("""
            ## read数を数える

            FASTQは4行で1 readである。行数を4で割るとread数になる。大きいファイルなので時間がかかる場合がある。
            """),
        code(
            r'''
            RUN_READ_COUNTS = False

            def count_fastq_reads(path: Path) -> int:
                line_count = 0
                with gzip.open(path, "rt") as handle:
                    for line_count, _ in enumerate(handle, start=1):
                        pass
                return line_count // 4

            if RUN_READ_COUNTS:
                read_rows = []
                for _, sample in SAMPLES.iterrows():
                    r1 = count_fastq_reads(PROJECT_DIR / sample["fastq_1"])
                    r2 = count_fastq_reads(PROJECT_DIR / sample["fastq_2"])
                    read_rows.append({"sample_id": sample["sample_id"], "reads_R1": r1, "reads_R2": r2})
                read_counts = pd.DataFrame(read_rows)
                read_counts.to_csv(QC_DIR / "read_counts.tsv", sep="\t", index=False)
                display(read_counts)
            else:
                print("Set RUN_READ_COUNTS = True to count reads. This can take time.")
            '''
        ),
        markdown("""
            ## FastQCを実行する

            FastQCは各FASTQを個別に検査する。結果はHTMLとzipで出る。

            初回だけ `RUN_FASTQC = True` にしよう。
            """),
        code(
            r'''
            RUN_FASTQC = False
            THREADS = int(CONFIG["quantification"].get("threads", 8))

            fastq_paths = [str(PROJECT_DIR / path) for path in inventory["path"]]
            fastqc_command = ["fastqc", "--threads", str(THREADS), "--outdir", str(FASTQC_DIR), *fastq_paths]
            (QC_DIR / "fastqc_command.txt").write_text(" ".join(fastqc_command) + "\n", encoding="utf-8")

            if RUN_FASTQC:
                fastqc = shutil.which("fastqc")
                if fastqc is None:
                    raise RuntimeError("fastqc was not found. Activate the rna-seq environment first.")
                fastqc_command[0] = fastqc
                subprocess.run(fastqc_command, check=True)
            else:
                print("Set RUN_FASTQC = True to run FastQC.")
                print("Command saved to:", (QC_DIR / "fastqc_command.txt").relative_to(PROJECT_DIR))
            '''
        ),
        markdown("""
            ## MultiQCを実行する

            MultiQCは、複数サンプルのFastQC結果を1つのHTMLにまとめる。FastQCが終わってから実行する。
            """),
        code(
            r'''
            RUN_MULTIQC = False

            if RUN_MULTIQC:
                multiqc = shutil.which("multiqc")
                if multiqc is None:
                    raise RuntimeError("multiqc was not found. Activate the rna-seq environment first.")
                command = [multiqc, str(FASTQC_DIR), "--outdir", str(QC_DIR), "--filename", "multiqc_report.html"]
                subprocess.run(command, check=True)
            else:
                print("Set RUN_MULTIQC = True after FastQC finishes.")
            '''
        ),
        markdown("""
            ## 何を見ればよいか

            MultiQCでまず見る項目は次の通りである。

            - Per base sequence quality: 末端で少し下がる程度ならよくある。
            - Adapter content: 強く出る場合はtrimmingを検討する。
            - GC content: サンプル間で大きくずれる場合は要注意である。
            - Sequence duplication levels: ライブラリの偏りや高発現RNAの影響を見る。
            - Total sequences: サンプル間で極端に違わないかを見る。

            **小さい練習**

            `results/qc/fastq_inventory.tsv` を開いて、R1/R2のペア数が各サンプルでそろっているか確認しよう。
            """),
    ]


def nb_02_quantification() -> list[dict]:
    return [
        markdown("""
            # 02. Salmon quantification and gene count matrix

            このノートブックは、FASTQ readを発現量テーブルへ変換する段階である。

            **この段階が答える問い**

            - 各サンプルで、どのtranscriptがどれくらい読まれたか。
            - transcript単位の結果をgene単位にまとめると、どんなcount matrixになるか。

            **入力**

            - `metadata/samples.tsv`: 各サンプル名、属する群、対応するFASTQファイルのパスをまとめたサンプルメタデータ表。
            - FASTQファイル: 各サンプルの生の配列リードデータ。
            - `reference/gencode_grch38/salmon_index/`: Salmonがreadを高速にマッピングするために構築したインデックスフォルダ。
            - `reference/gencode_grch38/tx2gene.tsv`: 転写産物ID（transcript ID）と遺伝子ID（gene ID）の対応を示したテキスト表。

            **出力**

            - `results/quant/salmon/<sample_id>/quant.sf`: 各サンプルの転写産物レベルでの発現量推計結果（推定カウント数、TPMなど）が含まれる結果ファイル。
            - `results/counts/gene_counts.tsv`: すべてのサンプルの遺伝子レベルでの発現リードカウント数をまとめた発現マトリクス表。

            **次に進む条件**

            - 9サンプルすべてに `quant.sf` がある。
            - gene count matrix の列名が `samples.tsv` の `sample_id` と一致している。
            """),
        code(
            r'''
            from pathlib import Path
            import json
            import shutil
            import subprocess

            import pandas as pd

            PROJECT_DIR = Path("/Users/yusuke_tateishi/Documents/RNA_seq").resolve()
            CONFIG = json.loads((PROJECT_DIR / "config" / "analysis_config.json").read_text(encoding="utf-8"))
            SAMPLES = pd.read_csv(PROJECT_DIR / CONFIG["samples_path"], sep="\t")

            QUANT_DIR = PROJECT_DIR / "results" / "quant" / "salmon"
            COUNTS_DIR = PROJECT_DIR / "results" / "counts"
            QUANT_DIR.mkdir(parents=True, exist_ok=True)
            COUNTS_DIR.mkdir(parents=True, exist_ok=True)

            SAMPLES[["sample_id", "condition", "fastq_1", "fastq_2"]]
            '''
        ),
        markdown("""
            ## 参照ファイルが準備済みか確認する

            ここが `False` なら、先に `00b_reference_setup_gencode_grch38.ipynb` を実行する。
            """),
        code(
            r'''
            def resolve_project_path(path_text: str) -> Path:
                path = Path(path_text)
                return path if path.is_absolute() else PROJECT_DIR / path

            reference = CONFIG["reference"]
            reference_paths = {
                "salmon_index": resolve_project_path(reference["salmon_index"]),
                "tx2gene_path": resolve_project_path(reference["tx2gene_path"]),
                "transcript_fasta": resolve_project_path(reference.get("transcript_fasta", "")) if reference.get("transcript_fasta") else None,
                "gtf_path": resolve_project_path(reference["gtf_path"]) if reference.get("gtf_path") else None,
            }

            readiness = {
                name: (path.exists() if path is not None else False)
                for name, path in reference_paths.items()
            }
            readiness
            '''
        ),
        markdown("""
            ## Salmonコマンドを作る

            `--libType A` は、Salmonにライブラリの向きを自動推定させる設定である。初心者の最初の解析ではこの設定が扱いやすい。
            """),
        code(
            r'''
            THREADS = int(CONFIG["quantification"].get("threads", 8))
            LIBRARY_TYPE = CONFIG["quantification"].get("salmon", {}).get("library_type", "A")

            salmon_commands = []
            for _, sample in SAMPLES.iterrows():
                output_dir = QUANT_DIR / sample["sample_id"]
                command = [
                    "salmon",
                    "quant",
                    "-i",
                    str(reference_paths["salmon_index"]),
                    "-l",
                    LIBRARY_TYPE,
                    "-1",
                    str(PROJECT_DIR / sample["fastq_1"]),
                    "-2",
                    str(PROJECT_DIR / sample["fastq_2"]),
                    "-p",
                    str(THREADS),
                    "--validateMappings",
                    "-o",
                    str(output_dir),
                ]
                salmon_commands.append(command)

            command_path = QUANT_DIR / "salmon_commands.txt"
            command_path.write_text("\n\n".join(" ".join(command) for command in salmon_commands) + "\n", encoding="utf-8")
            print("Commands written to:", command_path.relative_to(PROJECT_DIR))
            print("First command:")
            print(" ".join(salmon_commands[0]))
            '''
        ),
        markdown("""
            ## Salmonを実行する

            初回だけ `RUN_SALMON = True` にする。処理時間はデータ量とCPU数に依存する。
            """),
        code(
            r'''
            RUN_SALMON = False

            if RUN_SALMON:
                salmon = shutil.which("salmon")
                if salmon is None:
                    raise RuntimeError("salmon was not found. Activate the rna-seq environment first.")
                if not reference_paths["salmon_index"].exists():
                    raise FileNotFoundError(reference_paths["salmon_index"])
                for command in salmon_commands:
                    command[0] = salmon
                    print("Running:", " ".join(command))
                    subprocess.run(command, check=True)
            else:
                print("Set RUN_SALMON = True after the Salmon index is ready.")
            '''
        ),
        markdown("""
            ## Salmon結果がそろっているか確認する

            各サンプルの `quant.sf` が存在すれば、次にgene単位へ集計できる。
            """),
        code(
            r'''
            quant_status = []
            for sample_id in SAMPLES["sample_id"]:
                quant_path = QUANT_DIR / sample_id / "quant.sf"
                quant_status.append({"sample_id": sample_id, "quant_sf_exists": quant_path.exists(), "path": str(quant_path.relative_to(PROJECT_DIR))})

            quant_status = pd.DataFrame(quant_status)
            quant_status
            '''
        ),
        markdown("""
            ## gene count matrixを作る

            Salmonの `quant.sf` にはtranscript単位の `NumReads` が入っている。ここでは `tx2gene.tsv` を使ってgene単位に合計する。

            これはDESeq2へ渡すための表である。行がgene、列がsampleになる。
            """),
        code(
            r'''
            BUILD_GENE_COUNTS_FROM_SALMON = False

            if BUILD_GENE_COUNTS_FROM_SALMON:
                tx2gene_path = reference_paths["tx2gene_path"]
                if not tx2gene_path.exists():
                    raise FileNotFoundError(tx2gene_path)

                tx2gene = pd.read_csv(tx2gene_path, sep="\t")
                required_columns = {"Name", "gene_id"}
                if not required_columns.issubset(tx2gene.columns):
                    raise ValueError(f"tx2gene.tsv must contain columns: {required_columns}")
                tx2gene = tx2gene[["Name", "gene_id"]].drop_duplicates()

                per_sample_counts = []
                for sample_id in SAMPLES["sample_id"]:
                    quant_path = QUANT_DIR / sample_id / "quant.sf"
                    if not quant_path.exists():
                        raise FileNotFoundError(quant_path)
                    quant = pd.read_csv(quant_path, sep="\t", usecols=["Name", "NumReads"])
                    merged = quant.merge(tx2gene, on="Name", how="inner")
                    gene_counts = merged.groupby("gene_id", as_index=True)["NumReads"].sum()
                    gene_counts.name = sample_id
                    per_sample_counts.append(gene_counts)

                count_matrix = pd.concat(per_sample_counts, axis=1).fillna(0).round().astype(int)
                count_matrix.insert(0, "gene_id", count_matrix.index)
                out_path = PROJECT_DIR / CONFIG["differential_expression"]["count_matrix_path"]
                out_path.parent.mkdir(parents=True, exist_ok=True)
                count_matrix.to_csv(out_path, sep="\t", index=False)
                print("Wrote:", out_path.relative_to(PROJECT_DIR))
                display(count_matrix.head())
            else:
                print("Set BUILD_GENE_COUNTS_FROM_SALMON = True after all quant.sf files exist.")
            '''
        ),
        markdown("""
            ## count matrixの形を確認する

            count matrixが既にあれば、行数・列数・列名を確認する。
            """),
        code(
            r'''
            count_path = PROJECT_DIR / CONFIG["differential_expression"]["count_matrix_path"]
            if count_path.exists():
                counts = pd.read_csv(count_path, sep="\t")
                print("shape:", counts.shape)
                print("columns:", list(counts.columns[:10]))
                display(counts.head())
                missing_samples = set(SAMPLES["sample_id"]) - set(counts.columns)
                extra_samples = set(counts.columns) - {"gene_id"} - set(SAMPLES["sample_id"])
                print("missing_samples:", sorted(missing_samples))
                print("extra_samples:", sorted(extra_samples))
            else:
                print("No gene count matrix yet:", count_path.relative_to(PROJECT_DIR))
            '''
        ),
        markdown("""
            **よくある間違い**

            - `00b` を飛ばして `salmon_index` がない。
            - `quant.sf` が一部のサンプルだけ存在する。
            - `tx2gene.tsv` のtranscript IDと `quant.sf` の `Name` が合わず、集計後のgene数が少なすぎる。

            **小さい練習**

            `quant_status` で `False` のサンプルがあれば、そのサンプルのSalmonログを確認しよう。
            """),
    ]


def nb_03_sample_qc() -> list[dict]:
    return [
        markdown("""
            # 03. Sample QC（Quality Control） and exploratory normalization

            このノートブックは、count matrixができた後に、サンプル全体の関係を見る段階である。

            **この段階が答える問い**

            - 同じ群のreplicateが近いか。
            - read depthや検出遺伝子数が極端なサンプルはないか。
            - PCAや相関で明らかな外れ値がないか。

            **入力**

            - `results/counts/gene_counts.tsv`: すべてのサンプルの遺伝子レベルでの発現リードカウント数をまとめた発現マトリクス表。
            - `metadata/samples.tsv`: 各サンプル名、属する群、対応するFASTQファイルのパスをまとめたサンプルメタデータ表。

            **出力**

            - `results/sample_qc/library_size.tsv`: 各サンプルのシーケンスデプス（総リード数）と検出された遺伝子数をまとめた統計表。
            - `results/sample_qc/pca_logcpm.tsv`: サンプルの分類傾向を評価するために、正規化後の発現量データを用いて主成分分析（PCA（Principal Component Analysis））を行った結果の座標表。
            - `results/sample_qc/*.png`: 相関ヒートマップやPCAプロットなど、サンプルの品質管理やクラスター傾向を視覚化した画像ファイル。

            **次に進む条件**

            - 大きな外れ値がない、または外れ値の扱いを決めた。
            - 群間差よりbatchや個体差が支配的でないかを確認した。
            """),
        code(
            r'''
            from pathlib import Path
            import json

            import numpy as np
            import pandas as pd
            import matplotlib.pyplot as plt
            import seaborn as sns
            from sklearn.decomposition import PCA

            PROJECT_DIR = Path("/Users/yusuke_tateishi/Documents/RNA_seq").resolve()
            CONFIG = json.loads((PROJECT_DIR / "config" / "analysis_config.json").read_text(encoding="utf-8"))
            SAMPLES = pd.read_csv(PROJECT_DIR / CONFIG["samples_path"], sep="\t")
            COUNTS_PATH = PROJECT_DIR / CONFIG["differential_expression"]["count_matrix_path"]
            SAMPLE_QC_DIR = PROJECT_DIR / "results" / "sample_qc"
            SAMPLE_QC_DIR.mkdir(parents=True, exist_ok=True)

            if not COUNTS_PATH.exists():
                raise FileNotFoundError(f"Count matrix not found: {COUNTS_PATH}. Run notebook 02 first.")

            counts = pd.read_csv(COUNTS_PATH, sep="\t")
            counts = counts.set_index("gene_id")
            counts = counts[SAMPLES["sample_id"]]
            counts.head()
            '''
        ),
        markdown("""
            ## library sizeと検出遺伝子数

            library sizeは、各サンプルの総countである。検出遺伝子数は、countが1以上あるgene数である。
            """),
        code(
            r'''
            sample_qc = pd.DataFrame(
                {
                    "sample_id": counts.columns,
                    "library_size": counts.sum(axis=0).values,
                    "detected_genes": (counts > 0).sum(axis=0).values,
                }
            ).merge(SAMPLES[["sample_id", "condition", "replicate"]], on="sample_id", how="left")

            sample_qc.to_csv(SAMPLE_QC_DIR / "library_size.tsv", sep="\t", index=False)
            sample_qc
            '''
        ),
        code(
            r'''
            fig, axes = plt.subplots(1, 2, figsize=(11, 4))
            sns.barplot(data=sample_qc, x="sample_id", y="library_size", hue="condition", ax=axes[0])
            axes[0].tick_params(axis="x", rotation=45)
            axes[0].set_title("Library size")
            sns.barplot(data=sample_qc, x="sample_id", y="detected_genes", hue="condition", ax=axes[1])
            axes[1].tick_params(axis="x", rotation=45)
            axes[1].set_title("Detected genes")
            plt.tight_layout()
            plt.savefig(SAMPLE_QC_DIR / "library_size_detected_genes.png", dpi=160)
            plt.show()
            '''
        ),
        markdown("""
            ## logCPMを作る

            PCAや相関を見るために、countを `log2(CPM + 1)` に変換する。

            CPMは counts per million である。

            `CPM_gs = count_gs / library_size_s * 1,000,000`

            これは探索的可視化用である。DESeq2の統計検定そのものは次のノートブックで行う。
            """),
        code(
            r'''
            library_sizes = counts.sum(axis=0)
            cpm = counts.divide(library_sizes, axis=1) * 1_000_000
            log_cpm = np.log2(cpm + 1)
            log_cpm.head()
            '''
        ),
        markdown("""
            ## PCA（Principal Component Analysis）

            PCAは、サンプル間の大きな違いを2次元に圧縮して見る方法である。同じ群のreplicateが近くに集まるかを見る。
            """),
        code(
            r'''
            pca = PCA(n_components=2)
            pca_scores = pca.fit_transform(log_cpm.T)
            pca_df = pd.DataFrame(pca_scores, columns=["PC1", "PC2"])
            pca_df["sample_id"] = log_cpm.columns
            pca_df = pca_df.merge(SAMPLES[["sample_id", "condition", "replicate"]], on="sample_id", how="left")
            pca_df.to_csv(SAMPLE_QC_DIR / "pca_logcpm.tsv", sep="\t", index=False)

            explained = pca.explained_variance_ratio_ * 100
            fig, ax = plt.subplots(figsize=(6, 5))
            sns.scatterplot(data=pca_df, x="PC1", y="PC2", hue="condition", style="replicate", s=90, ax=ax)
            for _, row in pca_df.iterrows():
                ax.text(row["PC1"], row["PC2"], row["sample_id"], fontsize=8, ha="left", va="bottom")
            ax.set_xlabel(f"PC1 ({explained[0]:.1f}%)")
            ax.set_ylabel(f"PC2 ({explained[1]:.1f}%)")
            ax.set_title("PCA on logCPM")
            plt.tight_layout()
            plt.savefig(SAMPLE_QC_DIR / "pca_logcpm.png", dpi=160)
            plt.show()
            '''
        ),
        markdown("""
            ## sample correlation heatmap

            サンプル間相関は、サンプル同士が全体としてどれくらい似ているかを見る。同じ群のreplicateで高い相関が期待される。
            """),
        code(
            r'''
            correlation = log_cpm.corr(method="pearson")
            correlation.to_csv(SAMPLE_QC_DIR / "sample_correlation_logcpm.tsv", sep="\t")

            plt.figure(figsize=(7, 6))
            sns.heatmap(correlation, cmap="vlag", center=0.95, annot=True, fmt=".2f", square=True)
            plt.title("Sample correlation on logCPM")
            plt.tight_layout()
            plt.savefig(SAMPLE_QC_DIR / "sample_correlation_logcpm.png", dpi=160)
            plt.show()
            '''
        ),
        markdown("""
            ## 高発現遺伝子を見る

            高発現遺伝子はライブラリの構成に強く影響する。ミトコンドリア遺伝子、rRNA、ストレス応答遺伝子などが上位に出ることがある。
            """),
        code(
            r'''
            mean_counts = counts.mean(axis=1).sort_values(ascending=False)
            top_genes = mean_counts.head(30).rename("mean_count").reset_index()
            top_genes.to_csv(SAMPLE_QC_DIR / "top_mean_count_genes.tsv", sep="\t", index=False)
            top_genes.head(20)
            '''
        ),
        markdown("""
            **よくある間違い**

            - count matrixができた直後に、PCAや相関を見ずにDESeq2へ進む。
            - 外れ値らしきサンプルを見つけても、理由を調べずに機械的に削除する。

            **小さい練習**

            PCAで一番離れているサンプルがある場合、そのサンプルの `library_size` と `detected_genes` を見比べよう。
            """),
    ]


def nb_04_deseq2() -> list[dict]:
    return [
        markdown("""
            # 04. Differential expression with DESeq2

            このノートブックは、gene count matrixからDEGを検出する段階である。

            **この段階が答える問い**

            - ある条件で、どのgeneが基準群より上がったか、下がったか。
            - その変化は統計的にどれくらい信頼できるか。

            **入力**

            - `results/counts/gene_counts.tsv`: すべてのサンプルの遺伝子レベルでの発現リードカウント数をまとめた発現マトリクス表。
            - `metadata/samples.tsv`: 各サンプル名、属する群、対応するFASTQファイルのパスをまとめたサンプルメタデータ表。
            - `metadata/contrasts.tsv`: 比較対象となる群の組み合わせを定義した比較表。

            **出力**

            - `results/de/deseq2_<contrast_id>.csv`: 群間比較（例：`NAC_S2_2h` vs `Non`）の統計検定結果（log2FCやp-value、FDR（False Discovery Rate）調整後p-valueなど）をまとめたDEG（Differentially Expressed Gene）リスト表。
            - `results/de/deseq2_normalized_counts.tsv`: シーケンス深さの補正を行った、正規化後の遺伝子発現カウントマトリクス表。
            - `results/de/deseq2_vst_counts.tsv`: サンプル間の発現差をPCAや距離計算で扱いやすくするために、分散安定化変換（VST）を行った正規化データ表。
            - `results/de/MA_<contrast_id>.pdf`: 各遺伝子の平均発現量と対数フォールド変化（log2FC）の関係を可視化したMAプロット図。
            """),
        markdown("""
            ## DESeq2モデルの見取り図

            DESeq2は、gene `g`、sample `s` のcountを負の二項分布で扱う。

            `count_gs ~ NegativeBinomial(mean_gs, dispersion_g)`

            `design_formula = ~ condition` は、発現量の違いを `condition` の違いとして推定する設定である。

            batchを補正したい場合は、metadataに `batch` 列を作り、設定を `~ batch + condition` に変える。ただし、batchとconditionが完全に重なっている設計では補正できない。
            """),
        code(
            r'''
            from pathlib import Path
            import json
            import shutil
            import subprocess

            import pandas as pd

            PROJECT_DIR = Path("/Users/yusuke_tateishi/Documents/RNA_seq").resolve()
            CONFIG = json.loads((PROJECT_DIR / "config" / "analysis_config.json").read_text(encoding="utf-8"))
            COUNTS_PATH = PROJECT_DIR / CONFIG["differential_expression"]["count_matrix_path"]
            SAMPLES_PATH = PROJECT_DIR / CONFIG["samples_path"]
            CONTRASTS_PATH = PROJECT_DIR / CONFIG["contrasts_path"]
            DE_DIR = PROJECT_DIR / "results" / "de"
            DE_DIR.mkdir(parents=True, exist_ok=True)

            for path in [COUNTS_PATH, SAMPLES_PATH, CONTRASTS_PATH]:
                print(path.relative_to(PROJECT_DIR), "exists:", path.exists())
            '''
        ),
        markdown("""
            ## 入力表の確認

            count matrixのサンプル列とmetadataの `sample_id` が一致している必要がある。
            """),
        code(
            r'''
            if not COUNTS_PATH.exists():
                raise FileNotFoundError(f"Count matrix not found: {COUNTS_PATH}. Run notebook 02 first.")

            counts = pd.read_csv(COUNTS_PATH, sep="\t", nrows=5)
            samples = pd.read_csv(SAMPLES_PATH, sep="\t")
            contrasts = pd.read_csv(CONTRASTS_PATH, sep="\t")

            count_sample_columns = [column for column in counts.columns if column != "gene_id"]
            print("count matrix sample columns:", count_sample_columns)
            print("metadata sample IDs:", list(samples["sample_id"]))
            print("missing in counts:", sorted(set(samples["sample_id"]) - set(count_sample_columns)))
            print("extra in counts:", sorted(set(count_sample_columns) - set(samples["sample_id"])))
            display(contrasts)
            '''
        ),
        markdown("""
            ## DESeq2実行コマンド

            実際のDESeq2処理は `scripts/deseq2_differential_expression.R` に置いている。ノートブックは入力確認と実行管理に集中する。
            """),
        code(
            r'''
            DESEQ2_SCRIPT = PROJECT_DIR / "scripts" / "deseq2_differential_expression.R"

            deseq2_command = [
                "Rscript",
                str(DESEQ2_SCRIPT),
                f"--counts={COUNTS_PATH}",
                f"--metadata={SAMPLES_PATH}",
                f"--contrasts={CONTRASTS_PATH}",
                f"--outdir={DE_DIR}",
                f"--design={CONFIG['differential_expression']['design_formula']}",
                f"--reference={CONFIG['differential_expression']['reference_condition']}",
                f"--min-count={CONFIG['differential_expression']['min_count']}",
                f"--min-samples={CONFIG['differential_expression']['min_samples']}",
                f"--alpha={CONFIG['differential_expression']['alpha']}",
            ]

            command_path = DE_DIR / "deseq2_command.txt"
            command_path.write_text(" ".join(deseq2_command) + "\n", encoding="utf-8")
            print("Command written to:", command_path.relative_to(PROJECT_DIR))
            print(" ".join(deseq2_command))
            '''
        ),
        code(
            r'''
            RUN_DESEQ2 = False

            if RUN_DESEQ2:
                rscript = shutil.which("Rscript")
                if rscript is None:
                    raise RuntimeError("Rscript was not found. Activate the rna-seq environment first.")
                deseq2_command[0] = rscript
                subprocess.run(deseq2_command, check=True)
            else:
                print("Set RUN_DESEQ2 = True after sample QC looks acceptable.")
            '''
        ),
        markdown("""
            ## 結果の読み方

            DESeq2結果の主な列である。

            - `baseMean`: そのgeneの平均的な発現量。
            - `log2FoldChange`: test condition / reference condition のlog2比。
            - `pvalue`: 統計検定のp値。
            - `padj`: 多重検定補正後のp値。通常はこちらを重視する。
            - `direction`: このプロジェクトのRスクリプトが付けた簡易ラベル。
            """),
        code(
            r'''
            result_files = sorted(DE_DIR.glob("deseq2_*.csv"))
            result_files = [path for path in result_files if path.name not in {"deseq2_normalized_counts.tsv", "deseq2_vst_counts.tsv"}]

            summaries = []
            for path in result_files:
                de = pd.read_csv(path)
                summaries.append(
                    {
                        "file": path.name,
                        "rows": len(de),
                        "padj_lt_alpha": int((de["padj"] < CONFIG["differential_expression"]["alpha"]).sum()),
                        "up": int((de["direction"] == "up").sum()) if "direction" in de.columns else None,
                        "down": int((de["direction"] == "down").sum()) if "direction" in de.columns else None,
                    }
                )

            if summaries:
                display(pd.DataFrame(summaries))
            else:
                print("No DESeq2 result files yet. Run DESeq2 first.")
            '''
        ),
        markdown("""
            **よくある間違い**

            - `padj` ではなく、生の `pvalue` だけで判断する。
            - PCAで外れ値があるのに、そのままDESeq2へ進む。
            - `reference_condition` を確認せず、log2 fold changeの向きを誤解する。

            **小さい練習**

            `Oxi_2h_vs_Non` の `log2FoldChange > 0` は「Oxi_2hでNonより高い」という意味である。この向きを自分の言葉で確認しよう。
            """),
    ]


def nb_05_interpretation() -> list[dict]:
    return [
        markdown("""
            # 05. Biological interpretation and report materials

            このノートブックは、DESeq2の結果を生物学的なストーリーへ変換する段階である。

            **この段階が答える問い**

            - どの遺伝子が大きく・有意に変化したか。
            - 変化した遺伝子群は、どの経路・機能・細胞状態に関係しそうか。
            - レポートで見せる図と表はどこにあるか。

            **入力**

            - `results/de/deseq2_<contrast_id>.csv`: 各比較における遺伝子ごとの統計検定結果（フォールド変化、p-valueなど）を含むDEG（Differentially Expressed Gene）リスト表。
            - `results/de/deseq2_normalized_counts.tsv`: シーケンス深さ補正後の正規化遺伝子発現カウントマトリクス表。
            - `metadata/samples.tsv`: 各サンプル名、属する群、対応するFASTQファイルのパスをまとめたサンプルメタデータ表。

            **出力**

            - volcano plot: 横軸に対数フォールド変化（log2FC）、縦軸に有意性の対数（-log10 p-value）をプロットし、有意に変動した遺伝子を赤や青で強調した散布図。
            - DEGリスト: カットオフ基準（例：`|log2FC| > 1` かつ `FDR < 0.05`）を満たす有意な発現変動遺伝子を抽出した表。
            - top DEG heatmap: 発現変化が大きい主要な遺伝子の発現パターンの類似性を、サンプル間で階層的クラスタリングして可視化した熱マップ画像。
            - optional GO（Gene Ontology） enrichment / GSEA (Gene Set Enrichment Analysis): 有意な変動のあった遺伝子群が、特定の生物学的機能やパスウェイに統計的に集中（濃縮）しているかを確認するための機能濃縮分析結果。
            - `results/report/report_index.md`: 各解析ステップで作成したレポート用の図表へのリンクをまとめた、マークダウン形式の統合報告目次。
            """),
        code(
            r'''
            from pathlib import Path
            import json
            import shutil
            import subprocess

            import numpy as np
            import pandas as pd
            import matplotlib.pyplot as plt
            import seaborn as sns

            PROJECT_DIR = Path("/Users/yusuke_tateishi/Documents/RNA_seq").resolve()
            CONFIG = json.loads((PROJECT_DIR / "config" / "analysis_config.json").read_text(encoding="utf-8"))
            SAMPLES = pd.read_csv(PROJECT_DIR / CONFIG["samples_path"], sep="\t")
            CONTRASTS = pd.read_csv(PROJECT_DIR / CONFIG["contrasts_path"], sep="\t")
            DE_DIR = PROJECT_DIR / "results" / "de"
            REPORT_DIR = PROJECT_DIR / "results" / "report"
            ENRICHMENT_DIR = PROJECT_DIR / "results" / "enrichment"
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            ENRICHMENT_DIR.mkdir(parents=True, exist_ok=True)

            CONTRASTS
            '''
        ),
        markdown("""
            ## volcano plot

            volcano plotは、横軸に変化量、縦軸に有意性を置いた図である。

            - 右側: test conditionで上がる遺伝子。
            - 左側: test conditionで下がる遺伝子。
            - 上側: 統計的に強い遺伝子。
            """),
        code(
            r'''
            ALPHA = float(CONFIG["differential_expression"]["alpha"])
            LFC_THRESHOLD = float(CONFIG["differential_expression"]["lfc_threshold"])

            def load_de_result(contrast_id: str) -> pd.DataFrame:
                path = DE_DIR / f"deseq2_{contrast_id}.csv"
                if not path.exists():
                    raise FileNotFoundError(f"DESeq2 result not found: {path}. Run notebook 04 first.")
                de = pd.read_csv(path)
                de["minus_log10_padj"] = -np.log10(de["padj"].clip(lower=1e-300))
                de["is_deg"] = (de["padj"] < ALPHA) & (de["log2FoldChange"].abs() >= LFC_THRESHOLD)
                return de

            for contrast_id in CONTRASTS["contrast_id"]:
                try:
                    de = load_de_result(contrast_id)
                except FileNotFoundError as exc:
                    print(exc)
                    continue

                fig, ax = plt.subplots(figsize=(6.5, 5))
                sns.scatterplot(
                    data=de,
                    x="log2FoldChange",
                    y="minus_log10_padj",
                    hue="is_deg",
                    palette={False: "#9aa0a6", True: "#d62728"},
                    s=16,
                    linewidth=0,
                    ax=ax,
                )
                ax.axvline(LFC_THRESHOLD, color="black", linestyle="--", linewidth=0.8)
                ax.axvline(-LFC_THRESHOLD, color="black", linestyle="--", linewidth=0.8)
                ax.axhline(-np.log10(ALPHA), color="black", linestyle="--", linewidth=0.8)
                ax.set_title(contrast_id)
                ax.set_xlabel("log2 fold change")
                ax.set_ylabel("-log10 adjusted p-value")
                ax.legend(title="DEG", loc="upper right")
                plt.tight_layout()
                out_path = REPORT_DIR / f"volcano_{contrast_id}.png"
                plt.savefig(out_path, dpi=160)
                plt.show()
            '''
        ),
        markdown("""
            ## DEGリストを書き出す

            DEGリストは最終回答ではなく、解釈の材料である。ここではup/downに分けて保存する。
            """),
        code(
            r'''
            deg_summaries = []
            for contrast_id in CONTRASTS["contrast_id"]:
                path = DE_DIR / f"deseq2_{contrast_id}.csv"
                if not path.exists():
                    continue
                de = pd.read_csv(path)
                deg = de[(de["padj"] < ALPHA) & (de["log2FoldChange"].abs() >= LFC_THRESHOLD)].copy()
                deg = deg.sort_values(["padj", "log2FoldChange"], ascending=[True, False])
                deg.to_csv(REPORT_DIR / f"deg_{contrast_id}.csv", index=False)
                deg_summaries.append(
                    {
                        "contrast_id": contrast_id,
                        "deg_total": len(deg),
                        "up": int((deg["log2FoldChange"] > 0).sum()),
                        "down": int((deg["log2FoldChange"] < 0).sum()),
                    }
                )

            if deg_summaries:
                deg_summary = pd.DataFrame(deg_summaries)
                deg_summary.to_csv(REPORT_DIR / "deg_summary.tsv", sep="\t", index=False)
                display(deg_summary)
            else:
                print("No DEG outputs yet.")
            '''
        ),
        markdown("""
            ## top DEG（Differentially Expressed Gene） heatmap

            normalized countsがある場合、変化の大きい遺伝子をheatmapで見る。これは「各群で本当に一貫した変化があるか」を目で確認するためである。
            """),
        code(
            r'''
            normalized_counts_path = DE_DIR / "deseq2_normalized_counts.tsv"

            if normalized_counts_path.exists():
                normalized_counts = pd.read_csv(normalized_counts_path, sep="\t").set_index("gene_id")
                for contrast_id in CONTRASTS["contrast_id"]:
                    deg_path = REPORT_DIR / f"deg_{contrast_id}.csv"
                    if not deg_path.exists():
                        continue
                    deg = pd.read_csv(deg_path)
                    top_gene_ids = deg.head(40)["gene_id"].tolist()
                    top_gene_ids = [gene_id for gene_id in top_gene_ids if gene_id in normalized_counts.index]
                    if not top_gene_ids:
                        continue
                    matrix = np.log2(normalized_counts.loc[top_gene_ids, SAMPLES["sample_id"]] + 1)
                    matrix = matrix.sub(matrix.mean(axis=1), axis=0)
                    plt.figure(figsize=(9, max(5, len(top_gene_ids) * 0.18)))
                    sns.heatmap(matrix, cmap="vlag", center=0, yticklabels=True)
                    plt.title(f"Top DE genes: {contrast_id}")
                    plt.tight_layout()
                    plt.savefig(REPORT_DIR / f"heatmap_top_deg_{contrast_id}.png", dpi=160)
                    plt.show()
            else:
                print("No normalized counts yet. Run notebook 04 first.")
            '''
        ),
        markdown("""
            ## サンプルの階層的クラスタリング

            PCAはサンプル関係を2次元で見る方法であった。階層的クラスタリングは、サンプル同士の距離を計算して、近いサンプルから枝分かれ図としてまとめる。

            ここではDESeq2の `vst` 正規化値を使い、変動の大きい上位1000遺伝子でサンプルをクラスタリングする。

            読み方は単純である。同じconditionのreplicateが近くに集まれば、サンプル構造は比較的きれいである。`Non` と `Oxi_2h` が近く、`NAC_S2_2h` が別にまとまるなら、PCAで見えた構造と整合する。
            """),
        code(
            r'''
            vst_counts_path = DE_DIR / "deseq2_vst_counts.tsv"
            sample_cluster_path = REPORT_DIR / "sample_hierarchical_clustering_vst_top1000.png"
            sample_order_path = REPORT_DIR / "sample_hierarchical_clustering_order.tsv"

            if vst_counts_path.exists():
                from scipy.cluster.hierarchy import linkage, leaves_list
                from scipy.spatial.distance import pdist

                vst_counts = pd.read_csv(vst_counts_path, sep="\t").set_index("gene_id")
                vst_counts = vst_counts[SAMPLES["sample_id"]]

                top_variable_genes = vst_counts.var(axis=1).sort_values(ascending=False).head(1000).index
                sample_matrix = vst_counts.loc[top_variable_genes].T

                sample_linkage = linkage(pdist(sample_matrix, metric="correlation"), method="average")
                sample_order = [sample_matrix.index[i] for i in leaves_list(sample_linkage)]
                pd.DataFrame({"cluster_order": range(1, len(sample_order) + 1), "sample_id": sample_order}).merge(
                    SAMPLES[["sample_id", "condition", "replicate"]],
                    on="sample_id",
                    how="left",
                ).to_csv(sample_order_path, sep="\t", index=False)

                condition_palette = dict(zip(SAMPLES["condition"].unique(), sns.color_palette("Set2", n_colors=SAMPLES["condition"].nunique())))
                sample_colors = SAMPLES.set_index("sample_id").loc[sample_matrix.index, "condition"].map(condition_palette)

                grid = sns.clustermap(
                    sample_matrix,
                    row_linkage=sample_linkage,
                    col_cluster=False,
                    row_colors=sample_colors,
                    cmap="vlag",
                    center=sample_matrix.to_numpy().mean(),
                    xticklabels=False,
                    yticklabels=True,
                    figsize=(7, 6),
                )
                grid.fig.suptitle("Sample hierarchical clustering: VST top variable genes", y=1.02)
                grid.savefig(sample_cluster_path, dpi=180, bbox_inches="tight")
                plt.show()

                print("Sample cluster order:")
                display(pd.read_csv(sample_order_path, sep="\t"))
                print("Wrote:", sample_cluster_path.relative_to(PROJECT_DIR))
            else:
                print("No VST counts yet. Run notebook 04 first.")
            '''
        ),
        markdown("""
            ## DEGの階層的クラスタリング

            次に、各比較でDEGになった遺伝子だけを取り出し、発現パターンでクラスタリングする。

            ここではgeneごとに平均0、標準偏差1へ変換した値を使う。これにより「発現量が大きい遺伝子」ではなく、「どのサンプルで相対的に高いか/低いか」というパターンを見る。

            出力される `deg_clusters_<contrast>.tsv` は、各DEGがどのクラスタに入ったかを示す表である。たとえば、NAC_S2で上がるクラスタ、NAC_S2で下がるクラスタを読む材料になる。
            """),
        code(
            r'''
            if vst_counts_path.exists():
                from scipy.cluster.hierarchy import linkage, fcluster
                from scipy.spatial.distance import pdist

                vst_counts = pd.read_csv(vst_counts_path, sep="\t").set_index("gene_id")
                vst_counts = vst_counts[SAMPLES["sample_id"]]
                condition_palette = dict(zip(SAMPLES["condition"].unique(), sns.color_palette("Set2", n_colors=SAMPLES["condition"].nunique())))
                column_colors = SAMPLES.set_index("sample_id").loc[vst_counts.columns, "condition"].map(condition_palette)

                for contrast_id in CONTRASTS["contrast_id"]:
                    deg_path = REPORT_DIR / f"deg_{contrast_id}.csv"
                    if not deg_path.exists():
                        print("Skipping missing DEG file:", deg_path.relative_to(PROJECT_DIR))
                        continue

                    deg = pd.read_csv(deg_path)
                    deg_gene_ids = [gene_id for gene_id in deg["gene_id"].tolist() if gene_id in vst_counts.index]
                    if len(deg_gene_ids) < 2:
                        print(f"Skipping {contrast_id}: fewer than 2 DEG genes available for clustering.")
                        continue

                    matrix = vst_counts.loc[deg_gene_ids]
                    z_matrix = matrix.sub(matrix.mean(axis=1), axis=0).div(matrix.std(axis=1).replace(0, np.nan), axis=0).fillna(0)

                    row_linkage = linkage(pdist(z_matrix, metric="euclidean"), method="average")
                    cluster_labels = fcluster(row_linkage, t=2, criterion="maxclust")
                    cluster_table = pd.DataFrame({"gene_id": z_matrix.index, "cluster": cluster_labels}).merge(
                        deg[["gene_id", "log2FoldChange", "padj", "direction"]],
                        on="gene_id",
                        how="left",
                    )
                    cluster_table.to_csv(REPORT_DIR / f"deg_clusters_{contrast_id}.tsv", sep="\t", index=False)

                    grid = sns.clustermap(
                        z_matrix,
                        row_linkage=row_linkage,
                        col_cluster=True,
                        col_colors=column_colors,
                        cmap="vlag",
                        center=0,
                        yticklabels=True if len(deg_gene_ids) <= 80 else False,
                        xticklabels=True,
                        figsize=(9, max(5, len(deg_gene_ids) * 0.12)),
                    )
                    grid.fig.suptitle(f"DEG hierarchical clustering: {contrast_id}", y=1.02)
                    out_path = REPORT_DIR / f"clustermap_deg_{contrast_id}.png"
                    grid.savefig(out_path, dpi=180, bbox_inches="tight")
                    plt.show()

                    print("Wrote:", out_path.relative_to(PROJECT_DIR))
                    display(cluster_table.groupby(["cluster", "direction"]).size().reset_index(name="n_genes"))
            else:
                print("No VST counts yet. Run notebook 04 first.")
            '''
        ),
        markdown("""
            ## optional: clusterProfiler enrichment

            これは「DEGがどんな機能に偏っているか」を見る解析である。

            このworkflowのDESeq2結果では、`gene_id` にGENCODE由来のEnsembl gene ID（例: `ENSG000001234.5`）を使う。そのため `gene_id_type` は `ENSEMBL` にする。clusterProfilerへ渡す直前に、Rスクリプト側で末尾のversion番号（`.5` など）を外して照合する。
            """),
        code(
            r'''
            RUN_CLUSTERPROFILER = False
            ENRICHMENT_SCRIPT = PROJECT_DIR / "scripts" / "clusterprofiler_enrichment.R"
            CONFIG = json.loads((PROJECT_DIR / "config" / "analysis_config.json").read_text(encoding="utf-8"))

            if RUN_CLUSTERPROFILER:
                rscript = shutil.which("Rscript")
                if rscript is None:
                    raise RuntimeError("Rscript was not found. Activate the rna-seq environment first.")
                for contrast_id in CONTRASTS["contrast_id"]:
                    de_path = DE_DIR / f"deseq2_{contrast_id}.csv"
                    if not de_path.exists():
                        print("Skipping missing result:", de_path)
                        continue
                    outdir = ENRICHMENT_DIR / contrast_id
                    command = [
                        rscript,
                        str(ENRICHMENT_SCRIPT),
                        f"--de={de_path}",
                        f"--outdir={outdir}",
                        f"--organism={CONFIG['organism']}",
                        f"--gene-id-type={CONFIG['gene_id_type']}",
                        f"--padj={ALPHA}",
                        f"--lfc={LFC_THRESHOLD}",
                    ]
                    print("Running:", " ".join(command))
                    subprocess.run(command, check=True)
            else:
                print("Set RUN_CLUSTERPROFILER = True after DESeq2 results are ready.")
            '''
        ),
        markdown("""
            ## enrichment結果を可視化する

            ここでは、clusterProfilerが出したGO overrepresentation解析とGSEAのCSVを読み込み、比較ごとに見やすい図にする。

            **入力**

            - `results/enrichment/<contrast_id>/go_bp_overrepresentation.csv`: clusterProfilerを用いて、有意な発現変動遺伝子（DEG）が特定のGOのBiological Process（生物学的プロセス）のタームにどれだけ偏って存在するかを過剰表現解析した結果表。
            - `results/enrichment/<contrast_id>/go_bp_gsea.csv`: 発現変動の大きい順に並べたすべての遺伝子リストを用いて、遺伝子セット全体としてのシグナル変動を濃縮解析したGSEAの結果表。

            **出力**

            - `results/report/go_bp_overrepresentation_dotplot.png`: 過剰表現解析で有意に濃縮された上位のGOタームについて、濃縮率、関係する遺伝子数、および調整後p-valueを点で表現したドットプロット画像。
            - `results/report/go_bp_gsea_nes_barplot.png`: GSEA解析で活性化または抑制されている上位のGOタームを、標準化濃縮スコア（NES）の棒グラフで表現した画像。

            overrepresentation plotでは、点の横位置を `FoldEnrichment`、点の大きさをGO termに入ったDEG数 `Count`、色を次の値にする。

            $$
            -\\log_{10}(\\mathrm{p.adjust})
            $$

            `p.adjust` が小さいtermほど、この値は大きくなる。

            GSEA plotでは `NES` を見る。`NES > 0` はtest条件側に寄ったgene set、`NES < 0` はreference条件側に寄ったgene setとして読みる。
            """),
        code(
            r'''
            TOP_ENRICHMENT_TERMS = 10

            def read_enrichment_csv(contrast_id: str, filename: str) -> pd.DataFrame:
                path = ENRICHMENT_DIR / contrast_id / filename
                if not path.exists():
                    print("Missing enrichment file:", path.relative_to(PROJECT_DIR))
                    return pd.DataFrame()
                table = pd.read_csv(path)
                if table.empty:
                    return pd.DataFrame()
                table["contrast_id"] = contrast_id
                table["source_file"] = str(path.relative_to(PROJECT_DIR))
                return table

            ora_tables = [
                read_enrichment_csv(contrast_id, "go_bp_overrepresentation.csv")
                for contrast_id in CONTRASTS["contrast_id"]
            ]
            gsea_tables = [
                read_enrichment_csv(contrast_id, "go_bp_gsea.csv")
                for contrast_id in CONTRASTS["contrast_id"]
            ]

            ora_results = pd.concat([table for table in ora_tables if not table.empty], ignore_index=True) if any(not table.empty for table in ora_tables) else pd.DataFrame()
            gsea_results = pd.concat([table for table in gsea_tables if not table.empty], ignore_index=True) if any(not table.empty for table in gsea_tables) else pd.DataFrame()

            enrichment_summary = []
            for contrast_id in CONTRASTS["contrast_id"]:
                ora_n = int((ora_results["contrast_id"] == contrast_id).sum()) if not ora_results.empty else 0
                gsea_n = int((gsea_results["contrast_id"] == contrast_id).sum()) if not gsea_results.empty else 0
                enrichment_summary.append(
                    {
                        "contrast_id": contrast_id,
                        "ora_terms": ora_n,
                        "gsea_terms": gsea_n,
                    }
                )

            enrichment_summary = pd.DataFrame(enrichment_summary)
            display(enrichment_summary)
            '''
        ),
        code(
            r'''
            if ora_results.empty:
                print("No GO overrepresentation terms to plot. Run clusterProfiler first, or relax DEG thresholds if appropriate.")
            else:
                ora_results = ora_results.copy()
                ora_results["minus_log10_padj"] = -np.log10(ora_results["p.adjust"].clip(lower=1e-300))
                contrasts_with_ora = [cid for cid in CONTRASTS["contrast_id"] if (ora_results["contrast_id"] == cid).any()]

                fig, axes = plt.subplots(
                    nrows=len(contrasts_with_ora),
                    ncols=1,
                    figsize=(12, max(3.5, 3.8 * len(contrasts_with_ora))),
                    squeeze=False,
                )

                for ax, contrast_id in zip(axes[:, 0], contrasts_with_ora):
                    top_terms = (
                        ora_results[ora_results["contrast_id"] == contrast_id]
                        .sort_values("p.adjust")
                        .head(TOP_ENRICHMENT_TERMS)
                        .iloc[::-1]
                    )
                    sns.scatterplot(
                        data=top_terms,
                        x="FoldEnrichment",
                        y="Description",
                        size="Count",
                        hue="minus_log10_padj",
                        palette="viridis",
                        sizes=(45, 230),
                        edgecolor="black",
                        linewidth=0.3,
                        ax=ax,
                    )
                    ax.set_title(f"GO BP overrepresentation: {contrast_id}")
                    ax.set_xlabel("Fold enrichment")
                    ax.set_ylabel("")
                    ax.legend(
                        title="Count / -log10(padj)",
                        loc="center left",
                        bbox_to_anchor=(1.02, 0.5),
                        borderaxespad=0.0,
                        fontsize=8,
                        frameon=True,
                    )

                plt.tight_layout(rect=(0, 0, 0.82, 1))
                out_path = REPORT_DIR / "go_bp_overrepresentation_dotplot.png"
                plt.savefig(out_path, dpi=180, bbox_inches="tight")
                plt.show()
                print("Wrote:", out_path.relative_to(PROJECT_DIR))
            '''
        ),
        code(
            r'''
            if gsea_results.empty:
                print("No significant GSEA terms to plot. An empty GSEA file means no GO term passed the GSEA p-value cutoff.")
            else:
                gsea_results = gsea_results.copy()
                gsea_results["minus_log10_padj"] = -np.log10(gsea_results["p.adjust"].clip(lower=1e-300))
                contrasts_with_gsea = [cid for cid in CONTRASTS["contrast_id"] if (gsea_results["contrast_id"] == cid).any()]

                gsea_plot_terms = []
                for contrast_id in contrasts_with_gsea:
                    contrast_gsea = gsea_results[gsea_results["contrast_id"] == contrast_id]
                    up_terms = contrast_gsea[contrast_gsea["NES"] > 0].sort_values("p.adjust").head(TOP_ENRICHMENT_TERMS // 2)
                    down_terms = contrast_gsea[contrast_gsea["NES"] < 0].sort_values("p.adjust").head(TOP_ENRICHMENT_TERMS // 2)
                    top_terms = pd.concat([down_terms, up_terms], ignore_index=True).sort_values("NES")
                    if not top_terms.empty:
                        gsea_plot_terms.append((contrast_id, top_terms))

                max_abs_nes = max(float(top_terms["NES"].abs().max()) for _, top_terms in gsea_plot_terms)
                nes_limit = np.ceil((max_abs_nes + 0.1) * 10) / 10

                fig, axes = plt.subplots(
                    nrows=len(gsea_plot_terms),
                    ncols=1,
                    figsize=(10, max(3.5, 4.0 * len(gsea_plot_terms))),
                    squeeze=False,
                    sharex=True,
                )

                for ax, (contrast_id, top_terms) in zip(axes[:, 0], gsea_plot_terms):
                    colors = np.where(top_terms["NES"] >= 0, "#d62728", "#1f77b4")
                    ax.barh(top_terms["Description"], top_terms["NES"], color=colors)
                    ax.axvline(0, color="black", linewidth=0.8)
                    ax.set_xlim(-nes_limit, nes_limit)
                    ax.grid(axis="x", alpha=0.2)
                    ax.set_title(f"GO BP GSEA NES: {contrast_id}")
                    ax.set_xlabel("NES")
                    ax.set_ylabel("")
                    ax.text(
                        0.01,
                        0.02,
                        "blue: reference-side enrichment, red: test-side enrichment",
                        transform=ax.transAxes,
                        fontsize=8,
                        va="bottom",
                    )

                plt.tight_layout()
                out_path = REPORT_DIR / "go_bp_gsea_nes_barplot.png"
                plt.savefig(out_path, dpi=180, bbox_inches="tight")
                plt.show()
                print("Wrote:", out_path.relative_to(PROJECT_DIR))
            '''
        ),
        markdown("""
            ## report indexを作る

            最後に、どこに何が出力されたかを1つのMarkdownにまとめる。
            """),
        code(
            r'''
            report_lines = [
                "# RNA-seq analysis report index",
                "",
                "## Inputs",
                f"- Samples: `{CONFIG['samples_path']}`",
                f"- Contrasts: `{CONFIG['contrasts_path']}`",
                f"- Count matrix: `{CONFIG['differential_expression']['count_matrix_path']}`",
                "",
                "## Main outputs",
                "- QC: `results/qc/`",
                "- Quantification: `results/quant/salmon/`",
                "- Gene counts: `results/counts/gene_counts.tsv`",
                "- Sample QC: `results/sample_qc/`",
                "- DESeq2: `results/de/`",
                "- Report figures and DEG lists: `results/report/`",
                "- Enrichment: `results/enrichment/`",
                "",
                "## Contrasts",
            ]
            for _, row in CONTRASTS.iterrows():
                report_lines.append(f"- `{row['contrast_id']}`: {row['description']}")

            report_lines.extend(
                [
                    "",
                    "## Interpretation checklist",
                    "- Check sample QC before trusting DEG lists.",
                    "- Confirm log2 fold-change direction against the reference condition.",
                    "- Treat enrichment as hypothesis generation, not final proof.",
                ]
            )

            report_path = REPORT_DIR / "report_index.md"
            report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
            print(report_path.relative_to(PROJECT_DIR))
            '''
        ),
        markdown("""
            **よくある間違い**

            - DEGリストだけを見て結論を急ぐ。
            - pathway名だけを読んで、どの遺伝子が効いているか確認しない。
            - `NAC_S2_2h_vs_Oxi_2h` のような比較で、log2 fold changeの向きを取り違える。

            **小さい練習**

            1つのcontrastについて、up gene上位10個とdown gene上位10個を見て、既知のストレス応答遺伝子が含まれるか確認しよう。
            """),
    ]


def write_workflow_docs() -> None:
    write_text(
        "notebooks/README.md",
        """
        # RNA-seq notebook workflow

        Run the notebooks in numeric order. The workflow is written for a true beginner, so each notebook starts with the question answered by that stage, the required inputs, the outputs, and the condition for moving forward.

        ## 1. Common Setup (Run these first in the notebooks/ root directory)

        - `00a_project_setup_metadata.ipynb`  
          Create and review `metadata/samples.tsv`, `metadata/contrasts.tsv`, and `config/analysis_config.json`.
        - `00b_reference_setup_gencode_grch38.ipynb`  
          Download GENCODE GRCh38 release 49 reference files, build the Salmon index, create `tx2gene.tsv`, and update config.
        - `01_raw_read_qc.ipynb`  
          Check FASTQ file presence, gzip readability, optional read counts, FastQC, and MultiQC.

        ## 2. Downstream Analysis Paths (Branch into one of these subdirectories)

        Depending on your analysis strategy, choose one of the three directories below and run the numbered notebooks (02 to 05) inside it:

        ### A. Transcript Mapping Route (`transcript_mapping/`)
        Align reads to the transcriptome using Salmon, then aggregate abundance estimates to gene-level counts.
        - `02_quantification_count_matrix.ipynb` (Salmon quantification)
        - `03_sample_qc_normalization.ipynb` (PCA, correlation heatmaps)
        - `04_differential_expression.ipynb` (DESeq2 statistical testing)
        - `05_biological_interpretation_report.ipynb` (Volcano plots, clusterProfiler enrichment)

        ### B. Genome Mapping Route (`gene_mapping/`)
        Align reads to the genome using STAR, then summarize counts using featureCounts.
        - `02a_quantification_genome_mapping_featurecounts.ipynb` (STAR alignment + featureCounts)
        - `03_sample_qc_normalization.ipynb`
        - `04_differential_expression.ipynb`
        - `05_biological_interpretation_report.ipynb`

        ### C. Reference-Free Mapping Route (`ref_free_mapping/`)
        Perform de novo transcriptome assembly using Trinity, then quantify transcripts using Salmon.
        - `02c_quantification_denovo_trinity_salmon.ipynb` (Trinity assembly + Salmon quantification)
        - `03_sample_qc_normalization.ipynb`
        - `04_differential_expression.ipynb`
        - `05_biological_interpretation_report.ipynb`

        Start Jupyter from the activated environment:

        ```bash
        cd /Users/yusuke_tateishi/Documents/RNA_seq
        source scripts/activate_rna_seq.sh
        jupyter lab
        ```

        Heavy or external steps use explicit flags such as `RUN_DOWNLOAD = False`, `RUN_SALMON = False`, and `RUN_DESEQ2 = False`. Change one flag at a time after reading the explanation above that cell.
        """,
    )

    write_text(
        "config/README_config.md",
        """
        # analysis_config.json guide

        This file stores shared settings used by the RNA-seq notebooks.

        ## project paths

        - `project_dir`: Setting to the absolute project root used by every notebook.
        - `raw_data_dir`: Setting to the directory containing sample FASTQ folders.
        - `samples_path`: Setting to the sample metadata table.
        - `contrasts_path`: Setting to the DESeq2 contrast table.

        ## biological assumptions

        - `organism`: Setting to the organism assumption used for reference and enrichment. Current assumption: `human`.
        - `gene_id_type`: Setting to the gene identifier type expected by clusterProfiler. Current workflow uses `ENSEMBL` because DESeq2 outputs GENCODE Ensembl gene IDs.

        ## reference

        These paths are not arbitrary settings. They point to the reference dictionary used to translate reads into transcripts and genes.

        - `reference.gencode_release`: Setting to the GENCODE release used consistently across reference files.
        - `reference.transcript_fasta`: Setting to the transcript FASTA used to build the Salmon index.
        - `reference.salmon_index`: Setting to the Salmon transcriptome index directory.
        - `reference.tx2gene_path`: Setting to the transcript-to-gene mapping table used to aggregate Salmon output.
        - `reference.gtf_path`: Setting to the genome annotation file that matches the reference release.
        - `reference.genome_fasta`: Setting to the genome FASTA file. It is not required for the current Salmon-first workflow.

        Prepare these files in `00b_reference_setup_gencode_grch38.ipynb`.

        ## quantification

        - `quantification.method`: Setting to the quantification backend. Current workflow uses `salmon`.
        - `quantification.threads`: Setting to the number of CPU threads for external tools.

        ### Salmon parameters
        - `quantification.salmon.library_type`: Setting to Salmon library type. `A` means automatic detection.
        - `quantification.salmon.validate_mappings`: Setting to enable Salmon mapping validation.

        ### STAR mapping parameters (for genome alignment route)

        - `quantification.star.read_length`: Setting to the read length of FASTQ reads in base pairs (default: 150).
        - `quantification.star.sjdb_overhang`: Setting to the sjdbOverhang parameter for STAR genome index generation (typically read_length - 1 = 149).
        - `quantification.star.featurecounts_strandness`: Strand specificity for featureCounts (0: unstranded, 1: stranded, 2: reversely stranded).

        ### Trinity parameters (for de novo transcriptome assembly route)

        - `quantification.trinity.max_memory`: Maximum memory allocated for Trinity execution (e.g. "10G").
        - `quantification.trinity.seq_type`: Sequence file format, e.g. "fq" for FASTQ.
        - `quantification.trinity.ss_lib_type`: Strand-specific library type for Trinity (e.g., "RF", "FR", or empty if unstranded).

        ## differential_expression

        - `differential_expression.count_matrix_path`: Setting to the gene-level count matrix consumed by DESeq2.
        - `differential_expression.design_formula`: Setting to the DESeq2 design formula. Add batch terms here only when metadata supports them.
        - `differential_expression.reference_condition`: Setting to the baseline condition for factor releveling.
        - `differential_expression.min_count`: Setting to the minimum raw count used by the pre-DESeq2 gene filter.
        - `differential_expression.min_samples`: Setting to the number of samples that must pass the minimum count.
        - `differential_expression.alpha`: Setting to the adjusted p-value threshold.
        - `differential_expression.lfc_threshold`: Setting to the absolute log2 fold-change threshold used in plots and reports.
        """,
    )

    write_text(
        "config/analysis_config.json",
        """
        {
          "project_dir": "/Users/yusuke_tateishi/Documents/RNA_seq",
          "raw_data_dir": "raw_data",
          "samples_path": "metadata/samples.tsv",
          "contrasts_path": "metadata/contrasts.tsv",
          "organism": "human",
          "gene_id_type": "ENSEMBL",
          "reference": {
            "gencode_release": "49",
            "transcript_fasta": "reference/gencode_grch38/gencode.v49.transcripts.fa.gz",
            "salmon_index": "reference/gencode_grch38/salmon_index",
            "star_index": "reference/gencode_grch38/star_index",
            "tx2gene_path": "reference/gencode_grch38/tx2gene.tsv",
            "gtf_path": "reference/gencode_grch38/gencode.v49.annotation.gtf.gz",
            "genome_fasta": "reference/gencode_grch38/GRCh38.primary_assembly.genome.fa.gz"
          },
          "quantification": {
            "method": "salmon",
            "threads": 8,
            "salmon": {
              "library_type": "A",
              "validate_mappings": true
            },
            "star": {
              "read_length": 150,
              "sjdb_overhang": 149,
              "featurecounts_strandness": 0
            },
            "trinity": {
              "max_memory": "10G",
              "seq_type": "fq",
              "ss_lib_type": "RF"
            }
          },
          "differential_expression": {
            "count_matrix_path": "results/counts/gene_counts.tsv",
            "design_formula": "~ condition",
            "reference_condition": "Non",
            "min_count": 10,
            "min_samples": 2,
            "alpha": 0.05,
            "lfc_threshold": 1.0
          }
        }
        """,
    )

    write_text(
        "environment.yml",
        """
        name: rna-seq
        channels:
          - conda-forge
          - bioconda
          - defaults
        dependencies:
          - python=3.12
          - jupyterlab
          - ipykernel
          - pandas
          - numpy
          - matplotlib
          - seaborn
          - scikit-learn
          - fastqc
          - multiqc
          - salmon
          - subread
          - samtools
          - r-base
          - r-ggplot2
          - r-pheatmap
          - bioconductor-deseq2
          - bioconductor-clusterprofiler
          - bioconductor-org.hs.eg.db
          - bioconductor-org.mm.eg.db
        """,
    )


def main() -> None:
    write_notebook("00a_project_setup_metadata.ipynb", nb_00_project_setup_metadata())
    write_notebook("00b_reference_setup_gencode_grch38.ipynb", nb_00b_reference_setup())
    write_notebook("01_raw_read_qc.ipynb", nb_01_raw_read_qc())
    write_notebook("transcript_mapping/02_quantification_count_matrix.ipynb", nb_02_quantification())
    write_notebook("transcript_mapping/03_sample_qc_normalization.ipynb", nb_03_sample_qc())
    write_notebook("transcript_mapping/04_differential_expression.ipynb", nb_04_deseq2())
    write_notebook("transcript_mapping/05_biological_interpretation_report.ipynb", nb_05_interpretation())
    write_workflow_docs()


if __name__ == "__main__":
    main()
