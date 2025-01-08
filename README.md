# Observia Backend Metadata API

## Overview

The Observia Backend Metadata API is a FastAPI-based application designed for managing and processing metadata.

## Features

- **REST API** for metadata operations.
- Integration with **LangChain** and **OpenAI** for metadata processing.
- Structured output using **Pydantic** models.
- Ready for containerized deployment using **Docker Compose**.
- Includes development-friendly tools like Poetry for dependency management.

The system is deployed from SLGO's GitLab to Github to a Google Cloud Run service.

## Project Structure

```
observia_backend_metadata/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── endpoints.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── chain_setup.py
│   │   ├── models.py
│   │   └── prompts.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── metadata.py
│   │   └── eov.py
│   ├── services/
│   ├── utils/
│   │   └── helpers.py
│   └── __init__.py
├── main.py
├── tests/
├── Dockerfile
├── docker-compose.yml
├── poetry.lock
├── pyproject.toml
└── README.md
```

## Prerequisites

- **Python 3.9 or later**
- **Poetry** for dependency management
- **Docker and Docker Compose** for containerization

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/your-repo/observia-backend-metadata.git
   cd observia-backend-metadata
   ```

2. Set up environment variables:

   Create a `.env` file at the root of the project and define the following variables:

   ```env
   OPENAI_API_KEY=your-api-key-here
   ```

## Usage

### Using Docker

1. Build and start the containers:

   ```bash
   docker-compose up --build
   ```

2. Access the API documentation:

   Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.

### Continuous Integration

This project is maintained via the [SLGO selfhosted gitlab depository](http://10.0.4.9:1410/sandbox-ogsl/observia_backend_metadata).

Every changes to the repository are replicated on the [GitHub repository observia-backend-metadata](https://github.com/OGSL-SLGO/observia-backend-metadata/tree/main).

Any changes to main branch then trigger a redeployment of the Container as a service on a Google Cloud Run and made available at [here](https://observia-backend-metadata-797895507841.us-central1.run.app).

```mermaid
flowchart TD
    A[SLGO GitLab] -->B[SLGO Github]
    B --> C(main branch)
    C --> D[Google Cloud Run ]
```

## Contributing

## License
