FROM node:22-alpine
WORKDIR /srv
COPY node-service/package.json node-service/server.js ./
RUN adduser -S -u 10001 app && chown -R app /srv
USER app
EXPOSE 3100
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD wget -qO- http://localhost:3100/health || exit 1
CMD ["node", "server.js"]
