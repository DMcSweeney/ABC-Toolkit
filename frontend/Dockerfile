FROM node:20.12.1-slim


WORKDIR /app

## Copy all files and directories expect /src 
# Mount /src later for live updates

COPY * .
COPY ./src src

RUN npm install

CMD ["npm", "run", "host"]