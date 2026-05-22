#!/usr/bin/env bash

PROJECT_DIR="/Users/yusuke_tateishi/Documents/RNA_seq"
CONDA_SH="$HOME/miniconda3/etc/profile.d/conda.sh"

if [[ ! -f "$CONDA_SH" ]]; then
  echo "Conda initialization file not found: $CONDA_SH" >&2
  return 1 2>/dev/null || exit 1
fi

source "$CONDA_SH"
conda activate rna-seq

# Some local shell setups prepend other Python distributions ahead of Conda.
# Put the active environment back at the front so python, jupyter, and Rscript
# resolve to rna-seq consistently.
export PATH="$CONDA_PREFIX/bin:$PATH"

mkdir -p "$PROJECT_DIR/.cache/matplotlib" "$PROJECT_DIR/.cache/fontconfig" "$PROJECT_DIR/.cache/ipython"
export MPLCONFIGDIR="$PROJECT_DIR/.cache/matplotlib"
export XDG_CACHE_HOME="$PROJECT_DIR/.cache"
export IPYTHONDIR="$PROJECT_DIR/.cache/ipython"

hash -r 2>/dev/null || true

echo "Activated rna-seq"
echo "python: $(command -v python)"
echo "Rscript: $(command -v Rscript)"
