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
    except configparser.MissingSectionHeaderError:
        raise exceptions.InvalidConfiguration(
            f"Invalid config file {config_file}. "
            f"File contains no section headers."
        )
    except configparser.ParsingError:
        raise exceptions.InvalidConfiguration(
            f"Invalid config file {config_file}. "
            f"Source contains parsing errors."
        )

    config["repository"] = normalize_repository_url(cast(str, config["repository"]))
    return config