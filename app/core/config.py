"""
Core configuration management for the AI Music API.
Handles YAML configuration loading and validation.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field, field_validator
import logging

logger = logging.getLogger(__name__)
APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = APP_ROOT / "config" / "models.yaml"


class APIConfig(BaseModel):
    """API server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    title: str = "AI Music Generation API"
    version: str = "2.0.0"
    description: str = "Professional API for AI-powered music generation"


class StorageConfig(BaseModel):
    """Model storage configuration."""
    models_root: str = "./models"
    cache_enabled: bool = True
    max_loaded_models: int = 3
    auto_unload_after: int = 3600


class TokenizerConfig(BaseModel):
    """Tokenizer configuration."""
    type: str
    min_pitch: Optional[int] = None
    max_pitch: Optional[int] = None
    time_resolution: Optional[int] = None
    chord_types: Optional[List[str]] = None
    drum_kit: Optional[str] = None
    velocity_levels: Optional[int] = None


class ModelArchitecture(BaseModel):
    """Model architecture configuration."""
    vocab_size: int
    d_model: int
    n_heads: int
    n_layers: int
    d_ff: int
    max_seq_len: int
    dropout: float = 0.1
    bos_token: Optional[int] = None
    eos_token: Optional[int] = None
    pad_token: Optional[int] = None


class GenerationDefaults(BaseModel):
    """Default generation parameters."""
    temperature: float = 1.0
    top_k: int = 50
    top_p: float = 0.9
    repetition_penalty: float = 1.1
    max_length: int = 120


class ModelConfig(BaseModel):
    """Individual model configuration."""
    type: str
    tokenizer: str
    model_file: str
    config_file: str
    architecture: ModelArchitecture
    generation_defaults: GenerationDefaults
    tags: List[str] = []
    description: str = ""

    @field_validator('type')
    @classmethod
    def validate_model_type(cls, v):
        allowed_types = [
            'MelodyTransformer',
            'HarmonyTransformer',
            'DrumTransformer',
            'FullMusicTransformer'
        ]
        if v not in allowed_types:
            raise ValueError(f"Model type must be one of {allowed_types}")
        return v


class GenerationProfile(BaseModel):
    """Generation profile configuration."""
    temperature: float
    top_k: int
    top_p: float
    repetition_penalty: float
    description: str


class OutputFormat(BaseModel):
    """Output format configuration."""
    include_notes: bool = True
    include_midi: bool = True
    include_tokens: bool = False
    note_format: str = "beats"  # beats, seconds, ticks
    include_metadata: bool = False
    include_attention_weights: bool = False
    include_probabilities: bool = False


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    file: str = "logs/api.log"
    max_size: str = "100MB"
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class PerformanceConfig(BaseModel):
    """Performance configuration."""
    batch_size_limit: int = 10
    sequence_length_limit: int = 1000
    generation_timeout: int = 60
    memory_threshold: float = 0.9


class SecurityConfig(BaseModel):
    """Security configuration."""
    rate_limit: str = "100/minute"
    max_file_size: str = "10MB"
    allowed_file_types: List[str] = [".mid", ".midi"]
    cors_origins: List[str] = ["*"]


class AppConfig(BaseModel):
    """Complete application configuration."""
    api: APIConfig
    storage: StorageConfig
    tokenizers: Dict[str, TokenizerConfig]
    models: Dict[str, ModelConfig]
    generation_profiles: Dict[str, GenerationProfile]
    output_formats: Dict[str, OutputFormat]
    logging: LoggingConfig
    performance: PerformanceConfig
    security: SecurityConfig


