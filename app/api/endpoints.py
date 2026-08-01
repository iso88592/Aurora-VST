"""
API endpoints for the AI Music Generation API.
Comprehensive endpoints supporting all generation methods and model management.
"""

import json
import base64
import os
import uuid
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Query, BackgroundTasks
from fastapi.responses import FileResponse, Response

from ..schemas.requests import (
    GenerateRequest, LoadModelRequest, UnloadModelRequest,
    BatchGenerateRequest, GenerateFromMidiRequest, ConfigUpdateRequest,
    SimpleGenerateParams, GenerationParams, GenerationProfile, OutputFormat
)
from ..schemas.responses import (
    GenerateResponse, ModelsListResponse, ModelLoadResponse,
    SystemStatusResponse, BatchGenerateResponse, ErrorResponse,
    HealthResponse, ConfigResponse, GeneratedMelody, NoteResponse,
    GenerationMetadata, ModelInfo, GenerationStatus, ModelStatus
)
from ..services.model_registry import get_model_registry
from ..core.config import APP_ROOT, get_config_manager, get_config
from ..models.base import GenerationParams as BaseGenerationParams
from ..utils.note_conversion import parse_midi_to_notes

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


def get_temp_dir() -> Path:
    """Return the configured, repository-relative generated-file directory."""
    path = Path(os.environ.get("AURORA_TEMP_DIR", APP_ROOT / "temp")).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_notes_to_tokens(notes: List[Dict], model_name: str) -> List[int]:
    """Convert note sequence to tokens using the appropriate tokenizer."""
    registry = get_model_registry()
    loaded_model = registry.get_model(model_name)

    if not loaded_model:
        raise HTTPException(status_code=400, detail=f"Model {model_name} not loaded")

    # This is a simplified implementation - you'd need to implement
    # note-to-token conversion based on your tokenizer
    tokens = []
    for note in notes:
        # Convert note to appropriate token representation
        # This depends on your specific tokenizer implementation
        pass

    return tokens


def apply_generation_profile(params: Optional[GenerationParams], profile: Optional[GenerationProfile]) -> GenerationParams:
    """Apply generation profile or use custom parameters."""
    if profile and profile != GenerationProfile.CUSTOM:
        config_manager = get_config_manager()
        profile_config = config_manager.get_generation_profile(profile.value)

        if profile_config:
            return GenerationParams(
                temperature=profile_config.temperature,
                top_k=profile_config.top_k,
                top_p=profile_config.top_p,
                repetition_penalty=profile_config.repetition_penalty,
                max_length=params.max_length if params else 120
            )

    return params or GenerationParams()


def format_output_based_on_format(melody: GeneratedMelody, output_format: OutputFormat) -> GeneratedMelody:
    """Format output based on requested format."""
    config_manager = get_config_manager()
    format_config = config_manager.get_output_format(output_format.value)

    if not format_config:
        return melody

    # Apply format configuration
    if not format_config.include_tokens:
        melody.tokens = None
    if not format_config.include_midi:
        melody.midi_base64 = None

    return melody


@router.get("/health", response_model=HealthResponse, summary="Health Check")
async def health_check():
    """API health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version=get_config().api.version,
        dependencies={
            "torch": "available",
            "config": "loaded",
            "model_registry": "initialized"
        }
    )


@router.get("/status", response_model=SystemStatusResponse, summary="System Status")
async def get_system_status():
    """Get comprehensive system status."""
    registry = get_model_registry()
    config = get_config()

    return SystemStatusResponse(
        status="operational",
        timestamp=datetime.now().isoformat(),
        uptime=None,  # Could be implemented with server start time tracking
        loaded_models=registry.get_loaded_models(),
        max_loaded_models=config.storage.max_loaded_models,
        memory_info=registry.get_memory_info(),
        total_generations=None,  # Could be implemented with request counting
        average_response_time=None,  # Could be implemented with performance monitoring
        config_loaded=True,
        config_file=str(get_config_manager().config_path)
    )


@router.get("/models", response_model=ModelsListResponse, summary="List Available Models")
async def list_models():
    """Get list of all available models and their status."""
    registry = get_model_registry()
    available_models = registry.get_available_models()

    models_info = {}
    for name, info in available_models.items():
        models_info[name] = ModelInfo(
            name=name,
            type=info['type'],
            description=info['description'],
            tags=info['tags'],
            vocab_size=info['architecture']['vocab_size'],
            parameter_count=info.get('parameter_count'),
            model_file=info['model_file'],
            config_file=info['config_file'],
            file_exists=info['file_exists'],
            supported=info['supported'],
            status=ModelStatus.LOADED if info['is_loaded'] else ModelStatus.NOT_LOADED,
            load_time=info.get('load_time'),
            last_accessed=info.get('last_accessed'),
            access_count=info.get('access_count')
        )

    return ModelsListResponse(
        models=models_info,
        total_models=len(models_info),
        loaded_models=len(registry.get_loaded_models()),
        supported_types=["MelodyTransformer"]  # This could be dynamic
    )


@router.post("/models/load", response_model=ModelLoadResponse, summary="Load Model")
async def load_model(request: LoadModelRequest):
    """Load a specific model into memory."""
    registry = get_model_registry()

    # Unload if force reload
    if request.force_reload and registry.is_model_loaded(request.model_name):
        registry.unload_model(request.model_name)

    result = registry.load_model(request.model_name)

    if not result['success']:
        raise HTTPException(status_code=400, detail=result.get('error', 'Failed to load model'))

    return ModelLoadResponse(
        success=result.get('success', False),
        message=result.get('message', ''),
        model_name=request.model_name,
        load_time=result.get('load_time'),
        model_type=result.get('model_type'),
        parameter_count=result.get('parameter_count'),
        vocab_size=result.get('vocab_size'),
        device=result.get('device'),
        error=result.get('error'),
        already_loaded=result.get('already_loaded', False)
    )


@router.post("/models/unload", response_model=ModelLoadResponse, summary="Unload Model")
async def unload_model(request: UnloadModelRequest):
    """Unload a model from memory."""
    registry = get_model_registry()
    result = registry.unload_model(request.model_name)

    if not result['success']:
        raise HTTPException(status_code=400, detail=result.get('error', 'Failed to unload model'))

    return ModelLoadResponse(
        success=result.get('success', False),
        message=result.get('message', ''),
        model_name=request.model_name,
        load_time=result.get('load_time'),
        model_type=result.get('model_type'),
        parameter_count=result.get('parameter_count'),
        vocab_size=result.get('vocab_size'),
        device=result.get('device'),
        error=result.get('error'),
        already_loaded=result.get('already_loaded', False)
    )


@router.post("/generate", response_model=GenerateResponse, summary="Generate Music")
async def generate_music(request: GenerateRequest):
    """Generate music with comprehensive parameter support."""
    registry = get_model_registry()
    request_id = str(uuid.uuid4())
    start_time = time.time()

    # Validate model is loaded
    loaded_model = registry.get_model(request.model_name)
    if not loaded_model:
        raise HTTPException(
            status_code=400,
            detail=f"Model {request.model_name} not loaded. Load it first using /models/load"
        )

    # Prepare generation parameters
    gen_params = apply_generation_profile(request.params, request.profile)

    # Convert to base generation params
    base_params = BaseGenerationParams(
        temperature=gen_params.temperature,
        top_k=gen_params.top_k,
        top_p=gen_params.top_p,
        repetition_penalty=gen_params.repetition_penalty,
        max_length=gen_params.max_length,
        seed_tokens=request.seed_tokens
    )

    # Handle different seed inputs
    if request.seed_notes and not request.seed_tokens:
        # Convert notes to tokens
        try:
            base_params.seed_tokens = parse_notes_to_tokens(
                [note.dict() for note in request.seed_notes],
                request.model_name
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to convert notes to tokens: {e}")

    # Generate melodies
    melodies = []
    errors = []

    for i in range(request.num_generations):
        try:
            # Prepare start tokens
            start_tokens = base_params.seed_tokens if base_params.seed_tokens else [loaded_model.config.architecture.bos_token or 0]
            
            result = loaded_model.model.generate(
                start_tokens=start_tokens,
                params=base_params,
                device=str(registry.device)
            )

            # Convert tokens to MIDI and notes
            melody_tokens = [
                t for t in result.tokens
                if t not in [0, 1, 2]  # Remove special tokens
            ]

            if melody_tokens:
                # Convert to MIDI
                midi_bytes = loaded_model.tokenizer.detokenize(melody_tokens)
                midi_base64 = base64.b64encode(midi_bytes).decode('utf-8')
                
                # Save MIDI file for download
                midi_filename = f"{request_id}_melody_{i+1}.mid"
                midi_url = f"/api/v1/download/midi/{midi_filename}"
                
                # Ensure temp directory exists
                temp_dir = get_temp_dir()
                temp_dir.mkdir(exist_ok=True)
                
                # Save MIDI file
                midi_file_path = temp_dir / midi_filename
                with open(midi_file_path, 'wb') as f:
                    f.write(midi_bytes)

                # Parse MIDI bytes to notes
                try:
                    notes = parse_midi_to_notes(midi_bytes)
                except Exception as e:
                    logger.warning(f"Failed to parse MIDI to notes: {e}")
                    notes = []  # Fallback to empty list if parsing fails

                # Create metadata
                metadata = GenerationMetadata(
                    model_name=request.model_name,
                    model_type=loaded_model.config.type,
                    generation_params=gen_params.dict(),
                    generation_time=result.generation_time,
                    token_count=len(melody_tokens),
                    note_count=len(notes),
                    seed_used=request.seed_tokens is not None or request.seed_notes is not None,
                    seed_type="tokens" if request.seed_tokens else "notes" if request.seed_notes else None,
                    duration_beats=len(melody_tokens) * 0.25,  # Rough estimate: 4 tokens per beat
                    duration_seconds=len(melody_tokens) * 0.125,  # Rough estimate: 8 tokens per second
                    stopped_early=result.metadata.get('stopped_early', False)
                )

                melody = GeneratedMelody(
                    id=f"{request_id}_melody_{i+1}",
                    tokens=melody_tokens,
                    notes=notes,
                    midi_base64=midi_base64,
                    midi_url=midi_url,  # URL for downloading MIDI file
                    attention_weights=None,  # Optional field for research mode
                    token_probabilities=None,  # Optional field for research mode
                    metadata=metadata
                )

                # Apply output formatting
                melody = format_output_based_on_format(melody, request.output_format)
                melodies.append(melody)

        except Exception as e:
            logger.error(f"Generation {i+1} failed: {e}")
            errors.append(f"Generation {i+1}: {str(e)}")

    total_time = time.time() - start_time

    return GenerateResponse(
        status=GenerationStatus.SUCCESS if melodies else GenerationStatus.FAILED,
        request_id=request_id,
        timestamp=datetime.now().isoformat(),
        melodies=melodies,
        success_count=len(melodies),
        total_requested=request.num_generations,
        total_generation_time=total_time,
        average_generation_time=total_time / max(1, len(melodies)),
        model_info={
            "model_name": request.model_name,
            "model_type": loaded_model.config.type,
            "parameter_count": getattr(loaded_model.model, 'parameter_count', None),
            "vocab_size": loaded_model.config.architecture.vocab_size,
            "device": str(registry.device)
        },
        errors=errors if errors else None,
        warnings=[]  # Add empty warnings list
    )


@router.post("/generate/from-midi", response_model=GenerateResponse, summary="Generate from MIDI Seed")
async def generate_from_midi(
    model_name: str = Form(...),
    midi_file: UploadFile = File(...),
    params: Optional[str] = Form(default=None),
    profile: Optional[GenerationProfile] = Form(default=None),
    num_generations: int = Form(default=1),
    output_format: OutputFormat = Form(default=OutputFormat.VST_PLUGIN),
    use_full_midi: bool = Form(default=False),
    max_seed_length: int = Form(default=50)
):
    """Generate music using uploaded MIDI file as seed."""
    registry = get_model_registry()

    # Validate model
    loaded_model = registry.get_model(model_name)
    if not loaded_model:
        raise HTTPException(status_code=400, detail=f"Model {model_name} not loaded")

    # Validate file type
    if not midi_file.filename.lower().endswith(('.mid', '.midi')):
        raise HTTPException(status_code=400, detail="File must be a MIDI file (.mid or .midi)")

    try:
        # Read MIDI file
        midi_content = await midi_file.read()
        logger.info(f"Read MIDI file: {len(midi_content)} bytes")

        # Tokenize MIDI
        try:
            seed_tokens = loaded_model.tokenizer.tokenize(midi_content)
            logger.info(f"Tokenized MIDI: {len(seed_tokens)} tokens")
        except Exception as tokenize_error:
            logger.error(f"Tokenization failed: {tokenize_error}")
            raise HTTPException(
                status_code=400, 
                detail=f"Melody tokenization failed: {str(tokenize_error)}"
            )

        # Limit seed length
        if len(seed_tokens) > max_seed_length:
            seed_tokens = seed_tokens[:max_seed_length]
            logger.info(f"Limited seed tokens to {len(seed_tokens)}")

        # Parse custom parameters
        gen_params = None
        if params:
            try:
                params_dict = json.loads(params)
                gen_params = GenerationParams(**params_dict)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid parameters JSON: {e}")

        # Create generation request
        generate_request = GenerateRequest(
            model_name=model_name,
            params=gen_params,
            profile=profile,
            seed_tokens=seed_tokens,
            num_generations=num_generations,
            output_format=output_format
        )

        return await generate_music(generate_request)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process MIDI file: {e}")


@router.get("/generate/simple", response_model=GenerateResponse, summary="Simple Generation")
async def generate_simple(
    model_name: str = Query(..., description="Model to use"),
    temperature: float = Query(1.0, ge=0.1, le=2.0, description="Creativity level"),
    top_k: int = Query(50, ge=1, le=200, description="Top-K sampling"),
    top_p: float = Query(0.9, ge=0.01, le=1.0, description="Top-P sampling"),
    max_length: int = Query(120, ge=10, le=500, description="Max tokens"),
    num_generations: int = Query(1, ge=1, le=10, description="Number to generate"),
    profile: Optional[str] = Query(None, description="Generation profile")
):
    """Simple generation endpoint with query parameters."""
    # Convert to GenerateRequest
    request = GenerateRequest(
        model_name=model_name,
        params=GenerationParams(
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            max_length=max_length
        ),
        profile=GenerationProfile(profile) if profile else None,
        num_generations=num_generations
    )

    return await generate_music(request)


@router.post("/generate/batch", response_model=BatchGenerateResponse, summary="Batch Generation")
async def batch_generate(request: BatchGenerateRequest):
    """Generate multiple melodies with different parameters."""
    start_time = time.time()
    request_id = str(uuid.uuid4())

    results = []
    errors = []

    # Execute requests
    for i, gen_request in enumerate(request.requests):
        try:
            result = await generate_music(gen_request)
            results.append(result)
        except Exception as e:
            error_msg = f"Batch request {i+1}: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)

    total_time = time.time() - start_time

    return BatchGenerateResponse(
        status=GenerationStatus.SUCCESS if results else GenerationStatus.FAILED,
        request_id=request_id,
        timestamp=datetime.now().isoformat(),
        results=results,
        success_count=len(results),
        total_requests=len(request.requests),
        total_batch_time=total_time,
        parallel_execution=request.parallel,
        errors=errors if errors else None
    )


@router.get("/config", response_model=ConfigResponse, summary="Get Configuration")
async def get_configuration():
    """Get current API configuration information."""
    config_manager = get_config_manager()
    config = config_manager.config
    
    # Get file modification time
    import os
    try:
        mtime = os.path.getmtime(config_manager.config_path)
        last_modified = datetime.fromtimestamp(mtime).isoformat()
    except:
        last_modified = None

    return ConfigResponse(
        loaded=True,
        file_path=str(config_manager.config_path),
        last_modified=last_modified,
        total_models=len(config.models),
        total_tokenizers=len(config.tokenizers),
        generation_profiles=list(config.generation_profiles.keys()),
        output_formats=list(config.output_formats.keys()),
        storage_settings=config.storage.dict(),
        performance_settings=config.performance.dict(),
        security_settings=config.security.dict()
    )


@router.post("/config/reload", summary="Reload Configuration")
async def reload_configuration():
    """Reload configuration from file."""
    try:
        config_manager = get_config_manager()
        config_manager.reload_config()
        return {"success": True, "message": "Configuration reloaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload configuration: {e}")


@router.post("/models/discover", summary="Refresh Model Discovery")
async def refresh_model_discovery():
    """Refresh the discovery of models from filesystem."""
    try:
        config_manager = get_config_manager()
        result = config_manager.refresh_discovered_models()
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh model discovery: {e}")


# MIDI file download endpoint
@router.get("/download/midi/{filename}", summary="Download Generated MIDI File")
async def download_midi_file(filename: str):
    """Download a generated MIDI file."""
    # Validate filename
    if not filename.endswith('.mid'):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    # Security: only allow alphanumeric, hyphens, underscores, and dots
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+\.mid$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Check if file exists
    temp_dir = get_temp_dir()
    file_path = temp_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="MIDI file not found")
    
    # Return file
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="audio/midi",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# Bulk MIDI download endpoint
@router.get("/download/midi-zip/{request_id}", summary="Download All MIDI Files as ZIP")
async def download_midi_zip(request_id: str):
    """Download all MIDI files from a generation request as a ZIP file."""
    import zipfile
    import io
    
    # Validate request_id
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', request_id):
        raise HTTPException(status_code=400, detail="Invalid request ID")
    
    temp_dir = get_temp_dir()
    midi_files = list(temp_dir.glob(f"{request_id}_melody_*.mid"))
    
    if not midi_files:
        raise HTTPException(status_code=404, detail="No MIDI files found for this request")
    
    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for midi_file in midi_files:
            zip_file.write(midi_file, midi_file.name)
    
    zip_buffer.seek(0)
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={request_id}_melodies.zip"}
    )

# Background task for cleanup
@router.post("/maintenance/cleanup", summary="Cleanup Expired Models")
async def cleanup_models(background_tasks: BackgroundTasks):
    """Clean up expired models (background task)."""
    def cleanup():
        registry = get_model_registry()
        registry.cleanup_expired_models()

    background_tasks.add_task(cleanup)
    return {"message": "Cleanup task scheduled"}

# Cleanup old MIDI files
@router.post("/maintenance/cleanup-files", summary="Cleanup Old MIDI Files")
async def cleanup_midi_files(max_age_hours: int = Query(24, description="Max age in hours")):
    """Clean up old generated MIDI files."""
    import time
    
    temp_dir = get_temp_dir()
    if not temp_dir.exists():
        return {"message": "No temp directory found", "deleted_files": 0}
    
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    deleted_count = 0
    
    for file_path in temp_dir.glob("*.mid"):
        file_age = current_time - file_path.stat().st_mtime
        if file_age > max_age_seconds:
            file_path.unlink()
            deleted_count += 1
    
    return {"message": f"Cleaned up {deleted_count} old MIDI files", "deleted_files": deleted_count}


# Error handlers would be added at the app level
def create_error_response(error: str, detail: str = None, status_code: int = 500) -> ErrorResponse:
    """Create standardized error response."""
    return ErrorResponse(
        error=error,
        error_code=f"HTTP_{status_code}",
        detail=detail,
        timestamp=datetime.now().isoformat(),
        request_id=str(uuid.uuid4()),
        suggestions=["Check the API documentation at /docs"]
    )
