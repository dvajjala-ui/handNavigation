FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 HANDNAVIGATE_REMOTE_RUNNER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
WORKDIR /app
COPY windows-agent/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && python -m playwright install --with-deps chromium
COPY handnavigate /app/handnavigate
COPY windows-agent /app/windows-agent
RUN useradd --uid 10001 --create-home runner && mkdir /data && chown runner:runner /data
USER runner
ENTRYPOINT ["python", "/app/windows-agent/tools/collect_pinterest.py", "--channel", ""]
CMD ["--topic", "nature landscape", "--count", "20", "--output", "/data/pinterest-first-run"]
