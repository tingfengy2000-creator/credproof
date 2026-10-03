def get_repository_from_config(
    config_file: str,
    repository: str,
    repository_url: Optional[str] = None,
) -> RepositoryConfig:
    """Get repository config command-line values or the .pypirc file."""
    # Prefer CLI `repository_url` over `repository` or .pypirc
    if repository_url:
        _validate_repository_url(repository_url)
        return _config_from_repository_url(repository_url)

    try:
        config = get_config(config_file)[repository]
    except OSError as exc:
        raise exceptions.InvalidConfiguration(str(exc))
    except KeyError:
        raise exceptions.InvalidConfiguration(
            f"Missing '{repository}' section from {config_file}.\n"
            f"More info: https://packaging.python.org/specifications/pypirc/ "
        )

    config["repository"] = normalize_repository_url(cast(str, config["repository"]))
    return config