class ConfigManager:
    """Manages application configuration from YAML files."""

    def __init__(self, config_path: Optional[str] = None):
        configured_path = config_path or os.environ.get("AURORA_CONFIG") or DEFAULT_CONFIG_PATH
        self.config_path = Path(configured_path).expanduser().resolve()
        self._config: Optional[AppConfig] = None
        self._discovered_models: Dict[str, ModelConfig] = {}
        self.load_config()

    def load_config(self) -> AppConfig:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)

            self._config = AppConfig(**yaml_data)
            models_override = os.environ.get("AURORA_MODELS_DIR")
            models_root = Path(models_override or self._config.storage.models_root).expanduser()
            if not models_root.is_absolute():
                models_root = APP_ROOT / models_root
            self._config.storage.models_root = str(models_root.resolve())
            
            # Discover actual models from filesystem
            self._discover_models_from_filesystem()
            
            logger.info(f"Configuration loaded from {self.config_path}")
            return self._config

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML configuration: {e}")
        except Exception as e:
            raise ValueError(f"Configuration validation failed: {e}")

    def reload_config(self) -> AppConfig:
        """Reload configuration from file."""
        return self.load_config()
    
    def refresh_discovered_models(self) -> Dict[str, str]:
        """Refresh the discovered models from filesystem."""
        old_count = len(self._discovered_models)
        self._discovered_models.clear()
        self._discover_models_from_filesystem()
        new_count = len(self._discovered_models)
        
        return {
            "message": f"Model discovery refreshed. Found {new_count} models (was {old_count})",
            "discovered_models": list(self._discovered_models.keys()),
            "models_root": str(self._config.storage.models_root) if self._config else "Not configured"
        }

    @property
    def config(self) -> AppConfig:
        """Get current configuration."""
        if self._config is None:
            raise RuntimeError("Configuration not loaded")
        return self._config

    def get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        """Get configuration for a specific model (YAML + discovered)."""
        # First check YAML config
        config = self.config.models.get(model_name)
        if config:
            return config
        # Then check discovered models
        return self._discovered_models.get(model_name)

    def _discover_models_from_filesystem(self):
        """Discover models from the filesystem and create configurations."""
        if not self._config:
            return
            
        models_root = Path(self._config.storage.models_root)
        logger.info("Resolved model directory: %s", models_root)
        if not models_root.exists():
            logger.warning(f"Models root directory not found: {models_root}")
            logger.info("Discovered safetensors files: []")
            logger.info("Discovered model config files: []")
            logger.info("Final API model names: %s", sorted(self.config.models))
            return
            
        # Find all .safetensors files
        safetensor_files = sorted(models_root.glob("*.safetensors"))
        
        # Find all .json config files
        json_files = sorted(models_root.glob("*.json"))

        logger.info("Discovered safetensors files: %s", [p.name for p in safetensor_files])
        logger.info("Discovered model config files: %s", [p.name for p in json_files])
        
        # Group models by their base name and find shared configs
        model_groups = self._group_models_by_base_name(safetensor_files, json_files)
        
        for group_name, group_info in model_groups.items():
            for model_file in group_info['models']:
                model_name = model_file.stem
                
                # Skip if already in YAML config
                if model_name in self._config.models:
                    continue
                
                config_file = group_info['config']
                if not config_file:
                    logger.warning(f"No config file found for model group: {group_name}")
                    continue
                
                try:
                    # Load model config to get architecture info
                    with open(config_file, 'r') as f:
                        import json
                        model_config_data = json.load(f)
                    
                    # Create model configuration
                    model_config = self._create_model_config_from_file(
                        model_name, 
                        model_file.name, 
                        config_file.name, 
                        model_config_data,
                        is_checkpoint=group_info['is_checkpoint_group']
                    )
                    
                    self._discovered_models[model_name] = model_config
                    logger.info(f"Discovered model: {model_name} (config: {config_file.name})")
                    
                except Exception as e:
                    logger.error(f"Failed to process model {model_name}: {e}")

        logger.info("Final API model names: %s", sorted(self.get_available_models()))
    
    def _group_models_by_base_name(self, safetensor_files: List[Path], json_files: List[Path]) -> Dict[str, Dict]:
        """Group model files by their base name and find corresponding config files."""
        groups = {}
        
        for model_file in safetensor_files:
            model_name = model_file.stem
            
            # Determine base name (remove epoch/step suffixes)
            base_name = self._extract_base_model_name(model_name)
            
            if base_name not in groups:
                groups[base_name] = {
                    'models': [],
                    'config': None,
                    'is_checkpoint_group': False
                }
            
            groups[base_name]['models'].append(model_file)
        
        # Find config files for each group
        for base_name, group_info in groups.items():
            config_file = self._find_config_for_group(base_name, group_info['models'], json_files)
            group_info['config'] = config_file
            
            # Mark as checkpoint group if multiple models share one config
            if len(group_info['models']) > 1 and config_file:
                group_info['is_checkpoint_group'] = True
        
        return groups
    
    def _extract_base_model_name(self, model_name: str) -> str:
        """Extract base model name by removing epoch/step suffixes."""
        # Common patterns for checkpoint naming
        patterns = [
            r'_epoch_\d+$',  # _epoch_17
            r'_step_\d+$',   # _step_1000
            r'_\d+$',        # _2 (for best_melody_model_2)
            r'_checkpoint_\d+$',  # _checkpoint_5
        ]
        
        base_name = model_name
        for pattern in patterns:
            import re
            base_name = re.sub(pattern, '', base_name)
        
        return base_name
    
    def _find_config_for_group(self, base_name: str, model_files: List[Path], json_files: List[Path]) -> Optional[Path]:
        """Find the best matching config file for a group of models."""
        # Try exact matches first
        for json_file in json_files:
            json_stem = json_file.stem
            
            # Direct match patterns
            if json_stem == f"{base_name}_config":
                return json_file
            if json_stem == f"{base_name}config":
                return json_file
            if json_stem == base_name:
                return json_file
        
        # Try partial matches for any model in the group
        for model_file in model_files:
            model_stem = model_file.stem
            for json_file in json_files:
                json_stem = json_file.stem
                
                # Check if config name contains model name or vice versa
                if model_stem in json_stem or json_stem in model_stem:
                    return json_file
        
        # If only one config file exists, use it (common case)
        if len(json_files) == 1:
            logger.info(f"Using single config file {json_files[0].name} for model group: {base_name}")
            return json_files[0]
        
        return None
    
    def _create_model_config_from_file(self, model_name: str, model_file: str, config_file: str, config_data: dict, is_checkpoint: bool = False) -> ModelConfig:
        """Create a ModelConfig from discovered files."""
        # Extract architecture info from config
        architecture = ModelArchitecture(
            vocab_size=config_data.get('vocab_size', 1000),
            d_model=config_data.get('d_model', 512),
            n_heads=config_data.get('n_heads', 8),
            n_layers=config_data.get('n_layers', 6),
            d_ff=config_data.get('d_ff', 2048),
            max_seq_len=config_data.get('max_seq_len', 512),
            dropout=config_data.get('dropout', 0.1)
        )
        
        # Add special tokens if present
        if 'bos_token' in config_data:
            architecture.bos_token = config_data['bos_token']
        if 'eos_token' in config_data:
            architecture.eos_token = config_data['eos_token']
        if 'pad_token' in config_data:
            architecture.pad_token = config_data['pad_token']
        
        # Create generation defaults
        generation_defaults = GenerationDefaults(
            temperature=1.0,
            top_k=50,
            top_p=0.9,
            repetition_penalty=1.1,
            max_length=120
        )
        
        # Determine model type based on name or config
        model_type = "MelodyTransformer"  # Default
        if "harmony" in model_name.lower():
            model_type = "HarmonyTransformer"
        elif "drum" in model_name.lower():
            model_type = "DrumTransformer"
        
        # Use default tokenizer based on type
        tokenizer = "melody_tokenizer"
        if model_type == "HarmonyTransformer":
            tokenizer = "harmony_tokenizer"
        elif model_type == "DrumTransformer":
            tokenizer = "drum_tokenizer"
        
        # Create appropriate tags and description
        tags = ["discovered", "auto-generated"]
        description = f"Auto-discovered {model_type} model: {model_name}"
        
        if is_checkpoint:
            tags.append("checkpoint")
            # Extract epoch/step info if available
            if "_epoch_" in model_name:
                epoch_num = model_name.split("_epoch_")[-1]
                tags.append(f"epoch-{epoch_num}")
                description += f" (training epoch {epoch_num})"
            elif model_name.endswith("_2"):
                tags.append("version-2")
                description += " (version 2)"
            elif "_step_" in model_name:
                step_num = model_name.split("_step_")[-1]
                tags.append(f"step-{step_num}")
                description += f" (training step {step_num})"
            else:
                description += " (training checkpoint)"
        
        # Add validation loss info if available
        if 'val_loss' in config_data:
            val_loss = config_data['val_loss']
            tags.append(f"val-loss-{val_loss:.3f}")
            description += f" [val_loss: {val_loss:.4f}]"
        
        return ModelConfig(
            type=model_type,
            tokenizer=tokenizer,
            model_file=model_file,
            config_file=config_file,
            architecture=architecture,
            generation_defaults=generation_defaults,
            tags=tags,
            description=description
        )

    def get_available_models(self) -> Dict[str, ModelConfig]:
        """Get all available model configurations (YAML + discovered)."""
        all_models = dict(self.config.models)
        all_models.update(self._discovered_models)
        return all_models

    def get_tokenizer_config(self, tokenizer_name: str) -> Optional[TokenizerConfig]:
        """Get configuration for a specific tokenizer."""
        return self.config.tokenizers.get(tokenizer_name)

    def get_generation_profile(self, profile_name: str) -> Optional[GenerationProfile]:
        """Get generation profile configuration."""
        return self.config.generation_profiles.get(profile_name)

    def get_output_format(self, format_name: str) -> Optional[OutputFormat]:
        """Get output format configuration."""
        return self.config.output_formats.get(format_name)

    def validate_model_files(self, model_name: str) -> bool:
        """Validate that model files exist."""
        model_config = self.get_model_config(model_name)
        if not model_config:
            return False

        models_root = Path(self.config.storage.models_root)
        model_file = models_root / model_config.model_file
        config_file = models_root / model_config.config_file

        return model_file.exists() and config_file.exists()


# Global configuration instance
config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    global config_manager
    if config_manager is None:
        config_manager = ConfigManager()
    return config_manager


def get_config() -> AppConfig:
    """Get the current application configuration."""
    return get_config_manager().config
