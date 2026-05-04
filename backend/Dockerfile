# ══════════════════════════════════════════
# Stage 1 : Installation des dépendances
# ══════════════════════════════════════════
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ══════════════════════════════════════════
# Stage 2 : Image finale minimale
# ══════════════════════════════════════════
FROM python:3.11-slim

WORKDIR /app

# Copier les dépendances installées
COPY --from=builder /install /usr/local

# Copier le code applicatif
COPY ./app ./app

# Utilisateur non-root pour la sécurité (Zero-Trust)
RUN useradd -m -r appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
