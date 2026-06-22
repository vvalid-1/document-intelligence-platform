#!/bin/bash
set -e

# Remove incomplete blob
find /app/uploads/.whisper_cache -name "*.incomplete" -delete 2>/dev/null || true

# Download model with xet disabled (falls back to standard HTTPS)
export HF_HUB_DISABLE_XET=1
export HF_HOME=/app/uploads/.whisper_cache

python3 -c "
from faster_whisper import WhisperModel
print('Downloading faster-whisper base model...')
m = WhisperModel('base', device='cpu', compute_type='int8', download_root='/app/uploads/.whisper_cache')
print('Model ready.')
"
