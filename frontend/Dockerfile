FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Build arg so we can pass the EC2 IP at build time
ARG PUBLIC_API_URL
ARG PUBLIC_WS_URL
ENV PUBLIC_API_URL=$PUBLIC_API_URL
ENV PUBLIC_WS_URL=$PUBLIC_WS_URL

RUN npm run build

EXPOSE 3000

CMD ["node", "build"]