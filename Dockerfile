# 1. Use a lightweight base image
FROM python:3.9-slim


# 2. Set the working directory
WORKDIR /app

# 3. Copy Poetry configuration files first for dependency caching
COPY poetry.lock pyproject.toml /app/

# 4. Install Poetry and dependencies (cached if pyproject.toml or poetry.lock doesn't change)
RUN pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-root

# 5. Copy the application code (changes more frequently)
COPY . /app

# 6. Expose the FastAPI port
EXPOSE 8000

#7. Command to start the FastAPI application
#CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "::", "--port", "8000"]
