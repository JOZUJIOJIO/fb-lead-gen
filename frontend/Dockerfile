FROM node:18-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ENV BACKEND_URL=http://backend:8000
RUN npm run build

# --- 运行阶段（standalone 模式，镜像更小）---
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV BACKEND_URL=http://backend:8000

# standalone 输出包含所有必需文件
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
