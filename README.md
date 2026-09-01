## How to Run
```
uv sync
```
```
uv run hypercorn app.main:app --reload
```

### Run With Docker
```
docker build -t extracteur-backend .
docker run -p 8000:8000 extracteur-backend
```