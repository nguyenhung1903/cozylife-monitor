from types import SimpleNamespace

def dict_to_namespace(data):
    if isinstance(data, dict):
        return SimpleNamespace(**{
            key: dict_to_namespace(value)
            for key, value in data.items()
        })
    return data