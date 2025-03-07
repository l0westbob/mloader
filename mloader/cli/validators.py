import re
import click

def validate_urls(ctx: click.Context, param, value):
    """
    Validate URL arguments and extract title and viewer IDs.

    Each URL is expected to match the pattern <key>/<id> (for example, "viewer/123" or "titles/456").
    Extracted IDs are added to the context parameters 'titles' and 'chapters'.

    Parameters:
        ctx (click.Context): The Click context.
        param: The parameter definition.
        value: The list of URL strings provided.

    Returns:
        The original value if valid; otherwise, raises a click.BadParameter exception.
    """
    if not value:
        return value

    # Initialize result sets for viewer and title IDs.
    results = {"viewer": set(), "titles": set()}
    for url in value:
        match = re.search(r"(\w+)/(\d+)", url)
        if not match:
            raise click.BadParameter(f"Invalid url: {url}")
        try:
            key = match.group(1)
            id_value = int(match.group(2))
            results[key].add(id_value)
        except (ValueError, KeyError):
            raise click.BadParameter(f"Invalid url: {url}")

    ctx.params.setdefault("titles", set()).update(results["titles"])
    ctx.params.setdefault("chapters", set()).update(results["viewer"])
    return value


def validate_ids(ctx: click.Context, param, value):
    """
    Validate chapter or title IDs and update context parameters.

    Ensures that IDs provided for 'chapter' or 'title' are valid integers and updates the
    corresponding set in the context.

    Parameters:
        ctx (click.Context): The Click context.
        param: The parameter definition.
        value: The list of IDs provided.

    Returns:
        The original value if valid.
    """
    if not value:
        return value

    # Parameter name must be either 'chapter' or 'title'.
    assert param.name in ("chapter", "title"), f"Unexpected parameter: {param.name}"
    ctx.params.setdefault(f"{param.name}s", set()).update(value)
    return value