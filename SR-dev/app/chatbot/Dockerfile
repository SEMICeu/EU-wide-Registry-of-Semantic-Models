FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN python -c "from pathlib import Path; p=Path('/app/requirements.txt'); b=p.read_bytes(); txt=b.decode('utf-16') if b.count(b'\\x00') else b.decode('utf-8'); p.write_text(txt, encoding='utf-8')" \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8050

CMD ["sh", "-c", "python -m graph_rag.setup.bootstrap_backend && uvicorn graph_rag.main:app --host 0.0.0.0 --port 8050"]

