#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(clusterProfiler)
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
de_path <- read_arg(args, "de")
outdir <- read_arg(args, "outdir", "results/enrichment")
organism <- read_arg(args, "organism", "human")
gene_id_type <- read_arg(args, "gene-id-type", "SYMBOL")
padj_cutoff <- as.numeric(read_arg(args, "padj", "0.05"))
lfc_cutoff <- as.numeric(read_arg(args, "lfc", "1"))

if (is.null(de_path)) {
  stop("Required argument: --de=path/to/deseq2_contrast.csv")
}

if (organism == "human") {
  suppressPackageStartupMessages(library(org.Hs.eg.db))
  orgdb <- org.Hs.eg.db
} else if (organism == "mouse") {
  suppressPackageStartupMessages(library(org.Mm.eg.db))
  orgdb <- org.Mm.eg.db
} else {
  stop("Supported organisms: human, mouse")
}

dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
de <- read.csv(de_path, check.names = FALSE)
tested <- de[!is.na(de$padj) & !is.na(de$log2FoldChange), ]
selected <- tested[tested$padj < padj_cutoff & abs(tested$log2FoldChange) >= lfc_cutoff, ]

if (nrow(selected) == 0) {
  writeLines("No genes passed the enrichment threshold.", file.path(outdir, "enrichment_status.txt"))
  quit(save = "no", status = 0)
}

ego <- enrichGO(
  gene = selected$gene_id,
  OrgDb = orgdb,
  keyType = gene_id_type,
  ont = "BP",
  pAdjustMethod = "BH",
  pvalueCutoff = 0.05,
  qvalueCutoff = 0.2,
  readable = TRUE
)

write.csv(as.data.frame(ego), file.path(outdir, "go_bp_overrepresentation.csv"), row.names = FALSE)

ranked <- tested$log2FoldChange
names(ranked) <- tested$gene_id
ranked <- sort(ranked, decreasing = TRUE)

gsea_go <- gseGO(
  geneList = ranked,
  OrgDb = orgdb,
  keyType = gene_id_type,
  ont = "BP",
  minGSSize = 10,
  maxGSSize = 500,
  pvalueCutoff = 0.05,
  verbose = FALSE
)

write.csv(as.data.frame(gsea_go), file.path(outdir, "go_bp_gsea.csv"), row.names = FALSE)
writeLines(capture.output(sessionInfo()), file.path(outdir, "clusterprofiler_session_info.txt"))
