# Stage 1: Build the Python environment
FROM python:3.12-slim as build_stage # 'buster' hata diya, bhenchod!

# Set working directory
WORKDIR /app

# Install build dependencies
# Ye zaruri hain Python packages jinko compile karna padta hai (jaise pydantic-core, pycryptodomex)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    git \
    libxml2-dev \
    libxslt1-dev \
    # Agar ye chromium/chromedriver use kar raha hai toh ye bhi daal
    # chromium \
    # chromium-driver \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install -r requirements.txt

# Stage 2: Create the final lean image
FROM python:3.12-slim # 'buster' hata diya yahan bhi!

# Set working directory
WORKDIR /app

# Copy built dependencies from the build stage
COPY --from=build_stage /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
# Gunicorn ke liye, agar ye /usr/local/bin mein install hua hai
COPY --from=build_stage /usr/local/bin/gunicorn /usr/local/bin/gunicorn

# Copy your application code
COPY . .

# Expose the port your app will run on
EXPOSE $PORT

# Define the command to run your application
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]