FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/home/user/.local/bin:$PATH

RUN useradd --create-home --uid 1000 user
USER user
WORKDIR /home/user/app

COPY --chown=user:user pyproject.toml ./
COPY --chown=user:user src ./src
RUN python -m pip install --upgrade pip && python -m pip install .

COPY --chown=user:user alembic ./alembic
COPY --chown=user:user alembic.ini ./
COPY --chown=user:user scripts/index_procedures.py ./scripts/index_procedures.py
COPY --chown=user:user data ./data
COPY --chown=user:user rules ./rules

EXPOSE 7860

CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && (python scripts/index_procedures.py --embedding-provider ${EMBEDDING_PROVIDER:-auto} || echo 'Dense index unavailable; continuing with BM25') && exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips '*'"]
