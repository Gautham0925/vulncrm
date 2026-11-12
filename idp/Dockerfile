FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends libxml2 libxmlsec1 curl && rm -rf /var/lib/apt/lists/* && useradd --system --create-home --uid 10001 app
COPY idp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY idp/main.py idp/main.py
COPY backend/app/idp_lib.py backend/app/idp_lib.py
RUN mkdir -p /data/idp && chown -R app:app /data /srv
USER app
WORKDIR /srv/idp
EXPOSE 9000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD curl -fs http://localhost:9000/health || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
