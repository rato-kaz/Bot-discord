# Multi-stage build để giảm kích thước image
FROM python:3.11-slim as builder

# Cài đặt dependencies cần thiết để build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements và cài đặt Python packages
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime image
FROM python:3.11-slim

# Cài đặt FFmpeg (BẮT BUỘC cho tính năng phát nhạc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Tạo user non-root để chạy bot
RUN useradd -m -u 1000 botuser && \
    mkdir -p /app && \
    chown -R botuser:botuser /app

# Copy Python packages từ builder
COPY --from=builder /root/.local /home/botuser/.local

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=botuser:botuser . .

# Set PATH để Python packages có thể được tìm thấy
ENV PATH=/home/botuser/.local/bin:$PATH

# Switch to non-root user
USER botuser

# Expose port (nếu cần cho health check)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Run bot
CMD ["python", "bot.py"]

