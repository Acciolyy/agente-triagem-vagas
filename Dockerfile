FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=app:app app.py ./
COPY --chown=app:app src ./src
RUN chown app:app /app

USER app
EXPOSE 8501

# A chave vem de fora: docker run --env-file .env -p 8501:8501 <imagem>
CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
