# 1. Utiliser une image de base Python
FROM python:3.9-slim

# 2. Définir le répertoire de travail dans le conteneur
WORKDIR /app

# 3. Copier les fichiers nécessaires dans le conteneur
COPY . /app

# 4. Installer Poetry et les dépendances
RUN pip install poetry \
    && poetry install --no-root

# 5. Exposer le port utilisé par FastAPI
EXPOSE 8000

# 6. Commande pour lancer l'application
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
