# =====================================================================================
# Stage 1: Build the React Application
# This stage uses a full Node.js environment to install dependencies and
# create an optimized production build.
# =====================================================================================
FROM node:18-alpine as build

WORKDIR /app

# Copy package.json and package-lock.json first to leverage layer caching.
# This ensures 'npm install' only runs when dependencies change.
COPY package.json ./
COPY package-lock.json ./
RUN npm install

# Copy the rest of the application source code.
# This includes the 'src' and 'public' directories.
COPY ./public ./public
COPY ./src ./src
COPY tsconfig.json ./

# Run the production build command.
# This creates a static 'build' folder with all the compiled assets.
RUN npm run build


# =====================================================================================
# Stage 2: Serve the Application from a Lightweight Nginx Server
# This stage takes only the built static files and serves them with a
# highly optimized, secure, and small web server.
# =====================================================================================
FROM nginx:1.25-alpine

# Copy the optimized build output from the 'build' stage.
COPY --from=build /app/build /usr/share/nginx/html

# Copy a custom Nginx configuration to handle single-page application routing.
# This ensures that refreshing the page on a route like /project/123 still works.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80, which is the default for Nginx.
EXPOSE 80

# The command to start the Nginx server.
CMD ["nginx", "-g", "daemon off;"]