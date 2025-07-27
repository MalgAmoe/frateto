#!/bin/bash

echo "🏗️ Building Frateto Chat..."

# Build the React frontend
echo "📦 Building React frontend..."
cd chat && npm run build
cd ..

# Remove old static files
echo "🧹 Cleaning static directory..."
rm -rf static

# Copy built frontend to static directory
echo "📋 Copying built frontend..."
cp -r chat/dist static

# Verify
if [ -f "static/index.html" ]; then
    echo "✅ Build completed successfully!"
    echo "📁 Static files ready in /static/"
    echo ""
    echo "🚀 Run: uv run src/main.py"
    echo "🌐 Visit: http://localhost:8000"
else
    echo "❌ Build failed - index.html not found!"
    exit 1
fi
