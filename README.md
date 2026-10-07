```
docker build -t ocr-worker .
docker run --rm \
  --name ocr-worker \
  -e REDIS_URL="redis://" \
  ocr-worker
```