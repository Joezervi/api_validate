from app.parsers.zrevi_parse import ZerviParser
from app.parsers.toyota_parser import ToyotaParser


def get_parser(customer_name):
    parsers = {
        "zervi": ZerviParser(),
        "toyota": ToyotaParser(),
    }

    parser = parsers.get(customer_name.lower())
    if parser is None:
        raise ValueError(
            f"No parser found for customer: '{customer_name}'. "
            f"Available: {', '.join(parsers.keys())}"
        )
    return parser
