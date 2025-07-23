FROM python:3.11-bookworm as builder

RUN apt-get update && apt-get upgrade -y

RUN apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    libssl1.1 \          # Explicitly install the required libssl1.1 runtime library
    libxrender1 \        # Runtime library for X rendering, often needed by wkhtmltopdf
    fontconfig \         # Font configuration library, crucial for text rendering
    libjpeg-turbo8 \     # JPEG image library, common dependency for rendering engines
    libmemcached-dev \   # Development files for libmemcached
    zlib1g-dev \         # Development files for zlib compression library
    graphviz \           # Graphviz executable
    graphviz-dev \       # Development files for Graphviz
    xz-utils             # Utility for XZ compression, often needed for archives

# Download the wkhtmltox .deb package
# Using the specific version for buster as per your original Dockerfile
RUN wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.buster_amd64.deb

# Install the wkhtmltox .deb package using dpkg, then fix any missing dependencies
# 'dpkg -i ... || true' attempts installation and allows the build to continue even if dependencies are missing
# 'apt-get -f install' then resolves and installs any unmet dependencies
RUN dpkg -i wkhtmltox_0.12.6-1.buster_amd64.deb || true && \
    apt-get update && \
    apt-get install -y --no-install-recommends -f

# Clean up downloaded .deb package and apt cache to reduce image size
RUN rm wkhtmltox_0.12.6-1.buster_amd64.deb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set Python unbuffered output for better logging in container environments
ENV PYTHONUNBUFFERED 1

# Create a directory for the application code
RUN mkdir /code

# Set the working directory inside the container
WORKDIR /code/

# Define the path for the Python virtual environment
ENV VIRTUAL_ENV=/opt/venv

# Create a Python virtual environment
RUN python3 -m venv $VIRTUAL_ENV

# Add the virtual environment's bin directory to the PATH
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Upgrade pip and install wheel for faster package installations
RUN pip install --upgrade pip
RUN pip install wheel

# Copy requirements.txt and install Python dependencies
# This is done before copying the rest of the code to leverage Docker layer caching
ADD requirements.txt /code/requirements.txt
RUN pip install -r requirements.txt

# Copy the rest of the application code into the container
ADD . /code/

# Expose port 8000, which your application is expected to listen on
EXPOSE 8000

# Make the web server start script executable
RUN chmod +x /code/web_server.sh

# Define the command to run when the container starts
CMD ["/code/web_server.sh"]
