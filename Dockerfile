# Dockerfile

# Base Image: Python 3.11.9 istemal kar raha hoon. 
# Yeh 'greenlet' aur baaki libraries ke liye zyada stable hai.
FROM python:3.11.9-slim-bookworm

# Environment variable set kar, Render pe PORT uthane ke liye
ENV PORT 10000

# Working directory set kar
WORKDIR /app

# System dependencies install kar
# Playwright ko browser chalane ke liye kuch OS-level libraries chahiye hoti hain
# 'sudo' nahi lagta Dockerfile mein, seedha 'apt-get' use kar
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    chromium \
    # Agar ye libraries Playwright ke liye chahiye toh
    # libnss3 \
    # libnspr4 \
    # libatk1.0-0 \
    # libatk-bridge2.0-0 \
    # libcups2 \
    # libdrm2 \
    # libxkbcommon0 \
    # libxcomposite1 \
    # libxdamage1 \
    # libxext6 \
    # libxfixes3 \
    # libxrandr2 \
    # libgbm1 \
    # libasound2 \
    # libfontconfig1 \
    # libfreetype6 \
    # libglib2.0-0 \
    # libpango-1.0-0 \
    # libpangocairo-1.0-0 \
    # libcairo2 \
    # libgdk-pixbuf2.0-0 \
    # libgtk-3-0 \
    # libnotify4 \
    # libxss1 \
    # libappindicator1 \
    # libxcursort6 \
    # libxinerama1 \
    # libxrandr2 \
    # libgconf-2-4 \
    # libdbus-glib-1-2 \
    # libsecret-1-0 \
    # xdg-utils \
    # unzip \
    && rm -rf /var/lib/apt/lists/*

# Apne Python dependencies install kar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright browsers install kar (Chrome, Firefox, WebKit)
RUN playwright install --with-deps chromium firefox webkit

# Apne application files copy kar
COPY . .

# Server start karne ka command
# Yeh command Procfile ko overwrite karegi agar Dockerfile use ho rahi hai
CMD ["python", "main.py"]
