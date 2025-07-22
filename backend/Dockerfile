# Use Node.js 20 with full build environment
FROM node:20-bullseye

# Set working directory
WORKDIR /app

# Add Google Chrome repository
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list

# Install system dependencies for Sharp, Tesseract, OpenGL, and Chrome
RUN apt-get update && apt-get install -y \
    # Python and build tools
    python3 \
    python3-pip \
    python3-dev \
    make \
    g++ \
    gcc \
    # Image processing libraries (Sharp dependencies)
    pkg-config \
    libcairo2-dev \
    libpango1.0-dev \
    libjpeg-dev \
    libpng-dev \
    libgif-dev \
    librsvg2-dev \
    # OpenGL libraries (for gl dependency)
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    freeglut3-dev \
    # X11 libraries
    libx11-dev \
    libxi-dev \
    libxrandr-dev \
    libxinerama-dev \
    libxcursor-dev \
    libxext-dev \
    libxfixes-dev \
    libxss-dev \
    # Tesseract OCR
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libleptonica-dev \
    # Google Chrome for Puppeteer
    google-chrome-stable \
    # Additional utilities
    wget \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for native builds
ENV PYTHON=/usr/bin/python3
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production

# Puppeteer configuration
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/google-chrome-stable

# Copy package files first (for Docker layer caching)
COPY package*.json ./

# Set npm cache and optimization settings
RUN npm config set cache /tmp/.npm-cache --global
RUN npm config set fund false
RUN npm config set audit false

# Install dependencies with optimizations for heavy packages
RUN npm ci --only=production --silent

# Copy application code
COPY . .

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port (Railway will set PORT env var)
EXPOSE ${PORT:-5001}

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-5001}/api/health || exit 1

# Start the application
CMD ["npm", "start"] 