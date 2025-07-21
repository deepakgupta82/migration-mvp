# Stage 1: Build the React app
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Stage 2: Serve the app from Nginx
FROM nginx:1.25-alpine
# Copy the built static files from the build stage
COPY --from=build /app/build /usr/share/nginx/html
# The default nginx config serves files from this directory, so no further config is needed.
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
