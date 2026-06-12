"""Source indexers. Each module exposes:
    - iter_items(since_ts: float) -> Iterable[item dict]
    - poll_once() -> Iterable[item dict]   # for cheap live polling (clipboard)

An item dict is:
    {
        "id":      "<source>:<stable-hash>",   # PRIMARY KEY
        "source":  "<source-name>",
        "title":   str|None,
        "snippet": str|None,                    # main text, full-text indexed
        "url":     str|None,
        "app":     str|None,                    # source app name (clipboard)
        "ts":      float,                       # unix epoch seconds
        "extra":   dict|None,                   # source-specific metadata
    }
"""

# this package init just marks `sources` as a package.
