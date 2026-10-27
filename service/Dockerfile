FROM mcr.microsoft.com/playwright:v1.64.1-noble
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY service/package.json service/package-lock.json ./service/
RUN npm ci --prefix service --omit=dev && npm cache clean --force
COPY desktop/core.cjs desktop/engine.cjs desktop/dom.cjs ./desktop/
COPY service ./service/
RUN mkdir -p /data && chown -R pwuser:pwuser /data /app
USER pwuser
ENV HANDNAVIGATE_DATA=/data HANDNAVIGATE_HOST=0.0.0.0 HANDNAVIGATE_PORT=47832
EXPOSE 47832
CMD ["node", "service/server.cjs"]
