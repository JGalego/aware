import re

# name -> (regex for the URL segment, function turning the matched text into the handler argument)
CONVERTERS = {
    "str": (r"[^/]+", str),
    "int": (r"\d+", int),
    "path": (r".+", str),
}

PARAM = re.compile(r"<(?:(\w+):)?(\w+)>")
