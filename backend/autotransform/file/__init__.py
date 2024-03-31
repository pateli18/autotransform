from autotransform.utils import FileProviderType, settings

if settings.file_provider == FileProviderType.local:
    from .local import LocalFileClient

    file_client = LocalFileClient(settings.file_provider_config)
else:
    raise ValueError(f"Invalid file provider: {settings.file_provider}")
