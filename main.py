"""
Professional AI Music Generation API Server
Enterprise-grade FastAPI application with YAML configuration support.
"""

import logging
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# Make --config effective before the module-level FastAPI app is created.
if "--config" in sys.argv:
    try:
        os.environ["AURORA_CONFIG"] = str(Path(sys.argv[sys.argv.index("--config") + 1]).resolve())
    except (IndexError, ValueError):
        pass

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

# Add app directory to Python path
sys.path.append(str(Path(__file__).parent))

from app.core.config import APP_ROOT, get_config_manager, get_config
from app.api.endpoints import router, create_error_response
from app.services.model_registry import get_model_registry

# Setup logging before constructing FileHandler (also works outside the repo).
LOG_DIR = Path(os.environ.get("AURORA_LOG_DIR", APP_ROOT / "logs")).expanduser().resolve()
TEMP_DIR = Path(os.environ.get("AURORA_TEMP_DIR", APP_ROOT / "temp")).expanduser().resolve()
LOG_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("🚀 Starting AI Music Generation API...")

    try:
        # Initialize configuration
        config_manager = get_config_manager()
        config = get_config()
        logger.info(f"✅ Configuration loaded: {len(config.models)} models available")

        # Initialize model registry
        registry = get_model_registry()
        logger.info("✅ Model registry initialized")

        available = registry.get_available_models()
        usable = {name: info for name, info in available.items()
                  if info['file_exists'] and info['supported']}
        if not usable:
            raise RuntimeError(
                f"No usable model found in {config.storage.models_root}. "
                "Run setup again and verify the .safetensors and matching JSON files."
            )

        # Create necessary directories
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

        logger.info("🎵 AI Music Generation API is ready!")

    except Exception as e:
        logger.error(f"❌ Failed to initialize application: {e}")
        raise

    yield

    # Shutdown
    logger.info("🛑 Shutting down AI Music Generation API...")

    # Cleanup loaded models
    try:
        registry = get_model_registry()
        for model_name in registry.get_loaded_models():
            registry.unload_model(model_name)
        logger.info("✅ Models unloaded")
    except Exception as e:
        logger.error(f"⚠️ Error during cleanup: {e}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    # Load configuration early
    try:
        config = get_config()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise

    # Create FastAPI app
    app = FastAPI(
        title=config.api.title,
        description=config.api.description,
        version=config.api.version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.security.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom OpenAPI schema
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=config.api.title,
            version=config.api.version,
            description=f"""
            {config.api.description}

            ## Features
            - **Multiple Model Support**: Load and manage different AI music models
            - **Flexible Generation**: Support for various generation parameters and seeding methods
            - **MIDI Integration**: Upload MIDI files as seeds or download generated MIDI
            - **Multiple Output Formats**: Optimized for VST plugins, DAW integration, and research
            - **Professional Architecture**: Enterprise-grade design with proper error handling

            ## Quick Start
            1. Check available models: `GET /models`
            2. Load a model: `POST /models/load`
            3. Generate music: `POST /generate`

            ## Supported Input Types
            - Raw token sequences
            - Musical note sequences
            - MIDI file uploads
            - Generation parameters (temperature, top_k, top_p, etc.)

            ## Output Formats
            - **VST Plugin**: Notes + MIDI (optimized for real-time use)
            - **DAW Integration**: Notes + MIDI + metadata
            - **Research**: Full output including attention weights and probabilities
            """,
            routes=app.routes,
        )

        # Add example models to schema
        openapi_schema["info"]["x-example-models"] = [
            "melody_small",
            "melody_large",
            "harmony_basic",
            "drum_patterns"
        ]

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    # Include API routes
    app.include_router(router, prefix="/api/v1")

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """API root endpoint with information."""
        return {
            "message": "🎵 AI Music Generation API",
            "version": config.api.version,
            "status": "operational",
            "docs": "/docs",
            "models_endpoint": "/api/v1/models",
            "generate_endpoint": "/api/v1/generate",
            "features": [
                "Multiple AI model support",
                "MIDI file processing",
                "Flexible generation parameters",
                "Professional VST integration"
            ]
        }

    # Global exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions with consistent format."""
        return JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(
                error=exc.detail,
                detail=f"HTTP {exc.status_code}",
                status_code=exc.status_code
            ).dict()
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions."""
        logger.error(f"Unexpected error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                error="Internal server error",
                detail=str(exc) if config.api.version.endswith("-dev") else "An unexpected error occurred"
            ).dict()
        )

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        """Simple health check."""
        return {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",  # This would be dynamic
            "version": config.api.version
        }

    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description="AI Music Generation API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--config", help="Configuration file path (or AURORA_CONFIG)")

    args = parser.parse_args()

    # Override config path if specified
    logger.info(f"🌐 Starting server on {args.host}:{args.port}")
    logger.info(f"📚 API docs available at: http://{args.host}:{args.port}/docs")

    uvicorn.run(
        "main:app" if args.reload else app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )
