"""
Model registry and management service.
Handles dynamic loading, caching, and lifecycle management of AI models.
"""

import time
import logging
from typing import Dict, List, Optional, Any, Type
from pathlib import Path
from threading import RLock
from dataclasses import dataclass
from datetime import datetime

import torch

from ..core.config import get_config_manager, ModelConfig
from ..models.base import BaseModel, ModelFactory, BaseTokenizer
from ..models.melody import MelodyModelFactory

logger = logging.getLogger(__name__)


@dataclass
class LoadedModel:
    """Container for a loaded model with metadata."""
    model: BaseModel
    tokenizer: BaseTokenizer
    config: ModelConfig
    load_time: datetime
    last_accessed: datetime
    access_count: int = 0

    def update_access(self):
        """Update access tracking."""
        self.last_accessed = datetime.now()
        self.access_count += 1


class ModelRegistry:
    """Registry for managing multiple AI models."""

    # Registry of model factories by type
    _model_factories: Dict[str, Type[ModelFactory]] = {
        'MelodyTransformer': MelodyModelFactory,
        # Future model types will be registered here
        # 'HarmonyTransformer': HarmonyModelFactory,
        # 'DrumTransformer': DrumModelFactory,
    }

    def __init__(self):
        self._loaded_models: Dict[str, LoadedModel] = {}
        self._lock = RLock()
        self.config_manager = get_config_manager()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    @classmethod
    def register_factory(cls, model_type: str, factory: Type[ModelFactory]):
        """Register a new model factory."""
        cls._model_factories[model_type] = factory
        logger.info(f"Registered model factory for type: {model_type}")

    def get_available_models(self) -> Dict[str, Dict[str, Any]]:
        """Get list of all available models from configuration."""
        available_models = {}

        for model_name, model_config in self.config_manager.get_available_models().items():
            # Check if model files exist
            models_root = Path(self.config_manager.config.storage.models_root)
            model_file = models_root / model_config.model_file
            config_file = models_root / model_config.config_file

            file_exists = model_file.exists() and config_file.exists()
            is_loaded = model_name in self._loaded_models

            available_models[model_name] = {
                'type': model_config.type,
                'description': model_config.description,
                'tags': model_config.tags,
                'architecture': model_config.architecture.dict(),
                'file_exists': file_exists,
                'is_loaded': is_loaded,
                'model_file': str(model_file),
                'config_file': str(config_file),
                'supported': model_config.type in self._model_factories
            }

            if is_loaded:
                loaded_model = self._loaded_models[model_name]
                available_models[model_name].update({
                    'load_time': loaded_model.load_time.isoformat(),
                    'last_accessed': loaded_model.last_accessed.isoformat(),
                    'access_count': loaded_model.access_count,
                    'parameter_count': loaded_model.model.parameter_count
                })

        return available_models

    def get_loaded_models(self) -> List[str]:
        """Get list of currently loaded model names."""
        with self._lock:
            return list(self._loaded_models.keys())

    def is_model_loaded(self, model_name: str) -> bool:
        """Check if a model is currently loaded."""
        with self._lock:
            return model_name in self._loaded_models

    def load_model(self, model_name: str) -> Dict[str, Any]:
        """Load a model into memory."""
        with self._lock:
            # Check if already loaded
            if model_name in self._loaded_models:
                self._loaded_models[model_name].update_access()
                return {
                    'success': True,
                    'message': f'Model {model_name} already loaded',
                    'already_loaded': True
                }

            # Get model configuration
            model_config = self.config_manager.get_model_config(model_name)
            if not model_config:
                return {
                    'success': False,
                    'error': f'Model {model_name} not found in configuration'
                }

            # Check if model type is supported
            if model_config.type not in self._model_factories:
                return {
                    'success': False,
                    'error': f'Model type {model_config.type} not supported'
                }

            # Validate file paths
            models_root = Path(self.config_manager.config.storage.models_root)
            model_file = models_root / model_config.model_file
            config_file = models_root / model_config.config_file

            if not model_file.exists():
                return {
                    'success': False,
                    'error': f'Model file not found: {model_file}'
                }

            if not config_file.exists():
                return {
                    'success': False,
                    'error': f'Config file not found: {config_file}'
                }

            # Check memory limits
            max_loaded = self.config_manager.config.storage.max_loaded_models
            if len(self._loaded_models) >= max_loaded:
                self._unload_least_used_model()

            try:
                # Load the model
                start_time = time.time()
                factory = self._model_factories[model_config.type]
                
                logger.info(f"Loading model {model_name} using factory {factory.__name__}")
                logger.info(f"Model file: {model_file}")
                logger.info(f"Config file: {config_file}")
                logger.info(f"Device: {self.device}")

                # Load model using factory
                if hasattr(factory, 'load_model_from_files'):
                    logger.info("Using load_model_from_files method")
                    model = factory.load_model_from_files(
                        str(model_file),
                        str(config_file),
                        str(self.device)
                    )
                else:
                    # Fallback method
                    with open(config_file, 'r') as f:
                        import json
                        config_data = json.load(f)

                    model_arch_config = factory.create_config(config_data)
                    model = factory.create_model(model_arch_config)

                    from safetensors.torch import load_file
                    state_dict = load_file(str(model_file))
                    model.load_state_dict(state_dict)
                    model = model.to(self.device)
                    model.eval()

                # Create tokenizer
                tokenizer_name = model_config.tokenizer
                tokenizer_config = self.config_manager.get_tokenizer_config(tokenizer_name)
                if not tokenizer_config:
                    return {
                        'success': False,
                        'error': f'Tokenizer {tokenizer_name} not found in configuration'
                    }

                tokenizer = factory.create_tokenizer(tokenizer_config.dict())

                load_time = time.time() - start_time

                # Store loaded model
                loaded_model = LoadedModel(
                    model=model,
                    tokenizer=tokenizer,
                    config=model_config,
                    load_time=datetime.now(),
                    last_accessed=datetime.now()
                )

                self._loaded_models[model_name] = loaded_model

                logger.info(f"Successfully loaded model {model_name} in {load_time:.2f}s")

                return {
                    'success': True,
                    'message': f'Model {model_name} loaded successfully',
                    'load_time': load_time,
                    'model_type': model_config.type,
                    'parameter_count': model.parameter_count,
                    'device': str(self.device),
                    'vocab_size': model.config.vocab_size if hasattr(model.config, 'vocab_size') else None
                }

            except Exception as e:
                logger.error(f"Failed to load model {model_name}: {e}")
                message = str(e)
                if isinstance(e, ImportError) and "alv_tokenizer" in message:
                    message = "Tokenizer unavailable: install the downloaded alv_tokenizer wheel"
                elif isinstance(e, (RuntimeError, ValueError)):
                    message = f"Incompatible checkpoint or insufficient device memory: {message}"
                return {
                    'success': False,
                    'error': f'Failed to load model: {message}'
                }

    def unload_model(self, model_name: str) -> Dict[str, Any]:
        """Unload a model from memory."""
        with self._lock:
            if model_name not in self._loaded_models:
                return {
                    'success': False,
                    'error': f'Model {model_name} is not loaded'
                }

            # Remove from memory
            del self._loaded_models[model_name]

            # Force garbage collection
            import gc
            gc.collect()

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info(f"Unloaded model {model_name}")

            return {
                'success': True,
                'message': f'Model {model_name} unloaded successfully'
            }

    def get_model(self, model_name: str) -> Optional[LoadedModel]:
        """Get a loaded model instance."""
        with self._lock:
            if model_name in self._loaded_models:
                loaded_model = self._loaded_models[model_name]
                loaded_model.update_access()
                return loaded_model
            return None

    def _unload_least_used_model(self):
        """Unload the least recently used model."""
        if not self._loaded_models:
            return

        # Find least recently used model
        lru_model_name = min(
            self._loaded_models.keys(),
            key=lambda name: self._loaded_models[name].last_accessed
        )

        logger.info(f"Auto-unloading least used model: {lru_model_name}")
        self.unload_model(lru_model_name)

    def cleanup_expired_models(self):
        """Clean up models that haven't been accessed recently."""
        config = self.config_manager.config.storage
        if not config.auto_unload_after:
            return

        current_time = datetime.now()
        expired_models = []

        with self._lock:
            for model_name, loaded_model in self._loaded_models.items():
                time_since_access = (current_time - loaded_model.last_accessed).total_seconds()
                if time_since_access > config.auto_unload_after:
                    expired_models.append(model_name)

        for model_name in expired_models:
            logger.info(f"Auto-unloading expired model: {model_name}")
            self.unload_model(model_name)

    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory usage information."""
        info = {
            'loaded_models_count': len(self._loaded_models),
            'max_loaded_models': self.config_manager.config.storage.max_loaded_models,
            'device': str(self.device)
        }

        if torch.cuda.is_available():
            info.update({
                'gpu_memory_allocated': torch.cuda.memory_allocated(),
                'gpu_memory_reserved': torch.cuda.memory_reserved(),
                'gpu_memory_total': torch.cuda.get_device_properties(0).total_memory
            })

        return info


# Global model registry instance
_model_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """Get the global model registry instance."""
    global _model_registry
    if _model_registry is None:
        _model_registry = ModelRegistry()
    return _model_registry
