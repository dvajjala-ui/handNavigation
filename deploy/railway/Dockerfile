FROM mcr.microsoft.com/playwright:v1.64.1-noble
USER root
RUN apt-get update && apt-get install -y --no-install-recommends xvfb xauth coreutils util-linux && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY desktop/core.cjs desktop/engine.cjs desktop/dom.cjs ./desktop/
COPY service ./service/
COPY deploy/railway ./deploy/railway/
RUN chmod 755 deploy/railway/start.sh && mkdir -p /data && chown -R pwuser:pwuser /app /data
ENV HANDNAVIGATE_DATA=/data HANDNAVIGATE_HEADLESS=0 HANDNAVIGATE_INTERACTIVE_WAIT_SECONDS=0 HANDNAVIGATE_DAILY_LIMIT=20 HANDNAVIGATE_BATCH_SECONDS=1500 HANDNAVIGATE_BATCH_IDLE_SECONDS=90
CMD ["/app/deploy/railway/start.sh"]
