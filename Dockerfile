FROM node:20-slim AS frontend-builder

WORKDIR /app/chat
COPY chat/package*.json ./
RUN npm ci
COPY chat/ ./
RUN npm run build

# Main application stage
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (no Node.js needed in final image)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and ensure they own everything
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Copy dependency files and change ownership
COPY --chown=appuser:appuser pyproject.toml uv.lock ./

# Install uv and dependencies as non-root user
RUN pip install --user uv
ENV PATH="/home/appuser/.local/bin:$PATH"
RUN uv sync --frozen

# Copy built frontend from build stage (no source code, just built assets)
COPY --from=frontend-builder --chown=appuser:appuser /app/chat/dist ./static

# Copy Python application code
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser db_stuff/ ./db_stuff/

# Generate the database during build (keeps it in db_stuff/)
RUN cd db_stuff && uv run python howTheyVote.py

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uv", "run", "src/main.py"]
