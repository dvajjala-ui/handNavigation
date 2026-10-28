FROM mcr.microsoft.com/playwright:v1.64.1-noble
USER root
RUN apt-get update && apt-get install -y --no-install-recommends xvfb x11vnc novnc websockify openbox supervisor && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY desktop/core.cjs desktop/engine.cjs desktop/dom.cjs ./desktop/
COPY service ./service/
COPY deploy/vm ./deploy/vm/
RUN mkdir -p /data && chown -R pwuser:pwuser /data /app
USER pwuser
ENV DISPLAY=:99 HANDNAVIGATE_DATA=/data HANDNAVIGATE_HOST=0.0.0.0 HANDNAVIGATE_PORT=47832 HANDNAVIGATE_HEADLESS=0 HANDNAVIGATE_INTERACTIVE_WAIT_SECONDS=180
EXPOSE 47832 6080
CMD ["supervisord", "-c", "/app/deploy/vm/supervisord.conf"]
