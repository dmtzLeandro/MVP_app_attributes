from pathlib import Path

FILES = {
    ".env.example": """APP_ENV=local
APP_URL=http://localhost:8000

DB_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/tn_mvp

TN_CLIENT_ID=123
TN_CLIENT_SECRET=xxxxx

TN_OAUTH_BASE=https://www.tiendanube.com
TN_API_BASE=https://api.tiendanube.com/2025-03

# optional
REDIS_URL=redis://localhost:6379/0
""",
    "requirements.txt": """fastapi==0.115.8
uvicorn[standard]==0.34.0

pydantic==2.10.6
pydantic-settings==2.8.0

SQLAlchemy==2.0.38
psycopg2-binary==2.9.10
alembic==1.14.1

httpx==0.28.1
python-dotenv==1.0.1

# optional
redis==5.2.1
""",
    "README.md": """# TN Materiales MVP

## Run local
1) Create venv + install deps
2) Start Postgres (docker compose)
3) Run migrations
4) Run API

See `.vscode` tasks for one-command workflow.
""",
    "docker-compose.yml": """services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: tn_mvp
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - tn_pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    profiles: ["optional"]

volumes:
  tn_pgdata:
""",
    ".editorconfig": """root = true

[*]
end_of_line = lf
insert_final_newline = true
charset = utf-8
indent_style = space
indent_size = 2

[*.py]
indent_size = 4
""",
    ".vscode/settings.json": """{
  "python.defaultInterpreterPath": ".venv/Scripts/python.exe",
  "python.analysis.typeCheckingMode": "basic",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll": "explicit"
  },
  "ruff.organizeImports": true
}
""",
    ".vscode/launch.json": """{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI: Uvicorn",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload", "--port", "8000"],
      "envFile": "${workspaceFolder}/.env",
      "console": "integratedTerminal"
    }
  ]
}
""",
    ".vscode/tasks.json": """{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "docker: up db",
      "type": "shell",
      "command": "docker compose up -d db",
      "problemMatcher": []
    },
    {
      "label": "alembic: upgrade head",
      "type": "shell",
      "command": "alembic -c app/storage/alembic.ini upgrade head",
      "problemMatcher": []
    },
    {
      "label": "run: api",
      "type": "shell",
      "command": "uvicorn app.main:app --reload --port 8000",
      "problemMatcher": []
    }
  ]
}
""",
}

DIRS = [
    "app/core",
    "app/db/models",
    "app/storage/alembic/versions",
    "app/tiendanube_connector",
    "app/domain",
    "app/admin_api",
    "app/services",
]

INIT_PYS = [
    "app/__init__.py",
    "app/core/__init__.py",
    "app/db/__init__.py",
    "app/db/models/__init__.py",
    "app/storage/__init__.py",
    "app/tiendanube_connector/__init__.py",
    "app/domain/__init__.py",
    "app/admin_api/__init__.py",
    "app/services/__init__.py",
]

def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")

def main():
    for d in DIRS:
        Path(d).mkdir(parents=True, exist_ok=True)

    for f in INIT_PYS:
        Path(f).parent.mkdir(parents=True, exist_ok=True)
        Path(f).touch(exist_ok=True)

    for rel, content in FILES.items():
        write(Path(rel), content)

    print("OK: scaffolding created.")

if __name__ == "__main__":
    main()