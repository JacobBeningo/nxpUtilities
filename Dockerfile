# Use the latest version of Ubuntu as the base image (force x86_64 platform)
FROM --platform=linux/amd64 ubuntu:22.04

# Set the maintainer label
LABEL maintainer="jacob@beningo.com"

# Set environment variables to non-interactive (this will prevent some prompts)
ENV DEBIAN_FRONTEND=non-interactive

# Update package lists, install basic tools, toolchains, stlink-tools, and clean up
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
    autoconf \
    automake \
    curl \
    build-essential \
    git \
    libtool \
    make \
    pkg-config \
    ca-certificates \
    software-properties-common \
    clang-format \
    clang-tidy \
    pmccabe \
    python3 \
    python3-pip \
    python3-venv \
    stlink-tools \
    cmake \
    xz-utils \
    ninja-build \
    wget \
    libssl-dev \
    ruby \
    ruby-dev \
    unzip \
    udev \
    usbutils \
    libusb-1.0-0-dev \
    libusb-1.0-0 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python packages including west and setuptools
RUN pip3 install --no-cache-dir \
    setuptools \
    gcovr \
    west>=1.2.0

# USB tools are installed above in the main apt-get install command
# This allows testing USB connectivity and device detection inside the container

# Download and install the latest Ninja (1.12.1 - meets requirement >=1.12.1)
RUN wget "https://github.com/ninja-build/ninja/releases/download/v1.12.1/ninja-linux.zip" \
    && unzip ninja-linux.zip \
    && mv ninja /usr/local/bin/ \
    && rm ninja-linux.zip

# Setup a tool directory in /home/dev and download the ARM toolchain
WORKDIR /home/dev

# Install GNU Arm toolchain (Version 14.2.Rel1 - Latest version as requested)
RUN cd /home/dev && \
    curl -LO https://developer.arm.com/-/media/Files/downloads/gnu/14.2.rel1/binrel/arm-gnu-toolchain-14.2.rel1-x86_64-arm-none-eabi.tar.xz && \
    tar xf arm-gnu-toolchain-14.2.rel1-x86_64-arm-none-eabi.tar.xz && \
    rm arm-gnu-toolchain-14.2.rel1-x86_64-arm-none-eabi.tar.xz

# Add the GNU Arm toolchain to the PATH and set ARMGCC_DIR environment variable
ENV PATH="/home/dev/arm-gnu-toolchain-14.2.rel1-x86_64-arm-none-eabi/bin:${PATH}"
ENV ARMGCC_DIR="/home/dev/arm-gnu-toolchain-14.2.rel1-x86_64-arm-none-eabi"

# Clone, build, and install CppUTest
WORKDIR /home
RUN git clone https://github.com/cpputest/cpputest.git && \
    cd cpputest && \
    ./autogen.sh && \
    ./configure && \
    make install

# Set the CPPUTEST_HOME environment variable
ENV CPPUTEST_HOME=/home/cpputest

# Create MCUXpresso SDK workspace directory
WORKDIR /home/mcuxpresso-sdk

# Initialize west with MCUXpresso SDK manifest (commented out to avoid network dependency during build)
# Uncomment and run these commands when the container is running:
# RUN west init -m https://github.com/nxp-mcuxpresso/mcuxsdk-manifests/ . && \
#     west update && \
#     west config commands.allow_extensions true

# Create and set the working directory to /home/app
WORKDIR /home/app

# Verify installations (optional - can be commented out to reduce build time)
RUN echo "=== Tool Verification ===" && \
    (git --version || echo "Git check failed") && \
    (python3 --version || echo "Python3 check failed") && \
    (west --version || echo "West check failed") && \
    (cmake --version || echo "CMake check failed") && \
    (ninja --version || echo "Ninja check failed") && \
    (arm-none-eabi-gcc --version || echo "ARM GCC check failed") && \
    (ruby --version || echo "Ruby check failed") && \
    echo "=== Tool verification completed ==="

# Set the default command to bash
CMD ["/bin/bash"]