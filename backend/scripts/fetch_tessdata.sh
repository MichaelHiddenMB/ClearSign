#!/usr/bin/env sh
# Downloads the tessdata_best English model (float LSTM, more accurate than the
# integer tessdata_fast model most package managers install).
set -e
dir="$(cd "$(dirname "$0")/.." && pwd)/tessdata"
mkdir -p "$dir"
if [ -f "$dir/eng.traineddata" ]; then
  echo "eng.traineddata already present in $dir"
  exit 0
fi
echo "Downloading tessdata_best/eng.traineddata (about 15 MB)..."
curl -fsSL -o "$dir/eng.traineddata" https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata
echo "Saved to $dir/eng.traineddata"
