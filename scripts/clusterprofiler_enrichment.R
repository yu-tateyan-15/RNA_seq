#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(clusterProfiler)
})

empty_go_table <- function(path) {
  write.csv(
    data.frame(
      ID = character(),
      Description = character(),
      pvalue = numeric(),
      p.adjust = numeric(),
      qvalue = numeric(),
      geneID = character(),
      Count = integer()
    ),
    path,
    row.names = FALSE
  )
}

empty_gsea_table <- function(path) {
  write.csv(
    data.frame(
      ID = character(),
      Description = character(),
      setSize = integer(),
      enrichmentScore = numeric(),
      NES = numeric(),
      pvalue = numeric(),
      p.adjust = numeric(),
      qvalue = numeric(),
      core_enrichment = character()
    ),
    path,
    row.names = FALSE
  )
}

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
gene_id_type <- toupper(read_arg(args, "gene-id-type", "ENSEMBL"))
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
required_columns <- c("gene_id", "log2FoldChange", "padj")
if (!all(required_columns %in% colnames(de))) {
  stop("DE result must contain columns: ", paste(required_columns, collapse = ", "))
}

if (!gene_id_type %in% AnnotationDbi::keytypes(orgdb)) {
  stop(
    "Unsupported --gene-id-type for this organism: ", gene_id_type,
    ". Available key types include: ",
    paste(AnnotationDbi::keytypes(orgdb), collapse = ", ")
  )
}

normalize_gene_ids <- function(ids, key_type) {
  ids <- as.character(ids)
  ids <- trimws(ids)
  if (key_type == "ENSEMBL") {
    ids <- sub("\\.[0-9]+$", "", ids)
  }
  ids
}

tested <- de[!is.na(de$padj) & !is.na(de$log2FoldChange), ]
tested$enrichment_gene_id <- normalize_gene_ids(tested$gene_id, gene_id_type)
tested <- tested[!is.na(tested$enrichment_gene_id) & tested$enrichment_gene_id != "", ]
tested <- tested[!duplicated(tested$enrichment_gene_id), ]

selected <- tested[tested$padj < padj_cutoff & abs(tested$log2FoldChange) >= lfc_cutoff, ]

if (nrow(selected) == 0) {
  writeLines("No genes passed the enrichment threshold.", file.path(outdir, "enrichment_status.txt"))
  empty_go_table(file.path(outdir, "go_bp_overrepresentation.csv"))
  empty_gsea_table(file.path(outdir, "go_bp_gsea.csv"))
  writeLines(capture.output(sessionInfo()), file.path(outdir, "clusterprofiler_session_info.txt"))
  quit(save = "no", status = 0)
}

valid_keys <- AnnotationDbi::keys(orgdb, keytype = gene_id_type)
selected_gene_ids <- unique(selected$enrichment_gene_id)
selected_gene_ids <- selected_gene_ids[selected_gene_ids %in% valid_keys]

if (length(selected_gene_ids) == 0) {
  writeLines(
    c(
      "No selected genes could be mapped by clusterProfiler.",
      paste0("gene_id_type: ", gene_id_type),
      "If GENCODE Ensembl IDs include version suffixes such as ENSG000001234.5, use --gene-id-type=ENSEMBL; the script strips the suffix for enrichment lookup."
    ),
    file.path(outdir, "enrichment_status.txt")
  )
  empty_go_table(file.path(outdir, "go_bp_overrepresentation.csv"))
  empty_gsea_table(file.path(outdir, "go_bp_gsea.csv"))
  writeLines(capture.output(sessionInfo()), file.path(outdir, "clusterprofiler_session_info.txt"))
  quit(save = "no", status = 0)
}

ego <- enrichGO(
  gene = selected_gene_ids,
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
names(ranked) <- tested$enrichment_gene_id
ranked <- ranked[names(ranked) %in% valid_keys]
ranked <- sort(ranked, decreasing = TRUE)

if (length(ranked) < 10) {
  writeLines("Fewer than 10 ranked genes could be mapped; skipping GSEA.", file.path(outdir, "enrichment_status.txt"))
  empty_gsea_table(file.path(outdir, "go_bp_gsea.csv"))
} else {
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
}
writeLines(capture.output(sessionInfo()), file.path(outdir, "clusterprofiler_session_info.txt"))
