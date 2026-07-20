FROM node:20-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Vite inlina VITE_* em tempo de BUILD (import.meta.env) — num Dockerfile
# multi-stage isso não herda o ambiente do serviço automaticamente feito
# como o Nixpacks fazia; precisa declarar ARG explícito e Railway repassa
# o valor da variável do serviço com o mesmo nome. Sem isso, VITE_API_URL
# fica undefined no bundle e o app cai no fallback '/api' (relativo ao
# próprio domínio do frontend, que não tem proxy nenhum — toda chamada de
# API vira 200 falso servindo o próprio index.html via fallback de SPA).
ARG VITE_API_URL
ARG VITE_GOOGLE_CLIENT_ID
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
RUN npm run build

FROM node:20-slim
WORKDIR /app
RUN npm install -g serve@14.2.6
COPY --from=build /app/dist ./dist
EXPOSE 8080
CMD ["sh", "-c", "serve -s dist -l ${PORT:-8080}"]
