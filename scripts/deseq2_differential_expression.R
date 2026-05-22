#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(DESeq2)
})

read_arg <- function(args, name, default = NULL) {
  prefix <- paste0("--", name, "=")
  hit <- args[startsWith(args, prefix)]
  if (length(hit) == 0) {
    return(default)
  }
  sub(prefix, "", hit[[1]], fixed = TRUE)
}

args <- commandArgs(trailingOnly = TRUE)

counts_path <- read_arg(args, "counts")
metadata_path <- read_arg(args, "metadata")
contrasts_path <- read_arg(args, "contrasts")
outdir <- read_arg(args, "outdir", "results/de")
design_formula_text <- read_arg(args, "design", "~ condition")
reference_condition <- read_arg(args, "reference", "Non")
min_count <- as.integer(read_arg(args, "min-count", "10"))
min_samples <- as.integer(read_arg(args, "min-samples", "2"))
alpha <- as.numeric(read_arg(args, "alpha", "0.05"))

if (is.null(counts_path) || is.null(metadata_path) || is.null(contrasts_path)) {
  stop("Required arguments: --counts=..., --metadata=..., --contrasts=...")
}

dir.create(outdir, recursive = TRUE, showWarnings = FALSE)

counts <- read.delim(counts_path, check.names = FALSE)
if (!"gene_id" %in% colnames(counts)) {
  colnames(counts)[1] <- "gene_id"
}
rownames(counts) <- counts$gene_id
count_matrix <- as.matrix(round(counts[, setdiff(colnames(counts), "gene_id"), drop = FALSE]))
storage.mode(count_matrix) <- "integer"

metadata <- read.delim(metadata_path, check.names = FALSE)
rownames(metadata) <- metadata$sample_id
missing_samples <- setdiff(colnames(count_matrix), metadata$sample_id)
if (length(missing_samples) > 0) {
  stop("Count matrix samples missing from metadata: ", paste(missing_samples, collapse = ", "))
}
metadata <- metadata[colnames(count_matrix), , drop = FALSE]

if ("condition" %in% colnames(metadata)) {
  metadata$condition <- factor(metadata$condition)
  if (reference_condition %in% levels(metadata$condition)) {
    metadata$condition <- relevel(metadata$condition, ref = reference_condition)
  }
}

keep <- rowSums(count_matrix >= min_count) >= min_samples
filtered_count_matrix <- count_matrix[keep, , drop = FALSE]
if (nrow(filtered_count_matrix) == 0) {
  stop("No genes passed the count filter. Lower --min-count or --min-samples.")
}

design_formula <- as.formula(design_formula_text)
dds <- DESeqDataSetFromMatrix(
  countData = filtered_count_matrix,
  colData = metadata,
  design = design_formula
)
dds <- DESeq(dds)

normalized_counts <- counts(dds, normalized = TRUE)
write.table(
  data.frame(gene_id = rownames(normalized_counts), normalized_counts, check.names = FALSE),
  file = file.path(outdir, "deseq2_normalized_counts.tsv"),
  sep = "\t",
  quote = FALSE,
  row.names = FALSE
)

vst_counts <- assay(vst(dds, blind = FALSE))
write.table(
  data.frame(gene_id = rownames(vst_counts), vst_counts, check.names = FALSE),
  file = file.path(outdir, "deseq2_vst_counts.tsv"),
  sep = "\t",
  quote = FALSE,
  row.names = FALSE
)

contrasts <- read.delim(contrasts_path, check.names = FALSE)
required_contrast_columns <- c("contrast_id", "test_condition", "reference_condition")
if (!all(required_contrast_columns %in% colnames(contrasts))) {
  stop("Contrasts file must contain: ", paste(required_contrast_columns, collapse = ", "))
}

for (i in seq_len(nrow(contrasts))) {
  contrast_id <- contrasts$contrast_id[[i]]
  test_condition <- contrasts$test_condition[[i]]
  baseline_condition <- contrasts$reference_condition[[i]]
  result <- results(
    dds,
    contrast = c("condition", test_condition, baseline_condition),
    alpha = alpha
  )
  result_df <- as.data.frame(result)
  result_df$gene_id <- rownames(result_df)
  result_df$direction <- ifelse(
    is.na(result_df$padj),
    "not_tested",
    ifelse(
      result_df$padj < alpha & result_df$log2FoldChange > 0,
      "up",
      ifelse(result_df$padj < alpha & result_df$log2FoldChange < 0, "down", "not_significant")
    )
  )
  result_df <- result_df[, c("gene_id", setdiff(colnames(result_df), "gene_id"))]

  write.csv(
    result_df,
    file = file.path(outdir, paste0("deseq2_", contrast_id, ".csv")),
    row.names = FALSE,
    quote = TRUE
  )

  pdf(file.path(outdir, paste0("MA_", contrast_id, ".pdf")), width = 6, height = 5)
  plotMA(result, main = contrast_id, ylim = c(-6, 6))
  dev.off()
}

saveRDS(dds, file.path(outdir, "deseq2_dataset.rds"))
writeLines(capture.output(sessionInfo()), file.path(outdir, "deseq2_session_info.txt"))
